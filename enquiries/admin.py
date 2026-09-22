from django.contrib import admin

from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "project_type", "source", "status", "created_at"]
    list_filter = ["status", "source", "project_type", "created_at"]
    list_editable = ["status"]
    search_fields = ["name", "phone", "email", "message"]
    date_hierarchy = "created_at"
    actions = ["mark_contacted", "mark_spam"]

    # Everything the sender supplied is a record of what they sent, so it is
    # shown but not editable; only status and notes are ours to change.
    readonly_fields = [
        "name", "phone", "email", "message", "project_type", "budget",
        "subcategory", "source", "ip_address", "user_agent",
        "created_at", "updated_at",
    ]
    fieldsets = [
        ("Enquiry", {"fields": ["name", "phone", "email", "message"]}),
        ("Details", {"fields": ["project_type", "budget", "subcategory", "source"]}),
        ("Handling", {"fields": ["status", "notes"]}),
        ("Audit", {"classes": ["collapse"],
                   "fields": ["ip_address", "user_agent", "created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return False  # enquiries arrive through the form, not by hand

    @admin.action(description="Mark as contacted")
    def mark_contacted(self, request, queryset):
        n = queryset.update(status=Enquiry.Status.CONTACTED)
        self.message_user(request, f"{n} marked contacted.")

    @admin.action(description="Mark as spam")
    def mark_spam(self, request, queryset):
        n = queryset.update(status=Enquiry.Status.SPAM)
        self.message_user(request, f"{n} marked spam.")
