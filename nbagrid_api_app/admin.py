from django.contrib import admin

from nbagrid_api_app.admin.game_admin import GameAdmin
from nbagrid_api_app.admin.gamefilterdb_admin import GameFilterDBAdmin
from nbagrid_api_app.admin.gridmetadata_admin import GridMetadataAdmin
from nbagrid_api_app.admin.player_admin import PlayerAdmin
from nbagrid_api_app.admin.team_admin import TeamAdmin
from nbagrid_api_app.admin.filter_analytics_admin import FilterAnalyticsAdmin, FilterAnalytics
from nbagrid_api_app.models import GameFilterDB, GameGrid, GameResult, GridMetadata, Player, Team

# Register the GameGrid model with our custom admin view
admin.site.register(GameGrid, GameAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(GameResult)
admin.site.register(GameFilterDB, GameFilterDBAdmin)
admin.site.register(GridMetadata, GridMetadataAdmin)
admin.site.register(FilterAnalytics, FilterAnalyticsAdmin)
