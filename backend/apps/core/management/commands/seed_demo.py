from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.listings.seed import seed_demo_listings


class Command(BaseCommand):
    help = "Fill a local database with launch data and demo content (safe to run again)."

    def handle(self, *args, **options):
        call_command("seed_locations", stdout=self.stdout)
        call_command("seed_amenities", stdout=self.stdout)
        if settings.INTEGRATIONS_MODE != "mock":
            raise CommandError("Demo listings need INTEGRATIONS_MODE=mock (fake REGA licences).")
        created = seed_demo_listings()
        self.stdout.write(self.style.SUCCESS(f"Demo listings: {created} created."))
