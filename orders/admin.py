from django.contrib import admin

from .models import Address, Order, OrderItem


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "label", "recipient_name", "phone", "city", "is_default"]
    list_filter = ["label", "is_default", "city"]
    search_fields = ["recipient_name", "phone", "address", "landmark", "user__username"]
    list_select_related = ["user"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Snapshots of what was bought; editing them would rewrite history.
    readonly_fields = ["product", "name", "unit", "unit_price", "quantity", "line_total"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Line total")
    def line_total(self, obj):
        return obj.line_total


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "reference", "contact_name", "contact_phone", "scheduled_date",
        "slot", "total", "status", "delivery_partner", "created_at",
    ]
    # Empty-partner first: that is the dispatch queue for orders going out.
    list_filter = [
        ("delivery_partner", admin.EmptyFieldListFilter),
        "status", "slot", "created_at",
    ]
    list_editable = ["status"]
    search_fields = ["reference", "contact_name", "contact_phone", "delivery_address"]
    date_hierarchy = "created_at"
    autocomplete_fields = ["delivery_partner"]
    inlines = [OrderItemInline]
    list_select_related = ["delivery_partner"]

    readonly_fields = [
        "reference", "user", "contact_name", "contact_phone", "delivery_address",
        "landmark", "notes", "item_total", "delivery_fee", "total",
        "created_at", "updated_at",
    ]
    fieldsets = [
        ("Order", {"fields": ["reference", "status", "user"]}),
        ("Customer", {"fields": ["contact_name", "contact_phone",
                                 "delivery_address", "landmark"]}),
        ("Delivery", {"fields": ["scheduled_date", "slot", "delivery_partner", "notes"]}),
        ("Money", {"fields": ["item_total", "delivery_fee", "discount", "total"]}),
        ("Internal", {"fields": ["staff_notes"]}),
        ("Audit", {"classes": ["collapse"], "fields": ["created_at", "updated_at"]}),
    ]
    actions = ["mark_preparing", "mark_out_for_delivery", "mark_delivered"]

    def has_add_permission(self, request):
        # Orders come from the app; one typed in here has no customer behind it.
        return False

    @admin.action(description="Mark as preparing")
    def mark_preparing(self, request, queryset):
        n = queryset.update(status=Order.Status.PREPARING)
        self.message_user(request, f"{n} marked preparing.")

    @admin.action(description="Mark as out for delivery")
    def mark_out_for_delivery(self, request, queryset):
        n = queryset.update(status=Order.Status.OUT_FOR_DELIVERY)
        self.message_user(request, f"{n} marked out for delivery.")

    @admin.action(description="Mark as delivered")
    def mark_delivered(self, request, queryset):
        n = queryset.update(status=Order.Status.DELIVERED)
        self.message_user(request, f"{n} marked delivered.")
