import sqlite3
import requests
from typing import Dict, List, Tuple
import argparse

def get_player_team_relationships(db_path: str) -> List[Tuple[int, int]]:
    """Fetch all player-team relationships from local SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Fetch all relationships from the junction table
    cursor.execute("""
        SELECT player_id, team_id 
        FROM nbagrid_api_app_player_teams
    """)
    
    relationships = []
    for row in cursor.fetchall():
        # Get the stats_id for both player and team
        cursor.execute("SELECT stats_id FROM nbagrid_api_app_player WHERE id = ?", (row['player_id'],))
        player_stats_id = cursor.fetchone()['stats_id']
        
        cursor.execute("SELECT stats_id FROM nbagrid_api_app_team WHERE id = ?", (row['team_id'],))
        team_stats_id = cursor.fetchone()['stats_id']
        
        relationships.append((player_stats_id, team_stats_id))
    
    conn.close()
    return relationships

def sync_player_team_relationship(player_stats_id: int, team_stats_id: int, remote_url: str, api_key: str) -> bool:
    """Sync a single player-team relationship to the remote API."""
    try:
        response = requests.post(
            f"{remote_url}/player/{player_stats_id}/team/{team_stats_id}",
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': api_key
            }
        )
        response.raise_for_status()
        print(f"Successfully synced relationship: Player {player_stats_id} - Team {team_stats_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error syncing relationship Player {player_stats_id} - Team {team_stats_id}: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Sync player-team relationships from local SQLite to remote nbagrid API')
    parser.add_argument('--db', default='db.sqlite3', help='Path to local SQLite database')
    parser.add_argument('--remote', required=True, help='Base URL of remote nbagrid API (e.g., http://remote-api.com)')
    parser.add_argument('--player', type=int, help='Specific player stats_id to sync (optional)')
    parser.add_argument('--api-key', required=True, help='API key for authentication')
    args = parser.parse_args()
    
    # Get all relationships from local database
    relationships = get_player_team_relationships(args.db)
    
    if args.player:
        # Filter relationships for specific player
        relationships = [(p, t) for p, t in relationships if p == args.player]
        if not relationships:
            print(f"No team relationships found for player {args.player}")
            return
    
    # Sync all relationships
    success_count = 0
    total_count = len(relationships)
    
    for player_stats_id, team_stats_id in relationships:
        if sync_player_team_relationship(player_stats_id, team_stats_id, args.remote, args.api_key):
            success_count += 1
    
    print(f"\nSync completed: {success_count}/{total_count} relationships synced successfully")

if __name__ == "__main__":
    main() 