import random

from django.db.models import Case, IntegerField, Q, Value, When
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Collection, Product
from .serializers import CollectionSerializer, ProductSerializer

# Above this the CASE expression that holds a shuffled order gets unreasonable,
# and an aisle that long wants a real search rather than a shuffle anyway.
MAX_SHUFFLE = 1000


class ProductPagination(PageNumberPagination):
    """Lets the app ask for a page size.

    It loads an aisle ten at a time and fetches more as you scroll, rather
    than pulling every product and its photo up front.
    """

    page_size_query_param = "page_size"
    max_page_size = 100


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Products in a subcategory.

        GET /api/v1/products/?category=grocery
        GET /api/v1/products/aisles/?category=grocery
        GET /api/v1/products/?subcategory=vegetables-fruits
        GET /api/v1/products/?subcategory=vegetables-fruits&collection=seasonal
        GET /api/v1/products/?search=tomato
        GET /api/v1/products/?subcategory=vegetables-fruits&seed=4821&page_size=10
    """

    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    lookup_field = "slug"

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True, subcategory__is_active=True)
            .select_related("subcategory")
            .prefetch_related("collections")
            .order_by("sort_order", "name")
        )
        p = self.request.query_params
        if p.get("subcategory"):
            qs = qs.filter(subcategory__slug=p["subcategory"])
        # A whole section at once: Grocery opens on everything it sells rather
        # than on a list of aisles to pick between first.
        if p.get("category"):
            qs = qs.filter(subcategory__category__slug=p["category"])
        if p.get("collection"):
            qs = qs.filter(collections__slug=p["collection"])
        if search := p.get("search"):
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        # filtering across the m2m can repeat a row once per match
        qs = qs.distinct()

        if (seed := p.get("seed")) and seed.lstrip("-").isdigit():
            qs = self._shuffled(qs, int(seed))
        return qs

    @staticmethod
    def _shuffled(qs, seed):
        """The same aisle in a different order each visit.

        Seeded, not ORDER BY RAND(): the order has to be identical for page 1
        and page 2 of the same visit, or scrolling would repeat some products
        and never show others. The app picks a seed when the screen opens and
        sends it with every page.

        Done in Python because a seeded shuffle is not portable SQL - MySQL has
        RAND(seed), SQLite has nothing like it, and this project runs on both.
        """
        ids = list(qs.values_list("id", flat=True))
        if not ids or len(ids) > MAX_SHUFFLE:
            return qs
        random.Random(seed).shuffle(ids)
        order = Case(
            *[When(pk=pk, then=Value(i)) for i, pk in enumerate(ids)],
            output_field=IntegerField(),
        )
        return qs.filter(pk__in=ids).order_by(order)

    def get_object(self):
        # Slugs are unique per subcategory, not globally.
        qs = self.filter_queryset(self.get_queryset())
        return qs.get(slug=self.kwargs["slug"])

    @action(detail=False, methods=["get"])
    def aisles(self, request):
        """The aisles of a section that actually have something in them.

        Read from the products rather than from the catalog, so an aisle
        somebody created and never stocked does not become a chip that leads
        to an empty list.
        """
        qs = self.get_queryset()
        seen = {}
        for product in qs.select_related("subcategory").only(
            "id", "subcategory__name", "subcategory__slug",
            "subcategory__sort_order"
        ):
            sub = product.subcategory
            if sub is None:
                continue
            row = seen.setdefault(sub.slug, {
                "name": sub.name,
                "slug": sub.slug,
                "sort_order": sub.sort_order,
                "count": 0,
            })
            row["count"] += 1
        rows = sorted(seen.values(), key=lambda r: (r["sort_order"], r["name"]))
        for row in rows:
            row.pop("sort_order")
        return Response(rows)

    @action(detail=False, methods=["get"])
    def collections(self, request):
        """The filter chips, limited to those that actually have products in
        the subcategory being shown - an empty chip is just a dead end."""
        qs = Collection.objects.filter(is_active=True)
        if subcategory := request.query_params.get("subcategory"):
            qs = qs.filter(products__subcategory__slug=subcategory)
        if category := request.query_params.get("category"):
            qs = qs.filter(products__subcategory__category__slug=category)
        qs = qs.distinct()
        return Response(CollectionSerializer(qs, many=True).data)
