import sqlite3
import requests
from typing import Dict, Any
import argparse

def get_local_players(db_path: str) -> Dict[int, Dict[str, Any]]:
    """Fetch all players from local SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()
    
    # Get all columns from the players table
    cursor.execute("PRAGMA table_info(nbagrid_api_app_player)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Fetch all players
    cursor.execute("SELECT * FROM nbagrid_api_app_player")
    players = {}
    
    for row in cursor.fetchall():
        player_data = {}
        for col in columns:
            value = row[col]
            # Convert SQLite NULL to None
            if value is None:
                value = None
            # Convert boolean values
            elif col.startswith('is_'):
                value = bool(value)
            # Convert numeric values
            elif col.startswith(('career_', 'draft_', 'num_', 'weight_', 'height_')):
                value = float(value) if '.' in str(value) else int(value)
            player_data[col] = value
        
        players[row['stats_id']] = player_data
    
    conn.close()
    return players

def sync_player_to_remote(stats_id: int, player_data: Dict[str, Any], remote_url: str) -> bool:
    """Sync a single player to the remote API."""
    try:
        response = requests.post(
            f"{remote_url}/player/{stats_id}",
            json=player_data,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        print(f"Successfully synced player {stats_id}: {player_data.get('name', 'Unknown')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error syncing player {stats_id}: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Sync players from local SQLite to remote nbagrid API')
    parser.add_argument('--db', default='db.sqlite3', help='Path to local SQLite database')
    parser.add_argument('--remote', required=True, help='Base URL of remote nbagrid API (e.g., http://remote-api.com)')
    parser.add_argument('--player', type=int, help='Specific player stats_id to sync (optional)')
    args = parser.parse_args()
    
    # Get all players from local database
    players = get_local_players(args.db)
    
    if args.player:
        # Sync specific player if provided
        if args.player in players:
            sync_player_to_remote(args.player, players[args.player], args.remote)
        else:
            print(f"Player with stats_id {args.player} not found in local database")
    else:
        # Sync all players
        success_count = 0
        total_count = len(players)
        
        for stats_id, player_data in players.items():
            if sync_player_to_remote(stats_id, player_data, args.remote):
                print(f"\n...synced player {stats_id}: {player_data.get('name', 'Unknown')}")
                success_count += 1
        
        print(f"Sync completed: {success_count}/{total_count} players synced successfully")

if __name__ == "__main__":
    main() 