from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from django.db.models import Count, Q
from django.utils.html import format_html
from collections import defaultdict, Counter
from datetime import datetime, timedelta

from nbagrid_api_app.models import GameFilterDB


class FilterAnalyticsAdmin(admin.ModelAdmin):
    """Admin view for analyzing GameBuilder filter usage patterns"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='filter-analytics'),
        ]
        return custom_urls + urls
    
    def analytics_view(self, request):
        """Display filter usage analytics"""
        context = self.get_analytics_context(request)
        return render(request, 'admin/filter_analytics.html', context)
    
    def get_analytics_context(self, request):
        """Generate analytics data for the template"""
        # Get time range from request parameters (default to last 30 days)
        days = int(request.GET.get('days', 30))
        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        # Base queryset for the time period
        filters_queryset = GameFilterDB.objects.filter(date__gte=cutoff_date)
        
        # Overall filter usage statistics
        filter_usage = self.get_filter_usage_stats(filters_queryset)
        
        # Filter usage by type (static vs dynamic)
        static_usage = self.get_filter_usage_stats(filters_queryset.filter(filter_type='static'))
        dynamic_usage = self.get_filter_usage_stats(filters_queryset.filter(filter_type='dynamic'))
        
        # Recent trends (last 7 days vs previous period)
        recent_trends = self.get_recent_trends(days)
        
        # Filter position analysis
        position_analysis = self.get_position_analysis(filters_queryset)
        
        # Daily usage patterns
        daily_patterns = self.get_daily_patterns(filters_queryset)
        
        context = {
            'title': 'GameBuilder Filter Analytics',
            'days': days,
            'total_games': filters_queryset.values('date').distinct().count(),
            'filter_usage': filter_usage,
            'static_usage': static_usage,
            'dynamic_usage': dynamic_usage,
            'recent_trends': recent_trends,
            'position_analysis': position_analysis,
            'daily_patterns': daily_patterns,
            'opts': self.model._meta,
        }
        
        return context
    
    def get_filter_usage_stats(self, queryset):
        """Calculate filter usage statistics"""
        usage_stats = queryset.values('filter_class').annotate(
            count=Count('id')
        ).order_by('-count')
        
        total_count = sum(stat['count'] for stat in usage_stats)
        
        # Add percentage calculations
        for stat in usage_stats:
            stat['percentage'] = round((stat['count'] / total_count * 100), 1) if total_count > 0 else 0
        
        return usage_stats
    
    def get_recent_trends(self, total_days):
        """Compare recent usage (last 7 days) with previous period"""
        recent_cutoff = datetime.now().date() - timedelta(days=7)
        previous_cutoff = datetime.now().date() - timedelta(days=total_days)
        
        # Recent usage (last 7 days)
        recent_usage = GameFilterDB.objects.filter(
            date__gte=recent_cutoff
        ).values('filter_class').annotate(count=Count('id'))
        
        # Previous period usage
        previous_usage = GameFilterDB.objects.filter(
            date__gte=previous_cutoff,
            date__lt=recent_cutoff
        ).values('filter_class').annotate(count=Count('id'))
        
        # Convert to dictionaries for easier comparison
        recent_dict = {item['filter_class']: item['count'] for item in recent_usage}
        previous_dict = {item['filter_class']: item['count'] for item in previous_usage}
        
        # Calculate trends
        trends = []
        all_filters = set(recent_dict.keys()) | set(previous_dict.keys())
        
        for filter_class in all_filters:
            recent_count = recent_dict.get(filter_class, 0)
            previous_count = previous_dict.get(filter_class, 0)
            
            if previous_count > 0:
                change_percent = round(((recent_count - previous_count) / previous_count * 100), 1)
            elif recent_count > 0:
                change_percent = 100  # New filter appeared
            else:
                change_percent = 0
            
            trends.append({
                'filter_class': filter_class,
                'recent_count': recent_count,
                'previous_count': previous_count,
                'change_percent': change_percent,
                'trend': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
            })
        
        return sorted(trends, key=lambda x: abs(x['change_percent']), reverse=True)
    
    def get_position_analysis(self, queryset):
        """Analyze filter usage by position in grid"""
        position_stats = queryset.values('filter_class', 'filter_index').annotate(
            count=Count('id')
        ).order_by('filter_class', 'filter_index')
        
        # Group by filter class
        position_data = defaultdict(lambda: defaultdict(int))
        for stat in position_stats:
            position_data[stat['filter_class']][stat['filter_index']] = stat['count']
        
        # Convert to list format for template
        position_analysis = []
        for filter_class, positions in position_data.items():
            total = sum(positions.values())
            position_breakdown = []
            for pos in range(3):  # Assuming 3x3 grid
                count = positions.get(pos, 0)
                percentage = round((count / total * 100), 1) if total > 0 else 0
                position_breakdown.append({
                    'position': pos,
                    'count': count,
                    'percentage': percentage
                })
            
            position_analysis.append({
                'filter_class': filter_class,
                'total_usage': total,
                'positions': position_breakdown
            })
        
        return sorted(position_analysis, key=lambda x: x['total_usage'], reverse=True)
    
    def get_daily_patterns(self, queryset):
        """Analyze daily usage patterns"""
        daily_stats = queryset.values('date').annotate(
            total_filters=Count('id'),
            static_count=Count('id', filter=Q(filter_type='static')),
            dynamic_count=Count('id', filter=Q(filter_type='dynamic'))
        ).order_by('-date')[:14]  # Last 14 days
        
        return daily_stats

    def changelist_view(self, request, extra_context=None):
        """Override changelist to redirect to analytics view"""
        return self.analytics_view(request)


# We'll register this with a dummy model since we don't need actual model management
class FilterAnalytics:
    """Dummy model for filter analytics admin"""
    class _meta:
        app_label = 'nbagrid_api_app'
        model_name = 'filteranalytics'
        verbose_name = 'Filter Analytics'
        verbose_name_plural = 'Filter Analytics'