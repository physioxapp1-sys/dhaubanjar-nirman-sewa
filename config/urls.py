from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import CategoryViewSet, SubcategoryViewSet
from enquiries.views import EnquiryCreateView
from website import views as website_views

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubcategoryViewSet, basename="subcategory")

api_v1 = [
    path("", include(router.urls)),
    path("enquiries/", EnquiryCreateView.as_view(), name="enquiry-create"),
    path("health/", website_views.health, name="health"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "api"), namespace="api")),

    # Public website
    path("", website_views.home, name="home"),
    path("robots.txt", website_views.robots, name="robots"),
    path("sitemap.xml", website_views.sitemap, name="sitemap"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # WhiteNoise handles /static/, but not /media/ - and Passenger serves
    # neither. Uploaded catalog images would 404 without this. Django's own
    # file serving is slower than Apache's and is not meant for heavy traffic;
    # at this scale (a brochure site plus a few hundred catalog images) that
    # is an acceptable trade for not hand-editing Apache config on shared
    # hosting. Move /media/ to an Apache alias if image traffic ever grows.
    from django.views.static import serve as _serve
    from django.urls import re_path

    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", _serve, {"document_root": settings.MEDIA_ROOT}),
    ]

admin.site.site_header = "Dhaubanjar Nirman Sewa"
admin.site.site_title = "Dhaubanjar admin"
admin.site.index_title = "Website & Pakka Homes catalog"
