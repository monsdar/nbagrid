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
from nba_api.stats.static import players as static_players, teams as static_teams

# Import telegram notifications conditionally
try:
    from nbagrid_api_app.telegram_notifications import NBADataUpdateSummary, send_nba_update_notification
    TELEGRAM_AVAILABLE = True
except ImportError:
    # Create a dummy class if telegram is not available
    class NBADataUpdateSummary:
        def __init__(self):
            self.operations = []
            self.errors = []
            self.start_time = None
            self.end_time = None
        
        def set_start_time(self, start_time):
            self.start_time = start_time
            
        def set_end_time(self, end_time):
            self.end_time = end_time
            
        def add_operation(self, name, success_count=0, error_count=0, details=""):
            self.operations.append({
                'name': name,
                'success_count': success_count,
                'error_count': error_count,
                'details': details
            })
            
        def add_error(self, error):
            self.errors.append(error)
            
        def generate_telegram_message(self):
            return "NBA data update completed"
    
    def send_nba_update_notification(summary):
        return False
    
    TELEGRAM_AVAILABLE = False

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
            '--current-season-only',
            action='store_true',
            help='When used with --teammates or --all, only process current season data (faster, focuses on recent changes)'
        )
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
            if not TELEGRAM_AVAILABLE:
                self.stdout.write(
                    self.style.WARNING(
                        "Telegram notification requested but telegram module not available. "
                        "Notification will be skipped."
                    )
                )
            else:
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
            teammate_text = "Player teammates"
            if options.get('current_season_only'):
                teammate_text += " (current season only)"
            if options['teammates']: operations.append(teammate_text)
            if options['salaries']: operations.append("Player salaries")
            if options['init_only']: operations.append("Initialize only (no API calls)")
        
        self.stdout.write(f"Operations: {', '.join(operations)}")
        if options.get('current_season_only'):
            self.stdout.write(f"Current season only mode: Enabled")
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
                
        # Handle teammates updates
        if options['all'] or options['teammates']:
            if not options['init_only']:
                current_season_only = options.get('current_season_only', False)
                self._update_player_teammates(options, current_season_only=current_season_only)
                
        if options['all'] or options['salaries']:
            if not options['init_only']:
                self._update_player_salaries(options)

    def _init_players(self, options):
        """Initialize players from static data."""
        self.stdout.write("Initializing players from NBA API (checking roster status)...")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN: Would initialize players"))
            return
        
        # Use ALL active players from static data as a starting point
        all_active_players = static_players.get_active_players()
        created_count = 0
        updated_count = 0
        
        self.stdout.write(f"Found {len(all_active_players)} players in NBA static data...")
        
        for player_data in all_active_players:
            # Create or get the player (don't set is_active here, will be set by update_player_data_from_nba_stats)
            player, created = Player.objects.update_or_create(
                stats_id=player_data["id"],
                defaults={
                    "name": static_players._strip_accents(player_data["full_name"]),
                    "last_name": static_players._strip_accents(player_data["last_name"]),
                    "display_name": player_data["full_name"],
                },
            )
            
            if created:
                created_count += 1
                logger.debug(f"Created player: {player_data['full_name']}")
            else:
                updated_count += 1
                logger.debug(f"Updated player: {player_data['full_name']}")
        
        # Clean up the inactive players from the database
        # This is needed because we once added all available static players to the database,
        # but now we only want to keep the active players.
        players_deleted_count = 0
        all_active_players_stats_ids = [player['id'] for player in all_active_players]
        for player in Player.objects.all():
            if player.stats_id not in all_active_players_stats_ids:
                player.delete()
                players_deleted_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Players initialized: {created_count} created, {updated_count} updated, {players_deleted_count} deleted"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Note: is_active status will be set when running --players or --all to fetch ROSTERSTATUS from NBA API"
            )
        )
        
        # Track in summary
        if hasattr(self, 'summary'):
            self.summary.add_operation(
                'player_initialization',
                success_count=created_count + updated_count,
                error_count=0,
                details=f"{created_count} created, {updated_count} updated. Run with --players to update is_active status."
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

    def _update_player_teammates(self, options, current_season_only=False):
        """Update player teammates relationships and check for inactive/missing players.
        
        Args:
            options: Command options dictionary
            current_season_only: If True, only update teammates for current season (faster)
        """
        if current_season_only:
            self.stdout.write("Updating player teammates for current season only...")
        else:
            self.stdout.write("Updating player teammates...")
        
        players = self._get_players_to_update(options)
        
        # Track teammate-related operations
        reactivated_count = 0
        created_count = 0
        error_count = 0
        
        total_players = players.count()
        self.stdout.write(f"Processing {total_players} players for teammate updates...")
        
        if options['dry_run']:
            mode_text = "current season only" if current_season_only else "all seasons"
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would update teammates ({mode_text}) for {total_players} players")
            )
            return
        
        for i, player in enumerate(players, 1):
            try:
                if current_season_only:
                    # Current season only mode: Get teammates from current season API data
                    current_season_teammate_ids = self._get_current_season_teammate_ids_from_api(player)
                    
                    # Get existing teammates before updating
                    old_teammates = set(player.teammates.all())
                    current_season_teammates = set()
                    
                    # Process each current season teammate ID
                    for teammate_id in current_season_teammate_ids:
                        try:
                            # Check if teammate exists in our database
                            existing_teammate = Player.objects.get(stats_id=teammate_id)
                            current_season_teammates.add(existing_teammate)
                            
                            # If they exist but are inactive, reactivate them
                            if not existing_teammate.is_active:
                                existing_teammate.is_active = True
                                existing_teammate.save()
                                reactivated_count += 1
                                logger.info(f"Reactivated inactive current season teammate: {existing_teammate.name} (found as teammate of {player.name})")
                        except Player.DoesNotExist:
                            # Teammate doesn't exist in our database, create them
                            try:
                                new_teammate = self._create_missing_teammate(teammate_id)
                                if new_teammate:
                                    current_season_teammates.add(new_teammate)
                                    created_count += 1
                                    logger.info(f"Created missing current season teammate: {new_teammate.name} (found as teammate of {player.name})")
                            except Exception as e:
                                logger.warning(f"Failed to create missing teammate with stats_id {teammate_id}: {e}")
                                error_count += 1
                    
                    # Update teammates relationship: add current season teammates to existing ones
                    # We don't remove old teammates, just add new current season ones
                    if current_season_teammates:
                        player.teammates.add(*current_season_teammates)
                        logger.debug(f"Added {len(current_season_teammates)} current season teammates for {player.name}")
                else:
                    # Full history mode: Use existing populate_teammates method
                    # Get teammates before updating (to track changes)
                    old_teammates = set(player.teammates.all())
                    
                    # Update teammates using the existing method (processes all seasons)
                    teammates = player.populate_teammates()
                    
                    # Get new teammates after updating
                    new_teammates = set(player.teammates.all())
                    
                    # Check for teammates that were added
                    added_teammates = new_teammates - old_teammates
                    
                    # Process each new teammate
                    for teammate in added_teammates:
                        # Check if teammate was inactive and reactivate them
                        if not teammate.is_active:
                            teammate.is_active = True
                            teammate.save()
                            reactivated_count += 1
                            logger.info(f"Reactivated inactive player: {teammate.name} (found as teammate of {player.name})")
                    
                    # Check for current season teammates that don't exist in our database
                    # This requires getting the current season teammate IDs from the NBA API and checking if they exist
                    current_season_teammate_ids = self._get_current_season_teammate_ids_from_api(player)
                    for teammate_id in current_season_teammate_ids:
                        try:
                            # Check if teammate exists in our database
                            existing_teammate = Player.objects.get(stats_id=teammate_id)
                            # If they exist but are inactive, reactivate them
                            if not existing_teammate.is_active:
                                existing_teammate.is_active = True
                                existing_teammate.save()
                                reactivated_count += 1
                                logger.info(f"Reactivated inactive current season teammate: {existing_teammate.name} (found as teammate of {player.name})")
                        except Player.DoesNotExist:
                            # Teammate doesn't exist in our database, create them
                            try:
                                new_teammate = self._create_missing_teammate(teammate_id)
                                if new_teammate:
                                    created_count += 1
                                    logger.info(f"Created missing current season teammate: {new_teammate.name} (found as teammate of {player.name})")
                            except Exception as e:
                                logger.warning(f"Failed to create missing teammate with stats_id {teammate_id}: {e}")
                                error_count += 1
                
                # Show progress every 50 players
                if i % 50 == 0 or i == total_players:
                    self.stdout.write(f"Progress: {i}/{total_players} players processed...")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to update teammates for {player.name}: {e}")
                
                if not options['continue_on_error']:
                    self.stdout.write(
                        self.style.ERROR(f"Stopping due to error. Use --continue-on-error to continue processing.")
                    )
                    raise CommandError(f"Failed to update teammates for {player.name}: {e}")
        
        # Report results
        mode_text = " (current season only)" if current_season_only else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed teammate updates{mode_text}: {total_players} players processed, "
                f"{reactivated_count} players reactivated, {created_count} new players created, "
                f"{error_count} errors"
            )
        )
        
        # Track in summary
        if hasattr(self, 'summary'):
            operation_name = 'player_teammates_current_season' if current_season_only else 'player_teammates'
            details = f"Processed {total_players} players, reactivated {reactivated_count}, created {created_count}"
            if current_season_only:
                details += " (current season only)"
            self.summary.add_operation(
                operation_name,
                success_count=total_players - error_count,
                error_count=error_count,
                details=details
            )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_teammates', 'update_nba_data command')

    def _get_teammate_ids_from_api(self, player):
        """Get teammate IDs from NBA API for a player (all seasons)."""
        from nbagrid_api_app.nba_api_wrapper import get_player_career_stats, get_league_dash_lineups
        
        teammate_ids = set()
        
        try:
            # Get the player's career stats to see which teams they played for in each season
            career_data = get_player_career_stats(player.stats_id, per_mode36="PerGame")
            
            if 'SeasonTotalsRegularSeason' not in career_data:
                return teammate_ids
            
            # Process all seasons to get complete teammate history
            for season_data in career_data['SeasonTotalsRegularSeason']:
                season_id = season_data.get('SEASON_ID', '')
                team_id = season_data.get('TEAM_ID', '')
                games_played = season_data.get('GP', 0)
                
                # Skip total entries and seasons with no games
                if team_id == 0 or games_played == 0:
                    continue
                
                logger.debug(f"Processing {player.name} - Season {season_id}, Team {team_id}, Games: {games_played}")
                
                try:
                    # Get team lineups for this season (Regular Season only)
                    lineups_data = get_league_dash_lineups(
                        team_id=int(team_id), 
                        season=season_id,
                        group_quantity="5",
                        per_mode_detailed="PerGame",
                        season_type_all_star="Regular Season"  # Only regular season games
                    )
                    
                    lineups = lineups_data.get('Lineups', [])
                    logger.debug(f"Found {len(lineups)} lineups for team {team_id} in {season_id}")
                    
                    # Process each lineup to find teammates
                    for lineup in lineups:
                        group_id = lineup.get('GROUP_ID', '')
                        games_played_together = lineup.get('GP', 0)
                        
                        # Skip lineups with no games played together
                        if games_played_together == 0:
                            continue
                        
                        # Parse GROUP_ID to extract player IDs
                        if group_id and group_id.startswith('-') and group_id.endswith('-'):
                            # Remove leading and trailing dashes, then split by dash
                            player_ids_str = group_id[1:-1]
                            player_ids = player_ids_str.split('-')
                            
                            # Convert to integers and filter out invalid IDs
                            for pid in player_ids:
                                if pid.isdigit():
                                    teammate_id = int(pid)
                                    if teammate_id != player.stats_id:  # Don't include the player themselves
                                        teammate_ids.add(teammate_id)
                                        logger.debug(f"Found teammate ID: {teammate_id} from season {season_id}")
                                        
                except Exception as e:
                    logger.warning(f"Error getting lineups for team {team_id} in {season_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error getting teammate IDs for {player.name}: {e}")
            
        logger.info(f"Found {len(teammate_ids)} total teammates for {player.name}")
        return teammate_ids

    def _get_current_season_teammate_ids_from_api(self, player):
        """Get current season teammate IDs from NBA API for a player."""
        from nbagrid_api_app.nba_api_wrapper import get_player_career_stats, get_league_dash_lineups
        
        teammate_ids = set()
        current_season = "2025-26"  # Current season to find active teammates
        
        try:
            # Get the player's career stats to see which teams they played for in each season
            career_data = get_player_career_stats(player.stats_id, per_mode36="PerGame")
            
            if 'SeasonTotalsRegularSeason' not in career_data:
                return teammate_ids
            
            # Process only the current season
            for season_data in career_data['SeasonTotalsRegularSeason']:
                season_id = season_data.get('SEASON_ID', '')
                team_id = season_data.get('TEAM_ID', '')
                games_played = season_data.get('GP', 0)
                
                # Skip if not current season, total entries, or seasons with no games
                if season_id != current_season or team_id == 0 or games_played == 0:
                    continue
                
                logger.debug(f"Processing {player.name} - Current season {season_id}, Team {team_id}, Games: {games_played}")
                
                try:
                    # Get team lineups for current season only (Regular Season only)
                    lineups_data = get_league_dash_lineups(
                        team_id=int(team_id), 
                        season=season_id,
                        group_quantity="5",
                        per_mode_detailed="PerGame",
                        season_type_all_star="Regular Season"  # Only regular season games
                    )
                    
                    lineups = lineups_data.get('Lineups', [])
                    logger.debug(f"Found {len(lineups)} lineups for team {team_id} in {season_id}")
                    
                    # Process each lineup to find teammates
                    for lineup in lineups:
                        group_id = lineup.get('GROUP_ID', '')
                        games_played_together = lineup.get('GP', 0)
                        
                        # Skip lineups with no games played together
                        if games_played_together == 0:
                            continue
                        
                        # Parse GROUP_ID to extract player IDs
                        if group_id and group_id.startswith('-') and group_id.endswith('-'):
                            # Remove leading and trailing dashes, then split by dash
                            player_ids_str = group_id[1:-1]
                            player_ids = player_ids_str.split('-')
                            
                            # Convert to integers and filter out invalid IDs
                            for pid in player_ids:
                                if pid.isdigit():
                                    teammate_id = int(pid)
                                    if teammate_id != player.stats_id:  # Don't include the player themselves
                                        teammate_ids.add(teammate_id)
                                        logger.debug(f"Found current season teammate ID: {teammate_id}")
                                        
                except Exception as e:
                    logger.warning(f"Error getting lineups for team {team_id} in {season_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error getting current season teammate IDs for {player.name}: {e}")
            
        if teammate_ids:
            logger.info(f"Found {len(teammate_ids)} current season teammates for {player.name}")
        return teammate_ids

    def _create_missing_teammate(self, stats_id):
        """Create a missing teammate player from NBA API data (current season only)."""
        from nbagrid_api_app.nba_api_wrapper import get_common_player_info
        from nba_api.stats.static import players as static_players
        
        try:
            # Get player info from NBA API
            player_info = get_common_player_info(stats_id)
            
            if not player_info or 'CommonPlayerInfo' not in player_info:
                logger.warning(f"No player info found for stats_id {stats_id}")
                return None
                
            player_data = player_info['CommonPlayerInfo'][0]
            
            # Additional validation: Check if player is currently active and has a valid team
            # This is a safety check since we're only processing current season teammates
            # but we want to be extra sure we don't create inactive players or players without teams
            from nba_api.stats.static import players as static_players_api
            
            try:
                # Check if player is in the active players list
                active_players = static_players_api.get_active_players()
                is_currently_active = any(p['id'] == stats_id for p in active_players)
                
                if not is_currently_active:
                    logger.warning(f"Player with stats_id {stats_id} is not currently active, skipping creation")
                    return None
                
                # Additional check: Verify the player has a valid current team
                current_team_id = player_data.get('TEAM_ID', 0)
                current_team_name = player_data.get('TEAM_NAME', '')
                
                if current_team_id == 0 or not current_team_name:
                    logger.warning(f"Player with stats_id {stats_id} has no current team (Team ID: {current_team_id}, Team: {current_team_name}), skipping creation")
                    return None
                    
            except Exception as e:
                logger.warning(f"Could not verify active status for stats_id {stats_id}: {e}")
                # Continue with creation but log the warning
            
            # Create the player
            player, created = Player.objects.get_or_create(
                stats_id=stats_id,
                defaults={
                    'name': static_players._strip_accents(player_data.get('DISPLAY_FIRST_LAST', '')),
                    'last_name': static_players._strip_accents(player_data.get('LAST_NAME', '')),
                    'display_name': player_data.get('DISPLAY_FIRST_LAST', ''),
                    'is_active': True,  # If they're found as a current season teammate, they should be active
                }
            )
            
            if created:
                logger.info(f"Created missing current season teammate: {player.name} (stats_id: {stats_id})")
            else:
                # Player already exists, just make sure they're active
                if not player.is_active:
                    player.is_active = True
                    player.save()
                    logger.info(f"Reactivated existing player: {player.name} (stats_id: {stats_id})")
            
            return player
            
        except Exception as e:
            logger.error(f"Failed to create missing teammate with stats_id {stats_id}: {e}")
            return None

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
            if not TELEGRAM_AVAILABLE:
                self.stdout.write(self.style.WARNING("Telegram module not available, skipping notification"))
                return
                
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
