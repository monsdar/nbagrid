import argparse
import sqlite3
from typing import Any, Dict

import requests


def get_local_teams(db_path: str) -> Dict[int, Dict[str, Any]]:
    """Fetch all teams from local SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()

    # Get all columns from the teams table
    cursor.execute("PRAGMA table_info(nbagrid_api_app_team)")
    columns = [col[1] for col in cursor.fetchall()]

    # Fetch all teams
    cursor.execute("SELECT * FROM nbagrid_api_app_team")
    teams = {}

    for row in cursor.fetchall():
        team_data = {}
        for col in columns:
            value = row[col]
            # Convert SQLite NULL to None
            if value is None:
                value = None
            team_data[col] = value

        teams[row["stats_id"]] = team_data

    conn.close()
    return teams


def sync_team_to_remote(stats_id: int, team_data: Dict[str, Any], remote_url: str, api_key: str) -> bool:
    """Sync a single team to the remote API."""
    try:
        response = requests.post(
            f"{remote_url}/team/{stats_id}", json=team_data, headers={"Content-Type": "application/json", "X-API-Key": api_key}
        )
        response.raise_for_status()
        print(f"Successfully synced team {stats_id}: {team_data.get('name', 'Unknown')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error syncing team {stats_id}: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Sync teams from local SQLite to remote nbagrid API")
    parser.add_argument("--db", default="db.sqlite3", help="Path to local SQLite database")
    parser.add_argument("--remote", required=True, help="Base URL of remote nbagrid API (e.g., http://remote-api.com)")
    parser.add_argument("--team", type=int, help="Specific team stats_id to sync (optional)")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    args = parser.parse_args()

    # Get all teams from local database
    teams = get_local_teams(args.db)

    if args.team:
        # Sync specific team if provided
        if args.team in teams:
            sync_team_to_remote(args.team, teams[args.team], args.remote, args.api_key)
        else:
            print(f"Team with stats_id {args.team} not found in local database")
    else:
        # Sync all teams
        success_count = 0
        total_count = len(teams)

        for stats_id, team_data in teams.items():
            if sync_team_to_remote(stats_id, team_data, args.remote, args.api_key):
                success_count += 1

        print(f"\nSync completed: {success_count}/{total_count} teams synced successfully")


if __name__ == "__main__":
    main()
