"""Data for SEO area pages and sitemaps.

An "area" is purpose × property type, optionally narrowed to a city and then a district,
e.g. rent / apartment / Dammam / Al Shulah. Only areas that have active listings are returned.
"""

from collections import defaultdict

from django.core.paginator import Paginator
from django.db.models import Count

from apps.listings.models import Listing
from apps.locations.models import City, District

SITEMAP_CHUNK = 5000


def _place(obj) -> dict:
    return {
        "slug_en": obj.slug_en,
        "slug_ar": obj.slug_ar,
        "name_en": obj.name_en,
        "name_ar": obj.name_ar,
    }


def area_counts() -> list[dict]:
    """Active-listing counts at three levels: purpose+type, +city, +city+district.

    Listings in an inactive city are left out. Listings in an inactive district (or with no
    district) still count for their city, but get no district row.
    """
    grouped = (
        Listing.objects.filter(status=Listing.Status.ACTIVE, city__is_active=True)
        .values("purpose", "property_type", "city_id", "district_id")
        .annotate(n=Count("id"))
        .order_by()
    )
    by_type: dict[tuple, int] = defaultdict(int)
    by_city: dict[tuple, int] = defaultdict(int)
    by_district: dict[tuple, int] = defaultdict(int)
    for row in grouped:
        kind = (row["purpose"], row["property_type"])
        by_type[kind] += row["n"]
        by_city[(*kind, row["city_id"])] += row["n"]
        if row["district_id"]:
            by_district[(*kind, row["city_id"], row["district_id"])] += row["n"]

    cities = {c.pk: c for c in City.objects.filter(pk__in={k[2] for k in by_city})}
    districts = {
        d.pk: d for d in District.objects.filter(pk__in={k[3] for k in by_district}, is_active=True)
    }

    rows = [
        {"purpose": p, "type": t, "city": None, "district": None, "count": n}
        for (p, t), n in by_type.items()
    ]
    rows += [
        {"purpose": p, "type": t, "city": _place(cities[c]), "district": None, "count": n}
        for (p, t, c), n in by_city.items()
    ]
    rows += [
        {
            "purpose": p,
            "type": t,
            "city": _place(cities[c]),
            "district": _place(districts[d]),
            "count": n,
        }
        for (p, t, c, d), n in by_district.items()
        if d in districts
    ]
    rows.sort(key=lambda r: (r["purpose"], r["type"], -r["count"]))
    return rows


def sitemap_listings(page: int) -> dict:
    """One chunk of active listings for listings-N.xml, plus the total count."""
    qs = (
        Listing.objects.filter(status=Listing.Status.ACTIVE)
        .order_by("id")
        .values("reference", "updated_at")
    )
    paginator = Paginator(qs, SITEMAP_CHUNK)
    if 1 <= page <= paginator.num_pages and paginator.count:
        results = list(paginator.page(page).object_list)
    else:
        results = []
    return {
        "count": paginator.count,
        "chunk_size": SITEMAP_CHUNK,
        "results": [
            {"reference": r["reference"], "updated_at": r["updated_at"].isoformat()}
            for r in results
        ],
    }
