import os
import django
from django.core.management import call_command
from django.conf import settings
import mysql.connector
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_file = Path(__file__).resolve().parent / '.env'
if env_file.exists():
    print(f"Loading environment variables from .env file in {env_file.absolute()}!")
    load_dotenv(env_file, override=True)
else:
    print(f"No .env file found in {env_file.absolute()}, using predefined environment variables or default values!")

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nbagrid_api.settings')
django.setup()

def create_mysql_database():
    """Create MySQL database if it doesn't exist."""
    # MySQL connection parameters from environment variables
    mysql_config = {
        'host': os.environ.get('MYSQL_ADDRESS', 'localhost'),
        'user': os.environ.get('MYSQL_USER'),
        'password': os.environ.get('MYSQL_PASSWORD'),
        'database': os.environ.get('MYSQL_DATABASE', 'nbagrid_db')
    }
    
    # Validate required environment variables
    if not mysql_config['user'] or not mysql_config['password']:
        raise ValueError("MYSQL_USER and MYSQL_PASSWORD must be set in .env file")
    
    # Connect to MySQL server without specifying database
    conn = mysql.connector.connect(
        host=mysql_config['host'],
        user=mysql_config['user'],
        password=mysql_config['password']
    )
    cursor = conn.cursor()
    
    # Create database if it doesn't exist
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_config['database']}")
    cursor.close()
    conn.close()
    
    return mysql_config

def update_django_settings(mysql_config):
    """Update Django settings to use MySQL."""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': mysql_config['database'],
        'USER': mysql_config['user'],
        'PASSWORD': mysql_config['password'],
        'HOST': mysql_config['host'],
        'PORT': '3306',
    }

def migrate_data():
    """Migrate data from SQLite to MySQL."""
    # First, dump data from SQLite while still using SQLite configuration
    sqlite_db = Path(settings.BASE_DIR) / 'db.sqlite3'
    if not sqlite_db.exists():
        print("SQLite database not found!")
        return
    
    # Create a temporary file for the dump
    dump_file = 'db_dump.json'
    
    # Dump data from SQLite
    print("Dumping data from SQLite...")
    call_command('dumpdata', '--natural-foreign', '--natural-primary', '-e', 'contenttypes', '-e', 'auth.permission', output=dump_file)
    
    # Now switch to MySQL configuration
    mysql_config = create_mysql_database()
    update_django_settings(mysql_config)
    
    # Run migrations on MySQL database
    print("Running migrations on MySQL database...")
    call_command('migrate')
    
    # Load data into MySQL
    print("Loading data into MySQL...")
    call_command('loaddata', dump_file)
    
    # Clean up
    os.remove(dump_file)
    print("Migration completed successfully!")

if __name__ == '__main__':
    migrate_data() 