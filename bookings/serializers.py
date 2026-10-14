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

    # Maid work is hired as a bundle, so the app can send several. One service
    # still arrives as subcategory_slug, and both paths end up in `services`.
    subcategory_slugs = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    # Times that suit, most-wanted first. A household will take morning or
    # evening and not mind which, which a single choice cannot express.
    preferred_slots = serializers.ListField(
        child=serializers.ChoiceField(choices=Booking.Slot.choices),
        write_only=True, required=False,
    )

    class Meta:
        model = Booking
        fields = [
            "reference",
            "contact_name", "contact_phone", "address", "landmark",
            "scheduled_date", "slot", "notes", "engagement",
            "subcategory_slug", "subcategory_slugs", "preferred_slots",
            "provider_slug", "category_slug",
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
        subcategory_slugs = validated.pop("subcategory_slugs", [])
        provider_slug = validated.pop("provider_slug", "")
        preferred = validated.pop("preferred_slots", [])

        # One slug or many, the lookup is the same. Order is kept: the first
        # is what the customer picked first, and becomes the headline service.
        wanted = [s for s in ([subcategory_slug] + list(subcategory_slugs)) if s]
        seen, slugs = set(), []
        for slug in wanted:
            if slug not in seen:
                seen.add(slug)
                slugs.append(slug)

        services = []
        if slugs:
            qs = Subcategory.objects.filter(slug__in=slugs, is_active=True)
            # Slugs are unique per category, not globally, so the category
            # disambiguates 'water-heater-geyser' under Plumbing from the one
            # under Appliance Repair.
            if category_slug:
                qs = qs.filter(category__slug=category_slug)
            found = {s.slug: s for s in qs}
            services = [found[s] for s in slugs if s in found]
            if services:
                validated["subcategory"] = services[0]

        if preferred:
            validated["preferred_slots"] = ",".join(preferred)
            # Keep `slot` meaningful for everything that already reads it.
            validated["slot"] = preferred[0]

        if provider_slug:
            validated["provider"] = Provider.objects.filter(
                slug=provider_slug, is_active=True
            ).first()

        booking = super().create(validated)
        if services:
            booking.services.set(services)
        return booking


class BookingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    slot_display = serializers.CharField(source="get_slot_display", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.name", default=None, read_only=True)
    provider_name = serializers.CharField(source="provider.name", default=None, read_only=True)
    engagement_display = serializers.CharField(
        source="get_engagement_display", default="", read_only=True
    )
    service_names = serializers.SerializerMethodField()
    preferred_slots_display = serializers.CharField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "reference", "status", "status_display",
            "contact_name", "contact_phone", "address", "landmark",
            "scheduled_date", "slot", "slot_display", "notes",
            "subcategory_name", "service_names", "provider_name",
            "engagement", "engagement_display", "preferred_slots_display",
            "quoted_amount", "final_amount", "created_at",
        ]

    def get_service_names(self, obj):
        """Everything asked for. Falls back to the single service for the
        bookings taken before one could hold several."""
        names = [s.name for s in obj.services.all()]
        if not names and obj.subcategory:
            names = [obj.subcategory.name]
        return names
