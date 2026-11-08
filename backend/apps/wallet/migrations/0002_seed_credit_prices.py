"""Create one price row per paid action, all free (0 credits).

Final prices are set by the owner in the admin after the broker pilot (CLAUDE.md §11).
"""

from django.db import migrations

DEFAULTS = {"post": 0, "refresh": 0, "feature": 7}  # action -> days (feature lasts 7 days)


def seed(apps, schema_editor):
    CreditPrice = apps.get_model("wallet", "CreditPrice")
    for action, days in DEFAULTS.items():
        CreditPrice.objects.get_or_create(action=action, defaults={"credits": 0, "days": days})


class Migration(migrations.Migration):
    dependencies = [("wallet", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
