from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Category, Subcategory


class SubcategoryInline(admin.TabularInline):
    model = Subcategory
    extra = 0
    fields = ["name", "rate", "rate_unit", "sort_order", "is_popular", "is_active"]
    prepopulated_fields = {}
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "vertical", "item_count", "sort_order", "is_active", "thumb"]
    list_filter = ["vertical", "is_active"]
    list_editable = ["sort_order", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SubcategoryInline]
    fieldsets = [
        (None, {"fields": ["vertical", "name", "slug", "description"]}),
        ("Presentation", {"fields": ["image", "image_key", "icon", "sort_order", "is_active"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _count=Count("subcategories", filter=Q(subcategories__is_active=True))
        )

    @admin.display(description="Items", ordering="_count")
    def item_count(self, obj):
        return obj._count

    @admin.display(description="Image")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:34px;border-radius:4px">', obj.image.url)
        return "—"


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "vertical", "display_rate", "is_popular", "is_active"]
    list_filter = ["category__vertical", "is_popular", "is_active", "rate_unit", "category"]
    list_editable = ["is_popular", "is_active"]
    search_fields = ["name", "slug", "category__name"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["category"]
    list_select_related = ["category"]
    actions = ["mark_popular", "unmark_popular"]

    @admin.display(description="Vertical", ordering="category__vertical")
    def vertical(self, obj):
        return obj.category.get_vertical_display()

    @admin.action(description="Mark as popular")
    def mark_popular(self, request, queryset):
        n = queryset.update(is_popular=True)
        self.message_user(request, f"{n} marked popular.")

    @admin.action(description="Remove from popular")
    def unmark_popular(self, request, queryset):
        n = queryset.update(is_popular=False)
        self.message_user(request, f"{n} removed from popular.")
