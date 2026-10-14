"""
The Rent section's API.

Every endpoint answers for whoever is asking. An owner sees their properties,
their tenants and whether the rent arrived; a tenant sees the one place they
live, what they owe and their own lease. Nobody is flagged as either - owning
a property makes you an owner and being named on a live lease makes you a
tenant, and a person can be both.
"""
from datetime import date

from django.db.models import Q, Sum
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Property, RentPayment, Tenancy
from .serializers import (
    PropertySerializer,
    RecordPaymentSerializer,
    RentPaymentSerializer,
    TenancySerializer,
    TenancyWriteSerializer,
)


def owned_by(user):
    return Property.objects.filter(owner=user, is_active=True)


def rented_by(user):
    """Live leases naming this person.

    Matched on the account first and the phone number second, because a lease
    is usually typed in by the owner before the tenant ever installs the app -
    and that lease is still theirs.
    """
    mine = Q(tenant=user)
    # Accounts are keyed by phone number, so the last seven digits are what
    # links a lease typed in by the owner to the person who later signs up.
    phone = "".join(c for c in (getattr(user, "username", "") or "") if c.isdigit())
    if len(phone) >= 7:
        mine |= Q(tenant__isnull=True) & Q(tenant_phone__endswith=phone[-7:])
    return Tenancy.objects.filter(mine, status=Tenancy.Status.ACTIVE)


class RentHomeView(APIView):
    """What the Dashboard tab draws, and which tabs to draw at all.

    One request rather than four: the first thing the screen needs to know is
    which of the two sides the person is on, and asking that separately would
    mean a spinner before a spinner.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        properties = owned_by(user)
        tenancies = rented_by(user)
        today = date.today()

        payload = {
            "is_owner": properties.exists(),
            "is_tenant": tenancies.exists(),
            "owner": None,
            "tenant": None,
        }

        if payload["is_owner"]:
            live = Tenancy.objects.filter(
                property__in=properties, status=Tenancy.Status.ACTIVE
            )
            payments = RentPayment.objects.filter(tenancy__in=live)
            this_month = payments.filter(period__year=today.year, period__month=today.month)
            overdue = payments.filter(paid_on__isnull=True, due_date__lt=today)
            payload["owner"] = {
                "properties": properties.count(),
                "occupied": live.count(),
                "vacant": properties.count() - live.count(),
                "expected_this_month": this_month.aggregate(t=Sum("amount"))["t"] or 0,
                "collected_this_month": this_month.filter(paid_on__isnull=False)
                .aggregate(t=Sum("amount_paid"))["t"]
                or 0,
                "overdue_count": overdue.count(),
                "overdue_amount": overdue.aggregate(t=Sum("amount"))["t"] or 0,
            }

        if payload["is_tenant"]:
            tenancy = tenancies.select_related("property").first()
            due = (
                RentPayment.objects.filter(tenancy=tenancy, paid_on__isnull=True)
                .order_by("due_date")
                .first()
            )
            payload["tenant"] = {
                "tenancy": TenancySerializer(tenancy, context={"request": request}).data,
                "next_due": RentPaymentSerializer(due).data if due else None,
                "unpaid_count": RentPayment.objects.filter(
                    tenancy=tenancy, paid_on__isnull=True
                ).count(),
            }

        return Response(payload)


class PropertyListView(generics.ListCreateAPIView):
    """Owned properties, or - with ?listed=true - places going spare.

    The listed view is open: someone looking for a flat has no reason to have
    an account yet, and it carries no tenant names.
    """

    serializer_class = PropertySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Property.objects.filter(is_active=True).select_related("owner")
        if self.request.query_params.get("listed") == "true":
            # Listed and empty. A flat with someone in it is not available
            # however it is flagged.
            occupied = Tenancy.objects.filter(
                status=Tenancy.Status.ACTIVE
            ).values_list("property_id", flat=True)
            return qs.filter(is_listed=True).exclude(id__in=occupied)
        if not self.request.user.is_authenticated:
            return qs.none()
        return qs.filter(owner=self.request.user).prefetch_related("tenancies__payments")

    def get_permissions(self):
        # Browsing is open; adding a property is not.
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        # The owner is whoever is adding it, never whatever was posted.
        serializer.save(owner=self.request.user)


class PropertyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Edit or remove one of your own.

    Deleting is a soft delete: a property with a history of leases and
    payments behind it should stop being listed, not take that history with it.
    """

    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Property.objects.filter(owner=self.request.user, is_active=True)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class RentPaymentListView(generics.ListAPIView):
    """The rent roll. An owner sees every tenant's; a tenant sees their own."""

    serializer_class = RentPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = RentPayment.objects.select_related("tenancy__property")
        if self.request.query_params.get("as") == "tenant":
            return qs.filter(tenancy__in=rented_by(user))
        mine = qs.filter(tenancy__property__owner=user)
        if self.request.query_params.get("state") == "unpaid":
            mine = mine.filter(paid_on__isnull=True)
        return mine


class RecordPaymentView(APIView):
    """Mark a month's rent as received.

    Owners only, and only on their own property: a tenant saying they paid is
    not the same event as the money arriving.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        payment = (
            RentPayment.objects.filter(pk=pk, tenancy__property__owner=request.user)
            .select_related("tenancy")
            .first()
        )
        if payment is None:
            # Not 403: an id belonging to someone else is simply not found,
            # so this cannot be used to count other people's properties.
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        form = RecordPaymentSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        payment.paid_on = data.get("paid_on") or date.today()
        payment.amount_paid = data.get("amount_paid") or payment.amount
        payment.method = data.get("method", payment.method)
        payment.reference = data.get("reference", payment.reference)
        if data.get("notes"):
            payment.notes = data["notes"]
        payment.save()
        return Response(RentPaymentSerializer(payment).data)


class TenancyListView(generics.ListCreateAPIView):
    """Contracts: every lease on an owner's properties, or a tenant's own.

    Creating one is the owner putting a tenant into a flat.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return TenancyWriteSerializer if self.request.method == "POST" else TenancySerializer

    def create(self, request, *args, **kwargs):
        form = self.get_serializer(data=request.data)
        form.is_valid(raise_exception=True)
        tenancy = form.save()
        # Raise this month's rent straight away rather than waiting for the
        # monthly run: an owner who has just added a tenant should see the
        # rent roll fill, not an empty tab until the 1st.
        _raise_current_month(tenancy)
        return Response(
            TenancySerializer(tenancy, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        user = self.request.user
        qs = Tenancy.objects.select_related("property", "property__owner")
        if self.request.query_params.get("as") == "tenant":
            return qs.filter(id__in=rented_by(user).values("id"))
        return qs.filter(property__owner=user)


def _raise_current_month(tenancy):
    """This month's rent row for a lease that has started.

    The same thing `raise_rent` does every month, for the one lease. Harmless
    to repeat - (tenancy, period) is unique.
    """
    if tenancy.status != Tenancy.Status.ACTIVE:
        return
    today = date.today()
    period = date(today.year, today.month, 1)
    if tenancy.start_date > period and tenancy.start_date.month != today.month:
        return
    RentPayment.objects.get_or_create(
        tenancy=tenancy,
        period=period,
        defaults={
            "due_date": tenancy.due_date(period.year, period.month),
            "amount": tenancy.monthly_rent,
        },
    )


class EndTenancyView(APIView):
    """Someone has moved out.

    Ended rather than deleted: the lease and the rent paid under it are what
    happened, and next year's question is always "who was in it and what did
    they pay".
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        tenancy = Tenancy.objects.filter(
            pk=pk, property__owner=request.user
        ).select_related("property").first()
        if tenancy is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ended_on = request.data.get("end_date") or date.today().isoformat()
        tenancy.end_date = ended_on
        tenancy.status = Tenancy.Status.ENDED
        tenancy.save(update_fields=["end_date", "status"])
        return Response(TenancySerializer(tenancy, context={"request": request}).data)
