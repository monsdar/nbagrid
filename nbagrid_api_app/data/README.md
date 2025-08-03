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

## Loading Real NBA Data

For development and testing purposes, you can also load real NBA player data from the NBA API:

### Loading Individual Players

```bash
# Load data for existing players
python manage.py load_nba_player 1628378 2544 201142

# Create and load data for new players
python manage.py load_nba_player 1628378 --create --name "Donovan Mitchell"
```

### Using the Model Methods

You can also use the Player model methods directly in your code:

```python
from nbagrid_api_app.models import Player

# Create a player and load all data from NBA API
player = Player.objects.create(stats_id=1628378, name="Donovan Mitchell")
player.load_from_nba_api()  # Loads basic info, stats, and awards

# Or load data separately
player.update_player_data_from_nba_stats()    # Basic info (position, draft, etc.)
player.update_player_stats_from_nba_stats()   # Career statistics
player.update_player_awards_from_nba_stats()  # Awards and achievements
```

**Note**: Loading real NBA data requires internet access and may be subject to NBA API rate limits and availability.