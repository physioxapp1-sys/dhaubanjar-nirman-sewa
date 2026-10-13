"""
Things sold by the piece, as opposed to work quoted by the job.

Subcategory already carries a `rate`, but it is service-shaped: usually
"on request", with no unit, no original price to strike through, no rating
and no stock. Grocery needs all of those, so products are their own model
hanging off a Subcategory - Grocery > Vegetables & Fruits > Tomato (1 kg).
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from catalog.models import TimeStamped


class Collection(TimeStamped):
    """A filter chip on the listing - Leafy Greens, Seasonal, Exotic.

    A product can sit in several, and a collection can span subcategories,
    so this is a tag rather than a second tier of category.
    """

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:70]
        super().save(*args, **kwargs)


class Product(TimeStamped):
    subcategory = models.ForeignKey(
        "catalog.Subcategory", on_delete=models.CASCADE, related_name="products"
    )
    collections = models.ManyToManyField(Collection, blank=True, related_name="products")

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160)

    # Sold as "Tomato (1 kg)" - the pack, not a unit of measure to compute with.
    unit = models.CharField(max_length=40, blank=True, help_text="e.g. '1 kg', '1 pc', '5 kg'.")

    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    # What it was, for the strike-through. Empty means no discount is shown;
    # the percentage is derived rather than stored so the two cannot disagree.
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Original price. Leave empty when the item is not discounted.",
    )

    image = models.ImageField(upload_to="products/", blank=True, null=True)
    description = models.TextField(blank=True)

    # The expandable rows on the detail screen.
    origin = models.CharField(max_length=80, blank=True)
    shelf_life = models.CharField(max_length=80, blank=True)
    return_policy = models.CharField(max_length=120, blank=True)
    badge = models.CharField(
        max_length=40, blank=True, help_text="Small tag by the rating, e.g. 'Fresh & Natural'."
    )

    # Denormalised like Provider.rating, for the same reason: there is no
    # review model yet, and averaging on every list request would cost more
    # than it is worth before there is anything to average.
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    review_count = models.PositiveIntegerField(default=0)

    in_stock = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["subcategory", "slug"], name="uniq_product_subcategory_slug"
            )
        ]
        indexes = [models.Index(fields=["subcategory", "is_active", "sort_order"])]

    def __str__(self):
        return f"{self.name} ({self.unit})" if self.unit else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:160]
        super().save(*args, **kwargs)

    @property
    def discount_percent(self):
        """Whole percent off, or None when there is nothing to show.

        Guards mrp <= price so a mistyped original price shows no badge
        rather than a negative or zero discount.
        """
        if not self.mrp or self.mrp <= self.price:
            return None
        return int(round((self.mrp - self.price) / self.mrp * 100))

    @property
    def display_name(self):
        return f"{self.name} ({self.unit})" if self.unit else self.name
