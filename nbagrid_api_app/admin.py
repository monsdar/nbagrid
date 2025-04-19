
from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect

from nba_api.stats.static import teams as static_teams
from nba_api.stats.static import players as static_players

import requests
import logging
import time

from .models import Player, Team

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    change_list_template = "admin/team_changelist.html"
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('read_teams_from_nba_stats/', self.read_teams_from_nba_stats),
        ]
        return my_urls + urls

    def read_teams_from_nba_stats(self, request):
        for team in static_teams.get_teams():
            Team.objects.get_or_create(
                stats_id=team['id'],
                defaults={
                    'name': team['full_name'],
                    'abbr': team['abbreviation'],
                    })
        self.message_user(request, "Successfully updated teams", level="success")
        return HttpResponseRedirect("../")

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    change_list_template = "admin/player_changelist.html"
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('init_players_from_static_players/', self.init_players_from_static_players),
            path('sync_players_from_nba_stats/', self.sync_player_data_from_nba_stats),
            path('sync_player_stats_from_nba_stats/', self.sync_player_stats_from_nba_stats),
        ]
        return my_urls + urls
    
    def init_players_from_static_players(self, request):
        self.init_players()
        self.message_user(request, "Successfully initialized players", level="success")
        return HttpResponseRedirect("../")
    
    def sync_player_data_from_nba_stats(self, request):
        self.sync_player_data()
        self.message_user(request, "Successfully synced player data", level="success")
        return HttpResponseRedirect("../")
            
    def sync_player_stats_from_nba_stats(self, request):
        self.sync_player_stats()
        self.message_user(request, "Successfully synced player stats", level="success")
        return HttpResponseRedirect("../")
    
    def init_players(self):
        # Create all active players that are in the static players list
        all_players = static_players.get_active_players()
        logger.info(f"Initing {len(all_players)} players...")
        for player in all_players:
            (new_player, has_created) = Player.objects.update_or_create(
                stats_id=player['id'],
                defaults={
                    'name': static_players._strip_accents(player['full_name']),
                    'display_name': player['full_name'],
                    })
            if has_created:
                new_player.save()
                logger.info(f"...created new player: {player['full_name']}")
    
        # Check for players that aren't in the static_players list and delete them
        all_players = Player.objects.all().values_list('stats_id', flat=True)
        all_static_player_ids = [static_player['id'] for static_player in static_players.get_active_players()]
        for player in all_players:
            if player not in all_static_player_ids:
                Player.objects.filter(stats_id=player).delete()
                logger.info(f"...deleted player: {player.name}")
    
    def sync_player_stats(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_stats_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0) # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player stats: {player.name}")
            time.sleep(0.25) # wait a bit before doing the next API request to not run into stats.nba rate limits
    
    def sync_player_data(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_data_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0) # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player data: {player.name}")
            time.sleep(0.25) # wait a bit before doing the next API request to not run into stats.nba rate limits
            