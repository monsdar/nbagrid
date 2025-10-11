import json
import os
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.GameFilter import get_static_filters, get_dynamic_filters


class Command(BaseCommand):
    help = 'Pre-generate grids and save them as JSON files in ./.grids/ directory'

    def add_arguments(self, parser):
        parser.add_argument(
            'num_grids',
            type=int,
            help='Number of grids to generate'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            default=None,
            help='Start date for grids (YYYY-MM-DD format). If not provided, grids will have no specific date.'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='.grids',
            help='Output directory for generated grid files (default: .grids)'
        )
        parser.add_argument(
            '--quality-threshold',
            type=float,
            default=0.0,
            help='Minimum quality score threshold (0.0 to 1.0, default: 0.0 = no threshold)'
        )
        parser.add_argument(
            '--max-attempts',
            type=int,
            default=50,
            help='Maximum attempts per grid generation (default: 50)'
        )
        parser.add_argument(
            '--random-seed',
            type=int,
            default=None,
            help='Random seed for reproducible results (default: random)'
        )
        parser.add_argument(
            '--min-players',
            type=int,
            default=5,
            help='Minimum players per cell for quality scoring (default: 5)'
        )
        parser.add_argument(
            '--max-players',
            type=int,
            default=40,
            help='Maximum players per cell for quality scoring (default: 40)'
        )

    def handle(self, *args, **options):
        num_grids = options['num_grids']
        start_date_str = options.get('start-date')
        output_dir = options.get('output-dir', '.grids')
        quality_threshold = options.get('quality-threshold', 0.0)
        max_attempts = options.get('max-attempts', 50)
        random_seed = options.get('random-seed')
        min_players = options.get('min-players', 5)
        max_players = options.get('max-players', 40)

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.stdout.write(f"Created output directory: {output_dir}")

        # Parse start date if provided
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                self.stdout.write(f"Using start date: {start_date}")
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f'Invalid date format: {start_date_str}. Use YYYY-MM-DD format.')
                )
                return

        # Initialize grid generator
        generator = OfflineGridGenerator(quality_threshold, max_attempts, random_seed, min_players, max_players)
        
        self.stdout.write(f"Generating {num_grids} grids...")
        self.stdout.write(f"Quality threshold: {quality_threshold}")
        self.stdout.write(f"Max attempts per grid: {max_attempts}")
        self.stdout.write(f"Base random seed: {generator.base_random_seed}")
        self.stdout.write(f"Player range: {min_players}-{max_players} per cell")
        
        successful_grids = 0
        failed_grids = 0
        
        for i in range(num_grids):
            self.stdout.write(f"\nGenerating grid {i + 1}/{num_grids}...")
            
            try:
                # Generate grid
                if start_date:
                    target_date = start_date + timedelta(days=i)
                    grid_data, quality_score = generator.generate_high_quality_grid(target_date)
                else:
                    grid_data, quality_score = generator.generate_high_quality_grid()
                
                if grid_data and (quality_score >= quality_threshold):
                    # Save grid to file
                    filename = self._save_grid_to_file(grid_data, quality_score, i + 1, output_dir, start_date, generator)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Grid {i + 1} generated successfully (quality: {quality_score:.3f}) -> {filename}"
                        )
                    )
                    successful_grids += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"✗ Grid {i + 1} failed quality threshold (best score: {quality_score:.3f})"
                        )
                    )
                    failed_grids += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Grid {i + 1} generation failed: {str(e)}")
                )
                failed_grids += 1

        # Summary
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"Generation complete!")
        self.stdout.write(f"✓ Successful: {successful_grids} grids")
        self.stdout.write(f"✗ Failed: {failed_grids} grids")
        self.stdout.write(f"📁 Output directory: {os.path.abspath(output_dir)}")
                
        if successful_grids > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully generated {successful_grids} grids in {output_dir}/"
                )
            )

    def _save_grid_to_file(self, grid_data, quality_score, grid_number, output_dir, start_date, generator):
        """Save grid data to JSON file"""
        static_filters, dynamic_filters = grid_data
        
        # Prepare grid data for JSON serialization
        grid_json = {
            "grid_number": grid_number,
            "quality_score": quality_score,
            "generated_at": datetime.now().isoformat(),
            "generator_version": "1.0",
            "base_random_seed": generator.base_random_seed,
            "grid_specific_seed": generator.base_random_seed + grid_number if generator.base_random_seed else None,
            "filters": {
                "row": {},
                "col": {}
            }
        }
        
        # Add date if provided
        if start_date:
            grid_json["date"] = {
                "year": start_date.year,
                "month": start_date.month,
                "day": start_date.day
            }
        
        # Add static filters (rows)
        for idx, filter_obj in enumerate(static_filters):
            grid_json["filters"]["row"][str(idx)] = {
                "class": filter_obj.__class__.__name__,
                "config": filter_obj.__dict__,
                "description": filter_obj.get_desc()
            }
        
        # Add dynamic filters (columns)
        for idx, filter_obj in enumerate(dynamic_filters):
            grid_json["filters"]["col"][str(idx)] = {
                "class": filter_obj.__class__.__name__,
                "config": filter_obj.__dict__,
                "description": filter_obj.get_desc()
            }
        
        # Generate filename
        if start_date:
            filename = f"grid_{start_date.strftime('%Y%m%d')}_{grid_number:03d}.json"
        else:
            filename = f"grid_{grid_number:03d}.json"
        
        filepath = os.path.join(output_dir, filename)
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(grid_json, f, indent=2)
        
        return filename


class OfflineGridGenerator:
    """Offline grid generator for creating high-quality grids without time constraints"""
    
    def __init__(self, quality_threshold=0.0, max_attempts=50, random_seed=None, min_players=5, max_players=40):
        self.quality_threshold = quality_threshold
        self.max_attempts = max_attempts
        self.min_num_results = min_players
        self.max_num_results = max_players
        self.base_random_seed = random_seed if random_seed is not None else random.randint(1, 1000000)
        self.generated_grids = []  # Track generated grids for weight calculation
        
    def generate_high_quality_grid(self, target_date=None):
        """Generate a high-quality grid with optional target date"""
        best_grid = None
        best_score = 0
        
        # Create a fresh random seed for this grid generation
        grid_seed = self.base_random_seed + len(self.generated_grids) if self.base_random_seed else random.randint(1, 1000000)
        
        for attempt in range(self.max_attempts):
            # Use GameBuilder to generate the grid
            game_builder = GameBuilder(random_seed=grid_seed)
            
            # Set the builder's player range constraints
            game_builder.min_num_results = self.min_num_results
            game_builder.max_num_results = self.max_num_results
            
            # Generate grid using GameBuilder's existing logic
            static_filters, dynamic_filters = game_builder.get_tuned_filters(requested_date=None)
            
            # Test the grid quality
            quality_score = self._evaluate_grid_quality(static_filters, dynamic_filters)
            
            if quality_score > best_score:
                best_score = quality_score
                best_grid = (static_filters, dynamic_filters)
                
                # Early termination if we meet quality threshold
                if quality_score >= self.quality_threshold:
                    break
        
        # Track the generated grid for future weight calculations
        if best_grid:
            self._track_generated_grid(best_grid, target_date)
        
        return best_grid, best_score
    
    def _track_generated_grid(self, grid_data, target_date=None):
        """Track a generated grid to influence future filter selection weights"""
        static_filters, dynamic_filters = grid_data
        
        grid_info = {
            'date': target_date,
            'static_filters': [f.get_filter_type_description() for f in static_filters],
            'dynamic_filters': [f.get_filter_type_description() for f in dynamic_filters],
            'grid_number': len(self.generated_grids) + 1  # Track order within session
        }
        
        self.generated_grids.append(grid_info)
        
        # Keep only the last 100 grids to avoid memory issues
        if len(self.generated_grids) > 100:
            self.generated_grids = self.generated_grids[-100:]
    
    def _evaluate_grid_quality(self, static_filters, dynamic_filters):
        """Evaluate the quality of a generated grid"""
        try:
            from nbagrid_api_app.models import Player
            
            all_players = Player.active.all()
            cell_counts = []
            
            # Calculate player counts for each cell
            for row_filter in static_filters:
                for col_filter in dynamic_filters:
                    try:
                        count = len(row_filter.apply_filter(col_filter.apply_filter(all_players)))
                        cell_counts.append(count)
                    except:
                        # If filter application fails, count as 0
                        cell_counts.append(0)
            
            if not cell_counts:
                return 0.0
            
            # Quality scoring based on multiple factors
            total_score = 0.0
            
            # 1. Balance score (how evenly distributed)
            mean_count = sum(cell_counts) / len(cell_counts)
            variance = sum((c - mean_count) ** 2 for c in cell_counts) / len(cell_counts)
            balance_score = 1.0 / (1.0 + variance / 100)  # Lower variance = higher score
            total_score += balance_score * 0.3
            
            # 2. Difficulty score (appropriate challenge)
            target_range = (self.min_num_results, self.max_num_results)
            difficulty_score = sum(1.0 for c in cell_counts if target_range[0] <= c <= target_range[1]) / len(cell_counts)
            total_score += difficulty_score * 0.4
            
            # 3. Variety score (different filter types)
            filter_types = set()
            for f in static_filters + dynamic_filters:
                filter_types.add(f.__class__.__name__)
            variety_score = len(filter_types) / 6.0  # 6 total filters
            total_score += variety_score * 0.2
            
            # 4. Reliability score (filters that work consistently)
            reliability_score = 1.0 if all(c > 0 for c in cell_counts) else 0.5
            total_score += reliability_score * 0.1
            
            return total_score
            
        except Exception as e:
            # If evaluation fails, return 0
            return 0.0
