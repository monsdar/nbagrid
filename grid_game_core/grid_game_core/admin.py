from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import GameResult, GameCompletion, GameFilterDB, UserData, LastUpdated


class GameResultAdmin(admin.ModelAdmin):
    """Admin interface for GameResult model."""
    
    list_display = ['date', 'cell_key', 'entity', 'guess_count']
    list_filter = ['date', 'cell_key']
    search_fields = ['cell_key']
    date_hierarchy = 'date'
    
    def entity_display(self, obj):
        """Display the entity name."""
        if obj.entity:
            return str(obj.entity)
        return f"Entity {obj.object_id}"
    entity_display.short_description = 'Entity'


class GameCompletionAdmin(admin.ModelAdmin):
    """Admin interface for GameCompletion model."""
    
    list_display = ['date', 'session_key', 'correct_cells', 'final_score', 'completion_streak', 'perfect_streak', 'completed_at']
    list_filter = ['date', 'correct_cells']
    search_fields = ['session_key']
    date_hierarchy = 'date'
    readonly_fields = ['completed_at']


class GameFilterDBAdmin(admin.ModelAdmin):
    """Admin interface for GameFilterDB model."""
    
    list_display = ['date', 'filter_type', 'filter_class', 'filter_index', 'created_at']
    list_filter = ['date', 'filter_type', 'filter_class']
    search_fields = ['filter_class']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']


class UserDataAdmin(admin.ModelAdmin):
    """Admin interface for UserData model."""
    
    list_display = ['display_name', 'session_key', 'created_at', 'last_active']
    list_filter = ['created_at', 'last_active']
    search_fields = ['display_name', 'session_key']
    readonly_fields = ['created_at', 'last_active']


class LastUpdatedAdmin(admin.ModelAdmin):
    """Admin interface for LastUpdated model."""
    
    list_display = ['data_type', 'last_updated', 'updated_by']
    list_filter = ['last_updated']
    search_fields = ['data_type', 'updated_by']
    readonly_fields = ['last_updated']


# Register the models
admin.site.register(GameResult, GameResultAdmin)
admin.site.register(GameCompletion, GameCompletionAdmin)
admin.site.register(GameFilterDB, GameFilterDBAdmin)
admin.site.register(UserData, UserDataAdmin)
admin.site.register(LastUpdated, LastUpdatedAdmin) 