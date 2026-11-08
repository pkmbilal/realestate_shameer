"""Three placeholder credit packages (prices include 15% VAT).

Final packages are set by the owner in the admin after the broker pilot (CLAUDE.md §11).
"""

from django.db import migrations

PACKAGES = [
    # name_ar, name_en, credits, price in halalas, sort order
    ("باقة أساسية", "Starter", 100, 10000, 1),
    ("باقة متوسطة", "Standard", 300, 27000, 2),
    ("باقة احترافية", "Pro", 1000, 80000, 3),
]


def seed(apps, schema_editor):
    TopUpPackage = apps.get_model("payments", "TopUpPackage")
    if TopUpPackage.objects.exists():
        return
    for name_ar, name_en, credits, price, order in PACKAGES:
        TopUpPackage.objects.create(
            name_ar=name_ar,
            name_en=name_en,
            credits=credits,
            price_halalas=price,
            sort_order=order,
        )


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
