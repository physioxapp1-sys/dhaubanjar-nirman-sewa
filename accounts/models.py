"""
Customer accounts.

Django's User is kept rather than swapped for a custom model: the project
already has migrated tables, and AUTH_USER_MODEL cannot be changed after
that without a painful migration. What customers actually identify
themselves by here is a phone number, so that lives on a profile and is
copied into User.username to get uniqueness enforced by the database.
"""
from django.conf import settings
from django.db import models

from catalog.models import TimeStamped


def normalise_phone(value):
    """Reduce a phone number to digits, dropping Nepal's country code.

    977-9801234567, +9779801234567 and 9801234567 are one person, and they
    will each type it a different way on different days.
    """
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("977") and len(digits) > 10:
        digits = digits[3:]
    return digits


class Profile(TimeStamped):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=20, unique=True, db_index=True)
    full_name = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name or self.user.username} ({self.phone})"
