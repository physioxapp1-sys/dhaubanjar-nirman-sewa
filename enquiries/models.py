"""Enquiries captured from the website contact form and the app."""
from django.db import models


class Enquiry(models.Model):
    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        APP = "app", "Pakka Homes app"
        PHONE = "phone", "Phone"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUOTED = "quoted", "Quoted"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        SPAM = "spam", "Spam"

    class ProjectType(models.TextChoices):
        RESIDENTIAL = "residential", "Residential building"
        COMMERCIAL = "commercial", "Commercial building"
        RENOVATION = "renovation", "Renovation / interiors"
        CONSULTANCY = "consultancy", "Design & consultancy only"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32)
    email = models.EmailField(blank=True)
    message = models.TextField()

    project_type = models.CharField(
        max_length=20, choices=ProjectType.choices, blank=True
    )
    budget = models.CharField(max_length=60, blank=True)

    # Set when the enquiry came from a specific catalog entry in the app.
    subcategory = models.ForeignKey(
        "catalog.Subcategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enquiries",
    )

    source = models.CharField(
        max_length=12, choices=Source.choices, default=Source.WEBSITE, db_index=True
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.NEW, db_index=True
    )
    notes = models.TextField(blank=True, help_text="Internal only - not shown to the sender.")

    # Kept for spam triage; not exposed by the API.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "enquiries"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.name} ({self.phone}) - {self.get_status_display()}"
