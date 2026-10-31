import pytest
from django.core.management import call_command

from apps.locations.models import City, District
from apps.locations.services import arabic_slug, load_locations, load_locations_file

pytestmark = pytest.mark.django_db

DATA = {
    "cities": [
        {
            "name_en": "Dammam",
            "name_ar": "الدمام",
            "region": "eastern",
            "center": [50.0888, 26.4207],
            "districts": [
                {"name_en": "Al Shulah", "name_ar": "الشعلة"},
                {"name_en": "Al Shati Al Gharbi", "name_ar": "الشاطئ الغربي"},
            ],
        }
    ]
}


def test_arabic_slug_joins_words():
    assert arabic_slug(" الشاطئ الغربي ") == "الشاطئ-الغربي"


def test_load_creates_cities_and_districts_with_slugs():
    result = load_locations(DATA)

    assert (result.cities_created, result.districts_created) == (1, 2)
    city = City.objects.get()
    assert (city.slug_en, city.slug_ar) == ("dammam", "الدمام")
    assert (city.center.x, city.center.y) == (50.0888, 26.4207)
    district = District.objects.get(slug_en="al-shati-al-gharbi")
    assert district.slug_ar == "الشاطئ-الغربي"
    assert district.city == city


def test_load_twice_updates_without_duplicates():
    load_locations(DATA)
    fixed = {
        "cities": [
            {
                **DATA["cities"][0],
                "districts": [{"name_en": "Al Shulah", "name_ar": "الشعلة الجديدة"}],
            }
        ]
    }

    result = load_locations(fixed)

    assert (result.cities_updated, result.districts_updated) == (1, 1)
    assert City.objects.count() == 1
    # Nothing is deleted: the district missing from the second file is still there.
    assert District.objects.count() == 2
    assert District.objects.get(slug_en="al-shulah").name_ar == "الشعلة الجديدة"


def test_bundled_file_loads_the_four_launch_cities():
    load_locations_file()

    assert set(City.objects.values_list("slug_en", flat=True)) == {
        "dammam",
        "khobar",
        "dhahran",
        "jubail",
    }
    for city in City.objects.all():
        assert city.districts.exists()
        assert city.center is not None


def test_seed_demo_command_is_repeatable():
    call_command("seed_demo")
    counts = (City.objects.count(), District.objects.count())
    call_command("seed_demo")
    assert (City.objects.count(), District.objects.count()) == counts
