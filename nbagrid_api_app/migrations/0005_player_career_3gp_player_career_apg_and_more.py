# Generated by Django 5.2 on 2025-04-14 04:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nbagrid_api_app', '0004_alter_player_country'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='career_3gp',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_apg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_bpg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_fgp',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_ftp',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_3p',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_ast',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_blk',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_fg',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_ft',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_pts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_reb',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_high_stl',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_ppg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_rpg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='player',
            name='career_spg',
            field=models.FloatField(default=0.0),
        ),
    ]
