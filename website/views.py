from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET



@require_GET
def home(request):
    """The marketing site.

    The Pakka Homes catalog deliberately does not feed this page: it is a
    different business (a services marketplace) from the construction firm
    this site represents. The catalog is served to the app over /api/v1/.
    """
    return render(request, "website/home.html")


@require_GET
def robots(request):
    from django.shortcuts import render as _render

    return _render(request, "website/robots.txt", content_type="text/plain")


@require_GET
def sitemap(request):
    return render(request, "website/sitemap.xml", content_type="application/xml")


@require_GET
def health(request):
    """Cheap liveness probe that also proves the database is reachable."""
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok},
                        status=200 if db_ok else 503)
