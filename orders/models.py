"""
Grocery orders: a basket of products delivered to an address.

Distinct from a Booking, which is a job someone comes and does. An order has
line items, a running total and a delivery window, and it has to stay a
faithful record of what was bought - so names and prices are copied onto the
lines rather than read back through the product, which may be repriced or
withdrawn tomorrow.
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from bookings.models import REFERENCE_ALPHABET
from catalog.models import TimeStamped


def make_order_reference():
    # PO, so an order reference is never mistaken for a booking's PH on the
    # phone. Same alphabet: no 0/O/1/I, because these get read aloud.
    return "PO-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


class DeliverySlot(models.TextChoices):
    S09_11 = "09-11", "9:00 AM - 11:00 AM"
    S11_13 = "11-13", "11:00 AM - 1:00 PM"
    S13_15 = "13-15", "1:00 PM - 3:00 PM"
    S15_17 = "15-17", "3:00 PM - 5:00 PM"
    S17_19 = "17-19", "5:00 PM - 7:00 PM"


class Address(TimeStamped):
    """A saved delivery address.

    Nepali addresses are landmark-led rather than street-numbered, which is
    why `landmark` is its own field and not an afterthought in the text.
    """

    class Label(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(max_length=10, choices=Label.choices, default=Label.HOME)
    recipient_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32)
    address = models.TextField()
    landmark = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=80, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.get_label_display()} - {self.address[:40]}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            # Exactly one default per person, enforced here rather than by a
            # constraint so that setting a new one silently demotes the old.
            Address.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)

    @property
    def one_line(self):
        parts = [self.address.replace("\n", ", ").strip()]
        if self.landmark:
            parts.append(f"near {self.landmark}")
        if self.city:
            parts.append(self.city)
        return ", ".join(p for p in parts if p)


class Order(TimeStamped):
    class Status(models.TextChoices):
        PLACED = "placed", "Order Placed"
        PREPARING = "preparing", "Preparing Your Order"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    # The order the tracking timeline walks through. Cancelled is deliberately
    # absent: it ends the order rather than being a step along it.
    TIMELINE = [Status.PLACED, Status.PREPARING, Status.OUT_FOR_DELIVERY, Status.DELIVERED]

    reference = models.CharField(
        max_length=12, unique=True, default=make_order_reference, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=32, db_index=True)

    # Copied, not linked. Editing a saved address later must not rewrite where
    # a past order actually went.
    delivery_address = models.TextField()
    landmark = models.CharField(max_length=160, blank=True)

    scheduled_date = models.DateField(null=True, blank=True)
    slot = models.CharField(max_length=8, choices=DeliverySlot.choices, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLACED, db_index=True
    )
    # Totals are stored, not recomputed on read, for the same reason the line
    # names are: this is what the customer agreed to pay.
    item_total = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     validators=[MinValueValidator(Decimal("0"))])
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       validators=[MinValueValidator(Decimal("0"))])
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                   validators=[MinValueValidator(Decimal("0"))])
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                validators=[MinValueValidator(Decimal("0"))])

    delivery_partner = models.ForeignKey(
        "providers.Provider",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
        help_text="Assigned when the order goes out.",
    )
    staff_notes = models.TextField(blank=True, help_text="Internal only.")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["contact_phone", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.contact_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = make_order_reference()
        for _ in range(5):
            if not Order.objects.filter(reference=self.reference).exclude(pk=self.pk).exists():
                break
            self.reference = make_order_reference()
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status not in {self.Status.DELIVERED, self.Status.CANCELLED}


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, null=True, blank=True
    )

    # Snapshots. A product renamed, repriced or withdrawn must not change what
    # this order says was bought and for how much.
    name = models.CharField(max_length=180)
    unit = models.CharField(max_length=40, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} x {self.name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
