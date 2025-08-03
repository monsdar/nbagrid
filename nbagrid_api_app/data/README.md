# Test Data Import

This directory contains JSON files with test data for the NBA Grid application.

## Files

- `teams.json`: Contains all 30 NBA teams with real team names, abbreviations, and stats IDs
- `player_archetypes.json`: Contains 10 player archetypes representing different types of NBA players with realistic statistics

## Usage

### Manual Import

To manually import test data, use the Django management command:

```bash
python manage.py import_test_data --force
```

### Automatic Import

Set the `IMPORT_TEST_DATA` environment variable to automatically import test data when the application starts and the database is empty:

```bash
export IMPORT_TEST_DATA=1
python manage.py runserver
```

The automatic import will:
- Only run if `IMPORT_TEST_DATA` is set to `1`, `true`, or `yes`
- Only import data if both Player and Team tables are empty
- Generate 500 players from the 10 archetypes with statistical variations
- Assign each player to 1-3 random teams
- Skip import if data already exists (unless `--force` is used)

## Data Structure

### Teams
Each team has:
- `stats_id`: NBA API stats ID
- `name`: Full team name
- `abbr`: 3-letter abbreviation

### Player Archetypes
Each archetype includes:
- Basic info: name, position, height, weight, country
- Career statistics: PPG, APG, RPG, shooting percentages, etc.
- Career highs: Best single-game performances
- Draft information: year, round, pick number
- Awards: All-Star, MVP, championships, etc.

The import process creates 50 variations of each archetype (500 total players) with ±10% statistical variation to create diversity while maintaining realistic player profiles.