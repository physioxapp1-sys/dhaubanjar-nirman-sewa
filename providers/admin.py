from django.contrib import admin
from django.db import models
from django.utils.html import format_html

from .models import Provider


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = [
        "name", "trade", "engagement", "service_area", "rating", "review_count",
        "display_rate", "jobs_completed", "total_earned",
        "is_available", "is_verified", "is_active", "thumb",
    ]
    list_filter = ["engagement", "trade", "is_available", "is_verified", "is_active", "categories"]
    list_editable = ["is_available", "is_verified", "is_active"]
    search_fields = ["name", "slug", "phone", "service_area"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["jobs_completed_display", "total_earned_display"]

    # A provider covers a handful of categories out of ~23; the horizontal
    # picker is far less error-prone here than a multi-select box.
    filter_horizontal = ["categories"]

    fieldsets = [
        (None, {"fields": ["name", "slug", "trade", "engagement", "categories", "about"]}),
        ("Contact", {"fields": ["phone", "email", "facebook_url", "whatsapp_number", "service_area", "photo"]}),
        ("Standing", {
            "fields": [
                "experience_years", "rating", "review_count", "is_verified",
                "jobs_completed_display", "total_earned_display",
            ],
        }),
        ("Pricing", {"fields": ["rate", "rate_unit"]}),
        ("Listing", {"fields": ["is_available", "is_active", "sort_order"]}),
    ]
    actions = ["mark_available", "mark_unavailable", "verify"]

    def get_queryset(self, request):
        from django.db.models import Count, Sum

        from bookings.models import Booking

        completed = Count("bookings", filter=models.Q(bookings__status=Booking.Status.COMPLETED), distinct=True)
        earned = Sum("bookings__final_amount", filter=models.Q(bookings__status=Booking.Status.COMPLETED))
        return (
            super().get_queryset(request)
            .prefetch_related("categories")
            .annotate(jobs_completed=completed, total_earned=earned)
        )

    @admin.display(description="Jobs done", ordering="jobs_completed")
    def jobs_completed(self, obj):
        return obj.jobs_completed or 0

    @admin.display(description="Earned")
    def total_earned(self, obj):
        return obj.total_earned or 0

    @admin.display(description="Jobs completed")
    def jobs_completed_display(self, obj):
        return obj.jobs_completed or 0

    @admin.display(description="Total earned")
    def total_earned_display(self, obj):
        return obj.total_earned or 0

    @admin.display(description="Rate")
    def display_rate(self, obj):
        return obj.display_rate

    @admin.display(description="Photo")
    def thumb(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height:34px;border-radius:50%">', obj.photo.url
            )
        return "—"

    @admin.action(description="Mark as available today")
    def mark_available(self, request, queryset):
        n = queryset.update(is_available=True)
        self.message_user(request, f"{n} marked available.")

    @admin.action(description="Mark as unavailable")
    def mark_unavailable(self, request, queryset):
        n = queryset.update(is_available=False)
        self.message_user(request, f"{n} marked unavailable.")

    @admin.action(description="Mark as verified")
    def verify(self, request, queryset):
        n = queryset.update(is_verified=True)
        self.message_user(request, f"{n} verified.")
