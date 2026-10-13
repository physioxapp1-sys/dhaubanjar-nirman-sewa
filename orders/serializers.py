from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from products.models import Product

from .models import Address, DeliverySlot, Order, OrderItem

# Mirrors Cart in the app. Kept here too because the client is not trusted to
# do this arithmetic - see OrderCreateSerializer.create.
FREE_DELIVERY_ABOVE = Decimal("1000")
DELIVERY_FEE = Decimal("40")


class AddressSerializer(serializers.ModelSerializer):
    label_display = serializers.CharField(source="get_label_display", read_only=True)
    one_line = serializers.CharField(read_only=True)

    class Meta:
        model = Address
        fields = [
            "id", "label", "label_display", "recipient_name", "phone",
            "address", "landmark", "city", "is_default", "one_line",
        ]

    def validate_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value.strip()

    def validate_address(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError(
                "Enter enough address for someone to find you."
            )
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "name", "unit", "unit_price", "quantity", "line_total", "image"]

    def get_image(self, obj):
        if not obj.product or not obj.product.image:
            return None
        request = self.context.get("request")
        url = obj.product.image.url
        return request.build_absolute_uri(url) if request else url


class OrderSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    slot_display = serializers.CharField(source="get_slot_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    partner_name = serializers.CharField(source="delivery_partner.name", default=None,
                                         read_only=True)
    partner_phone = serializers.CharField(source="delivery_partner.phone", default=None,
                                          read_only=True)
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "reference", "status", "status_display",
            "contact_name", "contact_phone", "delivery_address", "landmark",
            "scheduled_date", "slot", "slot_display", "notes",
            "item_total", "delivery_fee", "discount", "total",
            "partner_name", "partner_phone", "items", "timeline", "created_at",
        ]

    def get_timeline(self, obj):
        """The tracking steps and which are done, so the app does not have to
        know the order of the statuses. Shared with the website's tracking
        page - see Order.timeline()."""
        return obj.timeline()


class OrderCreateSerializer(serializers.Serializer):
    """What the app posts at checkout.

    Items are slugs and quantities only. Prices are looked up here rather than
    accepted from the client - a posted price is a posted discount, and the
    total has to be something the shop stands behind.
    """

    contact_name = serializers.CharField(max_length=120)
    contact_phone = serializers.CharField(max_length=32)
    delivery_address = serializers.CharField()
    landmark = serializers.CharField(max_length=160, required=False, allow_blank=True)
    scheduled_date = serializers.DateField(required=False, allow_null=True)
    slot = serializers.ChoiceField(choices=DeliverySlot.choices, required=False,
                                   allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)

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

    def validate_delivery_address(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError(
                "Enter enough address for someone to find you."
            )
        return value

    def validate_items(self, value):
        cleaned = []
        for row in value:
            slug = str(row.get("slug", "")).strip()
            if not slug:
                raise serializers.ValidationError("Every item needs a slug.")
            try:
                quantity = int(row.get("quantity", 1))
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"Bad quantity for '{slug}'.")
            if quantity < 1:
                raise serializers.ValidationError(f"Quantity for '{slug}' must be at least 1.")
            cleaned.append({"slug": slug, "quantity": quantity})
        return cleaned

    @transaction.atomic
    def create(self, validated):
        rows = validated.pop("items")
        slugs = [r["slug"] for r in rows]
        products = {
            p.slug: p
            for p in Product.objects.filter(
                slug__in=slugs, is_active=True, subcategory__is_active=True
            )
        }

        missing = [s for s in slugs if s not in products]
        if missing:
            raise serializers.ValidationError(
                {"items": [f"No longer available: {', '.join(sorted(set(missing)))}"]}
            )
        out_of_stock = [s for s in slugs if not products[s].in_stock]
        if out_of_stock:
            raise serializers.ValidationError(
                {"items": [f"Out of stock: {', '.join(sorted(set(out_of_stock)))}"]}
            )

        order = Order(**validated)
        item_total = Decimal("0")
        lines = []
        for row in rows:
            product = products[row["slug"]]
            lines.append(
                OrderItem(
                    product=product,
                    name=product.display_name,
                    unit=product.unit,
                    unit_price=product.price,
                    quantity=row["quantity"],
                )
            )
            item_total += product.price * row["quantity"]

        order.item_total = item_total
        order.delivery_fee = Decimal("0") if item_total >= FREE_DELIVERY_ABOVE else DELIVERY_FEE
        order.total = order.item_total + order.delivery_fee - order.discount
        order.save()

        for line in lines:
            line.order = order
        OrderItem.objects.bulk_create(lines)
        return order
