"""Admin views for managing All-NBA team winners"""

import logging

from nba_api.stats.static import players as static_players

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path

from ..models import LastUpdated, Player

logger = logging.getLogger(__name__)

# Static lists of All-NBA team winners by name
static_all_nba_first_team = [
    # 2024-25 Season
    "Nikola Jokić",
    "Shai Gilgeous-Alexander",
    "Giannis Antetokounmpo",
    "Jayson Tatum",
    "Donovan Mitchell",
]

static_all_nba_second_team = [
    # 2024-25 Season
    "Jalen Brunson",
    "Stephen Curry",
    "Anthony Edwards",
    "LeBron James",
    "Evan Mobley",
]

static_all_nba_third_team = [
    # 2024-25 Season
    "Cade Cunningham",
    "Tyrese Haliburton",
    "James Harden",
    "Karl-Anthony Towns",
    "Jalen Williams",
]

static_all_nba_rookie_team = [
    # 2024-25 Season
    "Stephon Castle",
    "Zaccharie Risacher",
    "Jaylen Wells",
    "Zach Edey",
    "Alex Sarr",
    "Kel'el Ware",
    "Matas Buzelis",
    "Yves Missi",
    "Donovan Clingan",
    "Bub Carrington",
]

static_all_nba_defensive_team = [
    # 2024-25 Season
    "Dyson Daniels",
    "Luguentz Dort",
    "Draymond Green",
    "Evan Mobley",
    "Amen Thompson",
    "Toumani Camara",
    "Rudy Gobert",
    "Jaren Jackson Jr.",
    "Jalen Williams",
    "Ivica Zubac",
]


class PlayerStaticAllNbaAdmin(admin.ModelAdmin):
    """Admin view for managing All-NBA team winners"""

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("update_all_nba_teams/", self.update_all_nba_teams),
        ]
        return my_urls + urls

    def update_all_nba_teams(self, request):
        """Update All-NBA team status for players based on static lists"""
        first_team_count = 0
        second_team_count = 0
        third_team_count = 0
        rookie_team_count = 0
        defensive_team_count = 0

        # Update first team winners
        for player_name in static_all_nba_first_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_first = True
                player.save()
                first_team_count += 1

        # Update second team winners
        for player_name in static_all_nba_second_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_second = True
                player.save()
                second_team_count += 1

        # Update third team winners
        for player_name in static_all_nba_third_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_third = True
                player.save()
                third_team_count += 1

        # Update rookie team winners
        for player_name in static_all_nba_rookie_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_rookie = True
                player.save()
                rookie_team_count += 1

        # Update defensive team winners
        for player_name in static_all_nba_defensive_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_defensive = True
                player.save()
                defensive_team_count += 1

        # Record the update timestamp
        LastUpdated.update_timestamp(
            data_type="all_nba_teams_update",
            updated_by=f"Admin ({request.user.username})",
            notes=f"Updated All-NBA team winners: {first_team_count} first team, {second_team_count} second team, {third_team_count} third team, {rookie_team_count} rookie team, {defensive_team_count} defensive team",
        )

        self.message_user(
            request,
            f"Successfully updated All-NBA team winners: {first_team_count} first team, {second_team_count} second team, {third_team_count} third team, {rookie_team_count} rookie team, {defensive_team_count} defensive team",
            level="success",
        )
        return HttpResponseRedirect("../")
