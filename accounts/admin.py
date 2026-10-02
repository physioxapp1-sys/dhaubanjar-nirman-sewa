from django.contrib import admin

from .models import PasswordResetCode, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["phone", "full_name", "user", "created_at"]
    search_fields = ["phone", "full_name", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["user"]


@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    """Read-only: these are generated and consumed by the API, not hand-
    edited. Visible here mainly for support - looking up whether a customer
    who says "the code didn't work" was sent one, and when."""

    list_display = ["user", "code", "created_at", "consumed_at", "is_expired"]
    search_fields = ["user__username", "code"]
    readonly_fields = ["user", "code", "created_at", "updated_at", "consumed_at"]
    list_select_related = ["user"]

    def has_add_permission(self, request):
        return False

    @admin.display(boolean=True)
    def is_expired(self, obj):
        return obj.is_expired
