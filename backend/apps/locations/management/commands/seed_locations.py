from django.core.management.base import BaseCommand

from apps.locations.services import DEFAULT_DATA_FILE, load_locations_file


class Command(BaseCommand):
    help = "Load launch cities and districts (safe to run again, also in production)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_DATA_FILE), help="JSON file to load")

    def handle(self, *args, **options):
        result = load_locations_file(options["file"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Cities: {result.cities_created} created, {result.cities_updated} updated. "
                f"Districts: {result.districts_created} created, "
                f"{result.districts_updated} updated."
            )
        )
