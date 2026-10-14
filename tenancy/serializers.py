from datetime import date

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

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError(
                "Give it a name you will recognise, like 'Dhapasi 2BHK, first floor'."
            )
        return value

    def validate_address(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError(
                "Enter enough address for someone to find it."
            )
        return value


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


class TenancyWriteSerializer(serializers.ModelSerializer):
    """Putting a tenant into a property.

    The property has to be the caller's, and it has to be empty: two live
    leases on one flat is not a thing that can be true, and letting it be
    recorded would quietly double the rent roll.
    """

    # A family taking two rooms is one lease over both. The headline room is
    # the first of them, which is what a one-room lease has always been.
    rooms = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Property.objects.all(), required=False
    )
    # Optional, because create() takes it from the first room when only rooms
    # are sent. The model still requires one; validate() makes sure there is.
    property = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(), required=False
    )

    class Meta:
        model = Tenancy
        fields = [
            "id", "property", "rooms", "tenant_name", "tenant_phone",
            "start_date", "end_date", "monthly_rent", "deposit",
            "rent_due_day", "notes",
        ]

    def validate_property(self, value):
        self._check_room(value)
        return value

    def validate_rooms(self, value):
        for room in value:
            self._check_room(room)
        return value

    def _check_room(self, room):
        user = self.context["request"].user
        if room.owner_id != user.id:
            raise serializers.ValidationError(
                f"{room.title} is not your property."
            )
        if room.current_tenancy is not None:
            raise serializers.ValidationError(
                f"Someone is already in {room.title}. End that tenancy first."
            )

    def validate_tenant_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Enter the tenant's name.")
        return value

    def validate_tenant_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value.strip()

    def validate_rent_due_day(self, value):
        if not 1 <= value <= 31:
            raise serializers.ValidationError("Pick a day between 1 and 31.")
        return value

    def validate(self, attrs):
        start, end = attrs.get("start_date"), attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The tenancy cannot end before it starts."}
            )
        if not attrs.get("property") and not attrs.get("rooms"):
            raise serializers.ValidationError(
                {"rooms": "Pick at least one room."}
            )
        return attrs

    def create(self, validated):
        rooms = list(validated.pop("rooms", []))
        # Either way round: a lease given only rooms takes the first as its
        # headline, and one given only a property covers that one room.
        headline = validated.get("property") or rooms[0]
        validated["property"] = headline
        if headline not in rooms:
            rooms.insert(0, headline)

        validated.setdefault("monthly_rent", headline.monthly_rent)
        # A lease that has already begun starts active; one dated forward is
        # upcoming, and the monthly run picks it up when its month arrives.
        validated["status"] = (
            Tenancy.Status.ACTIVE
            if validated["start_date"] <= date.today()
            else Tenancy.Status.UPCOMING
        )
        tenancy = super().create(validated)
        tenancy.rooms.set(rooms)

        # A room with someone in it is not available, whatever it was flagged.
        listed = [r for r in rooms if r.is_listed]
        for room in listed:
            room.is_listed = False
            room.save(update_fields=["is_listed"])
        return tenancy


class TenancySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    property_title = serializers.CharField(source="property.title", read_only=True)
    property_address = serializers.CharField(source="property.address", read_only=True)
    owner_name = serializers.SerializerMethodField()
    document = serializers.SerializerMethodField()
    room_names = serializers.SerializerMethodField()

    class Meta:
        model = Tenancy
        fields = [
            "id", "property", "property_title", "property_address",
            "room_names", "tenant_name", "tenant_phone", "owner_name",
            "start_date", "end_date", "monthly_rent", "deposit", "rent_due_day",
            "status", "status_display", "document", "notes",
        ]

    def get_room_names(self, obj):
        """Every room the lease covers. One name for a one-room lease, which
        is what it has always been."""
        names = [r.title for r in obj.rooms.all()]
        return names or ([obj.property.title] if obj.property_id else [])

    def get_owner_name(self, obj):
        owner = obj.property.owner
        return (owner.get_full_name() or owner.username) if owner else None

    def get_document(self, obj):
        if not obj.document:
            return None
        request = self.context.get("request")
        url = obj.document.url
        return request.build_absolute_uri(url) if request else url
