from django.conf import settings


def site_details(request):
    """Contact details live in one place so the page, the footer and the
    JSON-LD block cannot drift apart."""
    return {
        "site": {
            "name": "Dhaubanjar Nirman Sewa",
            "name_ne": "धौबन्जार निर्माण सेवा",
            "phone": "+977 9841042319",
            "phone_link": "+9779841042319",
            "email": settings.DEFAULT_FROM_EMAIL,
            "address": "Dhaubanjar, Bhaktapur, Bagmati Province, Nepal",
            "canonical": "https://www.dhaubanjarnirmansewa.com.np/",
        }
    }
