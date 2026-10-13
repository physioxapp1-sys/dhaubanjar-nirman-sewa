from rest_framework import serializers

from .models import Collection, Product


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ["id", "name", "slug"]


class ProductSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    image = serializers.SerializerMethodField()
    collection_slugs = serializers.SerializerMethodField()
    subcategory_slug = serializers.CharField(source="subcategory.slug", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "display_name", "unit",
            "price", "mrp", "discount_percent",
            "image", "description", "badge",
            "origin", "shelf_life", "return_policy",
            "rating", "review_count", "in_stock",
            "subcategory_slug", "collection_slugs",
        ]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def get_collection_slugs(self, obj):
        # prefetched in the viewset, so this does not fire a query per row
        return [c.slug for c in obj.collections.all()]
