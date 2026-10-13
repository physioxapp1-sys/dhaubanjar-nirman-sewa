import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response

from .models import Address, DeliverySlot, Order
from .serializers import AddressSerializer, OrderCreateSerializer, OrderSerializer

log = logging.getLogger(__name__)


class AddressViewSet(viewsets.ModelViewSet):
    """Saved addresses, scoped to the caller - an id belonging to another
    account is simply not found rather than forbidden."""

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # The first address someone saves is their default, otherwise checkout
        # would open with nothing selected.
        first = not Address.objects.filter(user=self.request.user).exists()
        serializer.save(
            user=self.request.user,
            is_default=first or serializer.validated_data.get("is_default", False),
        )


class OrderCreateView(generics.CreateAPIView):
    """Place an order.

    Open, like bookings: someone can shop and check out before making an
    account, and a signed-in request simply gets the user attached.
    """

    serializer_class = OrderCreateSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "booking"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(
            user=request.user if request.user.is_authenticated else None
        )
        self._notify(order)
        return Response(
            OrderSerializer(order, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _notify(self, order):
        recipients = getattr(settings, "ENQUIRY_NOTIFY_EMAILS", None)
        if not recipients:
            return
        lines = [
            f"Reference: {order.reference}",
            f"Name:      {order.contact_name}",
            f"Phone:     {order.contact_phone}",
            f"When:      {order.scheduled_date or 'not set'} "
            f"({order.get_slot_display() or '-'})",
            f"Address:   {order.delivery_address}",
            "",
            "Items:",
        ]
        lines += [f"  {i.quantity} x {i.name} @ {i.unit_price}" for i in order.items.all()]
        lines += ["", f"Total:     NPR {order.total}"]
        try:
            send_mail(
                subject=f"New order {order.reference}",
                message="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )
        except Exception:
            # The order is saved; a mail outage must not fail the request.
            log.exception("Could not send order notification for %s", order.reference)


class MyOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("delivery_partner")
            .prefetch_related("items__product")
        )


class OrderLookupView(generics.RetrieveAPIView):
    """Track an order without an account. The phone must match, so a
    reference on its own - which gets forwarded - reveals nothing."""

    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "reference"

    def get_queryset(self):
        phone = self.request.query_params.get("phone", "")
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 7:
            return Order.objects.none()
        return (
            Order.objects.filter(contact_phone__endswith=digits[-7:])
            .select_related("delivery_partner")
            .prefetch_related("items__product")
        )


class DeliverySlotListView(generics.GenericAPIView):
    """The delivery windows, so the app does not hard-code them."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(
            [{"value": value, "label": label} for value, label in DeliverySlot.choices]
        )
