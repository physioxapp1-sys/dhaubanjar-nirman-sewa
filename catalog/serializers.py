from rest_framework import serializers

from .models import Category, Subcategory


class SubcategorySerializer(serializers.ModelSerializer):
    rate_unit_display = serializers.CharField(source="get_rate_unit_display", read_only=True)
    display_rate = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Subcategory
        fields = [
            "id", "name", "slug", "description",
            "rate", "rate_unit", "rate_unit_display", "display_rate",
            "image", "sort_order", "is_popular",
        ]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class CategorySerializer(serializers.ModelSerializer):
    vertical_display = serializers.CharField(source="get_vertical_display", read_only=True)
    subcategory_count = serializers.IntegerField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "vertical", "vertical_display", "name", "slug", "description",
            "image", "image_key", "icon", "sort_order", "subcategory_count",
        ]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class CategoryDetailSerializer(CategorySerializer):
    """Category with its subcategories inlined - what a category screen needs
    in a single round trip."""

    subcategories = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ["subcategories"]

    def get_subcategories(self, obj):
        # Uses the prefetched, already-filtered queryset when present so this
        # does not fire a query per category in list views.
        qs = getattr(obj, "active_subcategories", None)
        if qs is None:
            qs = obj.subcategories.filter(is_active=True)
        return SubcategorySerializer(qs, many=True, context=self.context).data
