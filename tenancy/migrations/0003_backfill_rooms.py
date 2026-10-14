"""Every lease that existed before `rooms` covered exactly its one property.

Without this they would all read as covering no rooms at all, which is how
`current_tenancy` now decides whether a room is occupied - so every let room
would show as vacant.
"""
from django.db import migrations


def fill(apps, schema_editor):
    Tenancy = apps.get_model("tenancy", "Tenancy")
    for tenancy in Tenancy.objects.exclude(property=None).prefetch_related("rooms"):
        if not tenancy.rooms.exists():
            tenancy.rooms.add(tenancy.property)


def unfill(apps, schema_editor):
    # Reversible, and lossless for anything this created: a one-room lease
    # still has its property, which is where the room came from.
    Tenancy = apps.get_model("tenancy", "Tenancy")
    for tenancy in Tenancy.objects.all():
        tenancy.rooms.clear()


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0002_tenancy_rooms")]
    operations = [migrations.RunPython(fill, unfill)]
