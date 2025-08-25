from django.core.management.base import BaseCommand
from nbagrid_api_app.models import Player
from nbagrid_api_app.nba_api_wrapper import nba_api_wrapper
import time


class Command(BaseCommand):
    help = 'Populate teammates field for all players based on their team history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
                        
        # Get all players
        players = Player.objects.all()
        total_players = players.count()
        
        self.stdout.write(f"Found {total_players} players to process")
        
        if total_players == 0:
            self.stdout.write(self.style.ERROR('No players found in database'))
            return
        
        # Process in batches
        processed = 0
        start_time = time.time()
        
        for player in players:
            try:
                if not dry_run:
                    teammates = player.populate_teammates()
                    self.stdout.write(f"  {player.name}: {len(teammates)} teammates")
                else:
                    # Count what would be added in dry-run mode
                    player_teams = player.teams.all()
                    if player_teams.exists():
                        potential_teammates = Player.objects.filter(teams__in=player_teams).exclude(id=player.id).distinct()
                        self.stdout.write(f"  {player.name}: would add {potential_teammates.count()} teammates")
                    else:
                        self.stdout.write(f"  {player.name}: no teams found")
                
                processed += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error processing {player.name}: {e}"))
            
            # Progress update with API status
            api_status = nba_api_wrapper.get_status()
            self.stdout.write(f"Processed {processed}/{total_players} players ({processed/total_players*100:.1f}%)")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Successfully processed {processed} players in {total_time:.1f} seconds"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Dry run completed - would process {processed} players"))
