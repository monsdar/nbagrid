"""Admin views for Game model"""

from datetime import datetime
from django.contrib import admin
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
import logging
import copy

from nbagrid_api_app.models import GameFilterDB, GameGrid, GameResult, GameCompletion, LastUpdated
from nbagrid_api_app.admin.gridbuilder_admin import GridBuilderAdmin

logger = logging.getLogger(__name__)

@admin.register(GameGrid)
class GameAdmin(GridBuilderAdmin):
    """Admin view for Game model"""
    
    change_list_template = "admin/game_changelist.html"
    list_display = ('date', 'grid_size', 'completion_count', 'total_correct_players', 'total_guesses', 'average_score', 'average_correct_cells')
    list_filter = ('date', 'grid_size')
    search_fields = ('date',)
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('view_game_dates/', self.view_game_dates, name='nbagrid_api_app_gamegrid_view_game_dates'),
            path('delete_game/<str:game_date>/', self.delete_game, name='nbagrid_api_app_gamegrid_delete_game'),
            path('create_missing_gamegrids/', self.create_missing_gamegrids, name='nbagrid_api_app_gamegrid_create_missing_gamegrids'),
            path('open_in_gridbuilder/<str:game_date>/', self.open_in_gridbuilder, name='nbagrid_api_app_gamegrid_open_in_gridbuilder'),
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
        dates = GameGrid.objects.all().order_by('-date')
        
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
                'date': game_grid.date,
                'completion_count': game_grid.completion_count,
                'total_guesses': game_grid.total_guesses,
                'min_correct_players': min_correct_players,
                'max_correct_players': max_correct_players,
                'avg_correct_players': avg_correct_players,
                'total_correct_players': game_grid.total_correct_players,
                'average_score': int(game_grid.average_score * 100),
                'average_correct_cells': game_grid.average_correct_cells,
            }
                                                
            # Add a delete link
            date_info['delete_link'] = reverse('admin:nbagrid_api_app_gamegrid_delete_game', args=[game_grid.date])
            
            # Add cell player counts details
            date_info['cell_stats'] = game_grid.cell_correct_players
                        
            date_info_list.append(date_info)
        
        from django.shortcuts import render
        return render(
            request,
            'admin/game_list.html',
            context={
                'title': 'Game Management',
                'dates': date_info_list,
                'opts': self.model._meta,
            }
        )
    
    def delete_game(self, request, game_date):
        try:
            # Parse the date string into a datetime.date object
            game_date_obj = datetime.strptime(game_date, '%Y-%m-%d').date()
            
            # Delete all GameFilterDB entries for this date
            deleted_count = GameFilterDB.objects.filter(date=game_date_obj).delete()[0]
            
            # Delete GameGrid entry
            if GameGrid.objects.filter(date=game_date_obj).exists():
                GameGrid.objects.filter(date=game_date_obj).delete()
            
            # Also delete related GameResult entries
            GameResult.objects.filter(date=game_date_obj).delete()
            
            # Also delete related GameCompletion entries
            GameCompletion.objects.filter(date=game_date_obj).delete()
            
            # Clear session data for this date across all sessions
            from django.contrib.sessions.models import Session
            from django.contrib.sessions.backends.db import SessionStore
            
            # Construct the session key for this date
            date_key = f'game_state_{game_date_obj.year}_{game_date_obj.month}_{game_date_obj.day}'
            
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
                notes=f"Game for {game_date} deleted (removed {deleted_count} filters and cleared session data)"
            )
            
            self.message_user(request, f"Successfully deleted game for {game_date} and cleared related session data", level="success")
        except Exception as e:
            self.message_user(request, f"Error deleting game: {str(e)}", level="error")
        
        # Use the proper reverse URL to the game_dates view instead of a relative path
        return HttpResponseRedirect(reverse('admin:nbagrid_api_app_gamegrid_view_game_dates'))
    
    def create_missing_gamegrids(self, request):
        """
        Create GameGrid objects for dates that have GameFilterDB entries but no GameGrid
        """
        try:
            # Import GameBuilder to use its functionality
            from nbagrid_api_app.GameBuilder import GameBuilder
            
            # Find dates with GameFilterDB entries
            filter_dates = GameFilterDB.objects.values('date').distinct()
            
            # Find dates that don't have GameGrid entries
            missing_grid_dates = []
            created_count = 0
            
            for date_dict in filter_dates:
                date = date_dict['date']
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
                    request, 
                    f"Successfully created {created_count} GameGrid objects for past games", 
                    level="success"
                )
            else:
                self.message_user(
                    request, 
                    "No missing GameGrid objects found", 
                    level="info"
                )
                
            # Record the action
            LastUpdated.update_timestamp(
                data_type="gamegrid_creation",
                updated_by=f"Admin ({request.user.username})",
                notes=f"Created {created_count} GameGrid objects for past games"
            )
            
        except Exception as e:
            self.message_user(request, f"Error creating GameGrid objects: {str(e)}", level="error")
            logger.error(f"Error in create_missing_gamegrids: {str(e)}")
        
        # Redirect back to the game_dates view
        return HttpResponseRedirect(reverse('admin:nbagrid_api_app_gamegrid_view_game_dates'))

    def open_in_gridbuilder(self, request, game_date):
        """Open a specific GameGrid in the GridBuilder"""
        try:
            # Parse the date string into a datetime.date object
            game_date_obj = datetime.strptime(game_date, '%Y-%m-%d').date()
                        
            # Get all available filters from GameFilter
            from nbagrid_api_app.GameFilter import get_static_filters, get_dynamic_filters, gamefilter_to_json, gamefilter_from_json
            available_filters = []
            static_filters = get_static_filters()
            dynamic_filters = get_dynamic_filters()
            all_filters = static_filters + dynamic_filters
            
            # Add filters to available_filters
            for filter in all_filters:
                filter_json = gamefilter_to_json(filter)
                filter_json['name'] = filter.get_desc()  # Add display name
                available_filters.append(filter_json)
                        
            # Get the filters from GameFilterDB and structure them by row and col
            filters = {
                'row': {},
                'col': {}
            }
            
            # Get static filters (rows)
            static_filters_db = GameFilterDB.objects.filter(
                date=game_date_obj,
                filter_type='static'
            ).order_by('filter_index', 'created_at')
            
            # Get dynamic filters (columns)
            dynamic_filters_db = GameFilterDB.objects.filter(
                date=game_date_obj,
                filter_type='dynamic'
            ).order_by('filter_index', 'created_at')
            
            # Process static filters (rows)
            for filter in static_filters_db:
                row_index = str(filter.filter_index)
                if row_index not in filters['row']:
                    # Find the matching filter class
                    filter_instance = None
                    for f in all_filters:
                        if f.__class__.__name__ == filter.filter_class:
                            filter_instance = copy.deepcopy(f)
                            # Initialize the filter with its config
                            filter_instance = gamefilter_from_json(filter_instance, {
                                'class': filter.filter_class,
                                'config': filter.filter_config
                            })
                            break
                    
                    if filter_instance:
                        filters['row'][row_index] = {
                            'class': filter.filter_class,
                            'config': filter.filter_config,
                            'name': filter_instance.get_desc()
                        }
            
            # Process dynamic filters (columns)
            for filter in dynamic_filters_db:
                col_index = str(filter.filter_index)
                if col_index not in filters['col']:
                    # Find the matching filter class
                    filter_instance = None
                    for f in all_filters:
                        if f.__class__.__name__ == filter.filter_class:
                            filter_instance = copy.deepcopy(f)
                            # Initialize the filter with its config
                            filter_instance = gamefilter_from_json(filter_instance, {
                                'class': filter.filter_class,
                                'config': filter.filter_config
                            })
                            break
                    
                    if filter_instance:
                        filters['col'][col_index] = {
                            'class': filter.filter_class,
                            'config': filter.filter_config,
                            'name': filter_instance.get_desc()
                        }
            
            context = {
                'title': f'Grid Builder - {game_date}',
                'available_filters': available_filters,
                'filters': filters,
                'opts': self.model._meta,
                'game_date': game_date,
            }
            
            return render(request, 'admin/grid_builder.html', context)
            
        except GameGrid.DoesNotExist:
            self.message_user(request, f"No game found for date {game_date}", level="error")
            return HttpResponseRedirect(reverse('admin:nbagrid_api_app_gamegrid_view_game_dates'))
        except Exception as e:
            self.message_user(request, f"Error opening game in GridBuilder: {str(e)}", level="error")
            return HttpResponseRedirect(reverse('admin:nbagrid_api_app_gamegrid_view_game_dates'))

@admin.register(GameFilterDB)
class GameFilterDBAdmin(admin.ModelAdmin):
    """Admin view for GameFilterDB model"""
    
    list_display = ('date', 'filter_type', 'filter_class', 'filter_index')
    list_filter = ('date', 'filter_type', 'filter_class')
    search_fields = ('date', 'filter_type', 'filter_class', 'filter_config') 