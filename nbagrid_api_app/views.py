from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from datetime import datetime, timedelta
from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import Player

cached_filters = {}

def index(request):
    current_date = datetime.now()
    return redirect('game', year=current_date.year, month=current_date.month, day=current_date.day)

def game(request, year, month, day):
    current_date = datetime.now()
    requested_date = datetime(year=year, month=month, day=day)
    earliest_date = datetime(2025, 4, 1)
    
    # Redirect future dates to today
    if requested_date > current_date:
        return redirect('game', 
            year=current_date.year, 
            month=current_date.month, 
            day=current_date.day
        )
    
    # Redirect dates before April 1st 2025 to that date
    if requested_date < earliest_date:
        return redirect('game',
            year=earliest_date.year,
            month=earliest_date.month,
            day=earliest_date.day
        )
    
    # Calculate previous and next dates for navigation
    prev_date = requested_date - timedelta(days=1)
    next_date = requested_date + timedelta(days=1)
    
    # Only show previous/next if they're within valid range
    show_prev = prev_date >= earliest_date
    show_next = next_date <= current_date
    
    if requested_date in cached_filters:
        (static_filters, dynamic_filters) = cached_filters[requested_date]
    else:
        builder = GameBuilder(requested_date.timestamp())
        (static_filters, dynamic_filters) = builder.get_tuned_filters()
        cached_filters[requested_date] = (static_filters, dynamic_filters)
        
    # Create a grid of filter pairs and track selected players
    grid = []
    selected_players = set()  # Track selected player IDs
    
    # Initialize or get the current game state from session
    game_state_key = f'game_state_{year}_{month}_{day}'
    game_state = request.session.get(game_state_key, {
        'attempts_remaining': 10,
        'selected_cells': {},
        'is_finished': False
    })
    
    logger.debug(f"Loading game state for {game_state_key}: {game_state}")  # Debug log
    
    attempts_remaining = game_state['attempts_remaining']
    selected_cells = game_state.get('selected_cells', {})
    is_finished = game_state.get('is_finished', False)
    
    # Log the structure of selected_cells
    logger.debug(f"Selected cells structure: {selected_cells}")
    for cell_key, cell_data in selected_cells.items():
        logger.debug(f"Cell {cell_key} data: {cell_data}")
    
    # Build grid with correct row/column structure
    for row_idx, dynamic in enumerate(dynamic_filters):
        row = []
        for col_idx, static in enumerate(static_filters):
            row.append((static, dynamic))
            # Initialize empty cell data if not exists
            cell_key = f'{row_idx}_{col_idx}'
            if cell_key not in selected_cells:
                selected_cells[cell_key] = {}
        grid.append(row)
    
    if request.method == 'POST':
        player_id = request.POST.get('player_id', '')
        row = int(request.POST.get('row', '0'))
        col = int(request.POST.get('col', '0'))
        try:
            player = Player.objects.get(stats_id=player_id)
            # Get the filter pair for this cell
            static_filter, dynamic_filter = grid[row][col]
            # Check if player matches the selected filter pair
            matching_players = static_filter.apply_filter(dynamic_filter.apply_filter(Player.objects.filter(stats_id=player_id)))
            is_correct = matching_players.exists()
            
            # Update game state
            attempts_remaining -= 1
            cell_key = f'{row}_{col}'
            cell_data = {
                'player_id': str(player_id),  # Ensure player_id is a string
                'player_name': player.name,
                'is_correct': is_correct
            }
            selected_cells[cell_key] = cell_data
            logger.debug(f"Updated cell {cell_key} with data: {cell_data}")
            
            # Check if game is finished (either by running out of attempts or completing all cells)
            if attempts_remaining == 0:
                is_finished = True
            else:
                # Check if all cells are correctly guessed
                all_correct = True
                for r in range(len(dynamic_filters)):
                    for c in range(len(static_filters)):
                        cell_key = f'{r}_{c}'
                        if not selected_cells.get(cell_key, {}).get('is_correct', False):
                            all_correct = False
                            break
                    if not all_correct:
                        break
                is_finished = all_correct
            
            if is_finished:
                # Get all correct players for each cell
                correct_players = {}
                for r in range(len(dynamic_filters)):
                    for c in range(len(static_filters)):
                        cell_key = f'{r}_{c}'
                        if cell_key not in selected_cells or not selected_cells[cell_key].get('is_correct', False):
                            static, dynamic = grid[r][c]
                            players = [p.name for p in static.apply_filter(dynamic.apply_filter(Player.objects.all()))]
                            correct_players[cell_key] = players
            
            # Save updated game state
            game_state = {
                'attempts_remaining': attempts_remaining,
                'selected_cells': selected_cells,
                'is_finished': is_finished,
                'correct_players': correct_players if is_finished else {}
            }
            request.session[game_state_key] = game_state
            logger.debug(f"Saving game state for {game_state_key}: {game_state}")
            
            return JsonResponse({
                'success': True,
                'player_name': player.name,
                'is_correct': is_correct,
                'player_id': player.stats_id,
                'attempts_remaining': attempts_remaining,
                'is_finished': is_finished,
                'correct_players': correct_players if is_finished else {}
            })
        except Player.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid player selected'
            }, status=400)
    
    logger.debug(f"Rendering template with selected_cells: {selected_cells}")
    return render(request, 'game.html', {
        'year': year,
        'month': requested_date.strftime('%B'),  # Month name for display
        'month_num': requested_date.month,        # Numeric month for URL
        'day': day,
        'static_filters': [f.get_desc() for f in static_filters],
        'dynamic_filters': [f.get_desc() for f in dynamic_filters],
        'grid': grid,
        'selected_players': selected_players,
        'attempts_remaining': attempts_remaining,
        'selected_cells': selected_cells,
        'is_finished': is_finished,
        'correct_players': game_state.get('correct_players', {}),
        'show_prev': show_prev,
        'show_next': show_next,
        'prev_date': prev_date,
        'next_date': next_date
    })

def search_players(request):
    name = request.GET.get('name', '')
    if len(name) < 3:
        return JsonResponse([], safe=False)
    
    players = Player.objects.filter(name__icontains=name)[:5]
    return JsonResponse([{"stats_id": player.stats_id, "name": player.name} for player in players], safe=False)
