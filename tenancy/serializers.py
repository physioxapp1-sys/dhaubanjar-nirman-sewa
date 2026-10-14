from rest_framework import serializers

from .models import Property, RentPayment, Tenancy


class PropertySerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    image = serializers.SerializerMethodField()
    is_occupied = serializers.BooleanField(read_only=True)
    tenant_name = serializers.SerializerMethodField()
    rent_state = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            "id", "title", "kind", "kind_display", "address", "city", "landmark",
            "bedrooms", "bathrooms", "area_sqft", "monthly_rent", "deposit",
            "is_listed", "description", "image", "is_occupied", "tenant_name",
            "rent_state",
        ]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def get_tenant_name(self, obj):
        """Only the owner sees who is in it. To anyone browsing for a place,
        a let property is simply not available."""
        if not self._is_owner(obj):
            return None
        tenancy = obj.current_tenancy
        return tenancy.tenant_name if tenancy else None

    def get_rent_state(self, obj):
        """paid / due / overdue for this month, for the owner's list."""
        if not self._is_owner(obj):
            return None
        tenancy = obj.current_tenancy
        if tenancy is None:
            return None
        payment = tenancy.payments.order_by("-period").first()
        return payment.state if payment else None

    def _is_owner(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.owner_id == user.id)


class RentPaymentSerializer(serializers.ModelSerializer):
    state = serializers.CharField(read_only=True)
    property_title = serializers.CharField(source="tenancy.property.title", read_only=True)
    tenant_name = serializers.CharField(source="tenancy.tenant_name", read_only=True)

    class Meta:
        model = RentPayment
        fields = [
            "id", "period", "due_date", "amount", "paid_on", "amount_paid",
            "method", "reference", "notes", "state", "property_title", "tenant_name",
        ]


class RecordPaymentSerializer(serializers.Serializer):
    """Marking a month's rent as received. Only an owner may, and only on
    their own property - see the view."""

    paid_on = serializers.DateField(required=False)
    amount_paid = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    method = serializers.CharField(max_length=40, required=False, allow_blank=True)
    reference = serializers.CharField(max_length=80, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class TenancySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    property_title = serializers.CharField(source="property.title", read_only=True)
    property_address = serializers.CharField(source="property.address", read_only=True)
    owner_name = serializers.SerializerMethodField()
    document = serializers.SerializerMethodField()

    class Meta:
        model = Tenancy
        fields = [
            "id", "property", "property_title", "property_address",
            "tenant_name", "tenant_phone", "owner_name",
            "start_date", "end_date", "monthly_rent", "deposit", "rent_due_day",
            "status", "status_display", "document", "notes",
        ]

    def get_owner_name(self, obj):
        owner = obj.property.owner
        return (owner.get_full_name() or owner.username) if owner else None

    def get_document(self, obj):
        if not obj.document:
            return None
        request = self.context.get("request")
        url = obj.document.url
        return request.build_absolute_uri(url) if request else url
