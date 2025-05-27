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

# Static lists of Olympic medal winners by name
# These will be manually updated when admin is running update_olympic_medal_winners
# This is needed because the stats.nba.com API doesn't provide this information for international players before 2024
static_olympic_gold_winners = [
    # Add Olympic gold medal winners here (empty by default)
]

static_olympic_silver_winners = [
    # France 2020
    "Frank Ntilikina",
    "Timothé Luwawu-Cabarrot",
    "Thomas Heurtel",
    "Nicolas Batum",
    "Guerschon Yabusele",
    "Evan Fournier",
    "Nando de Colo",
    "Vincent Poirier",
    "Andrew Albicy",
    "Rudy Gobert",
    "Petr Cornelie",
    "Moustapha Fall",
    
    # Serbia 2016
    "Miloš Teodosić",
    "Marko Simonović",
    "Bogdan Bogdanović",
    "Stefan Marković",
    "Nikola Kalinić",
    "Nemanja Nedović",
    "Stefan Birčević",
    "Miroslav Raduljica",
    "Nikola Jokić",
    "Vladimir Štimac",
    "Stefan Jović",
    "Milan Mačvan",
]

static_olympic_bronze_winners = [
    # Australia 2020
    "Chris Goulding",
    "Patty Mills",
    "Josh Green",
    "Joe Ingles",
    "Matthew Dellavedova",
    "Nathan Sobey",
    "Matisse Thybulle",
    "Dante Exum",
    "Aron Baynes",
    "Jock Landale",
    "Duop Reath",
    "Nick Kay",
    
    # Spain 2016
    "Pau Gasol",
    "Rudy Fernández",
    "Sergio Rodríguez",
    "Juan Carlos Navarro",
    "José Manuel Calderón",
    "Felipe Reyes",
    "Víctor Claver",
    "Willy Hernangómez",
    "Álex Abrines",
    "Sergio Llull",
    "Nikola Mirotić",
    "Ricky Rubio",
]

# Static lists of All-NBA team winners by name
# These will be manually updated when admin is running update_all_nba_teams
static_all_nba_first_team = [
    # 2024-25 Season
    "Nikola Jokić",
    "Shai Gilgeous-Alexander",
    "Giannis Antetokounmpo",
    "Jayson Tatum",
    "Donovan Mitchell",
]

static_all_nba_second_team = [
    # 2024-25 Season
    "Jalen Brunson",
    "Stephen Curry",
    "Anthony Edwards",
    "LeBron James",
    "Evan Mobley",
]

static_all_nba_third_team = [
    # 2024-25 Season
    "Cade Cunningham",
    "Tyrese Haliburton",
    "James Harden",
    "Karl-Anthony Towns",
    "Jalen Williams",
]
static_all_nba_rookie_team = [
    # 2024-25 Season
    "Stephon Castle",
    "Zaccharie Risacher",
    "Jaylen Wells",
    "Zach Edey",
    "Alex Sarr",
    "Kel'el Ware",
    "Matas Buzelis",
    "Yves Missi",
    "Donovan Clingan",
    "Bub Carrington",
]
static_all_nba_defensive_team = [
    # 2024-25 Season
    "Dyson Daniels",
    "Luguentz Dort",
    "Draymond Green",
    "Evan Mobley",
    "Amen Thompson",
    "Toumani Camara",
    "Rudy Gobert",
    "Jaren Jackson Jr.",
    "Jalen Williams",
    "Ivica Zubac",    
]

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
    list_display = ('name', 'position', 'country', 'is_award_olympic_gold_medal', 'is_award_olympic_silver_medal', 'is_award_olympic_bronze_medal', 'base_salary')
    list_filter = ('position', 'country', 'is_award_olympic_gold_medal', 'is_award_olympic_silver_medal', 'is_award_olympic_bronze_medal')
    search_fields = ('name', 'display_name')
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('init_players_from_static_players/', self.init_players_from_static_players),
            path('sync_players_from_nba_stats/', self.sync_player_data_from_nba_stats),
            path('sync_player_stats_from_nba_stats/', self.sync_player_stats_from_nba_stats),
            path('sync_player_awards_from_nba_stats/', self.sync_player_awards_from_nba_stats),
            path('update_olympic_medal_winners/', self.update_olympic_medal_winners),
            path('update_all_nba_teams/', self.update_all_nba_teams),
            path('sync_salaries_from_spotrac/', self.sync_salaries_from_spotrac),
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
    
    def sync_salaries_from_spotrac(self, request):
        """Sync player salaries from Spotrac.com"""
        import requests
        from bs4 import BeautifulSoup
        import re
        
        try:
            # Fetch the Spotrac page
            url = "https://www.spotrac.com/nba/rankings/player/_/year/2024/sort/cap_base"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the table with player salaries
            table = soup.find('ul', {"class": "list-group"})
            if not table:
                raise Exception("Could not find salary table on Spotrac page")
            
            # Process each row
            updated_count = 0
            for row in table.find_all('li'):
                player_link = row.find("a", {"class": "link"})  
                if not player_link:
                    continue
                player_name = player_link.text.strip()
                salary_span = row.find("span", {"class": "medium"})	    
                if not salary_span:
                    continue
                salary_text = salary_span.text.strip()
                                    
                # Convert salary text to integer (remove $ and commas)
                salary = int(re.sub(r'[^\d]', '', salary_text))
                
                # strip any left accents and special chars from the player_name
                player_name = static_players._strip_accents(player_name)
                # This is a list of players that have different names in Spotrac vs NBA.com
                # Key: Spotrac name, Value: NBA.com name
                player_mappings = { 
                    "Jimmy Butler": "Jimmy Butler III",
                    "C.J. McCollum": "CJ McCollum",
                    "Nicolas Claxton": "Nic Claxton",
                    "R.J. Barrett": "RJ Barrett",
                    "Bruce Brown Jr.": "Bruce Brown",
                    "PJ Washington": "P.J. Washington",
                    "Herb Jones": "Herbert Jones",
                    "Ron Holland II": "Ronald Holland II",
                    "Kenyon Martin Jr.": "KJ Martin",
                    "Jae’Sean Tate": "Jae'Sean Tate", # NOTE: keep the apostrophe, as this is how it's spelled in Spotrac
                    "Cameron Thomas": "Cam Thomas",
                    "Sviatoslav Mykhailiuk": "Svi Mykhailiuk",
                    "Vincent Williams Jr.": "Vince Williams Jr.",
                    "G.G. Jackson": "GG Jackson",
                    "Cameron Christie": "Cam Christie",
                    "Brandon Boston Jr": "Brandon Boston",
                    "Jeenathan Williams": "Nate Williams",
                    "Kevin Knox": "Kevin Knox II",
                    "Mohamed Bamba": "Mo Bamba",
                    "Kevon Harris": "Kevon Harris",
                    "Terence Davis": "Terence Davis",
                    "J.D. Davison": "JD Davison",
                }
                if player_name in player_mappings:
                    player_name = player_mappings[player_name]
                
                # Find matching player(s) and update salary
                players = Player.objects.filter(name__iexact=player_name)
                if players.exists():
                    for player in players:
                        player.base_salary = salary
                        player.save()
                        updated_count += 1
                        #logger.info(f"Updated salary for {player.name}: ${salary:,}")
                else:
                    logger.warning(f"No player found for {player_name}")
            
            # Record the update
            LastUpdated.update_timestamp(
                data_type="player_salaries_update",
                updated_by=f"Admin ({request.user.username})",
                notes=f"Updated salaries for {updated_count} players from Spotrac"
            )
            
            self.message_user(
                request,
                f"Successfully updated salaries for {updated_count} players",
                level="success"
            )
            
        except Exception as e:
            logger.error(f"Error syncing salaries: {str(e)}")
            self.message_user(
                request,
                f"Error syncing salaries: {str(e)}",
                level="error"
            )
        
        return HttpResponseRedirect("../")
    
    def update_olympic_medal_winners(self, request):
        """Update Olympic medal status for players based on static lists"""
        gold_count = 0
        silver_count = 0
        bronze_count = 0
        
        # Update gold medal winners
        for player_name in static_olympic_gold_winners:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_olympic_gold_medal = True
                player.save()
                gold_count += 1
                
        # Update silver medal winners
        for player_name in static_olympic_silver_winners:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_olympic_silver_medal = True
                player.save()
                silver_count += 1
                
        # Update bronze medal winners
        for player_name in static_olympic_bronze_winners:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_olympic_bronze_medal = True
                player.save()
                bronze_count += 1
        
        # Record the update timestamp
        LastUpdated.update_timestamp(
            data_type="olympic_medals_update",
            updated_by=f"Admin ({request.user.username})",
            notes=f"Updated Olympic medal winners: {gold_count} gold, {silver_count} silver, {bronze_count} bronze"
        )
        
        self.message_user(
            request, 
            f"Successfully updated Olympic medal winners: {gold_count} gold, {silver_count} silver, {bronze_count} bronze", 
            level="success"
        )
        return HttpResponseRedirect("../")
    
    def update_all_nba_teams(self, request):
        """Update All-NBA team status for players based on static lists"""
        first_team_count = 0
        second_team_count = 0
        third_team_count = 0
        rookie_team_count = 0
        defensive_team_count = 0
        
        # Update first team winners
        for player_name in static_all_nba_first_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_first_team = True
                player.save()
                first_team_count += 1
                
        # Update second team winners
        for player_name in static_all_nba_second_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_second_team = True
                player.save()
                second_team_count += 1
                
        # Update third team winners
        for player_name in static_all_nba_third_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_third_team = True
                player.save()
                third_team_count += 1
        
        # Update rookie team winners
        for player_name in static_all_nba_rookie_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_rookie_team = True
                player.save()
                rookie_team_count += 1
        
        # Update defensive team winners
        for player_name in static_all_nba_defensive_team:
            players = Player.objects.filter(name__iexact=static_players._strip_accents(player_name))
            for player in players:
                player.is_award_all_nba_defensive_team = True
                player.save()
                defensive_team_count += 1
        
        # Record the update timestamp
        LastUpdated.update_timestamp(
            data_type="all_nba_teams_update",
            updated_by=f"Admin ({request.user.username})",
            notes=f"Updated All-NBA team winners: {first_team_count} first team, {second_team_count} second team, {third_team_count} third team, {rookie_team_count} rookie team, {defensive_team_count} defensive team"
        )
        
        self.message_user(
            request, 
            f"Successfully updated All-NBA team winners: {first_team_count} first team, {second_team_count} second team, {third_team_count} third team, {rookie_team_count} rookie team, {defensive_team_count} defensive team",  
            level="success"
        )
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
            