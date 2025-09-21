# Generated manually to handle primary key change properly

from django.db import migrations, models


def change_primary_key_forward(apps, schema_editor):
    """Change primary key from date to id using raw SQL"""
    if schema_editor.connection.vendor == 'postgresql':
        # PostgreSQL specific operations
        schema_editor.execute("""
            -- Add the new id column
            ALTER TABLE nbagrid_api_app_gamegrid ADD COLUMN id SERIAL;
            
            -- Drop the existing primary key constraint
            ALTER TABLE nbagrid_api_app_gamegrid DROP CONSTRAINT nbagrid_api_app_gamegrid_pkey;
            
            -- Add primary key constraint to the new id column
            ALTER TABLE nbagrid_api_app_gamegrid ADD PRIMARY KEY (id);
            
            -- Add unique constraint to date column
            ALTER TABLE nbagrid_api_app_gamegrid ADD CONSTRAINT nbagrid_api_app_gamegrid_date_unique UNIQUE (date);
        """)
    else:
        # SQLite and other databases
        schema_editor.execute("""
            -- For SQLite, we need to recreate the table
            CREATE TABLE nbagrid_api_app_gamegrid_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                grid_size INTEGER NOT NULL DEFAULT 3,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                cell_correct_players TEXT NOT NULL DEFAULT '{}'
            );
            
            -- Copy data from old table to new table
            INSERT INTO nbagrid_api_app_gamegrid_new (date, grid_size, created_at, updated_at, cell_correct_players)
            SELECT date, grid_size, created_at, updated_at, cell_correct_players FROM nbagrid_api_app_gamegrid;
            
            -- Drop old table
            DROP TABLE nbagrid_api_app_gamegrid;
            
            -- Rename new table
            ALTER TABLE nbagrid_api_app_gamegrid_new RENAME TO nbagrid_api_app_gamegrid;
        """)


def change_primary_key_reverse(apps, schema_editor):
    """Reverse the primary key change"""
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            -- Drop the unique constraint on date
            ALTER TABLE nbagrid_api_app_gamegrid DROP CONSTRAINT nbagrid_api_app_gamegrid_date_unique;
            
            -- Drop the id primary key
            ALTER TABLE nbagrid_api_app_gamegrid DROP CONSTRAINT nbagrid_api_app_gamegrid_pkey;
            
            -- Drop the id column
            ALTER TABLE nbagrid_api_app_gamegrid DROP COLUMN id;
            
            -- Add primary key back to date
            ALTER TABLE nbagrid_api_app_gamegrid ADD PRIMARY KEY (date);
        """)
    else:
        # SQLite reverse operations would be more complex
        # For now, we'll leave this as a no-op for SQLite
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('nbagrid_api_app', '0030_change_gridmetadata_primary_key'),
    ]

    operations = [
        migrations.RunPython(
            change_primary_key_forward,
            change_primary_key_reverse,
        ),
    ]
