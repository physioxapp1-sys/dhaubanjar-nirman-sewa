from rest_framework import serializers

from .models import Enquiry


class EnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = [
            "id", "name", "phone", "email", "message",
            "project_type", "budget", "subcategory", "source",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            # Clients must not be able to set status, notes or the audit fields.
            "source": {"required": False},
        }

    def validate_phone(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value.strip()

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Please tell us a little more.")
        return value
