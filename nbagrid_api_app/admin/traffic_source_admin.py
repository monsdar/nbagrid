from django.contrib import admin
from nbagrid_api_app.models import TrafficSource

@admin.register(TrafficSource)
class TrafficSourceAdmin(admin.ModelAdmin):
    """Admin interface for TrafficSource model."""
    
    list_display = [
        'source', 'referrer_domain', 'utm_campaign', 'utm_source', 
        'visit_count', 'first_visit', 'last_visit', 'is_bot'
    ]
    
    list_filter = [
        'source', 'is_bot', 'utm_source', 'utm_medium', 'utm_campaign',
        ('first_visit', admin.DateFieldListFilter),
        ('last_visit', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'referrer_domain', 'utm_campaign', 'utm_source', 'utm_medium',
        'path', 'session_key'
    ]
    
    readonly_fields = [
        'first_visit', 'last_visit', 'visit_count', 'ip_address'
    ]
    
    fieldsets = (
        ('Traffic Source', {
            'fields': ('source', 'referrer', 'referrer_domain', 'is_bot')
        }),
        ('UTM Parameters', {
            'fields': ('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'),
            'classes': ('collapse',)
        }),
        ('Request Details', {
            'fields': ('path', 'query_string', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Session & Analytics', {
            'fields': ('session_key', 'ip_address', 'country'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('first_visit', 'last_visit', 'visit_count'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """TrafficSource records are created automatically, not manually."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow viewing but not editing."""
        return request.method in ['GET', 'HEAD']
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup purposes."""
        return True
    
    def get_actions(self, request):
        """Add custom actions for traffic source management."""
        actions = super().get_actions(request)
        
        # Add cleanup action
        actions['cleanup_duplicates'] = self.get_action('cleanup_duplicates')
        
        return actions
    
    def cleanup_duplicates(self, request, queryset):
        """Clean up duplicate traffic source records for the same session."""
        from nbagrid_api_app.models import TrafficSource
        
        cleaned_count = TrafficSource.cleanup_duplicate_sessions()
        
        if cleaned_count > 0:
            self.message_user(
                request,
                f"Successfully cleaned up {cleaned_count} duplicate traffic source records.",
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                "No duplicate traffic source records found.",
                level='INFO'
            )
    
    cleanup_duplicates.short_description = "Clean up duplicate records for the same session"