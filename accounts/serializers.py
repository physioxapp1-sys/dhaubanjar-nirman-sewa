from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from bookings.models import Booking

from .models import PasswordResetCode, Profile, normalise_phone

User = get_user_model()


def _validate_new_password(value, user=None):
    try:
        validate_password(value, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate_phone(self, value):
        digits = normalise_phone(value)
        if len(digits) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        if Profile.objects.filter(phone=digits).exists():
            raise serializers.ValidationError("An account with this number already exists.")
        return digits

    def validate_password(self, value):
        return _validate_new_password(value)

    @transaction.atomic
    def create(self, validated):
        phone = validated["phone"]
        user = User.objects.create_user(username=phone, password=validated["password"])
        Profile.objects.create(
            user=user, phone=phone, full_name=validated.get("full_name", "").strip()
        )

        # Bookings this person already made as a guest, on this number, become
        # theirs. Without this, signing up right after booking would show an
        # empty Bookings tab, which reads as "my booking was lost".
        Booking.objects.filter(user__isnull=True).filter(
            contact_phone__endswith=phone[-7:]
        ).update(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = normalise_phone(attrs["phone"])
        user = authenticate(username=phone, password=attrs["password"])
        if not user:
            # One message for both cases on purpose: saying which of the two
            # was wrong tells an attacker which numbers are registered.
            raise serializers.ValidationError("Phone number or password is incorrect.")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")
        attrs["user"] = user
        return attrs


class MeSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="profile.phone", read_only=True)
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    address = serializers.CharField(source="profile.address", read_only=True)

    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "address", "date_joined"]


class DeleteAccountSerializer(serializers.Serializer):
    """Deleting an account is irreversible, so it asks for the password
    again rather than trusting that holding a valid token is enough - a
    phone left unlocked on a table is a far more common way to lose an
    account than a stolen password."""

    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        return normalise_phone(value)

    def issue_code(self):
        """Returns the PasswordResetCode if the number is registered, or
        None - never raises for an unknown number. ForgotPasswordView
        always replies the same way either way, so the response can't be
        used to check which phone numbers have accounts."""
        phone = self.validated_data["phone"]
        profile = Profile.objects.filter(phone=phone).select_related("user").first()
        if not profile:
            return None
        return PasswordResetCode.issue(profile.user)


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=PasswordResetCode.CODE_LENGTH)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = normalise_phone(attrs["phone"])
        profile = Profile.objects.filter(phone=phone).select_related("user").first()
        # Same message whether the phone is unknown or the code is simply
        # wrong - matches LoginSerializer's reasoning for not telling an
        # attacker which half of their guess was the wrong one.
        generic_error = "That code is incorrect or has expired."

        reset = None
        if profile:
            reset = (
                PasswordResetCode.objects.filter(
                    user=profile.user, code=attrs["code"], consumed_at__isnull=True
                )
                .order_by("-created_at")
                .first()
            )
        if not reset or reset.is_expired:
            raise serializers.ValidationError({"code": generic_error})

        attrs["user"] = profile.user
        attrs["reset"] = reset
        attrs["new_password"] = _validate_new_password(attrs["new_password"], user=profile.user)
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        self.validated_data["reset"].consume()

        # A password reset should not leave old sessions valid - whoever
        # forgot the password is proving they're the owner right now, but a
        # token issued before the reset might be sitting on a device that
        # is no longer theirs to trust.
        from rest_framework.authtoken.models import Token

        Token.objects.filter(user=user).delete()
        return user
