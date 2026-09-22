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

admin.site.site_header = "Dhaubanjar Nirman Sewa"
admin.site.site_title = "Dhaubanjar admin"
admin.site.index_title = "Website & Pakka Homes catalog"
