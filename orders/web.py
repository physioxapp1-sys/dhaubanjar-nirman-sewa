"""The order tracking page on the website.

Someone who ordered through the app gets a reference. This is where that
reference turns into "where is it" without installing anything - a link that
can go in an SMS, or be read out over the phone.

It is deliberately not part of the marketing site's navigation: that site is
the construction firm, this is Pakka Homes, and they are different businesses
sharing a domain and a database.
"""
from django import forms
from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Order

# A reference alone is not a secret - it travels in SMS, gets forwarded, gets
# read aloud. The phone number is what proves the order is yours, and these
# limits are what stop someone trying a list of numbers against one reference.
MAX_ATTEMPTS = 12
ATTEMPT_WINDOW = 60 * 30  # seconds


class TrackOrderForm(forms.Form):
    reference = forms.CharField(
        label="Order reference",
        max_length=12,
        strip=True,
        widget=forms.TextInput(
            attrs={"placeholder": "PO-XXXXXX", "autocapitalize": "characters",
                   "autocomplete": "off", "spellcheck": "false"}
        ),
    )
    phone = forms.CharField(
        label="Phone number you ordered with",
        max_length=32,
        strip=True,
        widget=forms.TextInput(
            attrs={"placeholder": "98XXXXXXXX", "inputmode": "tel",
                   "autocomplete": "tel"}
        ),
    )

    def clean_reference(self):
        return self.cleaned_data["reference"].upper()

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if len(_digits(phone)) < 7:
            raise forms.ValidationError("Enter the full phone number.")
        return phone


def _digits(value):
    return "".join(ch for ch in value if ch.isdigit())


def _client_ip(request):
    # Apache/LiteSpeed sits in front, so the socket address is the proxy.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@require_http_methods(["GET", "POST"])
def track_order(request):
    """Look up one order by reference and phone.

    A wrong phone and a reference that does not exist give the same answer on
    purpose. Saying "that reference exists but the number is wrong" would turn
    the form into a way of checking which references are real.
    """
    order = None
    not_found = False
    throttled = False

    if request.method == "POST":
        form = TrackOrderForm(request.POST)
        key = "track-attempts:%s" % _client_ip(request)
        attempts = cache.get(key, 0)
        if attempts >= MAX_ATTEMPTS:
            throttled = True
        elif form.is_valid():
            # Counts every lookup, not just the failures: a script working
            # through references would otherwise get a free run on the ones
            # that happen to hit.
            cache.set(key, attempts + 1, ATTEMPT_WINDOW)
            order = _find(form.cleaned_data["reference"], form.cleaned_data["phone"])
            not_found = order is None
    else:
        # A tracking link can carry the reference so only the phone is left to
        # type: /track/?ref=PO-XQ3DUH
        reference = request.GET.get("ref", "").strip().upper()
        form = TrackOrderForm(initial={"reference": reference} if reference else None)

    return render(
        request,
        "orders/track.html",
        {
            "form": form,
            "order": order,
            "steps": _steps(order) if order else None,
            "not_found": not_found,
            "throttled": throttled,
        },
    )


def _steps(order):
    """The timeline, annotated for drawing.

    Which step is "now" and whether the line below a dot should be green are
    both questions about neighbouring steps, and a Django template is a poor
    place to ask those.
    """
    steps = order.timeline()
    last_done = max((i for i, s in enumerate(steps) if s["done"]), default=-1)
    return [
        {
            **step,
            "current": i == last_done,
            "bar_done": i + 1 < len(steps) and steps[i + 1]["done"],
        }
        for i, step in enumerate(steps)
    ]


def _find(reference, phone):
    digits = _digits(phone)
    if len(digits) < 7:
        return None
    return (
        Order.objects.filter(
            reference=reference, contact_phone__endswith=digits[-7:]
        )
        .select_related("delivery_partner")
        .prefetch_related("items")
        .first()
    )
