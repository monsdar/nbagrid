"""Admin views for Player model"""

import logging
import time

import requests
from nba_api.stats.static import players as static_players

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.template.response import TemplateResponse
import os
from django.conf import settings

from nbagrid_api_app.admin.player_salary_spotrac_admin import PlayerSalarySpotracAdmin
from nbagrid_api_app.admin.player_static_all_nba_admin import PlayerStaticAllNbaAdmin
from nbagrid_api_app.admin.player_static_olympians_admin import PlayerStaticOlympiansAdmin
from nbagrid_api_app.models import Player, GameResult

logger = logging.getLogger(__name__)


@admin.register(Player)
class PlayerAdmin(PlayerStaticOlympiansAdmin, PlayerStaticAllNbaAdmin, PlayerSalarySpotracAdmin):
    change_list_template = "admin/player_changelist.html"
    list_display = (
        "name",
        "position",
        "country",
        "is_award_olympic_gold_medal",
        "is_award_olympic_silver_medal",
        "is_award_olympic_bronze_medal",
        "base_salary",
    )
    list_filter = (
        "position",
        "country",
        "is_award_olympic_gold_medal",
        "is_award_olympic_silver_medal",
        "is_award_olympic_bronze_medal",
    )
    search_fields = ("name", "display_name")

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("init_players_from_static_players/", self.init_players_from_static_players),
            path("sync_players_from_nba_stats/", self.sync_player_data_from_nba_stats),
            path("sync_player_stats_from_nba_stats/", self.sync_player_stats_from_nba_stats),
            path("sync_player_awards_from_nba_stats/", self.sync_player_awards_from_nba_stats),
            path("ranking_by_guesses/", self.ranking_by_guesses_view, name="player_ranking_by_guesses"),
            path("ranking_by_user_guesses/", self.ranking_by_user_guesses_view, name="player_ranking_by_user_guesses"),
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

    def sync_player_awards_from_nba_stats(self, request):
        self.sync_player_awards()
        self.message_user(request, "Successfully synced player awards", level="success")
        return HttpResponseRedirect("../")

    def ranking_by_guesses_view(self, request):
        """Display ranking of players by total guess count"""
        ranking = GameResult.get_player_ranking_by_guesses()
        
        # Add portrait availability information
        ranking_with_portraits = []
        for player, total_guesses, total_user_guesses, total_wrong_guesses in ranking:
            has_portrait = self._check_portrait_availability(player.stats_id)
            ranking_with_portraits.append({
                'player': player,
                'total_guesses': total_guesses,
                'total_user_guesses': total_user_guesses,
                'total_wrong_guesses': total_wrong_guesses,
                'has_portrait': has_portrait,
                'stats_id': player.stats_id,
            })
        
        context = {
            'title': 'Player Ranking by Total Guesses',
            'ranking': ranking_with_portraits,
            'sort_type': 'total_guesses',
            'opts': self.model._meta,
        }
        
        return TemplateResponse(request, 'admin/player_ranking.html', context)
    
    def ranking_by_user_guesses_view(self, request):
        """Display ranking of players by user guess count (excluding initial guesses)"""
        ranking = GameResult.get_player_ranking_by_user_guesses()
        
        # Add portrait availability information
        ranking_with_portraits = []
        for player, total_user_guesses, total_guesses, total_wrong_guesses in ranking:
            has_portrait = self._check_portrait_availability(player.stats_id)
            ranking_with_portraits.append({
                'player': player,
                'total_guesses': total_guesses,
                'total_user_guesses': total_user_guesses,
                'total_wrong_guesses': total_wrong_guesses,
                'has_portrait': has_portrait,
                'stats_id': player.stats_id,
            })
        
        context = {
            'title': 'Player Ranking by User Guesses',
            'ranking': ranking_with_portraits,
            'sort_type': 'user_guesses',
            'opts': self.model._meta,
        }
        
        return TemplateResponse(request, 'admin/player_ranking.html', context)
    
    def _check_portrait_availability(self, stats_id):
        """Check if a player portrait is available"""
        # Check in staticfiles directory first (for production)
        static_portrait_path = os.path.join(settings.STATIC_ROOT, 'entity_images', f'{stats_id}.png')
        if os.path.exists(static_portrait_path):
            return True
        
        # Check in static directory (for development)
        static_portrait_path = os.path.join(settings.BASE_DIR, 'static', 'entity_images', f'{stats_id}.png')
        if os.path.exists(static_portrait_path):
            return True
        
        return False

    def init_players(self):
        # Create all active players that are in the static players list
        all_players = static_players.get_active_players()
        logger.info(f"Initing {len(all_players)} players...")
        for player in all_players:
            (new_player, has_created) = Player.objects.update_or_create(
                stats_id=player["id"],
                defaults={
                    "name": static_players._strip_accents(player["full_name"]),
                    "last_name": static_players._strip_accents(player["last_name"]),
                    "display_name": player["full_name"],
                },
            )
            if has_created:
                new_player.save()
                logger.info(f"...created new player: {player['full_name']}")

        # Check for players that aren't in the static_players list and delete them
        all_players = Player.objects.all().values_list("stats_id", flat=True)
        all_static_player_ids = [static_player["id"] for static_player in static_players.get_active_players()]
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
                time.sleep(10.0)  # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player stats: {player.name}")
            time.sleep(0.25)  # wait a bit before doing the next API request to not run into stats.nba rate limits

    def sync_player_awards(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_awards_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0)  # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player awards: {player.name}")
            time.sleep(0.25)  # wait a bit before doing the next API request to not run into stats.nba rate limits

    def sync_player_data(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_data_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0)  # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player data: {player.name}")
            time.sleep(0.25)  # wait a bit before doing the next API request to not run into stats.nba rate limits
