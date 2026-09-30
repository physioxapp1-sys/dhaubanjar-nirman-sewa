from rest_framework import serializers

from catalog.models import Subcategory
from providers.models import Provider

from .models import Booking


class BookingCreateSerializer(serializers.ModelSerializer):
    """What the app posts. Catalog links come in as slugs - the app knows
    those from the screens it just showed, and never sees database ids."""

    subcategory_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    provider_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    category_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Booking
        fields = [
            "reference",
            "contact_name", "contact_phone", "address", "landmark",
            "scheduled_date", "slot", "notes",
            "subcategory_slug", "provider_slug", "category_slug",
        ]
        read_only_fields = ["reference"]

    def validate_contact_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value.strip()

    def validate_contact_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Enter your name.")
        return value

    def validate_address(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Enter enough address for someone to find you.")
        return value

    def create(self, validated):
        category_slug = validated.pop("category_slug", "")
        subcategory_slug = validated.pop("subcategory_slug", "")
        provider_slug = validated.pop("provider_slug", "")

        if subcategory_slug:
            qs = Subcategory.objects.filter(slug=subcategory_slug, is_active=True)
            # Slugs are unique per category, not globally, so the category
            # disambiguates 'water-heater-geyser' under Plumbing from the one
            # under Appliance Repair.
            if category_slug:
                qs = qs.filter(category__slug=category_slug)
            validated["subcategory"] = qs.first()

        if provider_slug:
            validated["provider"] = Provider.objects.filter(
                slug=provider_slug, is_active=True
            ).first()

        return super().create(validated)


class BookingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    slot_display = serializers.CharField(source="get_slot_display", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.name", default=None, read_only=True)
    provider_name = serializers.CharField(source="provider.name", default=None, read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "reference", "status", "status_display",
            "contact_name", "contact_phone", "address", "landmark",
            "scheduled_date", "slot", "slot_display", "notes",
            "subcategory_name", "provider_name",
            "quoted_amount", "final_amount", "created_at",
        ]
