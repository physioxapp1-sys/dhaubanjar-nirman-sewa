import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer

log = logging.getLogger(__name__)


class BookingCreateView(generics.CreateAPIView):
    """Take a booking.

    Open to anyone: the app lets people book before they have an account
    (see task 2's soft gate), and a signed-in request simply gets the user
    attached. Throttled, since it writes.
    """

    serializer_class = BookingCreateSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "booking"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save(
            user=request.user if request.user.is_authenticated else None,
            source=Booking.Source.APP,
        )
        self._notify(booking)
        return Response(
            {
                "reference": booking.reference,
                "status": booking.status,
                "detail": f"Booking {booking.reference} received. We will call to confirm.",
            },
            status=status.HTTP_201_CREATED,
        )

    def _notify(self, booking):
        recipients = getattr(settings, "ENQUIRY_NOTIFY_EMAILS", None)
        if not recipients:
            return
        lines = [
            f"Reference: {booking.reference}",
            f"Name:      {booking.contact_name}",
            f"Phone:     {booking.contact_phone}",
            f"Service:   {booking.subcategory or '-'}",
            f"Provider:  {booking.provider or 'unassigned'}",
            f"When:      {booking.scheduled_date or 'not set'} ({booking.get_slot_display()})",
            f"Address:   {booking.address}",
            f"Notes:     {booking.notes or '-'}",
        ]
        try:
            send_mail(
                subject=f"New booking {booking.reference}",
                message="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )
        except Exception:
            # The booking is saved; a mail outage must not fail the request.
            log.exception("Could not send booking notification for %s", booking.reference)


class MyBookingListView(generics.ListAPIView):
    """The signed-in customer's own bookings - what the Bookings tab shows."""

    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related("subcategory", "provider")
        )


class BookingLookupView(generics.RetrieveAPIView):
    """Track a booking by reference without an account.

    The phone number must match, so a reference alone - which a customer
    might read out or forward - is not enough to expose someone's address.
    """

    serializer_class = BookingSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "reference"

    def get_queryset(self):
        phone = self.request.query_params.get("phone", "")
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 7:
            return Booking.objects.none()
        return Booking.objects.filter(contact_phone__endswith=digits[-7:]).select_related(
            "subcategory", "provider"
        )
