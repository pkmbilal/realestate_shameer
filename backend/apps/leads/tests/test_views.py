import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.leads.admin import LeadAdmin
from apps.leads.models import Lead
from apps.leads.views import CreateLeadView
from apps.listings.models import Listing
from apps.listings.tests.factories import ListingFactory

from .test_services import broker_listing

pytestmark = pytest.mark.django_db

URL = reverse("lead-create")


def post(data, user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client.post(URL, data, format="json")


def test_anonymous_whatsapp_click_logs_lead_and_returns_link(queued):
    listing = broker_listing()
    res = post({"listing": listing.reference, "channel": "whatsapp", "locale": "en"})
    assert res.status_code == 201
    assert res.data["whatsapp_url"].startswith("https://wa.me/")
    assert "tel_url" not in res.data
    lead = Lead.objects.get()
    assert lead.user is None and len(lead.client_hash) == 64


def test_call_click_returns_tel_link_and_records_user(queued):
    listing, user = broker_listing(), UserFactory(role=User.Role.BUYER)
    res = post({"listing": listing.reference, "channel": "call"}, user=user)
    assert res.status_code == 201
    assert res.data["tel_url"] == f"tel:{listing.broker.whatsapp}"
    assert Lead.objects.get().user == user


def test_form_lead_validation_errors():
    listing = broker_listing()
    res = post({"listing": listing.reference, "channel": "form", "name": "", "phone": "x"})
    assert res.status_code == 400
    assert res.data == {"code": "invalid", "fields": {"name": "required", "phone": "invalid_phone"}}


def test_form_lead_created(queued):
    listing = broker_listing()
    res = post(
        {
            "listing": listing.reference,
            "channel": "form",
            "name": "Sara",
            "phone": "0512345678",
            "message": "Is it available?",
        }
    )
    assert res.status_code == 201
    assert "whatsapp_url" not in res.data and "tel_url" not in res.data
    assert Lead.objects.get().phone == "+966512345678"


def test_inactive_listing_gives_404_and_no_number():
    listing = ListingFactory(status=Listing.Status.EXPIRED)
    res = post({"listing": listing.reference, "channel": "whatsapp"})
    assert res.status_code == 404
    assert res.data == {"code": "listing_not_active"}
    assert not Lead.objects.exists()


def test_unknown_channel_is_400():
    res = post({"listing": broker_listing().reference, "channel": "sms"})
    assert res.status_code == 400


def test_endpoint_is_rate_limited():
    assert CreateLeadView.throttle_scope == "lead_create"


def test_public_listing_does_not_expose_broker_number():
    listing = broker_listing()
    res = APIClient().get(reverse("listing-detail", args=[listing.reference]))
    assert res.status_code == 200
    assert listing.broker.whatsapp not in res.content.decode()


def test_my_listings_include_lead_count(queued):
    listing = broker_listing()
    post({"listing": listing.reference, "channel": "whatsapp"})
    post({"listing": listing.reference, "channel": "call"})
    client = APIClient()
    client.force_authenticate(listing.created_by)
    res = client.get(reverse("my-listings"))
    assert res.status_code == 200
    rows = res.data["results"] if isinstance(res.data, dict) else res.data
    assert rows[0]["lead_count"] == 2


def test_admin_shows_only_masked_phone():
    listing = broker_listing()
    lead = Lead.objects.create(listing=listing, channel="form", name="S", phone="+966512345678")
    admin = LeadAdmin(Lead, site)
    assert admin.masked_phone(lead) == "+9665•••••678"
    assert "phone" not in admin.fields and "client_hash" not in admin.fields
    request = RequestFactory().get("/")
    assert not admin.has_add_permission(request)
    assert not admin.has_delete_permission(request, lead)
