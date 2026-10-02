from django.db.models import Count, DecimalField, Exists, OuterRef, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import permissions, viewsets

from bookings.models import Booking
from catalog.models import Vertical

from .models import Provider, Trade
from .serializers import ProviderSerializer

_COMPLETED = Q(bookings__status=Booking.Status.COMPLETED)

# Same to_attr prefetch pattern catalog.views uses for active subcategories:
# load every relevant Booking once for the whole page, then read it back off
# each Provider in Python - not one extra query per row for the serializer's
# "what have they actually done" list.
_completed_bookings_prefetch = Prefetch(
    "bookings",
    queryset=Booking.objects.filter(status=Booking.Status.COMPLETED).select_related("subcategory"),
    to_attr="completed_bookings_cache",
)


class ProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """The dispatch roster. Staff only.

        GET /api/v1/providers/?category=construction&vertical=service
        GET /api/v1/providers/?trade=electrician&available=true
        GET /api/v1/providers/?min_jobs_completed=5
        GET /api/v1/providers/?worked_subcategory=new-wiring
        GET /api/v1/providers/?manager=ram-thapa-contractor
        GET /api/v1/providers/?ordering=-total_earned

    Not public, for two reasons. The customer books Pakka Homes and we
    assign someone, so the app has no need for it. And the roster is a list
    of tradespeople with phone numbers: published, it invites both poaching
    by competitors and customers going direct on the second job, which is
    where the margin is.

    jobs_completed and total_earned are annotated here, not stored on
    Provider, because they are only ever true as of the last completed
    Booking - the same reasoning the catalog's subcategory_count already
    uses one app over. Annotating rather than computing in Python is what
    lets min_jobs_completed and ?ordering=-total_earned work as real
    database filters/sorts instead of loading every provider to check.
    """

    serializer_class = ProviderSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = "slug"
    ordering_fields = ["sort_order", "rating", "name", "jobs_completed", "total_earned"]

    def get_queryset(self):
        qs = (
            Provider.objects.filter(is_active=True)
            .select_related("manager")
            .prefetch_related("categories", _completed_bookings_prefetch)
            .annotate(
                jobs_completed=Count("bookings", filter=_COMPLETED, distinct=True),
                total_earned=Coalesce(
                    Sum("bookings__final_amount", filter=_COMPLETED), 0,
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
            )
        )

        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(categories__slug=p["category"])
        if p.get("vertical") in Vertical.values:
            qs = qs.filter(categories__vertical=p["vertical"])
        if p.get("trade") in Trade.values:
            qs = qs.filter(trade=p["trade"])
        if str(p.get("available", "")).lower() in ("1", "true", "yes"):
            qs = qs.filter(is_available=True)
        if p.get("manager"):
            # manager is a to-one FK, so unlike categories/bookings below
            # this never multiplies rows - no Exists() needed here.
            qs = qs.filter(manager__slug=p["manager"])

        # Proven experience, not the self-reported trade label: has this
        # provider actually completed a job in this specific subcategory,
        # not just "do they claim to cover the broader category". This is
        # a correlated subquery rather than qs.filter(bookings__...=...)
        # on purpose - that form adds a second join on the same bookings
        # relation, which multiplies rows and silently doubles the
        # jobs_completed/total_earned aggregates above (confirmed by
        # providers.tests.test_worked_subcategory_does_not_corrupt_jobs_completed_or_total_earned
        # failing against that version). Exists() never joins, so the
        # aggregates stay untouched no matter how many bookings match.
        if p.get("worked_subcategory"):
            qs = qs.filter(
                Exists(
                    Booking.objects.filter(
                        provider=OuterRef("pk"),
                        subcategory__slug=p["worked_subcategory"],
                        status=Booking.Status.COMPLETED,
                    )
                )
            )
        if p.get("min_jobs_completed"):
            try:
                minimum = int(p["min_jobs_completed"])
            except ValueError:
                minimum = 0
            qs = qs.filter(jobs_completed__gte=minimum)

        ordering = p.get("ordering")
        if ordering and ordering.lstrip("-") in self.ordering_fields:
            qs = qs.order_by(ordering)

        # Filtering across a m2m, or across Bookings for worked_subcategory,
        # can repeat a row once per match.
        return qs.distinct()
