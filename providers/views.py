from catalog.models import Vertical
from rest_framework import permissions, viewsets

from .models import Provider, Trade
from .serializers import ProviderSerializer


class ProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """The dispatch roster. Staff only.

        GET /api/v1/providers/?category=construction&vertical=service
        GET /api/v1/providers/?trade=electrician&available=true

    Not public, for two reasons. The customer books Pakka Homes and we
    assign someone, so the app has no need for it. And the roster is a list
    of tradespeople with phone numbers: published, it invites both poaching
    by competitors and customers going direct on the second job, which is
    where the margin is.
    """

    serializer_class = ProviderSerializer
    permission_classes = [permissions.IsAdminUser]
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
