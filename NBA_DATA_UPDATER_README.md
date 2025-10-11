# NBA Grid Data Updater

This system streamlines NBA data updates with unified Django management commands that can run automatically on a Raspberry Pi.

## Management Commands

### `update_nba_data`

Comprehensive NBA data update command that replaces all admin panel operations.

#### Basic Usage
```bash
# Update everything
python manage.py update_nba_data --all

# Update specific components
python manage.py update_nba_data --players --teams --stats --awards --teammates

# Initialize data only (no API calls)
python manage.py update_nba_data --init-only

# Update specific players
python manage.py update_nba_data --players --player-ids 1234 5678
```

#### Advanced Options
```bash
# Continue processing even if some players fail
python manage.py update_nba_data --all --continue-on-error

# With production sync
python manage.py update_nba_data --all \
    --sync-to-production \
    --production-url https://api.nbagrid.com \
    --api-key YOUR_API_KEY

# Verbose logging
python manage.py update_nba_data --all --verbose

# With Telegram notifications
python manage.py update_nba_data --all --telegram-notify
```

#### Player Active Status Detection

The system automatically determines if players are active using the **`ROSTERSTATUS`** field from the NBA Stats API (`CommonPlayerInfo` endpoint):

- **Active players**: `ROSTERSTATUS = "Active"` → `is_active = True`
- **Inactive players**: `ROSTERSTATUS = "Inactive"` → `is_active = False`

This is more reliable than the `nba_api` static players list, which is often outdated. The `is_active` field is updated when running:
```bash
# Update player data (includes ROSTERSTATUS check)
python manage.py update_nba_data --players

# Or update everything
python manage.py update_nba_data --all
```

**Note:** The `--init-only` flag only initializes basic player data from the static list. To get accurate active/inactive status, you must run with `--players` or `--all` to fetch live data from the NBA API.

### `sync_to_production`

Dedicated command for syncing local data to production (replaces sync_*.py scripts).

#### Basic Usage
```bash
# Sync everything
python manage.py sync_to_production \
    --production-url https://api.nbagrid.com \
    --api-key YOUR_API_KEY \
    --all

# Sync specific data types
python manage.py sync_to_production \
    --production-url https://api.nbagrid.com \
    --api-key YOUR_API_KEY \
    --players --teams

# Sync specific entities
python manage.py sync_to_production \
    --production-url https://api.nbagrid.com \
    --api-key YOUR_API_KEY \
    --players --player-ids 1234 5678
```

#### Advanced Options
```bash
# Custom timeout and error handling
python manage.py sync_to_production \
    --production-url https://api.nbagrid.com \
    --api-key YOUR_API_KEY \
    --all \
    --batch-size 5 \
    --timeout 60 \
    --max-retries 3

# Dry run
python manage.py sync_to_production \
    --production-url https://api.nbagrid.com \
    --api-key YOUR_API_KEY \
    --all --dry-run
```

## Docker Deployment

### Local Docker Testing
```bash
# Build the image
docker-compose -f docker-compose.updater.yml build

# Run a test update
docker-compose -f docker-compose.updater.yml run --rm nbagrid-updater \
    python manage.py update_nba_data --all --dry-run

# Run with production sync
docker-compose -f docker-compose.updater.yml run --rm nbagrid-updater \
    python manage.py update_nba_data --all \
    --sync-to-production \
    --production-url $PRODUCTION_URL \
    --api-key $API_KEY
```

## Configuration

### Environment Variables (.env)
```bash
# Required
PRODUCTION_URL=https://your-production-api.com
API_KEY=your-api-key-here

# Optional
SYNC_ENABLED=true
UPDATE_TIMEOUT=3600
CLEANUP_LOGS_DAYS=30
NOTIFICATION_WEBHOOK=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
NOTIFY_SUCCESS=false

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
```

### Telegram Setup

To receive push notifications about nightly data updates:

1. **Create a Telegram Bot:**
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow the instructions
   - Save the bot token provided

2. **Get Your Chat ID:**
   - Start a conversation with your bot
   - Send any message to the bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

3. **Configure Environment Variables:**
   ```bash
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

4. **Test Notifications:**
   ```bash
   python manage.py update_nba_data --init-only --telegram-notify
   ```

#### Telegram Command Options
```bash
# Use environment variables
python manage.py update_nba_data --all --telegram-notify

# Override with command line options
python manage.py update_nba_data --all --telegram-notify \
    --telegram-bot-token YOUR_BOT_TOKEN \
    --telegram-chat-id YOUR_CHAT_ID
```

## Automation & Scheduling

### Nightly Updates with Telegram Notifications

For automated nightly updates with push notifications:

```bash
# Add to crontab (crontab -e)
# Run every night at 2:00 AM
0 2 * * * cd /path/to/nbagrid_api && python manage.py update_nba_data --all --telegram-notify --sync-to-production --production-url $PRODUCTION_URL --api-key $API_KEY >> logs/nba_update_cron.log 2>&1
```

### Docker Cron Example

```bash
# docker-compose.cron.yml
version: '3.8'
services:
  nbagrid-scheduler:
    build:
      context: .
      dockerfile: Dockerfile.updater
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - PRODUCTION_URL=${PRODUCTION_URL}
      - API_KEY=${API_KEY}
    command: >
      sh -c "echo '0 2 * * * cd /app && python manage.py update_nba_data --all --telegram-notify --sync-to-production --production-url $$PRODUCTION_URL --api-key $$API_KEY' | crontab - && crond -f"
```

## Monitoring and Logging

### Log Files
- `logs/nba_update_YYYYMMDD_HHMMSS.log` - Detailed update logs
- `logs/nba_update_latest.log` - Latest update log
- `logs/nba_update_errors.log` - Error-only log
- `logs/cron.log` - Cron execution log

## Troubleshooting


### 3. Replace Old Workflow
- **Remove**: Manual admin panel operations
- **Remove**: `sync_players.py`, `sync_teams.py`, `sync_player_teams.py` scripts
- **Replace with**: `python manage.py update_nba_data --all --sync-to-production`
