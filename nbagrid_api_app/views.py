from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.db.models import F

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from datetime import datetime, timedelta
from nbagrid_api_app.GameFilter import GameFilter
from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import Player, GameResult, GameCompletion, LastUpdated
from nbagrid_api_app.GameState import GameState, CellData

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

def get_navigation_dates(requested_date: datetime) -> tuple[datetime, datetime, bool, bool]:
    """Calculate previous and next dates for navigation."""
    prev_date: datetime = requested_date - timedelta(days=1)
    next_date: datetime = requested_date + timedelta(days=1)
    earliest_date: datetime	 = datetime(2025, 4, 1)
    
    show_prev = prev_date >= earliest_date
    show_next = next_date <= datetime.now()
    
    return prev_date, next_date, show_prev, show_next

def get_game_filters(requested_date: datetime) -> tuple[list[GameFilter], list[GameFilter]]:
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
                init_filters = [dynamic_filters[row], static_filters[col]]
                GameResult.initialize_scores_from_recent_games(requested_date.date(), cell_key, filters=init_filters)
    return filters
        
def initialize_game_state(request, year, month, day) -> tuple[str, GameState]:
    """Initialize or get the current game state from session."""
    game_state_key = f'game_state_{year}_{month}_{day}'
    game_state_dict = request.session.get(game_state_key, {})
    game_state = GameState().from_dict(game_state_dict)
    
    # Save the session if it's a new game state
    if game_state_key not in request.session:
        request.session[game_state_key] = game_state.to_dict()
        request.session.save()
    return game_state_key, game_state

def build_grid(static_filters: list[GameFilter], dynamic_filters: list[GameFilter]) -> list[list[dict]]:
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
    return grid

def handle_player_guess(request, game_grid, game_state: GameState, requested_date: datetime):
    """Handle a player's guess."""
    if game_state.is_finished or game_state.attempts_remaining <= 0:
        logger.error(f"Cannot handle another guess: Game is already finished or attempts remaining is 0")
        return JsonResponse({'error': 'Game is finished'}, status=400)
    
    try:    
        # Get data from request.POST instead of request.body
        player_id = request.POST.get('player_id')
        row = int(request.POST.get('row', 0))
        col = int(request.POST.get('col', 0))
        cell_key = f'{row}_{col}'
        
        # Check if this cell already has a correct guess
        cell_data_list = game_state.selected_cells.get(cell_key, [])
        if any(cell_data['is_correct'] for cell_data in cell_data_list):
            logger.error(f"Cannot handle another guess:Cell {cell_key} already has a correct guess")
            return JsonResponse({'error': 'Cell already correct'}, status=400)
                
        # check if player exists, we need it later
        try:
            player = Player.objects.get(stats_id=player_id)
        except Player.DoesNotExist:
            logger.error(f"Cannot handle guess: Player {player_id} not found")
            return JsonResponse({'error': 'Player not found'}, status=404)
                
        cell = game_grid[row][col]
        is_correct = all(f.apply_filter(Player.objects.filter(stats_id=player_id)).exists() for f in cell['filters'])
        
        # Create new cell data for this guess
        cell_data = CellData(
            player_id=player_id,
            player_name=player.name,
            is_correct=is_correct
        )
        
        # Add the guess to the cell's data list
        if cell_key not in game_state.selected_cells:
            game_state.selected_cells[cell_key] = []
        game_state.selected_cells[cell_key].append(cell_data)
        
        # Handle correct guess
        if is_correct:
            handle_correct_guess(requested_date, cell_key, player, cell_data, game_state)
        
        # Calculate total score for both correct and incorrect guesses
        update_total_score(game_state, requested_date)
        logger.info(f"Player {player.name} in cell {cell_key} guessed {'correctly' if is_correct else 'incorrectly'}. Total score: {game_state.total_score}")
        
        game_state.decrement_attempts()
        game_state.check_completion(len(game_grid) * len(game_grid[0]))
        
        # If game is finished, get correct players for all remaining cells
        cell_players = {}
        if game_state.is_finished:
            cell_players = get_correct_players(game_grid, game_state)
            
            # Record game completion
            if not GameCompletion.objects.filter(date=requested_date.date(), session_key=request.session.session_key).exists():
                # Count how many cells have correct guesses
                correct_cells_count = sum(1 for cell_key, cell_data_list in game_state.selected_cells.items() 
                                      if any(cell_data.get('is_correct', False) for cell_data in cell_data_list))
                
                GameCompletion.objects.create(
                    date=requested_date.date(),
                    session_key=request.session.session_key,
                    correct_cells=correct_cells_count,
                    final_score=game_state.total_score
                )
        
        # Save the updated game state to the session
        game_state_key = f'game_state_{requested_date.year}_{requested_date.month}_{requested_date.day}'
        request.session[game_state_key] = game_state.to_dict()
        request.session.save()
        
        # Get completion count
        completion_count = GameCompletion.get_completion_count(requested_date.date())
        
        return JsonResponse({
            'is_correct': is_correct,
            'player_name': player.name,
            'cell_data': game_state.selected_cells[cell_key],
            'attempts_remaining': game_state.attempts_remaining,
            'is_finished': game_state.is_finished,
            'total_score': game_state.total_score,
            'cell_players': cell_players,
            'completion_count': completion_count,
            'selected_cells': {k: [cd for cd in v] for k, v in game_state.selected_cells.items()}
        })
    except Exception as e:
        logger.error(f"Error handling guess: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)

def handle_correct_guess(requested_date, cell_key, player, cell_data, game_state):
    """Handle the logic for a correct guess."""
    try:
        result, created = GameResult.objects.get_or_create(
            date=requested_date.date(),
            cell_key=cell_key,
            player=player,
            defaults={'guess_count': 1}
        )
        
        if not created:
            result.guess_count = result.guess_count + 1
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
            
        # Update the cell data in game_state
        game_state.selected_cells[cell_key].append(cell_data)
            
        logger.info(f"Player {player.name} in cell {cell_key} - First guess: {is_first_guess}, Score: {cell_score}, Tier: {cell_data['tier']}")
    except Exception as e:
        logger.error(f"Failed to store game result: {e}")

def update_total_score(game_state, requested_date):
    """Calculate the total score for all correct cells."""
    total_score = 0
    for cell_key, cell_data_list in game_state.selected_cells.items():
        correct_cell_data = next((cell_data for cell_data in cell_data_list if cell_data.get('is_correct', False)), None)
        if correct_cell_data:
            total_score += correct_cell_data['score']
    game_state.total_score = total_score

def index(request):
    """Render today's game directly."""
    current_date = datetime.now()
    return game(request, current_date.year, current_date.month, current_date.day)

def get_correct_players(game_grid, game_state):
    """Get the correct players for each cell."""
    correct_players = {}
    for row in range(len(game_grid)):
        for col in range(len(game_grid[0])):
            cell_key = f'{row}_{col}'
            cell_data_list = game_state.selected_cells.get(cell_key, [])
            cell = game_grid[row][col]
            
            # Initialize the list for this cell
            correct_players[cell_key] = []
            
            # Add wrong guesses first
            for cell_data in cell_data_list:
                if not cell_data['is_correct']:
                    try:
                        wrong_player = Player.objects.get(stats_id=cell_data['player_id'])
                        correct_players[cell_key].append({
                            'name': wrong_player.name,
                            'stats': [f.get_player_stats_str(wrong_player) for f in cell['filters']],
                            'is_wrong_guess': True
                        })
                    except Player.DoesNotExist:
                        pass
            
            # Add correct players
            matching_players = Player.objects.all()
            for f in cell['filters']:
                matching_players = f.apply_filter(matching_players)
            # Include player stats for each matching player
            for p in matching_players:
                correct_players[cell_key].append({
                    'name': p.name,
                    'stats': [f.get_player_stats_str(p) for f in cell['filters']],
                    'is_wrong_guess': False
                })
    
    return correct_players

def game(request, year, month, day):
    """Main game view function."""
    requested_date = get_valid_date(year, month, day)
    # redirect to a valid date if the requested date is not valid
    if requested_date != datetime(year=year, month=month, day=day):
        return redirect('game', 
            year=requested_date.year, 
            month=requested_date.month, 
            day=requested_date.day
        )
    
    prev_date, next_date, show_prev, show_next = get_navigation_dates(requested_date)
    static_filters, dynamic_filters = get_game_filters(requested_date)
    game_state_key, game_state = initialize_game_state(request, year, month, day)
    
    game_grid = build_grid(static_filters, dynamic_filters)
    
    if request.method == 'POST':
        response = handle_player_guess(request, game_grid, game_state, requested_date)
        request.session[game_state_key] = game_state.to_dict()
        return response
    
    # Get correct players for each cell
    correct_players = get_correct_players(game_grid, game_state)
    
    # Get completion count
    completion_count = GameCompletion.get_completion_count(requested_date.date())
    
    # Get the last update timestamp for player data specifically
    try:
        last_updated = LastUpdated.objects.filter(data_type="player_data").order_by('-last_updated').first()
        last_updated_date = last_updated.last_updated if last_updated else None
    except Exception as e:
        logger.error(f"Error fetching last update timestamp: {e}")
        last_updated_date = None
    
    # Format the last updated date
    if last_updated_date:
        last_updated_str = last_updated_date.strftime('%B %d, %Y')
    else:
        last_updated_str = 'Unknown'
    
    return render(request, 'game.html', {
        'year': year,
        'month': requested_date.strftime('%B'),
        'month_num': requested_date.month,
        'day': day,
        'static_filters': [f.get_desc() for f in static_filters],
        'dynamic_filters': [f.get_desc() for f in dynamic_filters],
        'static_filters_detailed': [f.get_detailed_desc() for f in static_filters],
        'dynamic_filters_detailed': [f.get_detailed_desc() for f in dynamic_filters],
        'grid': game_grid,
        'selected_players': set(),
        'attempts_remaining': game_state.attempts_remaining,
        'selected_cells': game_state.selected_cells,
        'is_finished': game_state.is_finished,
        'correct_players': correct_players,
        'total_score': game_state.total_score,
        'completion_count': completion_count,
        'show_prev': show_prev,
        'show_next': show_next,
        'prev_date': prev_date,
        'next_date': next_date,
        'last_updated_date': last_updated_str
    })

def search_players(request):
    """Search for players by name."""
    name = request.GET.get('name', '')
    if len(name) < 3:
        return JsonResponse([], safe=False)
    
    players = Player.objects.filter(name__icontains=name)[:5]
    return JsonResponse([{"stats_id": player.stats_id, "name": player.name} for player in players], safe=False)
