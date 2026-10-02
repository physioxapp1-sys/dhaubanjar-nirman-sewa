import logging

from django.conf import settings
from rest_framework import generics, mixins, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    DeleteAccountSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    MeSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
)

log = logging.getLogger(__name__)


def _token_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {
        "token": token.key,
        "user": MeSerializer(user).data,
    }


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_token_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(_token_payload(serializer.validated_data["user"]))


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Drop the token so the device is signed out; other devices keep
        # working only if they have their own token, which they do not here.
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(mixins.RetrieveModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    """GET for the profile. DELETE for closing the account - requires the
    password again in the body (see DeleteAccountSerializer), since holding
    a valid token is not the same as being asked "are you sure"."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return DeleteAccountSerializer if self.request.method == "DELETE" else MeSerializer

    def perform_destroy(self, user):
        # Bookings keep their own history - Booking.user is SET_NULL, so a
        # closed account does not erase what was booked under it, only who
        # it belongs to. The Profile and the auth Token both cascade away
        # with the user themselves.
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        user.delete()


class ForgotPasswordView(APIView):
    """Always answers the same way regardless of whether the number is
    registered - see ForgotPasswordSerializer.issue_code. What actually
    happens to a real code is the one honest gap here: there is no SMS
    gateway wired in yet, so it is logged rather than delivered. Wiring one
    in is a few lines in this view; everything else in the flow already
    works end to end against that logged code."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset = serializer.issue_code()

        payload = {
            "detail": "If that phone number has an account, a reset code has been sent to it.",
        }
        if reset:
            log.info("Password reset code for user %s: %s", reset.user_id, reset.code)
            if settings.DEBUG:
                # Never included outside DEBUG - this is a development
                # convenience standing in for the SMS that would otherwise
                # carry the code, not a real delivery channel.
                payload["debug_code"] = reset.code
        return Response(payload)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed. Please log in again."})
