"""The ten service categories whose tile pictures have the name printed in.

Read off the artwork itself, not guessed: every numbered tile in these folders
carries its label. Grocery and Maid do not - those are plain photographs, and
their tiles need the caption.
"""
from django.db import migrations

LABELLED = [
    "construction", "electrical", "cleaning", "mason", "appliance-repair",
    "plumbing", "painting", "carpenter", "waterproofing", "interior",
]


def mark(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Category.objects.filter(vertical="service", slug__in=LABELLED).update(
        artwork_has_label=True
    )


def unmark(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Category.objects.filter(slug__in=LABELLED).update(artwork_has_label=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_category_artwork_has_label")]
    operations = [migrations.RunPython(mark, unmark)]
