"""Admin views for Game model"""

import copy
import logging
from datetime import datetime

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.db.models import Count, Q
from collections import defaultdict
from datetime import datetime, timedelta

from nbagrid_api_app.admin.gridbuilder_admin import GridBuilderAdmin
from nbagrid_api_app.models import GameCompletion, GameFilterDB, GameGrid, GameResult, GridMetadata, LastUpdated

logger = logging.getLogger(__name__)


@admin.register(GameGrid)
class GameAdmin(GridBuilderAdmin):
    """Admin view for Game model"""

    change_list_template = "admin/game_changelist.html"
    list_display = (
        "date",
        "grid_size",
        "completion_count",
        "total_correct_players",
        "total_guesses",
        "average_score",
        "average_correct_cells",
    )
    list_filter = ("date", "grid_size")
    search_fields = ("date",)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("view_game_dates/", self.view_game_dates, name="nbagrid_api_app_gamegrid_view_game_dates"),
            path("delete_game/<str:game_date>/", self.delete_game, name="nbagrid_api_app_gamegrid_delete_game"),
            path(
                "create_missing_gamegrids/",
                self.create_missing_gamegrids,
                name="nbagrid_api_app_gamegrid_create_missing_gamegrids",
            ),
            path(
                "open_in_gridbuilder/<str:game_date>/",
                self.open_in_gridbuilder,
                name="nbagrid_api_app_gamegrid_open_in_gridbuilder",
            ),
            path("filter_analytics/", self.filter_analytics_view, name="nbagrid_api_app_gamegrid_filter_analytics"),
        ]
        return my_urls + urls

    def has_add_permission(self, request):
        # Disable adding GameFilterDB objects directly through the admin
        return False

    def has_change_permission(self, request, obj=None):
        # Disable editing GameFilterDB objects directly
        return False

    def view_game_dates(self, request):
        # Get unique dates from GameGrid
        dates = GameGrid.objects.all().order_by("-date")

        date_info_list = []

        for game_grid in dates:
            min_correct_players = 999
            for cell in game_grid.cell_correct_players:
                if game_grid.cell_correct_players[cell] < min_correct_players:
                    min_correct_players = game_grid.cell_correct_players[cell]
            max_correct_players = 0
            for cell in game_grid.cell_correct_players:
                if game_grid.cell_correct_players[cell] > max_correct_players:
                    max_correct_players = game_grid.cell_correct_players[cell]
            avg_correct_players = game_grid.total_correct_players / 9

            date_info = {
                "date": game_grid.date,
                "completion_count": game_grid.completion_count,
                "total_guesses": game_grid.total_guesses,
                "min_correct_players": min_correct_players,
                "max_correct_players": max_correct_players,
                "avg_correct_players": avg_correct_players,
                "total_correct_players": game_grid.total_correct_players,
                "average_score": int(game_grid.average_score * 100),
                "average_correct_cells": game_grid.average_correct_cells,
            }

            # Add a delete link
            date_info["delete_link"] = reverse("admin:nbagrid_api_app_gamegrid_delete_game", args=[game_grid.date])

            # Add cell player counts details
            date_info["cell_stats"] = game_grid.cell_correct_players

            date_info_list.append(date_info)

        from django.shortcuts import render

        return render(
            request,
            "admin/game_list.html",
            context={
                "title": "Game Management",
                "dates": date_info_list,
                "opts": self.model._meta,
            },
        )

    def delete_game(self, request, game_date):
        try:
            # Parse the date string into a datetime.date object
            game_date_obj = datetime.strptime(game_date, "%Y-%m-%d").date()

            # Delete all GameFilterDB entries for this date
            deleted_count = GameFilterDB.objects.filter(date=game_date_obj).delete()[0]

            # Delete GameGrid entry
            if GameGrid.objects.filter(date=game_date_obj).exists():
                GameGrid.objects.filter(date=game_date_obj).delete()

            # Also delete related GameResult entries
            GameResult.objects.filter(date=game_date_obj).delete()

            # Also delete related GameCompletion entries
            GameCompletion.objects.filter(date=game_date_obj).delete()

            # Also delete related GridMetadata entries
            GridMetadata.objects.filter(date=game_date_obj).delete()

            # Clear session data for this date across all sessions
            from django.contrib.sessions.backends.db import SessionStore
            from django.contrib.sessions.models import Session

            # Construct the session key for this date
            date_key = f"game_state_{game_date_obj.year}_{game_date_obj.month}_{game_date_obj.day}"

            # Get all active sessions
            for session in Session.objects.all():
                try:
                    # Load the session data
                    session_data = SessionStore(session_key=session.session_key)
                    # If this session contains data for the deleted game
                    if date_key in session_data:
                        # Remove the game state for this date
                        del session_data[date_key]
                        # Save the session
                        session_data.save()
                        logger.info(f"Cleared session data for game date {game_date} from session {session.session_key}")
                except Exception as e:
                    logger.error(f"Error clearing session {session.session_key}: {str(e)}")

            # Record the deletion
            LastUpdated.update_timestamp(
                data_type="game_deletion",
                updated_by=f"Admin ({request.user.username})",
                notes=f"Game for {game_date} deleted (removed {deleted_count} filters and cleared session data)",
            )

            self.message_user(
                request, f"Successfully deleted game for {game_date} and cleared related session data", level="success"
            )
        except Exception as e:
            self.message_user(request, f"Error deleting game: {str(e)}", level="error")

        # Use the proper reverse URL to the game_dates view instead of a relative path
        return HttpResponseRedirect(reverse("admin:nbagrid_api_app_gamegrid_view_game_dates"))

    def create_missing_gamegrids(self, request):
        """
        Create GameGrid objects for dates that have GameFilterDB entries but no GameGrid
        """
        try:
            # Import GameBuilder to use its functionality
            from nbagrid_api_app.GameBuilder import GameBuilder

            # Find dates with GameFilterDB entries
            filter_dates = GameFilterDB.objects.values("date").distinct()

            # Find dates that don't have GameGrid entries
            missing_grid_dates = []
            created_count = 0

            for date_dict in filter_dates:
                date = date_dict["date"]
                if not GameGrid.objects.filter(date=date).exists():
                    missing_grid_dates.append(date)

            # Process each missing date
            for date in missing_grid_dates:
                # Create a GameBuilder
                builder = GameBuilder()

                # Get the filters for this date
                try:
                    # This will use existing filters and create a GameGrid
                    static_filters, dynamic_filters = builder.get_tuned_filters(date)
                    created_count += 1
                    logger.info(f"Created GameGrid for {date}")
                except Exception as e:
                    logger.error(f"Error creating GameGrid for {date}: {str(e)}")

            if created_count > 0:
                self.message_user(
                    request, f"Successfully created {created_count} GameGrid objects for past games", level="success"
                )
            else:
                self.message_user(request, "No missing GameGrid objects found", level="info")

            # Record the action
            LastUpdated.update_timestamp(
                data_type="gamegrid_creation",
                updated_by=f"Admin ({request.user.username})",
                notes=f"Created {created_count} GameGrid objects for past games",
            )

        except Exception as e:
            self.message_user(request, f"Error creating GameGrid objects: {str(e)}", level="error")
            logger.error(f"Error in create_missing_gamegrids: {str(e)}")

        # Redirect back to the game_dates view
        return HttpResponseRedirect(reverse("admin:nbagrid_api_app_gamegrid_view_game_dates"))

    def open_in_gridbuilder(self, request, game_date):
        """Open a specific GameGrid in the GridBuilder"""
        try:
            # Parse the date string into a datetime.date object
            game_date_obj = datetime.strptime(game_date, "%Y-%m-%d").date()

            # Get all available filters from GameFilter
            from nbagrid_api_app.GameFilter import (
                gamefilter_from_json,
                gamefilter_to_json,
                get_dynamic_filters,
                get_static_filters,
            )

            available_filters = []
            static_filters = get_static_filters()
            dynamic_filters = get_dynamic_filters()
            all_filters = static_filters + dynamic_filters

            # Add filters to available_filters
            for filter in all_filters:
                filter_json = gamefilter_to_json(filter)
                filter_json["name"] = filter.get_desc()  # Add display name
                available_filters.append(filter_json)

            # Get the filters from GameFilterDB and structure them by row and col
            filters = {"row": {}, "col": {}}

            # Get static filters (rows)
            static_filters_db = GameFilterDB.objects.filter(date=game_date_obj, filter_type="static").order_by(
                "filter_index", "created_at"
            )

            # Get dynamic filters (columns)
            dynamic_filters_db = GameFilterDB.objects.filter(date=game_date_obj, filter_type="dynamic").order_by(
                "filter_index", "created_at"
            )

            # Process static filters (rows)
            for filter in static_filters_db:
                row_index = str(filter.filter_index)
                if row_index not in filters["row"]:
                    # Find the matching filter class
                    filter_instance = None
                    for f in all_filters:
                        if f.__class__.__name__ == filter.filter_class:
                            filter_instance = copy.deepcopy(f)
                            # Initialize the filter with its config
                            filter_instance = gamefilter_from_json(
                                filter_instance, {"class": filter.filter_class, "config": filter.filter_config}
                            )
                            break

                    if filter_instance:
                        filters["row"][row_index] = {
                            "class": filter.filter_class,
                            "config": filter.filter_config,
                            "name": filter_instance.get_desc(),
                        }

            # Process dynamic filters (columns)
            for filter in dynamic_filters_db:
                col_index = str(filter.filter_index)
                if col_index not in filters["col"]:
                    # Find the matching filter class
                    filter_instance = None
                    for f in all_filters:
                        if f.__class__.__name__ == filter.filter_class:
                            filter_instance = copy.deepcopy(f)
                            # Initialize the filter with its config
                            filter_instance = gamefilter_from_json(
                                filter_instance, {"class": filter.filter_class, "config": filter.filter_config}
                            )
                            break

                    if filter_instance:
                        filters["col"][col_index] = {
                            "class": filter.filter_class,
                            "config": filter.filter_config,
                            "name": filter_instance.get_desc(),
                        }

            # Get the game title from GridMetadata if it exists
            try:
                game_metadata = GridMetadata.objects.get(date=game_date_obj)
                game_title = game_metadata.game_title
            except GridMetadata.DoesNotExist:
                game_title = ""

            context = {
                "title": f"Grid Builder - {game_date}",
                "available_filters": available_filters,
                "filters": filters,
                "opts": self.model._meta,
                "game_date": game_date,
                "game_title": game_title,
            }

            return render(request, "admin/grid_builder.html", context)

        except GameGrid.DoesNotExist:
            self.message_user(request, f"No game found for date {game_date}", level="error")
            return HttpResponseRedirect(reverse("admin:nbagrid_api_app_gamegrid_view_game_dates"))
        except Exception as e:
            self.message_user(request, f"Error opening game in GridBuilder: {str(e)}", level="error")
            return HttpResponseRedirect(reverse("admin:nbagrid_api_app_gamegrid_view_game_dates"))
    
    def filter_analytics_view(self, request):
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
        
        # Overall filter usage statistics with detailed descriptions
        filter_usage = self.get_detailed_filter_usage_stats(filters_queryset)
        
        # Filter usage by type (static vs dynamic) with detailed descriptions
        static_usage = self.get_detailed_filter_usage_stats(filters_queryset.filter(filter_type='static'))
        dynamic_usage = self.get_detailed_filter_usage_stats(filters_queryset.filter(filter_type='dynamic'))
        
        # Recent trends (last 7 days vs previous period)
        recent_trends = self.get_detailed_recent_trends(days)
        
        context = {
            'title': 'GameBuilder Filter Analytics',
            'days': days,
            'total_games': filters_queryset.values('date').distinct().count(),
            'filter_usage': filter_usage,
            'static_usage': static_usage,
            'dynamic_usage': dynamic_usage,
            'recent_trends': recent_trends,
            'opts': self.model._meta,
            'cl': self,  # For admin template compatibility
            'has_add_permission': False,
            'has_change_permission': False,
            'has_delete_permission': False,
        }
        
        return context
    
    def get_detailed_filter_usage_stats(self, queryset):
        """Calculate filter usage statistics with detailed descriptions"""
        from nbagrid_api_app.GameFilter import create_filter_from_db
        
        # Group by filter_class and filter_config to get unique filter configurations
        usage_data = queryset.values('filter_class', 'filter_config').annotate(
            count=Count('id')
        ).order_by('-count')
        
        total_count = sum(stat['count'] for stat in usage_data)
        
        # Create detailed descriptions for each unique filter configuration
        detailed_stats = []
        for stat in usage_data:
            # Create a temporary GameFilterDB object to reconstruct the filter
            temp_filter_db = type('TempFilter', (), {
                'filter_class': stat['filter_class'],
                'filter_config': stat['filter_config'],
                'filter_type': 'dynamic'  # We'll handle both types
            })()
            
            try:
                # Reconstruct the filter to get its description
                filter_obj = create_filter_from_db(temp_filter_db)
                if hasattr(filter_obj, 'get_desc'):
                    description = filter_obj.get_desc()
                else:
                    description = stat['filter_class']
            except:
                # Fallback to class name if reconstruction fails
                description = stat['filter_class']
            
            detailed_stats.append({
                'filter_class': stat['filter_class'],
                'description': description,
                'count': stat['count'],
                'percentage': round((stat['count'] / total_count * 100), 1) if total_count > 0 else 0
            })
        
        return detailed_stats
    
    def get_detailed_recent_trends(self, total_days):
        """Compare recent usage (last 7 days) with previous period using detailed descriptions"""
        from nbagrid_api_app.GameFilter import create_filter_from_db
        
        recent_cutoff = datetime.now().date() - timedelta(days=7)
        previous_cutoff = datetime.now().date() - timedelta(days=total_days)
        
        # Recent usage (last 7 days) - group by class and config
        recent_usage = GameFilterDB.objects.filter(
            date__gte=recent_cutoff
        ).values('filter_class', 'filter_config').annotate(count=Count('id'))
        
        # Previous period usage - group by class and config
        previous_usage = GameFilterDB.objects.filter(
            date__gte=previous_cutoff,
            date__lt=recent_cutoff
        ).values('filter_class', 'filter_config').annotate(count=Count('id'))
        
        # Create dictionaries with unique keys based on class + config
        def create_filter_key(item):
            return f"{item['filter_class']}_{hash(str(item['filter_config']))}"
        
        recent_dict = {create_filter_key(item): item for item in recent_usage}
        previous_dict = {create_filter_key(item): item for item in previous_usage}
        
        # Calculate trends
        trends = []
        all_filter_keys = set(recent_dict.keys()) | set(previous_dict.keys())
        
        for filter_key in all_filter_keys:
            recent_item = recent_dict.get(filter_key)
            previous_item = previous_dict.get(filter_key)
            
            recent_count = recent_item['count'] if recent_item else 0
            previous_count = previous_item['count'] if previous_item else 0
            
            # Get the filter info from whichever period has data
            filter_info = recent_item or previous_item
            
            # Get detailed description
            temp_filter_db = type('TempFilter', (), {
                'filter_class': filter_info['filter_class'],
                'filter_config': filter_info['filter_config'],
                'filter_type': 'dynamic'
            })()
            
            try:
                filter_obj = create_filter_from_db(temp_filter_db)
                description = filter_obj.get_desc() if hasattr(filter_obj, 'get_desc') else filter_info['filter_class']
            except:
                description = filter_info['filter_class']
            
            if previous_count > 0:
                change_percent = round(((recent_count - previous_count) / previous_count * 100), 1)
            elif recent_count > 0:
                change_percent = 100  # New filter appeared
            else:
                change_percent = 0
            
            trends.append({
                'filter_class': filter_info['filter_class'],
                'description': description,
                'recent_count': recent_count,
                'previous_count': previous_count,
                'change_percent': change_percent,
                'trend': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
            })
        
        return sorted(trends, key=lambda x: abs(x['change_percent']), reverse=True)


@admin.register(GameFilterDB)
class GameFilterDBAdmin(admin.ModelAdmin):
    """Admin view for GameFilterDB model"""

    list_display = ("date", "filter_type", "filter_class", "filter_index")
    list_filter = ("date", "filter_type", "filter_class")
    search_fields = ("date", "filter_type", "filter_class", "filter_config")
