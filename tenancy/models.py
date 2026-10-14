"""
Renting a place to live: the property, who is in it, and whether this month's
rent has arrived.

Deliberately not the catalog's `rental` vertical, which is scaffolding and
concrete mixers hired by the day. This is a tenancy - one home, one household,
a lease and a monthly payment.

Nobody is flagged an owner or a tenant. You are an owner if a property is
yours and a tenant if a live lease names you, both are possible, and neither
can drift out of step with the facts the way a flag on an account would.
"""
from datetime import date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
# Tenancy has a field called `property`, which shadows the builtin decorator
# for the rest of that class body. cached_property is the Django-side way out
# and costs nothing: these are read once per request.
from django.utils.functional import cached_property

from catalog.models import TimeStamped

from .buildings import Building, landlord_code  # noqa: F401


class Property(TimeStamped):
    """One thing that can be let on its own - a room, a flat, a whole house.

    Name them however the building is actually divided. A family taking two
    rooms is one tenancy over both, not two tenancies.
    """

    class Kind(models.TextChoices):
        FLAT = "flat", "Flat / Apartment"
        HOUSE = "house", "House"
        ROOM = "room", "Room"
        SHOP = "shop", "Shop / Commercial"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    # Null only for the rooms added before buildings existed. Everything made
    # since belongs to one.
    building = models.ForeignKey(
        "tenancy.Building",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="rooms",
    )
    # Ground floor is 1, the way the landlord's own sheet counts them. Null on
    # land, and on anything let whole.
    floor = models.PositiveSmallIntegerField(null=True, blank=True)

    title = models.CharField(max_length=140, help_text="e.g. Room 2, or Dhapasi 2BHK")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.FLAT)

    address = models.TextField()
    city = models.CharField(max_length=80, blank=True)
    landmark = models.CharField(max_length=160, blank=True)

    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.PositiveSmallIntegerField(default=0)
    area_sqft = models.PositiveIntegerField(null=True, blank=True)

    # Zero until it is set. Rooms are made a floor at a time, and nobody wants
    # to type twenty-four rents before they have a tenant for any of them.
    monthly_rent = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    deposit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )

    # The asking rent and the rent someone is actually paying are different
    # numbers: a sitting tenant keeps the rent their lease was signed at.
    is_listed = models.BooleanField(
        default=False,
        help_text="Show this to people looking for somewhere to rent.",
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="tenancy/properties/", blank=True, null=True)

    class Meta:
        verbose_name_plural = "properties"
        # Floor then name, so a building reads the way it is walked.
        ordering = ["building__name", "floor", "title"]
        indexes = [
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["building", "floor"]),
        ]

    def __str__(self):
        return self.title

    @property
    def current_tenancy(self):
        """The live lease covering this room, if there is one.

        Read through the rooms link rather than the headline one, because a
        lease over rooms 1 and 2 makes both of them occupied and only one of
        them is its headline.
        """
        return self.leases.filter(status=Tenancy.Status.ACTIVE).first()

    @property
    def is_occupied(self):
        return self.current_tenancy is not None

    @property
    def state(self):
        """The word the landlord's own sheet uses."""
        return "Occupied" if self.is_occupied else "Vacant"


class Tenancy(TimeStamped):
    """The contract: this household, this property, these dates, this rent."""

    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    # The headline room, which is what a one-room lease has and what the admin
    # lists. Every room the lease covers - including this one - is in `rooms`.
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="tenancies"
    )
    rooms = models.ManyToManyField(
        Property,
        related_name="leases",
        help_text="Every room this lease covers, including the one above.",
    )
    # Null while the tenant has no account. The name and number are what the
    # owner actually has, and are copied rather than linked for the same
    # reason an order copies its address: the lease records what was agreed.
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenancies",
    )
    tenant_name = models.CharField(max_length=120)
    tenant_phone = models.CharField(max_length=32, db_index=True)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Blank for rolling.")

    monthly_rent = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    deposit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    # Rent is due on the same day every month, and which day is part of the
    # deal. A 31 falls back to the last day of a short month - see due_date().
    rent_due_day = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    document = models.FileField(
        upload_to="tenancy/contracts/", blank=True, null=True,
        help_text="The signed agreement, if there is a copy.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "tenancies"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["status", "-start_date"]),
            models.Index(fields=["tenant_phone"]),
        ]

    def __str__(self):
        return f"{self.tenant_name} at {self.rooms_display() or self.property.title}"

    def rooms_display(self):
        """Every room the lease covers, for the admin and the app."""
        names = [r.title for r in self.rooms.all()]
        if not names and self.property_id:
            names = [self.property.title]
        return ", ".join(names)

    def due_date(self, year, month):
        """When this month's rent is due. The 31st of a 30-day month is the
        30th, not an error."""
        import calendar

        day = min(self.rent_due_day or 1, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @cached_property
    def is_live(self):
        return self.status == self.Status.ACTIVE


class RentPayment(TimeStamped):
    """One month's rent: what is owed, and whether it arrived.

    A row exists as soon as the month is due, paid or not - an unpaid row is
    the whole point, because that is what "overdue" is made of.
    """

    tenancy = models.ForeignKey(
        Tenancy, on_delete=models.CASCADE, related_name="payments"
    )
    # The month this rent is for, stored as its first day. The month someone
    # paid in is a different thing and lives in paid_on.
    period = models.DateField(help_text="The month this covers, as its first day.")
    due_date = models.DateField()
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    paid_on = models.DateField(null=True, blank=True)
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    method = models.CharField(
        max_length=40, blank=True, help_text="Cash, bank, eSewa, Khalti..."
    )
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period"]
        # One row per month per tenancy, so raising the month's rent twice
        # cannot double-bill anyone.
        constraints = [
            models.UniqueConstraint(
                fields=["tenancy", "period"], name="one_rent_row_per_month"
            )
        ]
        indexes = [models.Index(fields=["due_date", "paid_on"])]

    def __str__(self):
        return f"{self.tenancy.tenant_name} {self.period:%b %Y}"

    @property
    def is_paid(self):
        return self.paid_on is not None

    @property
    def is_overdue(self):
        return not self.is_paid and self.due_date < date.today()

    @property
    def state(self):
        if self.is_paid:
            return "paid"
        return "overdue" if self.is_overdue else "due"
