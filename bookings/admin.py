from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "reference", "contact_name", "contact_phone", "subcategory",
        "provider", "scheduled_date", "slot", "status", "created_at",
    ]
    list_filter = ["status", "slot", "source", "created_at", "provider"]
    list_editable = ["status"]
    search_fields = ["reference", "contact_name", "contact_phone", "address"]
    date_hierarchy = "created_at"
    autocomplete_fields = ["subcategory", "provider"]
    list_select_related = ["subcategory", "provider"]
    actions = ["mark_confirmed", "mark_completed", "mark_cancelled"]

    # What the customer sent is a record of what they sent. Staff change the
    # handling fields, not the request itself.
    readonly_fields = ["reference", "user", "contact_name", "contact_phone",
                       "address", "landmark", "notes", "source",
                       "created_at", "updated_at"]
    fieldsets = [
        ("Booking", {"fields": ["reference", "status", "source", "user"]}),
        ("Customer", {"fields": ["contact_name", "contact_phone", "address", "landmark"]}),
        ("Job", {"fields": ["subcategory", "provider", "scheduled_date", "slot", "notes"]}),
        ("Money", {"fields": ["quoted_amount", "final_amount"]}),
        ("Internal", {"fields": ["staff_notes"]}),
        ("Audit", {"classes": ["collapse"], "fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        # Bookings arrive from the app; adding one by hand here would have no
        # customer behind it. Phone bookings go in as an Enquiry instead.
        return False

    @admin.action(description="Mark as confirmed")
    def mark_confirmed(self, request, queryset):
        n = queryset.update(status=Booking.Status.CONFIRMED)
        self.message_user(request, f"{n} confirmed.")

    @admin.action(description="Mark as completed")
    def mark_completed(self, request, queryset):
        n = queryset.update(status=Booking.Status.COMPLETED)
        self.message_user(request, f"{n} completed.")

    @admin.action(description="Mark as cancelled")
    def mark_cancelled(self, request, queryset):
        n = queryset.update(status=Booking.Status.CANCELLED)
        self.message_user(request, f"{n} cancelled.")
