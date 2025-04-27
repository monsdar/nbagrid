from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.db.models import F

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from datetime import datetime, timedelta
from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import Player, GameResult, GameCompletion
import json

def get_valid_date(year, month, day):
    """Validate and return a valid date for the game."""
    current_date = datetime.now()
    requested_date = datetime(year=year, month=month, day=day)
    earliest_date = datetime(2025, 4, 1)
    
    if requested_date > current_date:
        return current_date
    if requested_date < earliest_date:
        return earliest_date
    return requested_date

def get_navigation_dates(requested_date):
    """Calculate previous and next dates for navigation."""
    prev_date = requested_date - timedelta(days=1)
    next_date = requested_date + timedelta(days=1)
    earliest_date = datetime(2025, 4, 1)
    
    show_prev = prev_date >= earliest_date
    show_next = next_date <= datetime.now()
    
    return prev_date, next_date, show_prev, show_next

def get_game_filters(requested_date):
    """Get or create game filters for the requested date."""
    # Create a GameBuilder with the requested date's timestamp as seed
    builder = GameBuilder(requested_date.timestamp())
    # Get the filters - this will either retrieve from DB or create new ones
    filters = builder.get_tuned_filters(requested_date)
        
    # Initialize scores for all cells if this is a new game and no completions exist
    # AND no initial game results exist for this date
    if (not GameCompletion.objects.filter(date=requested_date.date()).exists() and
        not GameResult.objects.filter(date=requested_date.date()).exists()):
        static_filters, dynamic_filters = filters
        for row in range(len(dynamic_filters)):
            for col in range(len(static_filters)):
                cell_key = f'{row}_{col}'
                GameResult.initialize_scores_from_recent_games(requested_date.date(), cell_key)
    
    return filters
        
def initialize_game_state(request, year, month, day):
    """Initialize or get the current game state from session."""
    game_state_key = f'game_state_{year}_{month}_{day}'
    game_state = request.session.get(game_state_key, {
        'attempts_remaining': 10,
        'selected_cells': {},
        'is_finished': False
    })
    # Save the session if it's a new game state
    if game_state_key not in request.session:
        request.session[game_state_key] = game_state
        request.session.save()
    return game_state_key, game_state

def build_grid(static_filters, dynamic_filters, selected_cells):
    """Build the game grid with correct row/column structure."""
    grid = []
    for row_idx, dynamic in enumerate(dynamic_filters):
        row = []
        for col_idx, static in enumerate(static_filters):
            cell = {
                'filters': [static, dynamic],
                'row': row_idx,
                'col': col_idx
            }
            row.append(cell)
        grid.append(row)
    
    # Debug log the grid structure
    logger.debug(f"Built grid structure: {grid}")
    logger.debug(f"Grid dimensions: {len(grid)} rows x {len(grid[0]) if grid else 0} columns")
    return grid

def handle_player_guess(request, grid, game_state, requested_date):
    """Handle a player's guess."""
    try:
        # Get data from request.POST instead of request.body
        player_id = request.POST.get('player_id')
        row = int(request.POST.get('row', 0))
        col = int(request.POST.get('col', 0))
        
        # Debug log the request data and grid access
        logger.debug(f"Handling guess - row: {row}, col: {col}, player_id: {player_id}")
        logger.debug(f"Grid dimensions: {len(grid)} rows x {len(grid[0]) if grid else 0} columns")
        
        if game_state['is_finished'] or game_state['attempts_remaining'] <= 0:
            return JsonResponse({'error': 'Game is finished'}, status=400)
        
        cell_key = f'{row}_{col}'
        cell_data = game_state['selected_cells'].get(cell_key, {})
        
        if cell_data.get('is_correct', False):
            return JsonResponse({'error': 'Cell already correct'}, status=400)
        
        try:
            player = Player.objects.get(stats_id=player_id)
        except Player.DoesNotExist:
            return JsonResponse({'error': 'Player not found'}, status=404)
        
        # Debug log the cell being accessed
        logger.debug(f"Accessing cell at row {row}, col {col}")
        logger.debug(f"Cell structure: {grid[row][col]}")
        
        cell = grid[row][col]
        # Use apply_filter instead of check
        is_correct = all(f.apply_filter(Player.objects.filter(stats_id=player_id)).exists() for f in cell['filters'])
        
        if not cell_key in game_state['selected_cells']:
            game_state['selected_cells'][cell_key] = {}
        
        cell_data = game_state['selected_cells'][cell_key]
        cell_data['player_id'] = player_id
        cell_data['player_name'] = player.name
        cell_data['is_correct'] = is_correct
        
        if is_correct:
            handle_correct_guess(requested_date, cell_key, player, cell_data)
        
        # Calculate total score for both correct and incorrect guesses
        calculate_total_score(game_state, requested_date)
        logger.info(f"Player {player.name} in cell {cell_key} guessed {'correctly' if is_correct else 'incorrectly'}. Total score: {game_state['total_score']}")
        
        game_state['attempts_remaining'] -= 1
        update_game_completion(game_state, grid)
        
        # If attempts reach 0, get correct players for all remaining cells
        correct_players = {}
        if game_state['attempts_remaining'] == 0:
            for r in range(len(grid)):
                for c in range(len(grid[0])):
                    cell_key = f'{r}_{c}'
                    if not game_state['selected_cells'].get(cell_key, {}).get('is_correct', False):
                        cell = grid[r][c]
                        matching_players = Player.objects.all()
                        for f in cell['filters']:
                            matching_players = f.apply_filter(matching_players)
                        correct_players[cell_key] = [p.name for p in matching_players]
            
            # Record game completion
            if not GameCompletion.objects.filter(date=requested_date.date(), session_key=request.session.session_key).exists():
                GameCompletion.objects.create(date=requested_date.date(), session_key=request.session.session_key)
        
        # Save the updated game state to the session
        game_state_key = f'game_state_{requested_date.year}_{requested_date.month}_{requested_date.day}'
        request.session[game_state_key] = game_state
        request.session.save()
        
        # Get completion count
        completion_count = GameCompletion.get_completion_count(requested_date.date())
        
        return JsonResponse({
            'is_correct': is_correct,
            'player_name': player.name,
            'cell_data': cell_data,
            'attempts_remaining': game_state['attempts_remaining'],
            'is_finished': game_state['is_finished'],
            'total_score': game_state.get('total_score', 0),
            'correct_players': correct_players,
            'completion_count': completion_count
        })
    except Exception as e:
        logger.error(f"Error handling guess: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)

def handle_correct_guess(requested_date, cell_key, player, cell_data):
    """Handle the logic for a correct guess."""
    try:
        result, created = GameResult.objects.get_or_create(
            date=requested_date.date(),
            cell_key=cell_key,
            player=player,
            defaults={'guess_count': 1}
        )
        
        if not created:
            result.guess_count = F('guess_count') + 1
            result.save()
        
        cell_score = GameResult.get_player_rarity_score(requested_date.date(), cell_key, player)
        cell_data['score'] = cell_score
        
        # Check if this is the first time this player has been guessed in this cell
        is_first_guess = created
        
        if is_first_guess:
            cell_data['tier'] = 'first'
        elif cell_score < 0.5:
            cell_data['tier'] = 'common'
        elif cell_score < 0.9:
            cell_data['tier'] = 'rare'
        else:
            cell_data['tier'] = 'epic'
            
        logger.info(f"Player {player.name} in cell {cell_key} - First guess: {is_first_guess}, Score: {cell_score}, Tier: {cell_data['tier']}")
    except Exception as e:
        logger.error(f"Failed to store game result: {e}")

def update_game_completion(game_state, grid):
    """Update game completion status."""
    if game_state['attempts_remaining'] == 0:
        game_state['is_finished'] = True
    else:
        all_correct = True
        for r in range(len(grid)):
            for c in range(len(grid[0])):
                cell_key = f'{r}_{c}'
                if not game_state['selected_cells'].get(cell_key, {}).get('is_correct', False):
                    all_correct = False
                    break
            if not all_correct:
                break
        game_state['is_finished'] = all_correct

def calculate_total_score(game_state, requested_date):
    """Calculate the total score for all correct cells."""
    total_score = 0
    for cell_key, cell_data in game_state['selected_cells'].items():
        if cell_data.get('is_correct', False):
            player_id = cell_data['player_id']
            try:
                player = Player.objects.get(stats_id=player_id)
                cell_score = GameResult.get_player_rarity_score(requested_date.date(), cell_key, player)
                total_score += cell_score
            except Player.DoesNotExist:
                continue
    game_state['total_score'] = total_score

def index(request):
    """Redirect to today's game."""
    current_date = datetime.now()
    return redirect('game', year=current_date.year, month=current_date.month, day=current_date.day)

def game(request, year, month, day):
    """Main game view function."""
    requested_date = get_valid_date(year, month, day)
    if requested_date != datetime(year=year, month=month, day=day):
        return redirect('game', 
            year=requested_date.year, 
            month=requested_date.month, 
            day=requested_date.day
        )
    
    prev_date, next_date, show_prev, show_next = get_navigation_dates(requested_date)
    static_filters, dynamic_filters = get_game_filters(requested_date)
    game_state_key, game_state = initialize_game_state(request, year, month, day)
    
    grid = build_grid(static_filters, dynamic_filters, game_state['selected_cells'])
    
    if request.method == 'POST':
        response = handle_player_guess(request, grid, game_state, requested_date)
        request.session[game_state_key] = game_state
        return response
    
    # Get correct players for each cell
    correct_players = {}
    for row in range(len(grid)):
        for col in range(len(grid[0])):
            cell_key = f'{row}_{col}'
            if not game_state['selected_cells'].get(cell_key, {}).get('is_correct', False):
                # Find all players that match the cell's filters
                cell = grid[row][col]
                matching_players = Player.objects.all()
                for f in cell['filters']:
                    matching_players = f.apply_filter(matching_players)
                correct_players[cell_key] = [p.name for p in matching_players]
    
    # Get completion count
    completion_count = GameCompletion.get_completion_count(requested_date.date())
    
    return render(request, 'game.html', {
        'year': year,
        'month': requested_date.strftime('%B'),
        'month_num': requested_date.month,
        'day': day,
        'static_filters': [f.get_desc() for f in static_filters],
        'dynamic_filters': [f.get_desc() for f in dynamic_filters],
        'grid': grid,
        'selected_players': set(),
        'attempts_remaining': game_state['attempts_remaining'],
        'selected_cells': game_state['selected_cells'],
        'is_finished': game_state['is_finished'],
        'correct_players': correct_players,
        'total_score': game_state.get('total_score', 0),
        'completion_count': completion_count,
        'show_prev': show_prev,
        'show_next': show_next,
        'prev_date': prev_date,
        'next_date': next_date
    })

def search_players(request):
    """Search for players by name."""
    name = request.GET.get('name', '')
    if len(name) < 3:
        return JsonResponse([], safe=False)
    
    players = Player.objects.filter(name__icontains=name)[:5]
    return JsonResponse([{"stats_id": player.stats_id, "name": player.name} for player in players], safe=False)
