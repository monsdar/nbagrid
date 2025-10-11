"""Admin views for managing Olympic medal winners"""

import logging

from nba_api.stats.static import players as static_players

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path

from nbagrid_api_app.models import LastUpdated, Player

logger = logging.getLogger(__name__)

# Static lists of Olympic medal winners by name
static_olympic_gold_winners = [
    # Add Olympic gold medal winners here (empty by default)
]

static_olympic_silver_winners = [
    # France 2020
    "Frank Ntilikina",
    "Timothé Luwawu-Cabarrot",
    "Thomas Heurtel",
    "Nicolas Batum",
    "Guerschon Yabusele",
    "Evan Fournier",
    "Nando de Colo",
    "Vincent Poirier",
    "Andrew Albicy",
    "Rudy Gobert",
    "Petr Cornelie",
    "Moustapha Fall",
    # Serbia 2016
    "Miloš Teodosić",
    "Marko Simonović",
    "Bogdan Bogdanović",
    "Stefan Marković",
    "Nikola Kalinić",
    "Nemanja Nedović",
    "Stefan Birčević",
    "Miroslav Raduljica",
    "Nikola Jokić",
    "Vladimir Štimac",
    "Stefan Jović",
    "Milan Mačvan",
]

static_olympic_bronze_winners = [
    # Australia 2020
    "Chris Goulding",
    "Patty Mills",
    "Josh Green",
    "Joe Ingles",
    "Matthew Dellavedova",
    "Nathan Sobey",
    "Matisse Thybulle",
    "Dante Exum",
    "Aron Baynes",
    "Jock Landale",
    "Duop Reath",
    "Nick Kay",
    # Spain 2016
    "Pau Gasol",
    "Rudy Fernández",
    "Sergio Rodríguez",
    "Juan Carlos Navarro",
    "José Manuel Calderón",
    "Felipe Reyes",
    "Víctor Claver",
    "Willy Hernangómez",
    "Álex Abrines",
    "Sergio Llull",
    "Nikola Mirotić",
    "Ricky Rubio",
]


class PlayerStaticOlympiansAdmin(admin.ModelAdmin):
    """Admin view for managing Olympic medal winners"""

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("update_olympic_medal_winners/", self.update_olympic_medal_winners),
        ]
        return my_urls + urls

    def update_olympic_medal_winners(self, request):
        """Update Olympic medal status for players based on static lists"""
        gold_count = 0
        silver_count = 0
        bronze_count = 0

        # Update gold medal winners
        for player_name in static_olympic_gold_winners:
            players = Player.active.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_olympic_gold_medal = True
                player.save()
                gold_count += 1

        # Update silver medal winners
        for player_name in static_olympic_silver_winners:
            players = Player.active.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_olympic_silver_medal = True
                player.save()
                silver_count += 1

        # Update bronze medal winners
        for player_name in static_olympic_bronze_winners:
            players = Player.active.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_olympic_bronze_medal = True
                player.save()
                bronze_count += 1

        # Record the update timestamp
        LastUpdated.update_timestamp(
            data_type="olympic_medals_update",
            updated_by=f"Admin ({request.user.username})",
            notes=f"Updated Olympic medal winners: {gold_count} gold, {silver_count} silver, {bronze_count} bronze",
        )

        self.message_user(
            request,
            f"Successfully updated Olympic medal winners: {gold_count} gold, {silver_count} silver, {bronze_count} bronze",
            level="success",
        )
        return HttpResponseRedirect("../")
