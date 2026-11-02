import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.listings import services
from apps.listings.models import Favourite

from .factories import ListingFactory
from .test_views import make_active

pytestmark = pytest.mark.django_db


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def buyer():
    return UserFactory(role=User.Role.BUYER)


def fav_url(listing):
    return reverse("listing-favourite", args=[listing.reference])


# --- Services ----------------------------------------------------------------------------


def test_add_favourite_is_idempotent():
    user, listing = buyer(), make_active()
    first = services.add_favourite(user, listing)
    second = services.add_favourite(user, listing)
    assert first.pk == second.pk
    assert Favourite.objects.count() == 1


def test_cannot_favourite_an_inactive_listing():
    with pytest.raises(services.ListingError) as exc:
        services.add_favourite(buyer(), ListingFactory())
    assert exc.value.code == "not_active"


def test_favourite_listings_hides_listings_that_stopped_being_active():
    user = buyer()
    kept, gone = make_active(), make_active()
    services.add_favourite(user, kept)
    services.add_favourite(user, gone)
    services.archive(gone, gone.created_by)
    assert [x.reference for x in services.favourite_listings(user)] == [kept.reference]
    assert services.favourite_references(user) == [kept.reference]


def test_favourites_are_per_user():
    me, other = buyer(), buyer()
    services.add_favourite(other, make_active())
    assert list(services.favourite_listings(me)) == []


def test_favourite_listings_newest_saved_first():
    user = buyer()
    first, second = make_active(), make_active()
    services.add_favourite(user, first)
    services.add_favourite(user, second)
    assert [x.reference for x in services.favourite_listings(user)] == [
        second.reference,
        first.reference,
    ]


# --- Endpoints ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,name", [("get", "favourite-list"), ("get", "favourite-ids")])
def test_favourite_lists_need_login(method, name):
    assert getattr(client_for(), method)(reverse(name)).status_code == 401


def test_toggle_needs_login():
    listing = make_active()
    assert client_for().put(fav_url(listing)).status_code == 401
    assert client_for().delete(fav_url(listing)).status_code == 401


def test_save_list_and_remove_via_api():
    user, listing = buyer(), make_active()
    api = client_for(user)

    assert api.put(fav_url(listing)).status_code == 204
    assert api.put(fav_url(listing)).status_code == 204  # repeat is fine

    assert api.get(reverse("favourite-ids")).data == {"references": [listing.reference]}
    listed = api.get(reverse("favourite-list")).data
    assert listed["count"] == 1
    assert listed["results"][0]["reference"] == listing.reference

    assert api.delete(fav_url(listing)).status_code == 204
    assert api.delete(fav_url(listing)).status_code == 204
    assert api.get(reverse("favourite-ids")).data == {"references": []}


def test_cannot_save_a_draft_via_api():
    response = client_for(buyer()).put(fav_url(ListingFactory()))
    assert response.status_code == 404
