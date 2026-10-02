"""
The people who actually do the work: contractors, electricians, plumbers and
the rest.

A provider is listed against catalog categories rather than subcategories.
An electrician who does "New Wiring" does the other eleven electrical jobs
too, so linking eleven rows per person would be noise to maintain in the
admin for no gain in the app.

`rating`/`review_count` are a provider's self-reported standing (see the
comment on them below); jobs_completed/total_earned/subcategories_worked are
the other kind of profile entirely - not stored here at all, but computed
from their own completed Bookings, which is the only place "what did this
person actually do, and were they paid for it" is genuinely recorded. See
ProviderViewSet for the queryset annotations and the real filters/sorting
those enable.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from accounts.models import normalise_phone
from catalog.models import RateUnit, TimeStamped


class Engagement(models.TextChoices):
    """Whether we employ this person or subcontract to them.

    Internal only. The customer books Pakka Homes and Pakka Homes stands
    behind the work either way - exposing the split would turn one promise
    into two tiers, and the partner tier would read as "not guaranteed".
    """

    IN_HOUSE = "in_house", "Own crew"
    PARTNER = "partner", "Partner"


class Trade(models.TextChoices):
    CONTRACTOR = "contractor", "Contractor"
    ELECTRICIAN = "electrician", "Electrician"
    PLUMBER = "plumber", "Plumber"
    MASON = "mason", "Mason"
    CARPENTER = "carpenter", "Carpenter"
    PAINTER = "painter", "Painter"
    CLEANER = "cleaning", "Cleaning crew"
    TECHNICIAN = "technician", "Appliance technician"
    WATERPROOFER = "waterproofer", "Waterproofing specialist"
    DESIGNER = "designer", "Interior designer"


class Provider(TimeStamped):
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True)
    trade = models.CharField(max_length=20, choices=Trade.choices, db_index=True)
    engagement = models.CharField(
        max_length=12,
        choices=Engagement.choices,
        default=Engagement.PARTNER,
        db_index=True,
        help_text="Partner unless they are on our own crew. Never shown to customers.",
    )

    categories = models.ManyToManyField(
        "catalog.Category",
        related_name="providers",
        blank=True,
        help_text="Which catalog categories this provider is listed under.",
    )

    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to="providers/", blank=True, null=True)

    # Contact links, not login credentials - there is no Facebook Login
    # integration here (that needs a registered Facebook Developer App and
    # its own secret, which this project does not have), and WhatsApp has
    # no public "login with WhatsApp" API to integrate even in principle.
    # What both practically mean for a tradesperson is "another number/page
    # to reach them on", so that is what gets stored: a profile URL and a
    # WhatsApp-reachable number, kept by staff on the record they already
    # manage - not a portal the provider logs into themselves.
    facebook_url = models.URLField(blank=True, help_text="Link to their Facebook profile or page.")
    whatsapp_number = models.CharField(
        max_length=20, blank=True,
        help_text="If different from the phone number above.",
    )

    # Distance needs the customer's coordinates and theirs. Until the app asks
    # for location, a human-readable area is what the listing shows.
    service_area = models.CharField(
        max_length=120, blank=True, help_text="e.g. 'Baneshwor, Kathmandu'."
    )
    experience_years = models.PositiveSmallIntegerField(default=0)
    about = models.TextField(blank=True)

    # Denormalised until reviews are a real model - an average recomputed from
    # a Review table on every list request would cost more than it is worth now.
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    review_count = models.PositiveIntegerField(default=0)

    # The provider's own call-out charge, separate from the catalog rate for
    # the job itself. Empty means they quote after seeing the site.
    rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Leave empty when the provider quotes on request.",
    )
    rate_unit = models.CharField(
        max_length=12, choices=RateUnit.choices, default=RateUnit.QUOTE
    )

    is_available = models.BooleanField(
        default=True, db_index=True, help_text="Shows the 'Available today' badge."
    )
    is_verified = models.BooleanField(
        default=False, help_text="Documents and references checked."
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-rating", "name"]
        indexes = [models.Index(fields=["is_active", "trade", "sort_order"])]

    def __str__(self):
        return f"{self.name} ({self.get_trade_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:160]
        if self.whatsapp_number:
            # Same normalisation accounts already applies to phone numbers -
            # 977-9801234567, +9779801234567 and 9801234567 should all read
            # back the same way here too.
            self.whatsapp_number = normalise_phone(self.whatsapp_number)
        super().save(*args, **kwargs)

    @property
    def display_rate(self):
        if self.rate is None:
            return "On request"
        return f"NPR {self.rate:,.0f} {self.get_rate_unit_display().lower()}"
