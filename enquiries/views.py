import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import generics, status
from rest_framework.response import Response

from .models import Enquiry
from .serializers import EnquirySerializer

log = logging.getLogger(__name__)


class EnquiryCreateView(generics.CreateAPIView):
    """Write-only. Enquiries are read in the Django admin, never over the API."""

    serializer_class = EnquirySerializer
    queryset = Enquiry.objects.none()
    throttle_scope = "enquiry"

    def _client_ip(self):
        # Behind Apache/LiteSpeed the real address is first in the chain.
        forwarded = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.request.META.get("REMOTE_ADDR")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquiry = serializer.save(
            ip_address=self._client_ip(),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        self._notify(enquiry)
        return Response(
            {
                "id": enquiry.id,
                "detail": "Thank you - we will reply within one working day.",
            },
            status=status.HTTP_201_CREATED,
        )

    def _notify(self, enquiry):
        recipients = getattr(settings, "ENQUIRY_NOTIFY_EMAILS", None)
        if not recipients:
            return
        body = (
            f"Name:    {enquiry.name}\n"
            f"Phone:   {enquiry.phone}\n"
            f"Email:   {enquiry.email or '-'}\n"
            f"Type:    {enquiry.get_project_type_display() or '-'}\n"
            f"Budget:  {enquiry.budget or '-'}\n"
            f"Source:  {enquiry.get_source_display()}\n\n"
            f"{enquiry.message}\n"
        )
        try:
            send_mail(
                subject=f"New enquiry from {enquiry.name}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )
        except Exception:
            # The enquiry is already saved; a mail outage must not lose it or
            # show the visitor an error.
            log.exception("Could not send notification for enquiry %s", enquiry.id)
