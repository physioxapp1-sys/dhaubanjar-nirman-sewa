from django.contrib import admin

from .models import Building, Property, RentPayment, Tenancy


class TenancyInline(admin.TabularInline):
    model = Tenancy
    extra = 0
    fields = ["tenant_name", "tenant_phone", "start_date", "end_date",
              "monthly_rent", "rent_due_day", "status"]
    show_change_link = True


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "kind", "city", "rooms_count", "is_active"]
    list_filter = ["kind", "is_active", "city"]
    search_fields = ["name", "address", "owner__username"]
    autocomplete_fields = ["owner"]
    list_select_related = ["owner"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("rooms")

    @admin.display(description="Rooms")
    def rooms_count(self, obj):
        return obj.rooms.count()


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["title", "building", "floor", "owner", "monthly_rent",
                    "occupied", "is_listed", "is_active"]
    list_filter = ["kind", "is_listed", "is_active", "city", "building"]
    search_fields = ["title", "address", "landmark", "owner__username"]
    list_select_related = ["owner", "building"]
    autocomplete_fields = ["owner", "building"]
    inlines = [TenancyInline]
    # No date_hierarchy - see the note in orders/admin.py.

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("tenancies")

    @admin.display(boolean=True, description="Occupied")
    def occupied(self, obj):
        return obj.is_occupied


class RentPaymentInline(admin.TabularInline):
    model = RentPayment
    extra = 0
    fields = ["period", "due_date", "amount", "paid_on", "amount_paid",
              "method", "reference"]
    ordering = ["-period"]


@admin.register(Tenancy)
class TenancyAdmin(admin.ModelAdmin):
    list_display = ["tenant_name", "tenant_phone", "rooms_display", "start_date",
                    "end_date", "monthly_rent", "rent_due_day", "status"]
    list_filter = ["status", "start_date", "property__city"]
    search_fields = ["tenant_name", "tenant_phone", "property__title"]
    list_select_related = ["property"]
    autocomplete_fields = ["property", "tenant"]
    filter_horizontal = ["rooms"]
    list_editable = ["status"]
    inlines = [RentPaymentInline]

    def get_queryset(self, request):
        # rooms_display walks the m2m for every row.
        return super().get_queryset(request).prefetch_related("rooms")


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ["tenancy", "period", "due_date", "amount", "paid_on",
                    "amount_paid", "state", "method"]
    # Unpaid first: that is the list anyone opens this page to see.
    list_filter = [("paid_on", admin.EmptyFieldListFilter), "due_date", "method"]
    search_fields = ["tenancy__tenant_name", "tenancy__tenant_phone",
                     "tenancy__property__title", "reference"]
    list_select_related = ["tenancy", "tenancy__property"]
    autocomplete_fields = ["tenancy"]
    actions = ["mark_paid"]

    @admin.display(description="State")
    def state(self, obj):
        return obj.state

    @admin.action(description="Mark as paid today, in full")
    def mark_paid(self, request, queryset):
        from datetime import date

        n = 0
        for payment in queryset.filter(paid_on__isnull=True):
            payment.paid_on = date.today()
            payment.amount_paid = payment.amount
            payment.save()
            n += 1
        self.message_user(request, f"{n} marked paid.")
