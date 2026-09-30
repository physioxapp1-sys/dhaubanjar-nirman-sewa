from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["phone", "full_name", "user", "created_at"]
    search_fields = ["phone", "full_name", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["user"]
