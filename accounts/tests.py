import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import PasswordResetCode, Profile
from bookings.models import Booking

User = get_user_model()


def post(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


class ThrottledTestCase(TestCase):
    """DRF's ScopedRateThrottle keeps its request history in Django's cache,
    which (with the default LocMemCache) is not reset between test methods
    or test classes the way the database is. Without this, a handful of
    test methods hitting the same real, tight rate (auth: 10/hour,
    password_reset: 5/hour) can trip a 429 against each other in a way that
    has nothing to do with what each test actually checks.

    Overriding REST_FRAMEWORK via @override_settings does not help here:
    SimpleRateThrottle.THROTTLE_RATES is bound once from api_settings at
    import time, not re-read per request, so a settings override after
    import never reaches it. Clearing the cache is what actually resets the
    counters, and it means every test below genuinely exercises the real,
    production throttle rates rather than an inflated test-only one.
    """

    def setUp(self):
        cache.clear()


class RegisterLoginLogoutTests(ThrottledTestCase):
    """Baseline coverage for the existing endpoints - there was no test file
    for this app before, so these are backfilled alongside the new work
    rather than leaving register/login/logout unverified."""

    def test_register_creates_user_and_profile_and_returns_a_token(self):
        res = post(self.client, "/api/v1/auth/register/", {
            "phone": "9841042319", "password": "a-strong-password-1", "full_name": "Sita Rai",
        })
        self.assertEqual(res.status_code, 201)
        self.assertIn("token", res.json())
        self.assertEqual(Profile.objects.get().phone, "9841042319")

    def test_register_rejects_duplicate_phone(self):
        post(self.client, "/api/v1/auth/register/",
             {"phone": "9841042319", "password": "a-strong-password-1"})
        res = post(self.client, "/api/v1/auth/register/",
                   {"phone": "9841042319", "password": "another-password-2"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_login_with_correct_password(self):
        post(self.client, "/api/v1/auth/register/",
             {"phone": "9841042319", "password": "a-strong-password-1"})
        res = post(self.client, "/api/v1/auth/login/",
                   {"phone": "9841042319", "password": "a-strong-password-1"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())

    def test_login_with_wrong_password_rejected(self):
        post(self.client, "/api/v1/auth/register/",
             {"phone": "9841042319", "password": "a-strong-password-1"})
        res = post(self.client, "/api/v1/auth/login/",
                   {"phone": "9841042319", "password": "wrong"})
        self.assertEqual(res.status_code, 400)

    def test_logout_removes_the_token(self):
        reg = post(self.client, "/api/v1/auth/register/",
                   {"phone": "9841042319", "password": "a-strong-password-1"})
        token = reg.json()["token"]
        res = self.client.post("/api/v1/auth/logout/", HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(res.status_code, 204)
        from rest_framework.authtoken.models import Token
        self.assertFalse(Token.objects.filter(key=token).exists())


class DeleteAccountTests(ThrottledTestCase):
    def setUp(self):
        super().setUp()
        reg = post(self.client, "/api/v1/auth/register/",
                  {"phone": "9841042319", "password": "a-strong-password-1", "full_name": "Sita Rai"})
        self.token = reg.json()["token"]
        self.user = User.objects.get()
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token}"}

    def test_delete_requires_authentication(self):
        res = self.client.delete("/api/v1/auth/me/",
                                  data=json.dumps({"password": "a-strong-password-1"}),
                                  content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_delete_with_wrong_password_is_rejected_and_nothing_is_deleted(self):
        res = self.client.delete("/api/v1/auth/me/",
                                  data=json.dumps({"password": "wrong-password"}),
                                  content_type="application/json", **self.auth)
        self.assertEqual(res.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_with_correct_password_removes_user_profile_and_token(self):
        res = self.client.delete("/api/v1/auth/me/",
                                  data=json.dumps({"password": "a-strong-password-1"}),
                                  content_type="application/json", **self.auth)
        self.assertEqual(res.status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Profile.objects.exists())
        from rest_framework.authtoken.models import Token
        self.assertFalse(Token.objects.filter(key=self.token).exists())

    def test_deleting_account_preserves_booking_history_without_the_owner(self):
        """Booking.user is SET_NULL by design - closing an account must not
        take the booking record (and its financial history) with it."""
        booking = Booking.objects.create(
            user=self.user, contact_name="Sita Rai", contact_phone="9841042319",
            address="Baneshwor", final_amount="1500.00",
        )
        self.client.delete("/api/v1/auth/me/",
                           data=json.dumps({"password": "a-strong-password-1"}),
                           content_type="application/json", **self.auth)
        booking.refresh_from_db()
        self.assertIsNone(booking.user)
        self.assertEqual(str(booking.final_amount), "1500.00")


class ForgotPasswordTests(ThrottledTestCase):
    def setUp(self):
        super().setUp()
        post(self.client, "/api/v1/auth/register/",
             {"phone": "9841042319", "password": "a-strong-password-1"})
        self.user = User.objects.get()

    def test_unknown_phone_gets_the_same_generic_response_and_issues_no_code(self):
        res = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9800000000"})
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("debug_code", res.json())
        self.assertEqual(PasswordResetCode.objects.count(), 0)

    def test_known_phone_issues_a_code(self):
        res = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9841042319"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PasswordResetCode.objects.filter(user=self.user).count(), 1)

    @override_settings(DEBUG=True)
    def test_debug_code_is_returned_only_when_debug_is_on(self):
        res = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9841042319"})
        code = PasswordResetCode.objects.get()
        self.assertEqual(res.json()["debug_code"], code.code)

    @override_settings(DEBUG=False)
    def test_debug_code_is_never_returned_outside_debug(self):
        res = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9841042319"})
        self.assertNotIn("debug_code", res.json())

    def test_phone_formatting_does_not_matter(self):
        """977-9841042319 and 9841042319 must reach the same account - same
        normalisation RegisterSerializer already relies on."""
        res = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "+977-9841042319"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PasswordResetCode.objects.filter(user=self.user).count(), 1)


class ResetPasswordTests(ThrottledTestCase):
    def setUp(self):
        super().setUp()
        reg = post(self.client, "/api/v1/auth/register/",
                  {"phone": "9841042319", "password": "original-password-1"})
        self.old_token = reg.json()["token"]
        self.user = User.objects.get()

    def _issue_code(self):
        post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9841042319"})
        return PasswordResetCode.objects.get()

    def test_correct_code_changes_the_password(self):
        reset = self._issue_code()
        res = post(self.client, "/api/v1/auth/password/reset/", {
            "phone": "9841042319", "code": reset.code, "new_password": "brand-new-password-2",
        })
        self.assertEqual(res.status_code, 200)
        login = post(self.client, "/api/v1/auth/login/",
                    {"phone": "9841042319", "password": "brand-new-password-2"})
        self.assertEqual(login.status_code, 200)

    def test_wrong_code_is_rejected(self):
        self._issue_code()
        res = post(self.client, "/api/v1/auth/password/reset/", {
            "phone": "9841042319", "code": "000000", "new_password": "brand-new-password-2",
        })
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("original-password-1"))

    def test_code_cannot_be_used_twice(self):
        reset = self._issue_code()
        first = post(self.client, "/api/v1/auth/password/reset/", {
            "phone": "9841042319", "code": reset.code, "new_password": "brand-new-password-2",
        })
        self.assertEqual(first.status_code, 200)
        second = post(self.client, "/api/v1/auth/password/reset/", {
            "phone": "9841042319", "code": reset.code, "new_password": "yet-another-password-3",
        })
        self.assertEqual(second.status_code, 400)

    def test_expired_code_is_rejected(self):
        reset = self._issue_code()
        reset.created_at = timezone.now() - PasswordResetCode.VALID_FOR - timezone.timedelta(minutes=1)
        reset.save(update_fields=["created_at"])
        res = post(self.client, "/api/v1/auth/password/reset/", {
            "phone": "9841042319", "code": reset.code, "new_password": "brand-new-password-2",
        })
        self.assertEqual(res.status_code, 400)

    def test_reset_invalidates_the_old_token(self):
        reset = self._issue_code()
        post(self.client, "/api/v1/auth/password/reset/", {
            "phone": "9841042319", "code": reset.code, "new_password": "brand-new-password-2",
        })
        res = self.client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Token {self.old_token}")
        self.assertEqual(res.status_code, 401)


class ThrottleScopeTests(ThrottledTestCase):
    def test_password_reset_endpoint_is_throttled_at_the_real_configured_rate(self):
        # settings.py sets password_reset to 5/hour - six requests from a
        # clean cache should let the first five through and stop the sixth.
        for _ in range(5):
            res = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9841042319"})
            self.assertNotEqual(res.status_code, 429)
        sixth = post(self.client, "/api/v1/auth/password/forgot/", {"phone": "9841042319"})
        self.assertEqual(sixth.status_code, 429)
