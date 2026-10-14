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

    class Engagement(models.TextChoices):
        """How often someone is wanted, for the help you hire rather than the
        job you book. A plumber comes once; a maid comes every day or a few
        hours of it, and the difference changes the price and the person."""

        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        ONE_TIME = "one_time", "One time"

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
    # Maid work is hired as a bundle - cooking and dishwashing and the
    # laundry, one person, one visit - so a booking can name several. The
    # single `subcategory` above stays the headline one, which is what the
    # admin lists and what a one-service booking sets on its own.
    services = models.ManyToManyField(
        "catalog.Subcategory",
        blank=True,
        related_name="booking_selections",
        help_text="Every service asked for. Includes the one above.",
    )
    engagement = models.CharField(
        max_length=12, choices=Engagement.choices, blank=True,
        help_text="Full or part time, for maid work. Blank for one-off jobs.",
    )
    # Comma-separated Slot values. A household will often take morning or
    # evening and not mind which, and a single choice cannot say that. `slot`
    # above keeps the first of them so the existing filters still read.
    preferred_slots = models.CharField(
        max_length=64, blank=True,
        help_text="Times that suit, most-wanted first.",
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

    @property
    def preferred_slot_list(self):
        return [s for s in self.preferred_slots.split(",") if s]

    def preferred_slots_display(self):
        """The chosen times in words, for the admin and the confirmation mail."""
        labels = dict(self.Slot.choices)
        chosen = [labels.get(s, s) for s in self.preferred_slot_list]
        return ", ".join(chosen) or self.get_slot_display()

    def services_display(self):
        """Every service asked for, falling back to the headline one for the
        bookings made before a booking could hold more than one."""
        names = [s.name for s in self.services.all()]
        if not names and self.subcategory:
            names = [self.subcategory.name]
        return ", ".join(names)
