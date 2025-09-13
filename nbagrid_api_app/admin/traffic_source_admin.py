from django.contrib import admin
from django.db.models import Count, Sum
from django.shortcuts import render
from django.urls import path
from nbagrid_api_app.models import TrafficSource

@admin.register(TrafficSource)
class TrafficSourceAdmin(admin.ModelAdmin):
    """Admin interface for TrafficSource model."""
    
    list_display = [
        'source', 'referrer_domain', 'utm_campaign', 'utm_source', 
        'visit_count', 'first_visit', 'last_visit', 'is_bot'
    ]
    
    def get_queryset(self, request):
        """Filter out bot traffic by default."""
        qs = super().get_queryset(request)
        # Only show non-bot traffic by default
        return qs.filter(is_bot=False)
    
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
    
    def changelist_view(self, request, extra_context=None):
        """Add custom context to the changelist view."""
        extra_context = extra_context or {}
        extra_context['referrer_summary_url'] = 'referrer-summary/'
        return super().changelist_view(request, extra_context)
    
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
    
    def get_urls(self):
        """Add custom URLs for summary views."""
        urls = super().get_urls()
        custom_urls = [
            path('referrer-summary/', self.admin_site.admin_view(self.referrer_summary_view), 
                 name='traffic_source_referrer_summary'),
        ]
        return custom_urls + urls
    
    def referrer_summary_view(self, request):
        """Show referrer domain summary with visit counts."""
        # Get all traffic sources (including bots for complete picture)
        queryset = TrafficSource.objects.all()
        
        # Group by referrer domain and sum visits
        referrer_stats = queryset.values('referrer_domain', 'source').annotate(
            total_visits=Sum('visit_count'),
            unique_sources=Count('id')
        ).order_by('-total_visits')
        
        # Separate bot and non-bot traffic
        bot_stats = referrer_stats.filter(source='bot')
        human_stats = referrer_stats.exclude(source='bot')
        
        # Calculate totals
        total_bot_visits = sum(stat['total_visits'] for stat in bot_stats)
        total_human_visits = sum(stat['total_visits'] for stat in human_stats)
        
        context = {
            'title': 'Traffic Source Summary by Referrer Domain',
            'human_stats': human_stats,
            'bot_stats': bot_stats,
            'total_human_visits': total_human_visits,
            'total_bot_visits': total_bot_visits,
            'total_visits': total_human_visits + total_bot_visits,
        }
        
        return render(request, 'admin/traffic_source_referrer_summary.html', context)