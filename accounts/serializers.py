from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from bookings.models import Booking

from .models import Profile, normalise_phone

User = get_user_model()


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
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

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
