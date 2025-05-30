from django.contrib import admin
from nbagrid_api_app.models import GridMetadata

@admin.register(GridMetadata)
class GridMetadataAdmin(admin.ModelAdmin):
    list_display = ('date', 'game_title')
    search_fields = ('date', 'game_title')
    ordering = ('-date',)  # Most recent dates first
    
    def has_add_permission(self, request):
        return True
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True 