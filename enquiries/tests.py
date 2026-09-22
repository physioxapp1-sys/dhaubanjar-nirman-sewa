from django.core import mail
from django.test import TestCase, override_settings

from enquiries.models import Enquiry

VALID = {
    "name": "Sita Rai",
    "phone": "9841042319",
    "email": "sita@example.com",
    "message": "We want a quote for a two-storey house in Bhaktapur.",
    "project_type": "residential",
}


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ENQUIRY_NOTIFY_EMAILS=["info@dhaubanjarnirmansewa.com.np"],
)
class EnquiryAPITests(TestCase):
    url = "/api/v1/enquiries/"

    def test_valid_submission_is_stored(self):
        res = self.client.post(self.url, VALID, content_type="application/json")
        self.assertEqual(res.status_code, 201)
        e = Enquiry.objects.get()
        self.assertEqual(e.name, "Sita Rai")
        self.assertEqual(e.status, Enquiry.Status.NEW)
        self.assertEqual(e.source, Enquiry.Source.WEBSITE)

    def test_response_carries_a_message(self):
        res = self.client.post(self.url, VALID, content_type="application/json")
        self.assertIn("detail", res.json())

    def test_notification_email_sent(self):
        self.client.post(self.url, VALID, content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Sita Rai", mail.outbox[0].subject)
        self.assertIn("9841042319", mail.outbox[0].body)

    def test_missing_fields_rejected(self):
        res = self.client.post(self.url, {"name": "x"}, content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.json())
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_short_phone_rejected(self):
        bad = dict(VALID, phone="123")
        res = self.client.post(self.url, bad, content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.json())

    def test_email_is_optional(self):
        no_email = dict(VALID)
        no_email.pop("email")
        res = self.client.post(self.url, no_email, content_type="application/json")
        self.assertEqual(res.status_code, 201)

    def test_client_cannot_set_status(self):
        """Status is ours to manage; a client must not be able to forge it."""
        res = self.client.post(
            self.url, dict(VALID, status="won"), content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Enquiry.objects.get().status, Enquiry.Status.NEW)

    def test_ip_recorded_from_forwarded_header(self):
        self.client.post(
            self.url, VALID, content_type="application/json",
            HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
        )
        self.assertEqual(Enquiry.objects.get().ip_address, "203.0.113.9")

    def test_enquiry_survives_mail_failure(self):
        """A broken SMTP server must not lose the enquiry or error the visitor."""
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.dummy.NoSuchBackend"):
            res = self.client.post(self.url, VALID, content_type="application/json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Enquiry.objects.count(), 1)

    def test_enquiries_are_not_readable_over_the_api(self):
        self.client.post(self.url, VALID, content_type="application/json")
        self.assertEqual(self.client.get(self.url).status_code, 405)


class WebsiteTests(TestCase):
    def test_home_renders(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Dhaubanjar Nirman Sewa")
        self.assertContains(res, "9841042319")

    def test_home_points_the_form_at_the_api(self):
        res = self.client.get("/")
        self.assertContains(res, 'data-endpoint="/api/v1/enquiries/"')

    def test_robots_and_sitemap(self):
        self.assertEqual(self.client.get("/robots.txt").status_code, 200)
        self.assertContains(self.client.get("/sitemap.xml"), "dhaubanjarnirmansewa")

    def test_health(self):
        res = self.client.get("/api/v1/health/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["database"])
