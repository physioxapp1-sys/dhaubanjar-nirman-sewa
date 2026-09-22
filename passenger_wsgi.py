"""
Entry point for cPanel's "Setup Python App" (Phusion Passenger).

Passenger imports `application` from this file. Point the app's Application
Root at this repository and its Application URL at the domain, then use
"Restart" in cPanel - or `touch tmp/restart.txt` - to reload after a deploy.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
