"""
A landlord's holdings: the house, its floors, the rooms on each.

The flat list of rooms this started as could not say which building a room was
in, so six rooms across two houses read as six unrelated things. A landlord
thinks in houses, and a house is floors, and a floor is rooms - so that is the
shape.

Land and the odd lock-up have no floors and no rooms. They are still let as
one thing, so creating one makes a single unit standing for the whole of it,
and a lease looks the same whatever it is over.
"""
from django.conf import settings
from django.db import models

from catalog.models import TimeStamped


class Building(TimeStamped):
    """One house, plot or other holding. Named by the landlord, renameable."""

    class Kind(models.TextChoices):
        HOUSE = "house", "House"
        LAND = "land", "Land"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buildings",
    )
    # "House 1" to begin with, renamed to "Dhapasi Ghar" when they get round
    # to it. Nothing keys off the name.
    name = models.CharField(max_length=140)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.HOUSE)

    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    landmark = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["owner", "is_active"])]

    def __str__(self):
        return self.name

    @property
    def has_rooms(self):
        """Land is let whole; a house is let room by room."""
        return self.kind == self.Kind.HOUSE

    def floor_numbers(self):
        return sorted(
            {f for f in self.rooms.filter(is_active=True)
             .values_list("floor", flat=True) if f is not None}
        )


def landlord_code(user):
    """A short code for a landlord, for the office to quote on the phone.

    Derived from the account rather than typed, so two landlords cannot pick
    the same one and nobody has to remember theirs to sign in.
    """
    if user is None or not getattr(user, "id", None):
        return ""
    return "LL-%04d" % user.id
