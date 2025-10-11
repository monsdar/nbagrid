from django.core.management.base import BaseCommand, CommandError
from nbagrid_api_app.models import Player


class Command(BaseCommand):
    help = "Load real NBA player data from the NBA API for specific players"

    def add_arguments(self, parser):
        parser.add_argument(
            'stats_ids',
            nargs='+',
            type=int,
            help='NBA stats IDs of players to load data for'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Optional: Player name to use when creating the player (only for single player)',
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create player if it does not exist',
        )

    def handle(self, *args, **options):
        stats_ids = options['stats_ids']
        player_name = options.get('name')
        create_player = options['create']
        
        if len(stats_ids) > 1 and player_name:
            raise CommandError("Cannot specify --name when loading multiple players")
        
        success_count = 0
        error_count = 0
        
        for stats_id in stats_ids:
            try:
                # Try to get existing player
                try:
                    player = Player.active.get(stats_id=stats_id)
                    self.stdout.write(f"Found existing player: {player.name} (ID: {stats_id})")
                except Player.DoesNotExist:
                    if create_player:
                        name = player_name if player_name else f"Player {stats_id}"
                        player = Player.active.create(stats_id=stats_id, name=name)
                        self.stdout.write(f"Created new player: {name} (ID: {stats_id})")
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"Player with ID {stats_id} not found. Use --create to create it.")
                        )
                        continue
                
                # Load data from NBA API
                self.stdout.write(f"Loading NBA API data for {player.name}...")
                player.load_from_nba_api()
                
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully loaded data for {player.name}")
                )
                self.stdout.write(f"  Position: {player.position}")
                self.stdout.write(f"  Country: {player.country}")
                self.stdout.write(f"  Career PPG: {player.career_ppg}")
                self.stdout.write(f"  Career APG: {player.career_apg}")
                self.stdout.write(f"  Career RPG: {player.career_rpg}")
                self.stdout.write(f"  Draft Year: {player.draft_year}")
                self.stdout.write(f"  All-Star: {player.is_award_all_star}")
                self.stdout.write("")
                
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to load data for player ID {stats_id}: {e}")
                )
                error_count += 1
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(f"Completed: {success_count} successful, {error_count} errors")
        )