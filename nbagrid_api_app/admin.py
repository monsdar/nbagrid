from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect
from django.db.models import Count
from django.urls import reverse

from nba_api.stats.static import teams as static_teams
from nba_api.stats.static import players as static_players

import requests
import logging
import time
from datetime import datetime

from .models import Player, Team, GameFilterDB, GameResult, GameCompletion, LastUpdated, GameGrid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    change_list_template = "admin/team_changelist.html"
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('read_teams_from_nba_stats/', self.read_teams_from_nba_stats),
        ]
        return my_urls + urls

    def read_teams_from_nba_stats(self, request):
        for team in static_teams.get_teams():
            Team.objects.get_or_create(
                stats_id=team['id'],
                defaults={
                    'name': team['full_name'],
                    'abbr': team['abbreviation'],
                    })
        self.message_user(request, "Successfully updated teams", level="success")
        return HttpResponseRedirect("../")

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    change_list_template = "admin/player_changelist.html"
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('init_players_from_static_players/', self.init_players_from_static_players),
            path('sync_players_from_nba_stats/', self.sync_player_data_from_nba_stats),
            path('sync_player_stats_from_nba_stats/', self.sync_player_stats_from_nba_stats),
            path('sync_player_awards_from_nba_stats/', self.sync_player_awards_from_nba_stats),
        ]
        return my_urls + urls
    
    def init_players_from_static_players(self, request):
        self.init_players()
        self.message_user(request, "Successfully initialized players", level="success")
        return HttpResponseRedirect("../")
    
    def sync_player_data_from_nba_stats(self, request):
        self.sync_player_data()
        self.message_user(request, "Successfully synced player data", level="success")
        return HttpResponseRedirect("../")
            
    def sync_player_stats_from_nba_stats(self, request):
        self.sync_player_stats()
        self.message_user(request, "Successfully synced player stats", level="success")
        return HttpResponseRedirect("../")
    
    def sync_player_awards_from_nba_stats(self, request):
        self.sync_player_awards()
        self.message_user(request, "Successfully synced player awards", level="success")
        return HttpResponseRedirect("../")
    
    def init_players(self):
        # Create all active players that are in the static players list
        all_players = static_players.get_active_players()
        logger.info(f"Initing {len(all_players)} players...")
        for player in all_players:
            (new_player, has_created) = Player.objects.update_or_create(
                stats_id=player['id'],
                defaults={
                    'name': static_players._strip_accents(player['full_name']),
                    'display_name': player['full_name'],
                    })
            if has_created:
                new_player.save()
                logger.info(f"...created new player: {player['full_name']}")
    
        # Check for players that aren't in the static_players list and delete them
        all_players = Player.objects.all().values_list('stats_id', flat=True)
        all_static_player_ids = [static_player['id'] for static_player in static_players.get_active_players()]
        for player in all_players:
            if player not in all_static_player_ids:
                Player.objects.filter(stats_id=player).delete()
                logger.info(f"...deleted player: {player.name}")
    
    def sync_player_stats(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_stats_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0) # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player stats: {player.name}")
            time.sleep(0.25) # wait a bit before doing the next API request to not run into stats.nba rate limits
    
    def sync_player_awards(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_awards_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0) # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player awards: {player.name}")
            time.sleep(0.25) # wait a bit before doing the next API request to not run into stats.nba rate limits
    
    def sync_player_data(self):
        all_players = Player.objects.all()
        logger.info(f"Updating {len(all_players)} players...")
        for player in all_players:
            try:
                player.update_player_data_from_nba_stats()
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Error updating player {player.name}, looks like we've ran into API limits: {e}")
                time.sleep(10.0) # wait some time before trying again to access the API
                continue
            logger.info(f"...updated player data: {player.name}")
            time.sleep(0.25) # wait a bit before doing the next API request to not run into stats.nba rate limits
            
class GameAdmin(admin.ModelAdmin):
    change_list_template = "admin/game_changelist.html"
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('game_dates/', self.view_game_dates, name='game_dates'),
            path('delete_game/<str:game_date>/', self.delete_game, name='delete_game'),
            path('create_missing_gamegrids/', self.create_missing_gamegrids, name='create_missing_gamegrids'),
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
            date_info['delete_link'] = reverse('admin:delete_game', args=[game_grid.date])
            
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
        return HttpResponseRedirect(reverse('admin:game_dates'))
    
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
        return HttpResponseRedirect(reverse('admin:game_dates'))

# Register the GameGrid model with our custom admin view
admin.site.register(GameGrid, GameAdmin)

# Register GameResult model
admin.site.register(GameResult)

# Create a dedicated admin view for GameFilterDB
class GameFilterDBAdmin(admin.ModelAdmin):
    list_display = ('date', 'filter_type', 'filter_class', 'filter_index')
    list_filter = ('date', 'filter_type', 'filter_class')
    search_fields = ('date', 'filter_class')
    date_hierarchy = 'date'

# Register GameFilterDB with the dedicated admin view
admin.site.register(GameFilterDB, GameFilterDBAdmin)
            