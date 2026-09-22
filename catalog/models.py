"""
Catalog for the Pakka Homes app.

The spreadsheet the app was built from has three sheets with an identical
shape - services, shop and rentals - each listing main categories with their
subcategories. Rather than three parallel model trees, one Category/Subcategory
pair is partitioned by `vertical`, so adding a fourth vertical later is a
choices entry rather than a migration of new tables.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class Vertical(models.TextChoices):
    SERVICE = "service", "Service"
    SHOP = "shop", "Shop"
    RENTAL = "rental", "Rental"


class RateUnit(models.TextChoices):
    """How a rate is quoted. Varies by vertical: services are usually per
    visit or per sq.ft., shop items per bag or per piece, rentals per day."""

    FIXED = "fixed", "Fixed price"
    HOUR = "hour", "Per hour"
    DAY = "day", "Per day"
    VISIT = "visit", "Per visit"
    SQFT = "sqft", "Per sq. ft."
    PIECE = "piece", "Per piece"
    BAG = "bag", "Per bag"
    KG = "kg", "Per kg"
    QUOTE = "quote", "On request"


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStamped):
    """A main category, e.g. Construction (service) or Cement (shop)."""

    vertical = models.CharField(max_length=16, choices=Vertical.choices, db_index=True)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    description = models.TextField(blank=True)

    # The Flutter app ships category artwork under assets/<vertical>/<slug>;
    # image_key keeps that link so the app can fall back to a bundled asset
    # when it is offline, while `image` is the server-hosted version.
    image_key = models.CharField(
        max_length=120,
        blank=True,
        help_text="Folder name of the bundled app asset, e.g. 'appliance-repair'.",
    )
    image = models.ImageField(upload_to="catalog/categories/", blank=True, null=True)
    icon = models.CharField(
        max_length=60, blank=True, help_text="Material icon name used by the app."
    )

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["vertical", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["vertical", "slug"], name="uniq_category_vertical_slug"
            ),
            models.UniqueConstraint(
                fields=["vertical", "name"], name="uniq_category_vertical_name"
            ),
        ]
        indexes = [models.Index(fields=["vertical", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.get_vertical_display()} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    # NOTE: no subcategory_count property here on purpose. Views annotate a
    # field of that name; a property would both shadow the annotation and
    # cost one query per row. See CategoryViewSet.get_queryset.


class Subcategory(TimeStamped):
    """A leaf entry, e.g. 'New House Construction' or 'OPC Cement'.

    The same name legitimately appears under different categories - 'Boundary
    Wall' is both Construction and Mason work, 'Water Heater / Geyser' is both
    Plumbing and Appliance Repair - so slugs are unique per category, never
    globally.
    """

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="subcategories"
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True)

    rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Leave empty when the price is quoted on request.",
    )
    rate_unit = models.CharField(
        max_length=12, choices=RateUnit.choices, default=RateUnit.QUOTE
    )
    image = models.ImageField(upload_to="catalog/subcategories/", blank=True, null=True)

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    is_popular = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Surfaces in the app's 'Popular services' row.",
    )

    class Meta:
        verbose_name_plural = "subcategories"
        ordering = ["category", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "slug"], name="uniq_subcategory_category_slug"
            )
        ]
        indexes = [models.Index(fields=["category", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.category.name} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:180]
        super().save(*args, **kwargs)

    @property
    def display_rate(self):
        if self.rate is None:
            return "On request"
        return f"NPR {self.rate:,.0f} {self.get_rate_unit_display().lower()}"
