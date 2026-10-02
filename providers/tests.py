from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from bookings.models import Booking
from catalog.models import Category, Subcategory, Vertical

from .models import Provider, Trade

User = get_user_model()


def make_provider(**kwargs):
    kwargs.setdefault("name", "Ram Thapa")
    kwargs.setdefault("trade", Trade.ELECTRICIAN)
    return Provider.objects.create(**kwargs)


def make_subcategory(name, category=None):
    category = category or Category.objects.create(
        vertical=Vertical.SERVICE, name="Electrical", slug="electrical"
    )
    return Subcategory.objects.create(category=category, name=name, slug=name.lower().replace(" ", "-"))


class ProviderModelTests(TestCase):
    def test_whatsapp_number_is_normalised_on_save(self):
        provider = make_provider(whatsapp_number="+977-9801234567")
        self.assertEqual(provider.whatsapp_number, "9801234567")

    def test_blank_whatsapp_number_is_left_alone(self):
        provider = make_provider(whatsapp_number="")
        self.assertEqual(provider.whatsapp_number, "")


class ProviderApiPermissionTests(TestCase):
    """The roster is staff-only - see ProviderViewSet's docstring."""

    def setUp(self):
        make_provider()

    def test_anonymous_request_is_rejected(self):
        res = self.client.get("/api/v1/providers/")
        self.assertIn(res.status_code, (401, 403))

    def test_non_staff_user_is_rejected(self):
        user = User.objects.create_user(username="customer", password="x")
        self.client.force_login(user)
        res = self.client.get("/api/v1/providers/")
        self.assertEqual(res.status_code, 403)

    def test_staff_user_can_list(self):
        staff = User.objects.create_user(username="dispatcher", password="x", is_staff=True)
        self.client.force_login(staff)
        res = self.client.get("/api/v1/providers/")
        self.assertEqual(res.status_code, 200)


class ProviderSearchAndProfileTests(TestCase):
    """Task 2: searching the roster by proven experience, and the computed
    profile (jobs_completed/total_earned/subcategories_worked) that makes
    that search possible. All of this reads existing Booking records -
    nothing here is a stored counter."""

    def setUp(self):
        self.staff = User.objects.create_user(username="dispatcher", password="x", is_staff=True)
        self.client.force_login(self.staff)

        self.wiring = make_subcategory("New Wiring")
        self.plumbing_category = Category.objects.create(
            vertical=Vertical.SERVICE, name="Plumbing", slug="plumbing"
        )
        self.pipe_fitting = make_subcategory("Pipe Fitting", category=self.plumbing_category)

        self.electrician = make_provider(name="Hari Gurung", trade=Trade.ELECTRICIAN)
        self.plumber = make_provider(name="Shyam Lama", trade=Trade.PLUMBER)

        # Two completed wiring jobs for the electrician, paid.
        Booking.objects.create(
            contact_name="A", contact_phone="9800000001", address="x",
            provider=self.electrician, subcategory=self.wiring,
            status=Booking.Status.COMPLETED, final_amount=Decimal("1000.00"),
        )
        Booking.objects.create(
            contact_name="B", contact_phone="9800000002", address="x",
            provider=self.electrician, subcategory=self.wiring,
            status=Booking.Status.COMPLETED, final_amount=Decimal("1500.00"),
        )
        # A still-open job must not count as completed work or earnings yet.
        Booking.objects.create(
            contact_name="C", contact_phone="9800000003", address="x",
            provider=self.electrician, subcategory=self.wiring,
            status=Booking.Status.PENDING, final_amount=None,
        )
        # The plumber has one completed job, in a different subcategory.
        Booking.objects.create(
            contact_name="D", contact_phone="9800000004", address="x",
            provider=self.plumber, subcategory=self.pipe_fitting,
            status=Booking.Status.COMPLETED, final_amount=Decimal("800.00"),
        )

    def _get(self, qs=""):
        return self.client.get(f"/api/v1/providers/{qs}")

    def _by_name(self, res, name):
        return next(p for p in res.json()["results"] if p["name"] == name) if "results" in res.json() \
            else next(p for p in res.json() if p["name"] == name)

    def test_jobs_completed_and_total_earned_ignore_open_bookings(self):
        res = self._get()
        electrician = self._by_name(res, "Hari Gurung")
        self.assertEqual(electrician["jobs_completed"], 2)
        self.assertEqual(Decimal(electrician["total_earned"]), Decimal("2500.00"))

    def test_subcategories_worked_lists_only_completed_work(self):
        res = self._get()
        electrician = self._by_name(res, "Hari Gurung")
        self.assertEqual(electrician["subcategories_worked"], ["New Wiring"])

    def test_provider_with_no_completed_bookings_reports_zero(self):
        make_provider(name="Fresh Face", trade=Trade.MASON)
        res = self._get()
        fresh = self._by_name(res, "Fresh Face")
        self.assertEqual(fresh["jobs_completed"], 0)
        self.assertEqual(Decimal(fresh["total_earned"]), Decimal("0"))
        self.assertEqual(fresh["subcategories_worked"], [])

    def test_worked_subcategory_filters_to_providers_with_completed_work_there(self):
        res = self._get("?worked_subcategory=new-wiring")
        names = {p["name"] for p in res.json()} if isinstance(res.json(), list) \
            else {p["name"] for p in res.json()["results"]}
        self.assertEqual(names, {"Hari Gurung"})

    def test_worked_subcategory_does_not_corrupt_jobs_completed_or_total_earned(self):
        """The flagged ORM concern: combining the annotate(Count/Sum, filter=
        completed) with a second .filter() on the same bookings relation
        (for worked_subcategory) must not turn the conditional aggregate
        into a join that double-counts or narrows it to just the matched
        rows. The electrician's two completed wiring jobs should still both
        be counted even though the filter is scoped to that subcategory."""
        res = self._get("?worked_subcategory=new-wiring")
        electrician = self._by_name(res, "Hari Gurung")
        self.assertEqual(electrician["jobs_completed"], 2)
        self.assertEqual(Decimal(electrician["total_earned"]), Decimal("2500.00"))

    def test_min_jobs_completed_filter(self):
        res = self._get("?min_jobs_completed=2")
        names = {p["name"] for p in res.json()} if isinstance(res.json(), list) \
            else {p["name"] for p in res.json()["results"]}
        self.assertEqual(names, {"Hari Gurung"})

    def test_ordering_by_total_earned_descending(self):
        res = self._get("?ordering=-total_earned")
        data = res.json() if isinstance(res.json(), list) else res.json()["results"]
        names = [p["name"] for p in data]
        self.assertEqual(names.index("Hari Gurung") < names.index("Shyam Lama"), True)

    def test_trade_filter(self):
        res = self._get("?trade=plumber")
        names = {p["name"] for p in res.json()} if isinstance(res.json(), list) \
            else {p["name"] for p in res.json()["results"]}
        self.assertEqual(names, {"Shyam Lama"})


class ProviderManagerTests(TestCase):
    """A contractor's crew: who reports to whom, and the ?manager= filter
    that lets staff pull up one contractor's workers."""

    def setUp(self):
        self.staff = User.objects.create_user(username="dispatcher", password="x", is_staff=True)
        self.client.force_login(self.staff)
        self.contractor = make_provider(name="Bikram Contractor", trade=Trade.CONTRACTOR)
        self.worker1 = make_provider(name="Hari Gurung", trade=Trade.MASON, manager=self.contractor)
        self.worker2 = make_provider(name="Shyam Lama", trade=Trade.PAINTER, manager=self.contractor)
        self.unrelated = make_provider(name="Gita Rai", trade=Trade.CLEANER)

    def _names(self, res):
        data = res.json()
        rows = data if isinstance(data, list) else data["results"]
        return {p["name"] for p in rows}

    def test_manager_filter_returns_only_that_contractors_workers(self):
        res = self.client.get(f"/api/v1/providers/?manager={self.contractor.slug}")
        self.assertEqual(self._names(res), {"Hari Gurung", "Shyam Lama"})

    def test_providers_without_a_manager_are_unaffected(self):
        res = self.client.get("/api/v1/providers/")
        self.assertEqual(
            self._names(res),
            {"Bikram Contractor", "Hari Gurung", "Shyam Lama", "Gita Rai"},
        )

    def test_worker_row_reports_its_manager_slug(self):
        res = self.client.get(f"/api/v1/providers/?manager={self.contractor.slug}")
        data = res.json()
        rows = data if isinstance(data, list) else data["results"]
        worker = next(p for p in rows if p["name"] == "Hari Gurung")
        self.assertEqual(worker["manager_slug"], self.contractor.slug)

    def test_contractor_row_has_no_manager_slug(self):
        res = self.client.get("/api/v1/providers/")
        rows = res.json() if isinstance(res.json(), list) else res.json()["results"]
        contractor = next(p for p in rows if p["name"] == "Bikram Contractor")
        self.assertIsNone(contractor["manager_slug"])

    def test_deleting_a_contractor_leaves_workers_in_place_unmanaged(self):
        """manager is SET_NULL - losing the contractor record must not take
        their crew's own Provider rows down with it."""
        self.contractor.delete()
        self.worker1.refresh_from_db()
        self.assertIsNone(self.worker1.manager)
