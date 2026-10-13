from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Collection, Product
from .serializers import CollectionSerializer, ProductSerializer


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Products in a subcategory.

        GET /api/v1/products/?subcategory=vegetables-fruits
        GET /api/v1/products/?subcategory=vegetables-fruits&collection=seasonal
        GET /api/v1/products/?search=tomato
    """

    serializer_class = ProductSerializer
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
        if p.get("collection"):
            qs = qs.filter(collections__slug=p["collection"])
        if search := p.get("search"):
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        # filtering across the m2m can repeat a row once per match
        return qs.distinct()

    def get_object(self):
        # Slugs are unique per subcategory, not globally.
        qs = self.filter_queryset(self.get_queryset())
        return qs.get(slug=self.kwargs["slug"])

    @action(detail=False, methods=["get"])
    def collections(self, request):
        """The filter chips, limited to those that actually have products in
        the subcategory being shown - an empty chip is just a dead end."""
        qs = Collection.objects.filter(is_active=True)
        if subcategory := request.query_params.get("subcategory"):
            qs = qs.filter(products__subcategory__slug=subcategory)
        qs = qs.distinct()
        return Response(CollectionSerializer(qs, many=True).data)
