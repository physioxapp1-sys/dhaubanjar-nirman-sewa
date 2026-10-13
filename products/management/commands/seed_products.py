"""
Sample grocery products, so the listing has something real to render.

Idempotent - matched on (subcategory, slug), so re-running updates rather
than duplicates. Prices edited in the admin are overwritten only with
--overwrite-prices, on the same reasoning as import_catalog.

    python manage.py seed_products
    python manage.py seed_products --clear
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Subcategory, Vertical
from products.models import Collection, Product

COLLECTIONS = ["Leafy Greens", "Seasonal", "Exotic"]

# subcategory name -> products
# (name, unit, price, mrp, rating, reviews, badge, origin, shelf life, collections)
CATALOG = {
    "Vegetables & Fruits": [
        ("Tomato", "1 kg", 60, 70, "4.5", 1200, "Fresh & Natural", "Nepal", "3-5 days", ["Seasonal"]),
        ("Potato", "1 kg", 40, None, "4.4", 980, "Fresh & Natural", "Nepal", "2-3 weeks", []),
        ("Onion", "1 kg", 45, 50, "4.3", 860, "Fresh & Natural", "Nepal", "2-3 weeks", []),
        ("Cauliflower", "1 pc", 70, None, "4.5", 720, "Fresh & Natural", "Nepal", "4-6 days", ["Seasonal"]),
        ("Carrot", "1 kg", 60, None, "4.4", 640, "Fresh & Natural", "Nepal", "1-2 weeks", []),
        ("Apple", "1 kg", 280, None, "4.6", 1100, "Fresh & Natural", "Imported", "1-2 weeks", ["Exotic"]),
        ("Spinach", "500 g", 35, None, "4.2", 410, "Fresh & Natural", "Nepal", "2-3 days", ["Leafy Greens"]),
    ],
    "Rice & Grains": [
        ("Basmati Rice", "5 kg", 720, 800, "4.6", 540, "Premium", "Nepal", "12 months", []),
        ("Jeera Masino Rice", "5 kg", 650, None, "4.4", 320, "Premium", "Nepal", "12 months", []),
        ("Lentils (Masoor)", "1 kg", 180, None, "4.3", 210, None, "Nepal", "9 months", []),
    ],
    "Dairy & Eggs": [
        ("Eggs", "1 dozen", 220, 240, "4.5", 760, "Farm Fresh", "Nepal", "2-3 weeks", []),
        ("Milk", "1 litre", 110, None, "4.4", 630, "Farm Fresh", "Nepal", "2-3 days", []),
    ],
    "Gas & Fuel": [
        ("Gas Cylinder", "14.2 kg", 1900, None, "4.7", 450, None, "Nepal", "Not applicable", []),
    ],
}


class Command(BaseCommand):
    help = "Create sample grocery products for the Pakka Homes app."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Delete the seeded products instead of creating them.")
        parser.add_argument("--overwrite-prices", action="store_true",
                            help="Reset prices edited in the admin back to the seed.")

    @transaction.atomic
    def handle(self, *args, **opts):
        grocery = Category.objects.filter(vertical=Vertical.SERVICE, slug="grocery").first()
        if not grocery:
            self.stdout.write(self.style.ERROR(
                "No Grocery category - run import_catalog first."))
            return

        if opts["clear"]:
            slugs = [slugify(p[0]) for items in CATALOG.values() for p in items]
            deleted, _ = Product.objects.filter(slug__in=slugs).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {deleted} seeded rows."))
            return

        collections = {}
        for name in COLLECTIONS:
            obj, _ = Collection.objects.get_or_create(
                slug=slugify(name), defaults={"name": name}
            )
            collections[name] = obj

        created = updated = 0
        for sub_name, items in CATALOG.items():
            subcategory = Subcategory.objects.filter(
                category=grocery, name=sub_name
            ).first()
            if not subcategory:
                self.stdout.write(self.style.WARNING(
                    f"  no '{sub_name}' subcategory under Grocery - skipped"))
                continue

            for order, (name, unit, price, mrp, rating, reviews,
                        badge, origin, shelf, tags) in enumerate(items):
                defaults = {
                    "name": name,
                    "unit": unit,
                    "rating": rating,
                    "review_count": reviews,
                    "badge": badge or "",   # CharField is blank, not null
                    "origin": origin,
                    "shelf_life": shelf,
                    "return_policy": "Not applicable",
                    "description": f"Fresh, local {name.lower()}, rich in vitamins and "
                                   f"perfect for your daily cooking needs.",
                    "sort_order": order,
                    "in_stock": True,
                    "is_active": True,
                }
                existing = Product.objects.filter(
                    subcategory=subcategory, slug=slugify(name)
                ).first()
                if existing is None or opts["overwrite_prices"]:
                    defaults["price"] = price
                    defaults["mrp"] = mrp

                product, was_created = Product.objects.update_or_create(
                    subcategory=subcategory, slug=slugify(name), defaults=defaults
                )
                created += was_created
                updated += not was_created
                product.collections.set([collections[t] for t in tags])

        self.stdout.write(self.style.SUCCESS(
            f"{created} created, {updated} updated, {len(collections)} collections."
        ))
