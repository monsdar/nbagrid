"""Admin views for Team model"""

from nba_api.stats.static import teams as static_teams

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path

from nbagrid_api_app.models import Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    change_list_template = "admin/team_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("read_teams_from_nba_stats/", self.read_teams_from_nba_stats),
        ]
        return my_urls + urls

    def read_teams_from_nba_stats(self, request):
        for team in static_teams.get_teams():
            Team.objects.get_or_create(
                stats_id=team["id"],
                defaults={
                    "name": team["full_name"],
                    "abbr": team["abbreviation"],
                },
            )
        self.message_user(request, "Successfully updated teams", level="success")
        return HttpResponseRedirect("../")
