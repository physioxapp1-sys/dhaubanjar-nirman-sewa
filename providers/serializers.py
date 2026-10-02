from rest_framework import serializers

from .models import Provider


class ProviderSerializer(serializers.ModelSerializer):
    trade_display = serializers.CharField(source="get_trade_display", read_only=True)
    rate_unit_display = serializers.CharField(source="get_rate_unit_display", read_only=True)
    display_rate = serializers.CharField(read_only=True)
    photo = serializers.SerializerMethodField()
    category_slugs = serializers.SerializerMethodField()
    manager_slug = serializers.SlugRelatedField(
        source="manager", slug_field="slug", read_only=True
    )

    # Real history, not self-reported standing - see ProviderViewSet for
    # where these come from. jobs_completed/total_earned are annotations
    # (None/0 if the queryset did not add them, e.g. a plain .get() in the
    # admin); subcategories_worked reads the prefetched completed Bookings.
    jobs_completed = serializers.IntegerField(read_only=True, default=0)
    total_earned = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, default=0
    )
    subcategories_worked = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = [
            "id", "name", "slug", "trade", "trade_display",
            "phone", "facebook_url", "whatsapp_number",
            "photo", "service_area", "about", "experience_years",
            "rating", "review_count",
            "rate", "rate_unit", "rate_unit_display", "display_rate",
            "is_available", "is_verified", "category_slugs", "manager_slug",
            "jobs_completed", "total_earned", "subcategories_worked",
        ]

    def get_photo(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url

    def get_category_slugs(self, obj):
        # prefetched in the viewset, so this does not fire a query per row
        return [c.slug for c in obj.categories.all()]

    def get_subcategories_worked(self, obj):
        bookings = getattr(obj, "completed_bookings_cache", None)
        if bookings is None:
            return []
        seen, names = set(), []
        for b in bookings:
            if b.subcategory_id and b.subcategory_id not in seen:
                seen.add(b.subcategory_id)
                names.append(b.subcategory.name)
        return names
