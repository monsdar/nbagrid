"""
Management command to sync local NBA data to production.

This command replaces the separate sync_*.py scripts with a unified Django management command
that can sync players, teams, and player-team relationships to production.

Usage:
    python manage.py sync_to_production --production-url https://api.nbagrid.com --api-key YOUR_KEY --all
    python manage.py sync_to_production --production-url https://api.nbagrid.com --api-key YOUR_KEY --players --teams
    python manage.py sync_to_production --production-url https://api.nbagrid.com --api-key YOUR_KEY --player-ids 1234 5678
"""

import logging
import time
from typing import Dict, Any, List, Tuple

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from nbagrid_api_app.models import Player, Team, LastUpdated

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync local NBA data to production API'

    def add_arguments(self, parser):
        # Required arguments
        parser.add_argument(
            '--production-url',
            type=str,
            required=True,
            help='Base URL of production API (e.g., https://api.nbagrid.com)'
        )
        parser.add_argument(
            '--api-key',
            type=str,
            required=True,
            help='API key for production authentication'
        )
        
        # What to sync
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all data (players, teams, relationships)'
        )
        parser.add_argument(
            '--players',
            action='store_true',
            help='Sync player data'
        )
        parser.add_argument(
            '--teams',
            action='store_true',
            help='Sync team data'
        )
        parser.add_argument(
            '--player-teams',
            action='store_true',
            help='Sync player-team relationships'
        )
        
        # Filtering options
        parser.add_argument(
            '--player-ids',
            nargs='+',
            type=int,
            help='Specific player stats_ids to sync'
        )
        parser.add_argument(
            '--team-ids',
            nargs='+',
            type=int,
            help='Specific team stats_ids to sync'
        )
        
        # Sync options
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of entities to sync in each batch (default: 10)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.1,
            help='Delay between API calls in seconds (default: 0.1)'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Request timeout in seconds (default: 30)'
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Maximum number of retries for failed requests (default: 3)'
        )
        
        # Utility options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making actual requests'
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
        
        start_time = timezone.now()
        
        try:
            # Execute sync operations
            self._sync_data(options)
                
        except Exception as e:
            logger.error(f"Sync command failed: {e}")
            raise CommandError(f"Production sync failed: {e}")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        self.stdout.write(
            self.style.SUCCESS(f"Production sync completed successfully in {duration:.1f} seconds")
        )

    def _validate_arguments(self, options):
        """Validate command arguments."""
        # If no specific sync options are given, default to --all
        if not any([
            options['all'], options['players'], options['teams'], options['player_teams']
        ]):
            options['all'] = True
            self.stdout.write(
                self.style.WARNING("No specific sync options provided, defaulting to --all")
            )
        
        # Validate production URL format
        production_url = options['production_url'].rstrip('/')
        if not production_url.startswith(('http://', 'https://')):
            raise CommandError("Production URL must start with http:// or https://")
        
        options['production_url'] = production_url

    def _show_configuration(self, options):
        """Display the current configuration."""
        self.stdout.write(self.style.HTTP_INFO("=== Production Sync Configuration ==="))
        
        operations = []
        if options['all']:
            operations.append("All data (players, teams, relationships)")
        else:
            if options['players']: operations.append("Players")
            if options['teams']: operations.append("Teams")
            if options['player_teams']: operations.append("Player-team relationships")
        
        self.stdout.write(f"Operations: {', '.join(operations)}")
        self.stdout.write(f"Production URL: {options['production_url']}")
        self.stdout.write(f"Batch size: {options['batch_size']}")
        self.stdout.write(f"Request delay: {options['delay']}s")
        self.stdout.write(f"Request timeout: {options['timeout']}s")
        self.stdout.write(f"Max retries: {options['max_retries']}")
        
        if options['player_ids']:
            self.stdout.write(f"Player IDs filter: {options['player_ids']}")
        if options['team_ids']:
            self.stdout.write(f"Team IDs filter: {options['team_ids']}")
            
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No requests will be made"))
            
        self.stdout.write("=" * 50)

    def _sync_data(self, options):
        """Sync data based on options."""
        if options['all'] or options['teams']:
            self._sync_teams(options)
            
        if options['all'] or options['players']:
            self._sync_players(options)
            
        if options['all'] or options['player_teams']:
            self._sync_player_teams(options)

    def _sync_teams(self, options):
        """Sync team data to production."""
        self.stdout.write("Syncing teams to production...")
        
        # Get teams to sync
        if options['team_ids']:
            teams = Team.objects.filter(stats_id__in=options['team_ids'])
        else:
            teams = Team.objects.all()
        
        total_teams = teams.count()
        
        if total_teams == 0:
            self.stdout.write(self.style.WARNING("No teams found to sync"))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would sync {total_teams} teams"))
            return
        
        success_count = 0
        error_count = 0
        
        for team in teams:
            team_data = self._serialize_team(team)
            
            if self._sync_entity_to_production(
                f"/team/{team.stats_id}",
                team_data,
                f"team {team.stats_id}: {team.name}",
                options
            ):
                success_count += 1
            else:
                error_count += 1
            
            # Rate limiting
            if options['delay'] > 0:
                time.sleep(options['delay'])
        
        self.stdout.write(
            self.style.SUCCESS(f"Teams sync completed: {success_count} successful, {error_count} errors")
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('team_sync', 'sync_to_production command')

    def _sync_players(self, options):
        """Sync player data to production."""
        self.stdout.write("Syncing players to production...")
        
        # Get players to sync
        if options['player_ids']:
            players = Player.active.filter(stats_id__in=options['player_ids'])
        else:
            players = Player.active.all()
        
        total_players = players.count()
        
        if total_players == 0:
            self.stdout.write(self.style.WARNING("No players found to sync"))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would sync {total_players} players"))
            return
        
        success_count = 0
        error_count = 0
        batch_size = options['batch_size']
        
        self.stdout.write(f"Processing {total_players} players in batches of {batch_size}...")
        
        for i in range(0, total_players, batch_size):
            batch = players[i:i + batch_size]
            self.stdout.write(f"Processing batch {i//batch_size + 1}/{(total_players + batch_size - 1)//batch_size}...")
            
            for player in batch:
                player_data = self._serialize_player(player)
                
                if self._sync_entity_to_production(
                    f"/player/{player.stats_id}",
                    player_data,
                    f"player {player.stats_id}: {player.name}",
                    options
                ):
                    success_count += 1
                else:
                    error_count += 1
                
                # Rate limiting
                if options['delay'] > 0:
                    time.sleep(options['delay'])
        
        self.stdout.write(
            self.style.SUCCESS(f"Players sync completed: {success_count} successful, {error_count} errors")
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_sync', 'sync_to_production command')

    def _sync_player_teams(self, options):
        """Sync player-team relationships to production."""
        self.stdout.write("Syncing player-team relationships to production...")
        
        # Get relationships from database
        relationships = self._get_player_team_relationships(options)
        
        total_relationships = len(relationships)
        
        if total_relationships == 0:
            self.stdout.write(self.style.WARNING("No player-team relationships found to sync"))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would sync {total_relationships} relationships"))
            return
        
        success_count = 0
        error_count = 0
        
        for player_stats_id, team_stats_id in relationships:
            if self._sync_entity_to_production(
                f"/player/{player_stats_id}/team/{team_stats_id}",
                {},  # No data payload for relationship endpoints
                f"relationship Player {player_stats_id} - Team {team_stats_id}",
                options
            ):
                success_count += 1
            else:
                error_count += 1
            
            # Rate limiting
            if options['delay'] > 0:
                time.sleep(options['delay'])
        
        self.stdout.write(
            self.style.SUCCESS(f"Relationships sync completed: {success_count} successful, {error_count} errors")
        )
        
        # Update timestamp
        LastUpdated.update_timestamp('player_team_sync', 'sync_to_production command')

    def _get_player_team_relationships(self, options) -> List[Tuple[int, int]]:
        """Get player-team relationships from database."""
        with connection.cursor() as cursor:
            # Build the query based on filters
            base_query = """
                SELECT p.stats_id as player_stats_id, t.stats_id as team_stats_id
                FROM nbagrid_api_app_player_teams pt
                JOIN nbagrid_api_app_player p ON pt.player_id = p.id
                JOIN nbagrid_api_app_team t ON pt.team_id = t.id
            """
            
            conditions = []
            params = []
            
            if options['player_ids']:
                placeholders = ','.join(['%s'] * len(options['player_ids']))
                conditions.append(f"p.stats_id IN ({placeholders})")
                params.extend(options['player_ids'])
            
            if options['team_ids']:
                placeholders = ','.join(['%s'] * len(options['team_ids']))
                conditions.append(f"t.stats_id IN ({placeholders})")
                params.extend(options['team_ids'])
            
            if conditions:
                query = base_query + " WHERE " + " AND ".join(conditions)
            else:
                query = base_query
            
            cursor.execute(query, params)
            return [(row[0], row[1]) for row in cursor.fetchall()]

    def _serialize_player(self, player: Player) -> Dict[str, Any]:
        """Serialize player data for API sync."""
        # Get all model fields except relations
        data = {}
        
        for field in player._meta.fields:
            if not field.is_relation:
                value = getattr(player, field.name)
                # Convert any special types if needed
                if hasattr(value, 'isoformat'):  # datetime objects
                    value = value.isoformat()
                data[field.name] = value
        
        return data

    def _serialize_team(self, team: Team) -> Dict[str, Any]:
        """Serialize team data for API sync."""
        data = {}
        
        for field in team._meta.fields:
            if not field.is_relation:
                value = getattr(team, field.name)
                # Convert any special types if needed
                if hasattr(value, 'isoformat'):  # datetime objects
                    value = value.isoformat()
                data[field.name] = value
        
        return data

    def _sync_entity_to_production(self, endpoint: str, data: Dict[str, Any], description: str, options) -> bool:
        """Sync a single entity to production with retry logic."""
        url = options['production_url'] + endpoint
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": options['api_key']
        }
        
        max_retries = options['max_retries']
        timeout = options['timeout']
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json=data,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()
                
                logger.debug(f"Successfully synced {description}")
                return True
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Error syncing {description} (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to sync {description} after {max_retries + 1} attempts: {e}")
                    return False
        
        return False
