from django.contrib import admin
from django.utils.html import format_html

from .models import Provider


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = [
        "name", "trade", "service_area", "rating", "review_count",
        "display_rate", "is_available", "is_verified", "is_active", "thumb",
    ]
    list_filter = ["trade", "is_available", "is_verified", "is_active", "categories"]
    list_editable = ["is_available", "is_verified", "is_active"]
    search_fields = ["name", "slug", "phone", "service_area"]
    prepopulated_fields = {"slug": ("name",)}

    # A provider covers a handful of categories out of ~23; the horizontal
    # picker is far less error-prone here than a multi-select box.
    filter_horizontal = ["categories"]

    fieldsets = [
        (None, {"fields": ["name", "slug", "trade", "categories", "about"]}),
        ("Contact", {"fields": ["phone", "email", "service_area", "photo"]}),
        ("Standing", {"fields": ["experience_years", "rating", "review_count", "is_verified"]}),
        ("Pricing", {"fields": ["rate", "rate_unit"]}),
        ("Listing", {"fields": ["is_available", "is_active", "sort_order"]}),
    ]
    actions = ["mark_available", "mark_unavailable", "verify"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("categories")

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
