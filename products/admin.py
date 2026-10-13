from django.contrib import admin
from django.utils.html import format_html

from .models import Collection, Product


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name", "unit", "subcategory", "price", "mrp", "off",
        "rating", "review_count", "in_stock", "is_active", "thumb",
    ]
    list_filter = ["in_stock", "is_active", "collections", "subcategory"]
    list_editable = ["price", "in_stock", "is_active"]
    search_fields = ["name", "slug", "subcategory__name"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["subcategory"]
    filter_horizontal = ["collections"]
    list_select_related = ["subcategory"]
    fieldsets = [
        (None, {"fields": ["subcategory", "collections", "name", "slug", "unit"]}),
        ("Price", {"fields": ["price", "mrp"]}),
        ("Detail screen", {"fields": ["image", "description", "badge",
                                      "origin", "shelf_life", "return_policy"]}),
        ("Standing", {"fields": ["rating", "review_count"]}),
        ("Listing", {"fields": ["in_stock", "is_active", "sort_order"]}),
    ]
    actions = ["mark_in_stock", "mark_out_of_stock"]

    @admin.display(description="Off")
    def off(self, obj):
        pct = obj.discount_percent
        return f"{pct}%" if pct else "-"

    @admin.display(description="Image")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:34px;border-radius:4px">', obj.image.url)
        return "-"

    @admin.action(description="Mark as in stock")
    def mark_in_stock(self, request, queryset):
        n = queryset.update(in_stock=True)
        self.message_user(request, f"{n} marked in stock.")

    @admin.action(description="Mark as out of stock")
    def mark_out_of_stock(self, request, queryset):
        n = queryset.update(in_stock=False)
        self.message_user(request, f"{n} marked out of stock.")
