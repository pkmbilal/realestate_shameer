from django.core.management.base import BaseCommand

from apps.listings.seed import seed_amenities


class Command(BaseCommand):
    help = "Load the listing amenities (safe to run again, also in production)."

    def handle(self, *args, **options):
        count = seed_amenities()
        self.stdout.write(self.style.SUCCESS(f"Amenities: {count} loaded."))
