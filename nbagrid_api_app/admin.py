from django.contrib import admin

from nbagrid_api_app.admin.game_admin import GameAdmin
from nbagrid_api_app.admin.gamefilterdb_admin import GameFilterDBAdmin
from nbagrid_api_app.admin.gridmetadata_admin import GridMetadataAdmin
from nbagrid_api_app.admin.player_admin import PlayerAdmin
from nbagrid_api_app.admin.team_admin import TeamAdmin
from nbagrid_api_app.models import GameFilterDB, GameGrid, GameResult, GridMetadata, Player, Team, ImpressumContent

# Register the GameGrid model with our custom admin view
admin.site.register(GameGrid, GameAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(GameResult)
admin.site.register(GameFilterDB, GameFilterDBAdmin)
admin.site.register(GridMetadata, GridMetadataAdmin)


@admin.register(ImpressumContent)
class ImpressumContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'order', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    list_editable = ('is_active', 'order')
    search_fields = ('title', 'content')
    ordering = ('order', 'created_at')
    fields = ('title', 'content', 'is_active', 'order')
    
    class Meta:
        verbose_name = "Impressum Content"
        verbose_name_plural = "Impressum Content"
