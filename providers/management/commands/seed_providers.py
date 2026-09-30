"""
Sample providers, so the app's provider list has something to show before
real ones are entered in the admin.

Idempotent - matched on slug, so re-running updates rather than duplicates.
Category links are only made for categories that exist, so this is safe to
run before `import_catalog`; re-run it afterwards to attach the links.

    python manage.py seed_providers
    python manage.py seed_providers --clear
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Vertical
from providers.models import Provider, Trade

# (name, trade, [category slugs], area, years, rating, reviews, rate, unit)
SEED = [
    ("Ramesh Construction", Trade.CONTRACTOR,
     ["construction", "mason", "waterproofing"],
     "Baneshwor, Kathmandu", 14, "4.8", 124, None, "quote"),
    ("Himalaya Builders", Trade.CONTRACTOR,
     ["construction", "interior", "mason"],
     "Lalitpur", 9, "4.6", 88, None, "quote"),
    ("Sagarmatha Nirman Sewa", Trade.CONTRACTOR,
     ["construction", "waterproofing"],
     "Bhaktapur", 21, "4.5", 61, None, "quote"),

    ("Krishna Electricals", Trade.ELECTRICIAN,
     ["electrical", "appliance-repair"],
     "Chabahil, Kathmandu", 11, "4.9", 143, "600", "visit"),
    ("Nabin Electric Service", Trade.ELECTRICIAN,
     ["electrical"],
     "Kalanki, Kathmandu", 6, "4.5", 74, "550", "visit"),

    ("Shiva Plumbers", Trade.PLUMBER,
     ["plumbing"],
     "Koteshwor, Kathmandu", 8, "4.7", 89, "700", "visit"),
    ("Bikash Plumbing Works", Trade.PLUMBER,
     ["plumbing"],
     "Patan, Lalitpur", 5, "4.4", 52, "650", "visit"),

    ("Deepak Appliance Care", Trade.TECHNICIAN,
     ["appliance-repair"],
     "New Baneshwor, Kathmandu", 7, "4.6", 96, "800", "visit"),

    ("Sunita Cleaning Services", Trade.CLEANER,
     ["cleaning"],
     "Maharajgunj, Kathmandu", 6, "4.8", 167, "1500", "fixed"),
    ("Everest Home Care", Trade.CLEANER,
     ["cleaning"],
     "Kirtipur", 3, "4.3", 45, "1200", "fixed"),

    ("Gopal Painters", Trade.PAINTER,
     ["painting"],
     "Thimi, Bhaktapur", 12, "4.7", 78, "25", "sqft"),
    ("Roshan Painting Service", Trade.PAINTER,
     ["painting"],
     "Balaju, Kathmandu", 4, "4.4", 39, "20", "sqft"),

    ("Ram Bahadur Carpentry", Trade.CARPENTER,
     ["carpenter", "interior"],
     "Gongabu, Kathmandu", 16, "4.5", 63, "900", "visit"),
    ("Maya Interiors", Trade.DESIGNER,
     ["interior", "carpenter"],
     "Jhamsikhel, Lalitpur", 10, "4.9", 52, None, "quote"),
]


class Command(BaseCommand):
    help = "Create sample providers for the Pakka Homes app."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete the seeded providers instead of creating them.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        slugs = [self._slug(row[0]) for row in SEED]

        if opts["clear"]:
            deleted, _ = Provider.objects.filter(slug__in=slugs).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {deleted} seeded rows."))
            return

        by_slug = {
            c.slug: c
            for c in Category.objects.filter(vertical=Vertical.SERVICE, is_active=True)
        }
        if not by_slug:
            self.stdout.write(self.style.WARNING(
                "No service categories found - run import_catalog first, then "
                "re-run this to attach category links."
            ))

        created = updated = links = 0
        unknown = set()

        for name, trade, cats, area, years, rating, reviews, rate, unit in SEED:
            provider, was_created = Provider.objects.update_or_create(
                slug=self._slug(name),
                defaults={
                    "name": name,
                    "trade": trade,
                    "service_area": area,
                    "experience_years": years,
                    "rating": rating,
                    "review_count": reviews,
                    "rate": rate,
                    "rate_unit": unit,
                    "is_available": True,
                    "is_verified": True,
                    "is_active": True,
                },
            )
            created += was_created
            updated += not was_created

            matched = [by_slug[s] for s in cats if s in by_slug]
            unknown |= {s for s in cats if s not in by_slug}
            if matched:
                provider.categories.set(matched)
                links += len(matched)

        self.stdout.write(self.style.SUCCESS(
            f"{created} created, {updated} updated, {links} category links."
        ))
        if unknown:
            self.stdout.write(self.style.WARNING(
                f"No such service category (skipped): {', '.join(sorted(unknown))}"
            ))

    @staticmethod
    def _slug(name):
        from django.utils.text import slugify
        return slugify(name)[:160]
