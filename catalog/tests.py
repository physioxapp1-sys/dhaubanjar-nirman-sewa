from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Subcategory, Vertical


class CatalogModelTests(TestCase):
    def test_slug_autofills_from_name(self):
        c = Category.objects.create(vertical=Vertical.SERVICE, name="Appliance Repair")
        self.assertEqual(c.slug, "appliance-repair")

    def test_same_name_allowed_in_different_verticals(self):
        """'Electrical' is both a service and a shop category in the sheet."""
        Category.objects.create(vertical=Vertical.SERVICE, name="Electrical")
        Category.objects.create(vertical=Vertical.SHOP, name="Electrical")
        self.assertEqual(Category.objects.filter(name="Electrical").count(), 2)

    def test_duplicate_name_within_vertical_rejected(self):
        Category.objects.create(vertical=Vertical.SHOP, name="Steel")
        with self.assertRaises(Exception):
            Category.objects.create(vertical=Vertical.SHOP, name="Steel")

    def test_same_subcategory_name_under_two_categories(self):
        """'Boundary Wall' is legitimately both Construction and Mason work."""
        a = Category.objects.create(vertical=Vertical.SERVICE, name="Construction")
        b = Category.objects.create(vertical=Vertical.SERVICE, name="Mason")
        Subcategory.objects.create(category=a, name="Boundary Wall")
        Subcategory.objects.create(category=b, name="Boundary Wall")
        self.assertEqual(Subcategory.objects.filter(name="Boundary Wall").count(), 2)

    def test_display_rate_falls_back_to_on_request(self):
        c = Category.objects.create(vertical=Vertical.RENTAL, name="Ladders")
        s = Subcategory.objects.create(category=c, name="Step Ladder")
        self.assertEqual(s.display_rate, "On request")
        s.rate, s.rate_unit = 1500, "day"
        self.assertIn("1,500", s.display_rate)


class CatalogAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.service = Category.objects.create(
            vertical=Vertical.SERVICE, name="Plumbing", sort_order=0
        )
        cls.shop = Category.objects.create(
            vertical=Vertical.SHOP, name="Cement", sort_order=0
        )
        Subcategory.objects.create(
            category=cls.service, name="Leakage Repair", is_popular=True
        )
        Subcategory.objects.create(category=cls.service, name="Pipe Installation")
        Subcategory.objects.create(category=cls.service, name="Hidden", is_active=False)
        Subcategory.objects.create(category=cls.shop, name="OPC Cement")

    def test_category_list(self):
        res = self.client.get("/api/v1/categories/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 2)

    def test_filter_by_vertical(self):
        res = self.client.get("/api/v1/categories/?vertical=shop")
        names = [c["name"] for c in res.json()["results"]]
        self.assertEqual(names, ["Cement"])

    def test_subcategory_count_excludes_inactive(self):
        res = self.client.get("/api/v1/categories/?vertical=service")
        self.assertEqual(res.json()["results"][0]["subcategory_count"], 2)

    def test_tree_returns_nested_subcategories(self):
        res = self.client.get("/api/v1/categories/tree/")
        body = res.json()
        self.assertEqual(res.status_code, 200)
        self.assertIn("verticals", body)
        plumbing = next(c for c in body["categories"] if c["name"] == "Plumbing")
        names = [s["name"] for s in plumbing["subcategories"]]
        self.assertEqual(names, ["Leakage Repair", "Pipe Installation"])
        self.assertNotIn("Hidden", names)

    def test_search(self):
        res = self.client.get("/api/v1/subcategories/?search=leak")
        self.assertEqual(res.json()["count"], 1)

    def test_popular_filter(self):
        res = self.client.get("/api/v1/subcategories/?popular=true")
        self.assertEqual(res.json()["count"], 1)

    def test_inactive_category_hidden(self):
        Category.objects.filter(pk=self.shop.pk).update(is_active=False)
        res = self.client.get("/api/v1/categories/")
        self.assertEqual(res.json()["count"], 1)

    def test_tree_query_count_is_flat(self):
        """The whole catalog must not cost one query per category."""
        with self.assertNumQueries(2):  # categories + prefetched subcategories
            self.client.get("/api/v1/categories/tree/")
