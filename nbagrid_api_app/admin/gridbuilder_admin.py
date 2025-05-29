"""Admin views for managing grid builder functionality"""

from datetime import datetime, timedelta
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render
import json
import logging

from nbagrid_api_app.models import Player, Team, GameFilterDB, LastUpdated
from nbagrid_api_app.GameFilter import gamefilter_to_json, gamefilter_from_json, get_dynamic_filters, get_static_filters, TeamFilter, PositionFilter

logger = logging.getLogger(__name__)

class GridBuilderAdmin(admin.ModelAdmin):
    """Admin view for managing grid builder functionality"""
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('grid_builder/', self.grid_builder, name='nbagrid_api_app_gamegrid_grid_builder'),
            path('calculate_grid_stats/', self.calculate_grid_stats, name='nbagrid_api_app_gamegrid_calculate_grid_stats'),
            path('adjust_filter/', self.adjust_filter, name='nbagrid_api_app_gamegrid_adjust_filter'),
            path('randomize_filter/', self.randomize_filter, name='nbagrid_api_app_gamegrid_randomize_filter'),
            path('export_grid/', self.export_grid, name='nbagrid_api_app_gamegrid_export_grid'),
            path('submit_game/', self.submit_game, name='nbagrid_api_app_gamegrid_submit_game'),
        ]
        return my_urls + urls
    
    def grid_builder(self, request):
        """View for the grid builder interface"""
        # Get all available filters from GameFilter
        available_filters = []
        
        # Add static filters
        for filter in get_static_filters():
            available_filters.append(gamefilter_to_json(filter))
        
        # Add dynamic filters
        for filter in get_dynamic_filters():
            available_filters.append(gamefilter_to_json(filter))
        
        context = {
            'title': 'Grid Builder',
            'available_filters': available_filters,
            'filters': {},  # Empty filters for initial state
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/grid_builder.html', context)
    
    @method_decorator(csrf_exempt)
    def calculate_grid_stats(self, request):
        """Calculate statistics for the selected filters"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
        
        try:
            data = json.loads(request.body)
            filters = data.get('filters', {})
            logger.info(f"Received filters: {filters}")
            
            # Initialize intersection counts
            intersection_counts = {}
            total_players = 0
            
            # get a list of all possible filters
            all_filters = get_static_filters() + get_dynamic_filters()
            
            # Process each intersection
            for row in "012":
                intersection_counts[row] = {}
                for col in "012":
                    # Get the filters for this intersection
                    row_filter_data = filters.get('row', {}).get(row)
                    col_filter_data = filters.get('col', {}).get(col)
                    
                    if row_filter_data and col_filter_data:
                        logger.info(f"Processing intersection {row}_{col}")
                        
                        # Create filter instances from the data
                        row_filter = None
                        col_filter = None
                        for filter in all_filters:
                            if filter.__class__.__name__ == row_filter_data['class']:
                                logger.info(f"Found row filter: {filter.__class__.__name__}")
                                row_filter = gamefilter_from_json(filter, row_filter_data)
                            if filter.__class__.__name__ == col_filter_data['class']:
                                logger.info(f"Found col filter: {filter.__class__.__name__}")
                                col_filter = gamefilter_from_json(filter, col_filter_data)
                                                
                        if row_filter and col_filter:
                            # Get players that match both filters
                            matching_players = Player.objects.all()
                            initial_count = matching_players.count()
                            logger.info(f"Initial player count: {initial_count}")
                            
                            matching_players = row_filter.apply_filter(matching_players)
                            after_row_count = matching_players.count()
                            logger.info(f"After row filter count: {after_row_count}")
                            
                            matching_players = col_filter.apply_filter(matching_players)
                            final_count = matching_players.count()
                            logger.info(f"Final count: {final_count}")
                            
                            intersection_counts[row][col] = final_count
                            total_players += final_count
                        else:
                            logger.warning(f"Could not create filter instances for {row}_{col}")
                            intersection_counts[row][col] = 0
                    else:
                        intersection_counts[row][col] = 0
            
            # Calculate average players per cell
            num_intersections = sum(1 for row in intersection_counts.values() for col in row.values() if col > 0)
            avg_players = total_players / num_intersections if num_intersections > 0 else 0
            
            response_data = {
                'total_players': total_players,
                'avg_players': avg_players,
                'intersection_counts': intersection_counts
            }
            
            logger.info(f"Grid stats response: {response_data}")
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.exception(f"Error calculating grid stats: {str(e)}")
            return JsonResponse({
                'error': str(e),
                'total_players': 0,
                'avg_players': 0,
                'intersection_counts': {}
            }, status=500)

    @method_decorator(csrf_exempt)
    def adjust_filter(self, request):
        """Adjust the range of a dynamic filter"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
        
        try:
            data = json.loads(request.body)
            filter_data = data.get('filter')
            action = data.get('action')
            config = data.get('config')
            
            if not filter_data or not action:
                return JsonResponse({'error': 'Missing filter data or action'}, status=400)
            
            # Find the filter instance
            filter_class_name = filter_data['class']
            filter_instance = None
            
            for filter in get_static_filters() + get_dynamic_filters():
                if filter.__class__.__name__ == filter_class_name:
                    logger.info(f"Found filter to adjust: {filter.__class__.__name__}")
                    filter_instance = gamefilter_from_json(filter, filter_data)
                    break
            if filter_instance:
                if action == 'widen':
                    filter_instance.widen_filter()
                elif action == 'narrow':
                    filter_instance.narrow_filter()
                else:
                    logger.error(f"Invalid action: {action}")
                    return JsonResponse({'error': 'Invalid action'}, status=400)
            else:
                logger.error(f"Invalid filter or filter does not support range adjustment: {filter_class_name}")
                return JsonResponse({'error': 'Invalid filter or filter does not support range adjustment'}, status=400)
            
            return JsonResponse({
                'new_name': filter_instance.get_desc(),
                'new_config': gamefilter_to_json(filter_instance)['config']
            })
            
        except Exception as e:
            logger.error(f"Error adjusting filter: {str(e)}")
            return JsonResponse({
                'error': str(e)
            }, status=500)

    @method_decorator(csrf_exempt)
    def randomize_filter(self, request):
        """Randomize a TeamFilter or PositionFilter"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
        
        try:
            data = json.loads(request.body)
            filter_data = data.get('filter')
            
            if not filter_data:
                return JsonResponse({'error': 'Missing filter data'}, status=400)
            
            # Find the filter instance
            filter_class_name = filter_data['class']
            filter_instance = None
            
            for filter in get_static_filters() + get_dynamic_filters():
                if filter.__class__.__name__ == filter_class_name:
                    filter_instance = gamefilter_from_json(filter, filter_data)
                    break
            
            if not filter_instance:
                return JsonResponse({'error': 'Filter not found'}, status=400)
            
            # Randomize based on filter type
            if isinstance(filter_instance, TeamFilter):
                teams = list(Team.objects.all())
                # get next team in the list
                next_index = 0
                for index, team in enumerate(teams):
                    if team.name == filter_instance.team_name:
                        next_index = (index + 1) % len(teams)
                        break
                filter_instance.team_name = teams[next_index].name
                filter_data['config']['team_name'] = filter_instance.team_name
            elif isinstance(filter_instance, PositionFilter):
                positions = ['Guard', 'Forward', 'Center']
                # get next position in the list
                next_index = 0
                for index, position in enumerate(positions):
                    if position == filter_instance.selected_position:
                        next_index = (index + 1) % len(positions)
                        break
                filter_instance.selected_position = positions[next_index]
                filter_data['config']['selected_position'] = filter_instance.selected_position
            else:
                return JsonResponse({'error': 'Filter type does not support randomization'}, status=400)
            
            return JsonResponse({
                'new_name': filter_instance.get_desc(),
                'new_config': filter_data['config']
            })
            
        except Exception as e:
            logger.error(f"Error randomizing filter: {str(e)}")
            return JsonResponse({
                'error': str(e)
            }, status=500)

    @method_decorator(csrf_exempt)
    def export_grid(self, request):
        """Export the current grid configuration to a JSON file"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
        
        try:
            data = json.loads(request.body)
            filters = data.get('filters', {})
            
            # Create a response with the JSON data
            response = HttpResponse(
                json.dumps(filters, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = 'attachment; filename="grid_config.json"'
            return response
            
        except Exception as e:
            logger.error(f"Error exporting grid: {str(e)}")
            return JsonResponse({
                'error': str(e)
            }, status=500)

    def get_next_available_date(self):            # Find the next available date that doesn't have a game
        target_date = datetime.now().date()
        while GameFilterDB.objects.filter(date=target_date).exists():
            target_date += timedelta(days=1)
        target_date = datetime.combine(target_date, datetime.min.time())
        return target_date

    @method_decorator(csrf_exempt)
    def submit_game(self, request):
        """Submit the current grid configuration as a new game"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
        
        try:
            data = json.loads(request.body)
            filters = data.get('filters', {})
            logger.info(f"Received filters for submission: {filters}")
            
            # Validate filter configuration
            if not filters or not isinstance(filters, dict):
                logger.error("Invalid filters format received")
                return JsonResponse({'error': 'Invalid filters format'}, status=400)
                
            # Extract row and column filters
            row_filters = filters.get('row', {})
            col_filters = filters.get('col', {})
            logger.info(f"Row filters: {row_filters}")
            logger.info(f"Column filters: {col_filters}")
            
            # Validate we have the correct number of filters
            if len(row_filters) != 3 or len(col_filters) != 3:
                error_msg = f'Invalid filter configuration: expected 3 row and 3 column filters, got {len(row_filters)} row and {len(col_filters)} column'
                logger.error(error_msg)
                return JsonResponse({
                    'error': error_msg
                }, status=400)
            
            # Create GameFilterDB objects for each filter
            # Get the next available date
            target_date = self.get_next_available_date()
            
            # Process row filters (static filters)
            for index, filter_data in row_filters.items():
                GameFilterDB.objects.create(
                    date=target_date.date(),
                    filter_type='static',
                    filter_class=filter_data['class'],
                    filter_config=filter_data['config'],
                    filter_index=int(index)
                )
            
            # Process column filters (dynamic filters)
            for index, filter_data in col_filters.items():
                GameFilterDB.objects.create(
                    date=target_date.date(),
                    filter_type='dynamic',
                    filter_class=filter_data['class'],
                    filter_config=filter_data['config'],
                    filter_index=int(index)
                )
            
            # Create the GameGrid object
            from nbagrid_api_app.GameBuilder import GameBuilder
            builder = GameBuilder()
            builder.get_tuned_filters(target_date)
            
            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="game_data",
                updated_by="GridBuilder submission",
                notes=f"Imported prebuilt game for {target_date.date()}"
            )
            
            return JsonResponse({
                "status": "success",
                "message": f"Game imported for {target_date.date()}",
                "date": {
                    "year": target_date.year,
                    "month": target_date.month,
                    "day": target_date.day
                }
            })
            
        except Exception as e:
            error_msg = f"Error submitting game: {str(e)}"
            logger.error(error_msg)
            return JsonResponse({
                'error': error_msg
            }, status=500)