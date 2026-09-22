from django.db.models import Count, Prefetch, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Category, Subcategory, Vertical
from .serializers import (
    CategoryDetailSerializer,
    CategorySerializer,
    SubcategorySerializer,
)


def _active_subcategories():
    return Prefetch(
        "subcategories",
        queryset=Subcategory.objects.filter(is_active=True),
        to_attr="active_subcategories",
    )


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Categories, optionally filtered by vertical.

        GET /api/v1/categories/?vertical=service
        GET /api/v1/categories/<vertical>/<slug>/
    """

    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = (
            Category.objects.filter(is_active=True)
            .annotate(
                subcategory_count=Count(
                    "subcategories", filter=Q(subcategories__is_active=True)
                )
            )
        )
        vertical = self.request.query_params.get("vertical")
        if vertical in Vertical.values:
            qs = qs.filter(vertical=vertical)
        if self.action == "retrieve":
            qs = qs.prefetch_related(_active_subcategories())
        return qs

    def get_serializer_class(self):
        return CategoryDetailSerializer if self.action == "retrieve" else CategorySerializer

    def get_object(self):
        # Slugs are unique per vertical, not globally, so a bare slug can be
        # ambiguous; the vertical query param disambiguates it.
        qs = self.filter_queryset(self.get_queryset())
        return qs.get(slug=self.kwargs["slug"])

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Whole catalog in one response - what the app loads on first run.

            GET /api/v1/categories/tree/?vertical=shop
        """
        qs = self.get_queryset().prefetch_related(_active_subcategories())
        data = CategoryDetailSerializer(qs, many=True, context={"request": request}).data
        return Response({"verticals": dict(Vertical.choices), "categories": data})


class SubcategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Flat subcategory list - backs search and the 'popular' row.

        GET /api/v1/subcategories/?search=wiring&vertical=service&popular=true
    """

    serializer_class = SubcategorySerializer

    def get_queryset(self):
        qs = Subcategory.objects.filter(
            is_active=True, category__is_active=True
        ).select_related("category")

        p = self.request.query_params
        if p.get("vertical") in Vertical.values:
            qs = qs.filter(category__vertical=p["vertical"])
        if p.get("category"):
            qs = qs.filter(category__slug=p["category"])
        if str(p.get("popular", "")).lower() in ("1", "true", "yes"):
            qs = qs.filter(is_popular=True)
        if search := p.get("search"):
            qs = qs.filter(
                Q(name__icontains=search) | Q(category__name__icontains=search)
            )
        return qs
