from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fill a local database with launch data and demo content (safe to run again)."

    def handle(self, *args, **options):
        call_command("seed_locations", stdout=self.stdout)
        # Demo brokers and listings are added here once those apps exist.
