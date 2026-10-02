"""
Customer accounts.

Django's User is kept rather than swapped for a custom model: the project
already has migrated tables, and AUTH_USER_MODEL cannot be changed after
that without a painful migration. What customers actually identify
themselves by here is a phone number, so that lives on a profile and is
copied into User.username to get uniqueness enforced by the database.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

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


class PasswordResetCode(TimeStamped):
    """A one-time code for the phone-based forgot-password flow.

    There is no email on an account and no SMS gateway wired into this
    project yet, so a code cannot actually be delivered anywhere outside of
    Django's own log. `is_delivered` exists to make that honest rather than
    silently pretending an SMS went out: see ForgotPasswordView. Plugging in
    a real gateway (e.g. Sparrow SMS, common for Nepali numbers) is a matter
    of sending `code` through it instead of only logging it - everything
    else here already works end to end.
    """

    CODE_LENGTH = 6
    VALID_FOR = timedelta(minutes=15)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_codes"
    )
    code = models.CharField(max_length=CODE_LENGTH, db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "code"])]

    def __str__(self):
        return f"reset code for {self.user} ({'used' if self.consumed_at else 'active'})"

    @classmethod
    def issue(cls, user):
        # Numeric and zero-padded, not a secrets.token_hex - this gets read
        # off a phone screen and typed back in, so it needs to look like the
        # OTP codes people already know how to use.
        code = "".join(secrets.choice("0123456789") for _ in range(cls.CODE_LENGTH))
        return cls.objects.create(user=user, code=code)

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + self.VALID_FOR

    @property
    def is_used(self):
        return self.consumed_at is not None

    def consume(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])
