from rest_framework import serializers

from .models import Provider


class ProviderSerializer(serializers.ModelSerializer):
    trade_display = serializers.CharField(source="get_trade_display", read_only=True)
    rate_unit_display = serializers.CharField(source="get_rate_unit_display", read_only=True)
    display_rate = serializers.CharField(read_only=True)
    photo = serializers.SerializerMethodField()
    category_slugs = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = [
            "id", "name", "slug", "trade", "trade_display",
            "phone", "photo", "service_area", "about", "experience_years",
            "rating", "review_count",
            "rate", "rate_unit", "rate_unit_display", "display_rate",
            "is_available", "is_verified", "category_slugs",
        ]

    def get_photo(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url

    def get_category_slugs(self, obj):
        # prefetched in the viewset, so this does not fire a query per row
        return [c.slug for c in obj.categories.all()]
