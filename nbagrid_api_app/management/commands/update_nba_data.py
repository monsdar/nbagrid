"""
Comprehensive NBA data update management command.

This command consolidates all NBA data update operations into a single, 
streamlined command that can be run locally or in a Docker container.

Usage:
    python manage.py update_nba_data --all
    python manage.py update_nba_data --players --teams
    python manage.py update_nba_data --players --sync-to-production
    python manage.py update_nba_data --init-only
"""

import logging
from typing import Optional, List

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from nbagrid_api_app.models import Player, Team, LastUpdated
from nbagrid_api_app.telegram_notifications import NBADataUpdateSummary, send_nba_update_notification
from nba_api.stats.static import players as static_players, teams as static_teams

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Comprehensive NBA data update command'

    def add_arguments(self, parser):
        # Data update options
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all NBA data (players, teams, stats, awards)'
        )
        parser.add_argument(
            '--players',
            action='store_true',
            help='Update player data'
        )
        parser.add_argument(
            '--teams',
            action='store_true',
            help='Update team data'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Update player stats only'
        )
        parser.add_argument(
            '--awards',
            action='store_true',
            help='Update player awards only'
        )
        parser.add_argument(
            '--teammates',
            action='store_true',
            help='Update player teammates relationships'
        )
        parser.add_argument(
            '--salaries',
            action='store_true',
            help='Update player salaries from Spotrac'
        )
        
        # Initialization options
        parser.add_argument(
            '--init-only',
            action='store_true',
            help='Only initialize players/teams from static data (no API calls)'
        )
        
        # Filtering options
        parser.add_argument(
            '--player-ids',
            nargs='+',
            type=int,
            help='Specific player stats_ids to update'
        )
        parser.add_argument(
            '--team-ids',
            nargs='+',
            type=int,
            help='Specific team stats_ids to update'
        )
        
        # Processing options
        parser.add_argument(
            '--continue-on-error',
            action='store_true',
            help='Continue processing other players if one fails (default: stop on error)'
        )
        
        # Sync to production options
        parser.add_argument(
            '--sync-to-production',
            action='store_true',
            help='Sync updated data to production after local updates'
        )
        parser.add_argument(
            '--production-url',
            type=str,
            help='Production API base URL (required if --sync-to-production is used)'
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for production sync (required if --sync-to-production is used)'
        )
        
        # Telegram notification options
        parser.add_argument(
            '--telegram-notify',
            action='store_true',
            help='Send summary notification to Telegram after completion'
        )
        parser.add_argument(
            '--telegram-bot-token',
            type=str,
            help='Telegram bot token (overrides TELEGRAM_BOT_TOKEN env var)'
        )
        parser.add_argument(
            '--telegram-chat-id',
            type=str,
            help='Telegram chat ID (overrides TELEGRAM_CHAT_ID env var)'
        )
        
        # Utility options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )

    def handle(self, *args, **options):
        # Set up logging
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)

        # Validate arguments
        self._validate_arguments(options)
        
        # Show configuration
        self._show_configuration(options)
        
        # Initialize summary tracking
        self.summary = NBADataUpdateSummary()
        start_time = timezone.now()
        self.summary.set_start_time(start_time)
        
        try:
            # Execute requested operations
            if options['init_only']:
                self._init_data_only(options)
            else:
                self._update_nba_data(options)
            
            # Sync to production if requested
            if options['sync_to_production']:
                self._sync_to_production(options)
                
        except Exception as e:
            logger.error(f"Command failed: {e}")
            self.summary.add_error(str(e))
            
            # Send notification even on failure
            if options['telegram_notify']:
                self._send_telegram_notification(options)
            
            raise CommandError(f"NBA data update failed: {e}")
        
        end_time = timezone.now()
        self.summary.set_end_time(end_time)
        duration = (end_time - start_time).total_seconds()
        
        # Send Telegram notification if requested
        if options['telegram_notify']:
            self._send_telegram_notification(options)
        
        self.stdout.write(
            self.style.SUCCESS(f"NBA data update completed successfully in {duration:.1f} seconds")
        )

    def _validate_arguments(self, options):
        """Validate command arguments."""
        if options['sync_to_production']:
            if not options['production_url']:
                raise CommandError("--production-url is required when using --sync-to-production")
            if not options['api_key']:
                raise CommandError("--api-key is required when using --sync-to-production")
        
        # Validate Telegram options
        if options['telegram_notify']:
            # Check if configuration is available (either from env vars or command line)
            from django.conf import settings
            bot_token = options.get('telegram_bot_token') or getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
            chat_id = options.get('telegram_chat_id') or getattr(settings, 'TELEGRAM_CHAT_ID', None)
            
            if not bot_token or not chat_id:
                self.stdout.write(
                    self.style.WARNING(
                        "Telegram notification requested but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured. "
                        "Notification will be skipped."
                    )
                )
        
        # If no specific options are given, default to --all
        if not any([
            options['all'], options['players'], options['teams'], 
            options['stats'], options['awards'], options['teammates'],
            options['salaries'], options['init_only']
        ]):
            options['all'] = True
            self.stdout.write(
                self.style.WARNING("No specific update options provided, defaulting to --all")
            )

    def _show_configuration(self, options):
        """Display the current configuration."""
        self.stdout.write(self.style.HTTP_INFO("=== NBA Data Update Configuration ==="))
        
        operations = []
        if options['all']:
            operations.append("All data (players, teams, stats, awards, salaries)")
        else:
            if options['players']: operations.append("Players")
            if options['teams']: operations.append("Teams") 
            if options['stats']: operations.append("Player stats")
            if options['awards']: operations.append("Player awards")
            if options['teammates']: operations.append("Player teammates")
            if options['salaries']: operations.append("Player salaries")
            if options['init_only']: operations.append("Initialize only (no API calls)")
        
        self.stdout.write(f"Operations: {', '.join(operations)}")
        self.stdout.write(f"Continue on error: {options['continue_on_error']}")
        
        if options['player_ids']:
            self.stdout.write(f"Player IDs filter: {options['player_ids']}")
        if options['team_ids']:
            self.stdout.write(f"Team IDs filter: {options['team_ids']}")
            
        if options['sync_to_production']:
            self.stdout.write(f"Production sync: {options['production_url']}")
        
        if options['telegram_notify']:
            self.stdout.write("Telegram notification: Enabled")
            
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
            
        self.stdout.write("=" * 50)

    def _init_data_only(self, options):
        """Initialize players and teams from static data only."""
        self.stdout.write("Initializing data from static sources...")
        
        if options['all'] or options['players']:
            self._init_players(options)
            
        if options['all'] or options['teams']:
            self._init_teams(options)

    def _update_nba_data(self, options):
        """Update NBA data based on options."""
        if options['all'] or options['players']:
            self._init_players(options)
            if not options['init_only']:
                self._update_player_data(options)
                
        if options['all'] or options['teams']:
            self._init_teams(options)
            
        if options['all'] or options['stats']:
            if not options['init_only']:
                self._update_player_stats(options)
                
        if options['all'] or options['awards']:
            if not options['init_only']:
                self._update_player_awards(options)
                
        if options['all'] or options['teammates']:
            if not options['init_only']:
                self._update_player_teammates(options)
                
        if options['all'] or options['salaries']:
            if not options['init_only']:
                self._update_player_salaries(options)

    def _init_players(self, options):
        """Initialize players from static data."""
        self.stdout.write("Initializing players from static data...")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN: Would initialize players"))
            return
            
        all_players = static_players.get_active_players()
        created_count = 0
        updated_count = 0
        
        for player_data in all_players:
            player, created = Player.objects.update_or_create(
                stats_id=player_data["id"],
                defaults={
                    "name": static_players._strip_accents(player_data["full_name"]),
                    "last_name": static_players._strip_accents(player_data["last_name"]),
                    "display_name": player_data["full_name"],
                    "is_active": True,  # Mark as active when syncing from active players list
                },
            )
            
            if created:
                created_count += 1
                logger.debug(f"Created player: {player_data['full_name']}")
            else:
                updated_count += 1
                logger.debug(f"Updated player: {player_data['full_name']}")
        
        # Mark players not in active list as inactive
        all_static_player_ids = [p["id"] for p in all_players]
        inactive_count = 0
        for player in Player.objects.filter(is_active=True).exclude(stats_id__in=all_static_player_ids):
            player.is_active = False
            player.save()
            inactive_count += 1
            logger.debug(f"Marked player as inactive: {player.name}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Players initialized: {created_count} created, {updated_count} updated, {inactive_count} marked inactive"
            )
        )
        
        # Track in summary
        if hasattr(self, 'summary'):
            self.summary.add_operation(
                'player_initialization',
                success_count=created_count + updated_count,
                error_count=0,
                details=f"{created_count} created, {updated_count} updated, {inactive_count} marked inactive"
            )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_init', 'update_nba_data command')

    def _init_teams(self, options):
        """Initialize teams from static data."""
        self.stdout.write("Initializing teams from static data...")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN: Would initialize teams"))
            return
            
        all_teams = static_teams.get_teams()
        created_count = 0
        updated_count = 0
        
        for team_data in all_teams:
            team, created = Team.objects.update_or_create(
                stats_id=team_data["id"],
                defaults={
                    "name": team_data["full_name"],
                    "abbr": team_data["abbreviation"],
                },
            )
            
            if created:
                created_count += 1
                logger.debug(f"Created team: {team_data['full_name']}")
            else:
                updated_count += 1
                logger.debug(f"Updated team: {team_data['full_name']}")
        
        self.stdout.write(
            self.style.SUCCESS(f"Teams initialized: {created_count} created, {updated_count} updated")
        )
        
        # Track in summary
        if hasattr(self, 'summary'):
            self.summary.add_operation(
                'team_initialization',
                success_count=created_count + updated_count,
                error_count=0,
                details=f"{created_count} created, {updated_count} updated"
            )
        
        # Update timestamp
        LastUpdated.update_timestamp('team_init', 'update_nba_data command')

    def _update_player_data(self, options):
        """Update player basic data from NBA API."""
        self.stdout.write("Updating player data from NBA API...")
        
        players = self._get_players_to_update(options)
        self._process_players(
            players, 
            lambda p: p.update_player_data_from_nba_stats(),
            "player data",
            options
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_data', 'update_nba_data command')

    def _update_player_stats(self, options):
        """Update player stats from NBA API."""
        self.stdout.write("Updating player stats from NBA API...")
        
        players = self._get_players_to_update(options)
        self._process_players(
            players,
            lambda p: p.update_player_stats_from_nba_stats(),
            "player stats",
            options
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_stats', 'update_nba_data command')

    def _update_player_awards(self, options):
        """Update player awards from NBA API."""
        self.stdout.write("Updating player awards from NBA API...")
        
        players = self._get_players_to_update(options)
        self._process_players(
            players,
            lambda p: p.update_player_awards_from_nba_stats(),
            "player awards",
            options
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_awards', 'update_nba_data command')

    def _update_player_teammates(self, options):
        """Update player teammates relationships."""
        self.stdout.write("Updating player teammates...")
        
        players = self._get_players_to_update(options)
        self._process_players(
            players,
            lambda p: p.populate_teammates(),
            "player teammates",
            options
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_teammates', 'update_nba_data command')

    def _update_player_salaries(self, options):
        """Update player salaries from Spotrac."""
        self.stdout.write("Updating player salaries from Spotrac...")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN: Would update player salaries"))
            return
        
        try:
            import re
            import requests
            from bs4 import BeautifulSoup
            from nba_api.stats.static import players as static_players
            
            # Fetch the Spotrac page
            url = "https://www.spotrac.com/nba/rankings/player/_/year/2025/sort/cap_base"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Find the table with player salaries
            table = soup.find("ul", {"class": "list-group"})
            if not table:
                raise Exception("Could not find salary table on Spotrac page")

            # Player name mappings for differences between Spotrac and NBA.com
            player_mappings = {
                "Jimmy Butler": "Jimmy Butler III",
                "C.J. McCollum": "CJ McCollum",
                "Nicolas Claxton": "Nic Claxton",
                "R.J. Barrett": "RJ Barrett",
                "Bruce Brown Jr.": "Bruce Brown",
                "PJ Washington": "P.J. Washington",
                "Herb Jones": "Herbert Jones",
                "Ron Holland II": "Ronald Holland II",
                "Kenyon Martin Jr.": "KJ Martin",
                "Jae'Sean Tate": "Jae'Sean Tate",
                "Cameron Thomas": "Cam Thomas",
                "Sviatoslav Mykhailiuk": "Svi Mykhailiuk",
                "Vincent Williams Jr.": "Vince Williams Jr.",
                "G.G. Jackson": "GG Jackson",
                "Cameron Christie": "Cam Christie",
                "Brandon Boston Jr": "Brandon Boston",
                "Jeenathan Williams": "Nate Williams",
                "Kevin Knox": "Kevin Knox II",
                "Mohamed Bamba": "Mo Bamba",
                "Kevon Harris": "Kevon Harris",
                "Terence Davis": "Terence Davis",
                "J.D. Davison": "JD Davison",
            }

            # Process each row
            updated_count = 0
            error_count = 0
            
            for row in table.find_all("li"):
                try:
                    player_link = row.find("a", {"class": "link"})
                    if not player_link:
                        continue
                    player_name = player_link.text.strip()
                    salary_span = row.find("span", {"class": "medium"})
                    if not salary_span:
                        continue
                    salary_text = salary_span.text.strip()

                    # Convert salary text to integer (remove $ and commas)
                    salary = int(re.sub(r"[^\d]", "", salary_text))

                    # Strip accents and special chars from the player_name
                    player_name = static_players._strip_accents(player_name)
                    
                    # Apply name mapping if needed
                    if player_name in player_mappings:
                        player_name = player_mappings[player_name]

                    # Find matching player(s) and update salary (check all players, not just active)
                    players = Player.objects.filter(name__iexact=player_name)
                    if players.exists():
                        for player in players:
                            player.base_salary = salary
                            player.save()
                            updated_count += 1
                            logger.debug(f"Updated salary for {player.name}: ${salary:,}")
                    else:
                        logger.warning(f"No player found for {player_name}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing salary row: {e}")
                    if not options['continue_on_error']:
                        raise

            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed salary update: {updated_count} successful, {error_count} errors"
                )
            )
            
            # Track in summary
            if hasattr(self, 'summary'):
                self.summary.add_operation(
                    'player_salaries',
                    success_count=updated_count,
                    error_count=error_count,
                    details=f"Updated salaries from Spotrac"
                )
            
            # Update timestamp
            LastUpdated.update_timestamp('player_salaries', 'update_nba_data command')
            
        except Exception as e:
            logger.error(f"Failed to update player salaries: {e}")
            if hasattr(self, 'summary'):
                self.summary.add_error(f"Salary update failed: {e}")
            raise CommandError(f"Failed to update player salaries: {e}")

    def _get_players_to_update(self, options) -> List[Player]:
        """Get the list of players to update based on options."""
        if options['player_ids']:
            return Player.objects.filter(stats_id__in=options['player_ids'])
        else:
            # By default, only update active players
            return Player.active.all()

    def _process_players(self, players, update_func, operation_name, options):
        """Process players with simple error handling (rate limiting handled by nba_api_wrapper)."""
        total_players = players.count()
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would update {operation_name} for {total_players} players")
            )
            return
        
        success_count = 0
        error_count = 0
        
        self.stdout.write(f"Processing {total_players} players...")
        
        for i, player in enumerate(players, 1):
            try:
                update_func(player)
                success_count += 1
                logger.debug(f"Updated {operation_name} for {player.name}")
                
                # Show progress every 50 players
                if i % 50 == 0 or i == total_players:
                    self.stdout.write(f"Progress: {i}/{total_players} players processed...")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to update {operation_name} for {player.name}: {e}")
                
                if not options['continue_on_error']:
                    self.stdout.write(
                        self.style.ERROR(f"Stopping due to error. Use --continue-on-error to continue processing.")
                    )
                    raise CommandError(f"Failed to update {operation_name} for {player.name}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed {operation_name} update: {success_count} successful, {error_count} errors"
            )
        )
        
        # Track in summary
        if hasattr(self, 'summary'):
            self.summary.add_operation(
                operation_name.replace(' ', '_'),
                success_count=success_count,
                error_count=error_count
            )

    def _sync_to_production(self, options):
        """Sync updated data to production."""
        self.stdout.write("Syncing data to production...")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN: Would sync to production"))
            return
        
        # Import the sync functionality
        from django.core.management import call_command
        
        try:
            call_command(
                'sync_to_production',
                production_url=options['production_url'],
                api_key=options['api_key'],
                players=options.get('all') or options.get('players'),
                teams=options.get('all') or options.get('teams'),
                player_teams=options.get('all') or options.get('players'),
                verbosity=2 if options['verbose'] else 1
            )
        except Exception as e:
            logger.error(f"Production sync failed: {e}")
            if hasattr(self, 'summary'):
                self.summary.add_error(f"Production sync failed: {e}")
            raise CommandError(f"Production sync failed: {e}")

    def _send_telegram_notification(self, options):
        """Send Telegram notification with operation summary."""
        self.stdout.write("Sending Telegram notification...")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN: Would send Telegram notification"))
            return
        
        try:
            # Override Telegram settings if provided via command line
            from nbagrid_api_app.telegram_notifications import TelegramNotifier
            
            bot_token = options.get('telegram_bot_token')
            chat_id = options.get('telegram_chat_id')
            
            if bot_token or chat_id:
                notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
                message = self.summary.generate_telegram_message()
                success = notifier.send_message(message)
            else:
                success = send_nba_update_notification(self.summary)
            
            if success:
                self.stdout.write(self.style.SUCCESS("Telegram notification sent successfully"))
            else:
                self.stdout.write(self.style.WARNING("Failed to send Telegram notification"))
                
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            self.stdout.write(self.style.ERROR(f"Error sending Telegram notification: {e}"))
