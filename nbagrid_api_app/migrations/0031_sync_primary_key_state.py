# Migration to sync Django's migration state with actual database schema

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nbagrid_api_app', '0030_change_primary_keys'),
    ]

    operations = [
        # First add the id fields to Django's state
        migrations.AddField(
            model_name='gridmetadata',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AddField(
            model_name='gamegrid',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        
        # Then update the date fields
        migrations.AlterField(
            model_name='gridmetadata',
            name='date',
            field=models.DateField(unique=True),
        ),
        migrations.AlterField(
            model_name='gamegrid',
            name='date',
            field=models.DateField(unique=True),
        ),
    ]
