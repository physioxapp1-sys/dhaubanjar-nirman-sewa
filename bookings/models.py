"""
What a customer actually asked for: this job, this provider, this day.

Distinct from an Enquiry, which is an open-ended "please get in touch".
A booking names a catalog item and carries an address and a date, so it
has a lifecycle to move through and a reference the customer can quote.
"""
import secrets
import string

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import TimeStamped

# No 0/O/1/I - these get read aloud over the phone.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def make_reference():
    return "PH-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


class Booking(TimeStamped):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Slot(models.TextChoices):
        MORNING = "morning", "Morning (8am - 12pm)"
        AFTERNOON = "afternoon", "Afternoon (12pm - 4pm)"
        EVENING = "evening", "Evening (4pm - 8pm)"
        ANYTIME = "anytime", "Anytime"

    class Source(models.TextChoices):
        APP = "app", "Pakka Homes app"
        WEBSITE = "website", "Website"
        PHONE = "phone", "Phone"

    reference = models.CharField(max_length=12, unique=True, default=make_reference, editable=False)

    # Null for a guest booking. The app lets people book before they have an
    # account and attaches one afterwards, so this cannot be required.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )

    subcategory = models.ForeignKey(
        "catalog.Subcategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    provider = models.ForeignKey(
        "providers.Provider",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Empty means the customer let us assign someone.",
    )

    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=32, db_index=True)
    address = models.TextField()
    landmark = models.CharField(max_length=160, blank=True)

    scheduled_date = models.DateField(null=True, blank=True)
    slot = models.CharField(max_length=12, choices=Slot.choices, default=Slot.ANYTIME)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    # Quoted first, settled after the work. Both empty while a provider is
    # still to visit and price the job.
    quoted_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    final_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )

    source = models.CharField(max_length=12, choices=Source.choices, default=Source.APP)
    staff_notes = models.TextField(blank=True, help_text="Internal only - not shown to the customer.")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["contact_phone", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.contact_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # default= covers the normal path; this is the retry for the rare clash.
        if not self.reference:
            self.reference = make_reference()
        for _ in range(5):
            if not Booking.objects.filter(reference=self.reference).exclude(pk=self.pk).exists():
                break
            self.reference = make_reference()
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in {self.Status.PENDING, self.Status.CONFIRMED, self.Status.IN_PROGRESS}
