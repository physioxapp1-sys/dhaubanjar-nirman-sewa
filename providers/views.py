from catalog.models import Vertical
from rest_framework import viewsets

from .models import Provider, Trade
from .serializers import ProviderSerializer


class ProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """Providers, filtered to what a category screen needs.

        GET /api/v1/providers/?category=construction&vertical=service
        GET /api/v1/providers/?trade=electrician&available=true
    """

    serializer_class = ProviderSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = Provider.objects.filter(is_active=True).prefetch_related("categories")

        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(categories__slug=p["category"])
        if p.get("vertical") in Vertical.values:
            qs = qs.filter(categories__vertical=p["vertical"])
        if p.get("trade") in Trade.values:
            qs = qs.filter(trade=p["trade"])
        if str(p.get("available", "")).lower() in ("1", "true", "yes"):
            qs = qs.filter(is_available=True)

        # Filtering across a m2m can repeat a row once per matching category.
        return qs.distinct()
