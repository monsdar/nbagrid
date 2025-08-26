import argparse
import sqlite3
from typing import Dict, List, Any
import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Sync player teammates from local SQLite database to remote nbagrid API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db',
            default='db.sqlite3',
            help='Path to local SQLite database'
        )
        parser.add_argument(
            '--remote',
            required=True,
            help='Base URL of remote nbagrid API (e.g., http://remote-api.com)'
        )
        parser.add_argument(
            '--player',
            type=int,
            help='Specific player stats_id to sync (optional)'
        )
        parser.add_argument(
            '--api-key',
            required=True,
            help='API key for authentication'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def get_local_teammates(self, db_path: str) -> Dict[int, List[int]]:
        """Fetch all player teammates from local SQLite database."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all players with their teammates
        cursor.execute("""
            SELECT 
                p1.stats_id as player_stats_id,
                p2.stats_id as teammate_stats_id
            FROM nbagrid_api_app_player p1
            JOIN nbagrid_api_app_player_teammates pt ON p1.id = pt.from_player_id
            JOIN nbagrid_api_app_player p2 ON pt.to_player_id = p2.id
            ORDER BY p1.stats_id, p2.stats_id
        """)
        
        teammates_data = {}
        for row in cursor.fetchall():
            player_id = row['player_stats_id']
            teammate_id = row['teammate_stats_id']
            
            if player_id not in teammates_data:
                teammates_data[player_id] = []
            teammates_data[player_id].append(teammate_id)

        conn.close()
        return teammates_data

    def sync_player_teammates_to_remote(
        self, 
        stats_id: int, 
        teammate_stats_ids: List[int], 
        remote_url: str, 
        api_key: str,
        dry_run: bool = False
    ) -> bool:
        """Sync a single player's teammates to the remote API."""
        if dry_run:
            self.stdout.write(f"  Would sync player {stats_id} with {len(teammate_stats_ids)} teammates")
            return True
            
        try:
            response = requests.post(
                f"{remote_url}/player/{stats_id}/teammates",
                json={"teammate_stats_ids": teammate_stats_ids},
                headers={"Content-Type": "application/json", "X-API-Key": api_key},
            )
            response.raise_for_status()
            self.stdout.write(f"  Successfully synced player {stats_id} with {len(teammate_stats_ids)} teammates")
            return True
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"  Error syncing player {stats_id}: {str(e)}"))
            return False

    def handle(self, *args, **options):
        db_path = options['db']
        remote_url = options['remote']
        player_stats_id = options['player']
        api_key = options['api_key']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get all teammates from local database
        self.stdout.write(f"Reading teammates from local database: {db_path}")
        teammates_data = self.get_local_teammates(db_path)

        if not teammates_data:
            self.stdout.write(self.style.WARNING('No teammate relationships found in local database'))
            return

        self.stdout.write(f"Found {len(teammates_data)} players with teammates")

        if player_stats_id:
            # Sync specific player if provided
            if player_stats_id in teammates_data:
                self.stdout.write(f"Syncing specific player {player_stats_id}")
                self.sync_player_teammates_to_remote(
                    player_stats_id, 
                    teammates_data[player_stats_id], 
                    remote_url, 
                    api_key,
                    dry_run
                )
            else:
                self.stdout.write(self.style.ERROR(f"Player with stats_id {player_stats_id} not found in local database"))
        else:
            # Sync all players
            success_count = 0
            total_count = len(teammates_data)

            self.stdout.write(f"Syncing {total_count} players to remote API: {remote_url}")

            for stats_id, teammate_stats_ids in teammates_data.items():
                if self.sync_player_teammates_to_remote(
                    stats_id, 
                    teammate_stats_ids, 
                    remote_url, 
                    api_key,
                    dry_run
                ):
                    success_count += 1

            self.stdout.write(f"\nSync completed: {success_count}/{total_count} players synced successfully")
