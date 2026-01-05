import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import GameFilterDB

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate grid for tomorrow if it does not already exist'

    def handle(self, *args, **options):
        # Calculate tomorrow's date
        tomorrow_date = datetime.now().date() + timedelta(days=1)
        
        self.stdout.write(f"Checking for grid on {tomorrow_date}...")
        
        # Check if a grid already exists for tomorrow
        if GameFilterDB.objects.filter(date=tomorrow_date).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"Grid for {tomorrow_date} already exists. Nothing to do."
                )
            )
            return
        
        self.stdout.write(f"No grid found for {tomorrow_date}. Generating new grid...")
        
        try:
            # Create GameBuilder with tomorrow's date timestamp as seed for consistency
            tomorrow_datetime = datetime.combine(tomorrow_date, datetime.min.time())
            builder = GameBuilder(random_seed=int(tomorrow_datetime.timestamp()))
            
            # Generate the grid
            static_filters, dynamic_filters = builder.get_tuned_filters(
                requested_date=tomorrow_datetime,
                num_iterations=10,
                reuse_cached_game=True
            )
            
            # Verify the grid was created successfully
            if static_filters and dynamic_filters:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Successfully generated grid for {tomorrow_date}"
                    )
                )
                self.stdout.write(f"  Static filters: {[f.get_desc() for f in static_filters]}")
                self.stdout.write(f"  Dynamic filters: {[f.get_desc() for f in dynamic_filters]}")
                logger.info(f"Successfully generated grid for {tomorrow_date}")
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Failed to generate grid for {tomorrow_date}: Filters are None"
                    )
                )
                logger.error(f"Failed to generate grid for {tomorrow_date}: Filters are None")
                raise SystemExit(1)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"✗ Error generating grid for {tomorrow_date}: {str(e)}"
                )
            )
            logger.error(f"Error generating grid for {tomorrow_date}: {str(e)}", exc_info=True)
            raise SystemExit(1)

