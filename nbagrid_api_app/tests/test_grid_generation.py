from datetime import datetime, timedelta
from django.test import TestCase

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.GameFilter import get_dynamic_filters, get_static_filters, create_filter_from_db
from nbagrid_api_app.models import GameFilterDB, Player, Team


class GridGenerationTest(TestCase):
    def setUp(self):
        """Set up test data."""
        # Create a test team
        self.team = Team.objects.create(stats_id=1, name="Test Team", abbr="TT")
        
        # Create test players with varied stats
        for i in range(50):
            Player.objects.create(
                stats_id=i,
                name=f'Test Player {i}',
                career_ppg=10 + (i % 20),
                career_rpg=5 + (i % 10),
                career_apg=3 + (i % 8),
                career_gp=100 + (i * 10),
                num_seasons=3 + (i % 10),
                height_cm=180 + (i % 30),
                base_salary=1000000 + (i * 500000),
                career_high_pts=20 + (i % 40),
                career_high_reb=8 + (i % 15),
                career_high_ast=5 + (i % 12),
                career_high_stl=2 + (i % 6),
                career_high_blk=1 + (i % 8),
                last_name=f'Player{i}',
                country='USA' if i % 3 == 0 else 'Canada',
                position=['Guard', 'Forward', 'Center'][i % 3],
                draft_number=1 + (i % 60),
                is_undrafted=(i % 10 == 0),
            )
        
        # Add team relationships
        for i in range(0, 50, 5):
            player = Player.objects.get(stats_id=i)
            player.teams.add(self.team)

    def test_filter_weight_calculation(self):
        """Test that filter weight calculation works correctly with new type descriptions."""
        builder = GameBuilder(random_seed=42)
        
        # Test dynamic filter weights
        dynamic_filters = get_dynamic_filters(seed=42)
        weights = builder.get_filter_weights(dynamic_filters, 'dynamic')
        
        # Verify all filters have weights
        filter_type_descs = [f.get_filter_type_description() for f in dynamic_filters]
        missing_weights = [desc for desc in filter_type_descs if desc not in weights]
        
        self.assertEqual(len(missing_weights), 0, f"Missing weights for: {missing_weights}")
        self.assertEqual(len(weights), len(dynamic_filters), "Should have weights for all dynamic filters")
        
        # Test static filter weights
        static_filters = get_static_filters(seed=42)
        weights = builder.get_filter_weights(static_filters, 'static')
        
        # Verify all filters have weights
        filter_type_descs = [f.get_filter_type_description() for f in static_filters]
        missing_weights = [desc for desc in filter_type_descs if desc not in weights]
        
        self.assertEqual(len(missing_weights), 0, f"Missing weights for: {missing_weights}")
        self.assertEqual(len(weights), len(static_filters), "Should have weights for all static filters")

    def test_filter_type_consistency(self):
        """Test that filter type descriptions are consistent between fresh filters and reconstructed ones."""
        # Create a fresh dynamic filter
        dynamic_filters = get_dynamic_filters(seed=42)
        original_filter = dynamic_filters[0]  # Take the first one
        
        original_type = original_filter.get_filter_type_description()
        
        # Save it to database (simulate what GameBuilder does)
        test_date = datetime.now().date() + timedelta(days=10)
        
        db_filter = GameFilterDB.objects.create(
            date=test_date,
            filter_type="dynamic",
            filter_class=original_filter.__class__.__name__,
            filter_config=original_filter.__dict__,
            filter_index=0,
        )
        
        # Reconstruct from database
        reconstructed_filter = create_filter_from_db(db_filter)
        reconstructed_type = reconstructed_filter.get_filter_type_description()
        
        # Check if they match
        self.assertEqual(original_type, reconstructed_type,
                        f"Filter type descriptions don't match: {original_type} vs {reconstructed_type}")

    def test_grid_generation_success(self):
        """Test that complete grid generation works."""
        builder = GameBuilder(random_seed=123)
        
        # Try to generate a grid
        test_date = datetime.now().date() + timedelta(days=1)
        
        try:
            static_filters, dynamic_filters = builder.get_tuned_filters(test_date, num_iterations=3)
            
            # Verify we got the expected number of filters
            self.assertEqual(len(static_filters), builder.num_statics, 
                           f"Expected {builder.num_statics} static filters, got {len(static_filters)}")
            self.assertEqual(len(dynamic_filters), builder.num_dynamics,
                           f"Expected {builder.num_dynamics} dynamic filters, got {len(dynamic_filters)}")
            
            # Verify all filters have valid type descriptions
            for f in static_filters:
                type_desc = f.get_filter_type_description()
                self.assertIsNotNone(type_desc, "Static filter should have type description")
                self.assertTrue(len(type_desc) > 0, "Static filter type description should not be empty")
            
            for f in dynamic_filters:
                type_desc = f.get_filter_type_description()
                self.assertIsNotNone(type_desc, "Dynamic filter should have type description")
                self.assertTrue(len(type_desc) > 0, "Dynamic filter type description should not be empty")
                # Dynamic filters should have the format: ClassName_field_comparison
                self.assertIn('_', type_desc, "Dynamic filter type should contain underscores")
                
        except Exception as e:
            self.fail(f"Grid generation failed: {e}")

    def test_filter_type_descriptions_are_distinct(self):
        """Test that different dynamic filters have different type descriptions."""
        dynamic_filters = get_dynamic_filters(seed=42)
        
        # Group filters by their type description
        type_groups = {}
        for filter_obj in dynamic_filters:
            type_desc = filter_obj.get_filter_type_description()
            if type_desc not in type_groups:
                type_groups[type_desc] = []
            type_groups[type_desc].append(filter_obj)
        
        # Check that we have multiple distinct types (this was the original bug)
        self.assertGreater(len(type_groups), 1, "Should have multiple distinct filter types")
        
        # Most types should have only one filter (unless there are legitimate duplicates)
        single_filter_types = [desc for desc, filters in type_groups.items() if len(filters) == 1]
        self.assertGreater(len(single_filter_types), 10, "Most filter types should be unique")

    def test_weight_calculation_with_usage_history(self):
        """Test that weight calculation works correctly when there's usage history."""
        builder = GameBuilder(random_seed=42)
        
        # Create some historical usage data
        test_date = datetime.now().date() - timedelta(days=3)
        
        # Create a dynamic filter and save its usage
        dynamic_filters = get_dynamic_filters(seed=42)
        used_filter = dynamic_filters[0]
        
        GameFilterDB.objects.create(
            date=test_date,
            filter_type="dynamic",
            filter_class=used_filter.__class__.__name__,
            filter_config=used_filter.__dict__,
            filter_index=0,
        )
        
        # Calculate weights
        weights = builder.get_filter_weights(dynamic_filters, 'dynamic')
        
        # The used filter should have higher weight (less likely to be selected)
        used_filter_type = used_filter.get_filter_type_description()
        self.assertIn(used_filter_type, weights, "Used filter should have weight entry")
        self.assertGreater(weights[used_filter_type], 1.0, "Used filter should have higher weight")

    def test_filter_selection_with_weights(self):
        """Test that filter selection respects the weights."""
        builder = GameBuilder(random_seed=42)
        
        dynamic_filters = get_dynamic_filters(seed=42)
        
        # Select filters multiple times and ensure we get variety
        selected_types = set()
        for _ in range(5):
            selected = builder.select_filters(dynamic_filters, 3, 'dynamic')
            for f in selected:
                selected_types.add(f.get_filter_type_description())
        
        # We should see some variety in the selected filter types
        self.assertGreater(len(selected_types), 3, "Should see variety in selected filter types")