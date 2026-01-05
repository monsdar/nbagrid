import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import GameFilterDB

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate grid for tomorrow if it does not already exist'

    def add_arguments(self, parser):
        parser.add_argument(
            '--next-missing',
            action='store_true',
            help='Generate grid for the next date that is missing a grid (instead of tomorrow)',
        )

    def find_next_missing_date(self):
        """Find the next date (starting from tomorrow) that does not have a grid."""
        current_date = datetime.now().date()
        check_date = current_date + timedelta(days=1)
        max_days_ahead = 365  # Prevent infinite loop
        
        for _ in range(max_days_ahead):
            if not GameFilterDB.objects.filter(date=check_date).exists():
                return check_date
            check_date += timedelta(days=1)
        
        # If all dates up to a year ahead have grids, return None
        return None

    def handle(self, *args, **options):
        next_missing = options.get('next_missing', False)
        
        # Determine which date to generate for
        if next_missing:
            target_date = self.find_next_missing_date()
            if target_date is None:
                self.stdout.write(
                    self.style.SUCCESS(
                        "All dates up to 365 days ahead already have grids. Nothing to do."
                    )
                )
                return
            self.stdout.write(f"Found next missing date: {target_date}")
        else:
            # Calculate tomorrow's date
            target_date = datetime.now().date() + timedelta(days=1)
        
        self.stdout.write(f"Checking for grid on {target_date}...")
        
        # Check if a grid already exists for the target date (only if not using --next-missing)
        if not next_missing and GameFilterDB.objects.filter(date=target_date).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"Grid for {target_date} already exists. Nothing to do."
                )
            )
            return
        
        self.stdout.write(f"No grid found for {target_date}. Generating new grid...")
        
        # Get count of existing grids before this date for reporting
        existing_grids_count = GameFilterDB.objects.filter(
            date__lt=target_date
        ).values('date').distinct().count()
        
        self.stdout.write(
            f"Using {existing_grids_count} existing grid(s) before {target_date} to calculate filter weights..."
        )
        
        try:
            # Create GameBuilder with target date timestamp as seed for consistency
            target_datetime = datetime.combine(target_date, datetime.min.time())
            builder = GameBuilder(random_seed=int(target_datetime.timestamp()))
            
            # Generate the grid - the GameBuilder will automatically use historical
            # grids before this date to calculate weights and ensure variety
            static_filters, dynamic_filters = builder.get_tuned_filters(
                requested_date=target_datetime,
                num_iterations=10,
                reuse_cached_game=True
            )
            
            # Verify the grid was created successfully
            if static_filters and dynamic_filters:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Successfully generated grid for {target_date}"
                    )
                )
                self.stdout.write(f"  Static filters: {[f.get_desc() for f in static_filters]}")
                self.stdout.write(f"  Dynamic filters: {[f.get_desc() for f in dynamic_filters]}")
                logger.info(f"Successfully generated grid for {target_date}")
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Failed to generate grid for {target_date}: Filters are None"
                    )
                )
                logger.error(f"Failed to generate grid for {target_date}: Filters are None")
                raise SystemExit(1)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"✗ Error generating grid for {target_date}: {str(e)}"
                )
            )
            logger.error(f"Error generating grid for {target_date}: {str(e)}", exc_info=True)
            raise SystemExit(1)

