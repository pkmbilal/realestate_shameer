"""Loading cities and districts from the JSON files in data/."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils.text import slugify

from .models import City, District

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATA_FILE = DATA_DIR / "eastern_province.json"


@dataclass
class LoadResult:
    cities_created: int = 0
    cities_updated: int = 0
    districts_created: int = 0
    districts_updated: int = 0


def arabic_slug(name: str) -> str:
    """'الشاطئ الغربي' -> 'الشاطئ-الغربي'. Keeps Arabic letters, joins words with hyphens."""
    return re.sub(r"[\s_]+", "-", name.strip())


def _point(coords):
    return Point(coords[0], coords[1], srid=4326) if coords else None


@transaction.atomic
def load_locations(data: dict) -> LoadResult:
    """Create or update cities and districts. Safe to run again; it never deletes anything.

    Rows are matched by English slug, so correcting a name updates the existing row.
    """
    result = LoadResult()
    for city_data in data["cities"]:
        city, created = City.objects.update_or_create(
            slug_en=city_data.get("slug_en") or slugify(city_data["name_en"]),
            defaults={
                "name_ar": city_data["name_ar"],
                "name_en": city_data["name_en"],
                "slug_ar": city_data.get("slug_ar") or arabic_slug(city_data["name_ar"]),
                "region": city_data["region"],
                "center": _point(city_data.get("center")),
                "sort_order": city_data.get("sort_order", 0),
            },
        )
        if created:
            result.cities_created += 1
        else:
            result.cities_updated += 1

        for district_data in city_data.get("districts", []):
            _, created = District.objects.update_or_create(
                city=city,
                slug_en=district_data.get("slug_en") or slugify(district_data["name_en"]),
                defaults={
                    "name_ar": district_data["name_ar"],
                    "name_en": district_data["name_en"],
                    "slug_ar": district_data.get("slug_ar")
                    or arabic_slug(district_data["name_ar"]),
                    "center": _point(district_data.get("center")),
                },
            )
            if created:
                result.districts_created += 1
            else:
                result.districts_updated += 1
    return result


def load_locations_file(path: Path = DEFAULT_DATA_FILE) -> LoadResult:
    return load_locations(json.loads(Path(path).read_text(encoding="utf-8")))
