from django.core.management.base import BaseCommand
from properties.models import Property
from properties.geocoding import GeocodingService
import time


class Command(BaseCommand):
    help = 'Geocode all properties that are missing coordinates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-geocode all properties, even those with existing coordinates',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of properties to process (default: 100)',
        )

    def handle(self, *args, **options):
        force = options['force']
        limit = options['limit']

        if force:
            properties = Property.objects.all()[:limit]
            self.stdout.write(f'Geocoding all properties (limit: {limit})...')
        else:
            from django.db.models import Q
            properties = Property.objects.filter(
                Q(latitude__isnull=True) | Q(longitude__isnull=True)
            )[:limit]
            self.stdout.write(f'Geocoding {len(properties)} properties missing coordinates...')

        if not properties:
            self.stdout.write(self.style.SUCCESS('No properties need geocoding.'))
            return

        success_count = 0
        failed_count = 0

        for i, property_obj in enumerate(properties, 1):
            self.stdout.write(f'[{i}] Processing: {property_obj.title} ({property_obj.suburb})')

            if not force and property_obj.latitude and property_obj.longitude:
                self.stdout.write(self.style.WARNING('  → Skipping (already has coordinates)'))
                continue

            # Clear existing coordinates if forcing
            if force:
                property_obj.latitude = None
                property_obj.longitude = None

            try:
                # Save will trigger automatic geocoding
                property_obj.save()

                if property_obj.latitude and property_obj.longitude:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ Success: ({property_obj.latitude}, {property_obj.longitude})'
                        )
                    )
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR('  ❌ Failed: No coordinates returned'))
                    failed_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Error: {e}'))
                failed_count += 1

            # Rate limiting to be nice to the geocoding service
            if i < len(properties):
                time.sleep(1)

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Geocoding complete!'))
        self.stdout.write(f'  ✅ Successful: {success_count}')
        self.stdout.write(f'  ❌ Failed: {failed_count}')

        if failed_count > 0:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Some properties failed to geocode. This could be due to:'
            ))
            self.stdout.write('  - Invalid or incomplete addresses')
            self.stdout.write('  - Network connectivity issues')
            self.stdout.write('  - Rate limiting from the geocoding service')
            self.stdout.write('  - Non-existent locations')