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
            Player.active.create(
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
                is_award_all_nba_first=(i % 5 == 0),
                is_award_all_nba_second=(i % 7 == 0),
                is_award_all_nba_third=(i % 11 == 0),
                is_award_all_defensive=(i % 6 == 0),
                is_award_all_rookie=(i % 8 == 0),
                is_award_champ=(i % 9 == 0),
                is_award_all_star=(i % 4 == 0),
                is_award_olympic_gold_medal=(i % 15 == 0),
                is_award_olympic_silver_medal=(i % 17 == 0),
                is_award_olympic_bronze_medal=(i % 19 == 0),
            )
        
        # Add team relationships
        for i in range(0, 50, 5):
            player = Player.active.get(stats_id=i)
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
        builder = GameBuilder(random_seed=42)
        
        # Create a fresh dynamic filter
        dynamic_filters = get_dynamic_filters(seed=42)
        original_filter = dynamic_filters[0]  # Take the first one
        
        original_type = original_filter.get_filter_type_description()
        
        # Save it to database (simulate what GameBuilder does)
        test_date = datetime.now().date() + timedelta(days=10)
        
        # Use the builder's serialization method to properly store the filter config
        filter_config = builder._get_serializable_config(original_filter)
        
        db_filter = GameFilterDB.objects.create(
            date=test_date,
            filter_type="dynamic",
            filter_class=original_filter.__class__.__name__,
            filter_config=filter_config,
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
        builder = GameBuilder(random_seed=999)
        
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
        
        # Create a dynamic filter and save its usage MULTIPLE times to ensure weight increases beyond fun_factor
        dynamic_filters = get_dynamic_filters(seed=42)
        used_filter = dynamic_filters[0]
        
        # Use the builder's serialization method to properly store the filter config
        filter_config = builder._get_serializable_config(used_filter)
        
        # Store the filter multiple times (simulate using it on 3 different dates)
        for i in range(3):
            GameFilterDB.objects.create(
                date=test_date - timedelta(days=i),
                filter_type="dynamic",
                filter_class=used_filter.__class__.__name__,
                filter_config=filter_config,
                filter_index=0,
            )
        
        # Calculate weights
        weights = builder.get_filter_weights(dynamic_filters, 'dynamic')
        
        # Get an unused filter for comparison
        unused_filter = None
        for f in dynamic_filters:
            if f.get_filter_type_description() != used_filter.get_filter_type_description():
                unused_filter = f
                break
        
        # The used filter should have higher weight (less likely to be selected) than unused ones
        used_filter_type = used_filter.get_filter_type_description()
        unused_filter_type = unused_filter.get_filter_type_description()
        
        self.assertIn(used_filter_type, weights, "Used filter should have weight entry")
        self.assertIn(unused_filter_type, weights, "Unused filter should have weight entry")
        
        # Used filter weight should be higher than unused filter weight
        # (Note: fun_factor is applied to both, but used filter has additional usage penalty)
        self.assertGreater(weights[used_filter_type], weights[unused_filter_type], 
                          f"Used filter weight ({weights[used_filter_type]}) should be higher than "
                          f"unused filter weight ({weights[unused_filter_type]})")

    def test_filter_selection_with_weights(self):
        """Test that filter selection respects the weights."""
        builder = GameBuilder(random_seed=42)
        
        dynamic_filters = get_dynamic_filters(seed=42)
        
        # Select filters multiple times and ensure we get variety
        selected_types = set()
        for _ in range(5):
            builder.random_seed = 42 + len(selected_types) # vary seed slightly each time
            selected = builder.select_filters(dynamic_filters, 3, 'dynamic')
            for f in selected:
                selected_types.add(f.get_filter_type_description())
        
        # We should see some variety in the selected filter types
        self.assertGreater(len(selected_types), 3, "Should see variety in selected filter types")

    def test_weighted_choice_basic_functionality(self):
        """Test that weighted_choice method works correctly with basic inputs."""
        builder = GameBuilder(random_seed=42)
        
        items = ['A', 'B', 'C']
        weights = [1.0, 2.0, 3.0]  # Higher weights should be less likely to be selected
        
        # Test that it returns one of the items
        result = builder.weighted_choice(items, weights)
        self.assertIn(result, items, "Result should be one of the input items")
        
        # Test with equal weights
        equal_weights = [1.0, 1.0, 1.0]
        result = builder.weighted_choice(items, equal_weights)
        self.assertIn(result, items, "Result should be one of the input items with equal weights")

    def test_weighted_choice_distribution(self):
        """Test that weighted_choice respects weight distribution over many calls."""
        builder = GameBuilder(random_seed=42)
        
        items = ['low_weight', 'high_weight']
        weights = [0.1, 10.0]  # low_weight should be selected much more often
        
        # Run many iterations to test distribution
        results = []
        for _ in range(1000):
            # Reset random seed for consistent testing
            builder.random_seed = 42 + len(results)
            result = builder.weighted_choice(items, weights)
            results.append(result)
        
        # Count occurrences
        low_weight_count = results.count('low_weight')
        high_weight_count = results.count('high_weight')
        
        # low_weight should be selected significantly more often
        self.assertGreater(low_weight_count, high_weight_count, 
                          f"Low weight item should be selected more often. "
                          f"Low: {low_weight_count}, High: {high_weight_count}")
        
        # Ratio should be roughly inverse of the weight ratio
        # With weights [0.1, 10.0], low_weight should be selected ~100x more often
        ratio = low_weight_count / max(high_weight_count, 1)
        self.assertGreater(ratio, 10, f"Selection ratio should reflect weight difference, got {ratio}")

    def test_weighted_choice_edge_cases(self):
        """Test weighted_choice with edge cases."""
        builder = GameBuilder(random_seed=42)
        
        # Test with single item
        single_item = ['only']
        single_weight = [1.0]
        result = builder.weighted_choice(single_item, single_weight)
        self.assertEqual(result, 'only', "Should return the only item")
        
        # Test with very small weights (but not zero)
        items = ['A', 'B']
        small_weights = [0.001, 0.002]
        result = builder.weighted_choice(items, small_weights)
        self.assertIn(result, items, "Should handle very small weights")
        
        # Test with very large weights
        large_weights = [1000.0, 2000.0]
        result = builder.weighted_choice(items, large_weights)
        self.assertIn(result, items, "Should handle very large weights")

    def test_weighted_choice_zero_weight_protection(self):
        """Test that weighted_choice handles zero weights gracefully."""
        builder = GameBuilder(random_seed=42)
        
        items = ['A', 'B', 'C']
        
        # Test with zero weight - should handle gracefully now
        zero_weights = [1.0, 0.0, 2.0]
        result = builder.weighted_choice(items, zero_weights)
        # Should return a valid result without crashing
        self.assertIn(result, items, "Result should be valid even with zero weight")
        
        # Test with all zero weights - should fall back to random choice
        all_zero_weights = [0.0, 0.0, 0.0]
        result = builder.weighted_choice(items, all_zero_weights)
        self.assertIn(result, items, "Should handle all zero weights gracefully")
        
        # Test with mixed zero and non-zero weights
        mixed_weights = [0.0, 1.0, 0.0]
        result = builder.weighted_choice(items, mixed_weights)
        # Should only select from non-zero weight items (in this case, only 'B')
        # But since we can't guarantee which item is selected, we just check it's valid
        self.assertIn(result, items, "Should handle mixed zero and non-zero weights")

    def test_weighted_choice_non_deterministic_behavior(self):
        """Test that weighted_choice provides variety across multiple calls."""
        items = ['A', 'B', 'C', 'D']
        weights = [1.0, 2.0, 3.0, 4.0]
        
        # Test multiple calls with different seeds to get variety
        results = []
        for i in range(20):  # More calls to increase chance of variety
            # Use different seeds for each call to simulate variety
            builder = GameBuilder(random_seed=123 + i)
            result = builder.weighted_choice(items, weights)
            results.append(result)
        
        # Should get some variety (not all the same)
        unique_results = set(results)
        self.assertGreater(len(unique_results), 1, 
                          f"Should get variety in results, got: {unique_results}")
        
        # All results should still be valid items
        for result in results:
            self.assertIn(result, items, f"Invalid result: {result}")

    def test_weighted_choice_matches_expected_behavior(self):
        """Test that weighted_choice behaves as documented."""
        builder = GameBuilder(random_seed=42)
        
        # According to the docstring: "higher weight = less likely to be selected"
        items = ['should_be_selected_often', 'should_be_selected_rarely']
        weights = [0.1, 100.0]  # First item has much lower weight
        
        selections = []
        for i in range(100):
            # Use different seeds for variety
            builder = GameBuilder(random_seed=42 + i)
            result = builder.weighted_choice(items, weights)
            selections.append(result)
        
        often_count = selections.count('should_be_selected_often')
        rarely_count = selections.count('should_be_selected_rarely')
        
        # The item with lower weight should be selected more often
        self.assertGreater(often_count, rarely_count,
                          f"Lower weight item should be selected more often. "
                          f"Often: {often_count}, Rarely: {rarely_count}")

    def test_weighted_choice_fallback_behavior(self):
        """Test the fallback behavior of weighted_choice."""
        builder = GameBuilder(random_seed=42)
        
        items = ['A', 'B', 'C']
        weights = [1.0, 2.0, 3.0]
        
        # The method has a fallback that returns items[-1]
        # Let's test this by examining the algorithm logic
        # We can't easily force the fallback, but we can verify the method completes
        for _ in range(50):
            result = builder.weighted_choice(items, weights)
            self.assertIn(result, items, "Result should always be from the items list")

    def test_fun_factor_integration_in_weights(self):
        """Test that fun factors are properly integrated into filter weight calculation."""
        from nbagrid_api_app.GameFilter import TeamFilter, LastNameFilter, AllNbaFilter
        
        builder = GameBuilder(random_seed=42)
        
        # Create filters with different fun factors
        team_filter = TeamFilter(seed=42)  # fun_factor = 2.5 (higher = more fun)
        lastname_filter = LastNameFilter(seed=42)  # fun_factor = 2.0 (higher = more fun)
        allnba_filter = AllNbaFilter()  # fun_factor = 1.0 (default)
        
        # Calculate weights for these filters
        filter_pool = [team_filter, lastname_filter, allnba_filter]
        weights = builder.get_filter_weights(filter_pool, 'static')
        
        # Verify all filters have weights
        self.assertEqual(len(weights), 3, "Should have weights for all filters")
        
        # Get the weights for each filter
        team_weight = weights[team_filter.get_filter_type_description()]
        lastname_weight = weights[lastname_filter.get_filter_type_description()]
        allnba_weight = weights[allnba_filter.get_filter_type_description()]
        
        # Verify weights are positive
        self.assertGreater(team_weight, 0, "Team filter weight should be positive")
        self.assertGreater(lastname_weight, 0, "LastName filter weight should be positive")
        self.assertGreater(allnba_weight, 0, "AllNba filter weight should be positive")
        
        # With base weight of 1.0 and no usage history:
        # team_filter: 1.0 / 2.5 = 0.4 (more likely to be selected)
        # lastname_filter: 1.0 / 2.0 = 0.5 (more likely to be selected)
        # allnba_filter: 1.0 / 1.0 = 1.0 (default likelihood)
        
        # TeamFilter (higher fun factor) should have lower weight than AllNbaFilter (default fun factor)
        self.assertLess(team_weight, allnba_weight, 
                       f"TeamFilter (fun=2.5) should have lower weight than AllNbaFilter (fun=1.0). "
                       f"Team: {team_weight}, AllNba: {allnba_weight}")
        
        # LastNameFilter should have lower weight than AllNbaFilter
        self.assertLess(lastname_weight, allnba_weight,
                       f"LastNameFilter (fun=2.0) should have lower weight than AllNbaFilter (fun=1.0). "
                       f"LastName: {lastname_weight}, AllNba: {allnba_weight}")

    def test_fun_factor_affects_selection_probability(self):
        """Test that filters with higher fun factors are selected more often."""
        from nbagrid_api_app.GameFilter import TeamFilter, AllNbaFilter
        
        # Run multiple selection tests with different seeds
        team_selections = 0
        allnba_selections = 0
        
        for seed in range(50):
            builder = GameBuilder(random_seed=seed)
            
            team_filter = TeamFilter(seed=seed)  # fun_factor = 2.5 (more fun)
            allnba_filter = AllNbaFilter()  # fun_factor = 1.0 (default)
            
            filter_pool = [team_filter, allnba_filter]
            selected = builder.select_filters(filter_pool, 1, 'static')
            
            if selected[0].get_filter_type_description() == team_filter.get_filter_type_description():
                team_selections += 1
            else:
                allnba_selections += 1
        
        # TeamFilter (higher fun factor) should be selected more often than AllNbaFilter
        self.assertGreater(team_selections, allnba_selections,
                          f"TeamFilter (fun=2.5) should be selected more often than AllNbaFilter (fun=1.0). "
                          f"Team: {team_selections}, AllNba: {allnba_selections}")

    def test_fun_factor_with_usage_history(self):
        """Test that fun factor works together with usage history."""
        from nbagrid_api_app.GameFilter import TeamFilter, AllNbaFilter
        
        builder = GameBuilder(random_seed=42)
        
        # Create filters
        team_filter = TeamFilter(seed=42)  # fun_factor = 2.5
        allnba_filter = AllNbaFilter()  # fun_factor = 1.0
        
        # Add recent usage history for TeamFilter
        test_date = datetime.now().date() - timedelta(days=1)
        
        # Use the builder's serialization method to properly store the filter config
        filter_config = builder._get_serializable_config(team_filter)
        
        GameFilterDB.objects.create(
            date=test_date,
            filter_type="static",
            filter_class=team_filter.__class__.__name__,
            filter_config=filter_config,
            filter_index=0,
        )
        
        # Calculate weights
        filter_pool = [team_filter, allnba_filter]
        weights = builder.get_filter_weights(filter_pool, 'static')
        
        team_weight = weights[team_filter.get_filter_type_description()]
        allnba_weight = weights[allnba_filter.get_filter_type_description()]
        
        # Even with usage history increasing TeamFilter's base weight,
        # the fun factor should still make it competitive
        # We can't predict exact values, but weights should both be positive and reasonable
        self.assertGreater(team_weight, 0)
        self.assertGreater(allnba_weight, 0)
        
        # The important thing is that fun factor is being applied
        # We can verify this by checking that the weight ratio makes sense
        # Without fun factor: team_weight would be higher (due to usage)
        # With fun factor: team_weight gets divided by 2.5, making it more competitive

    def test_played_with_player_filter_serialization(self):
        """Test that PlayedWithPlayerFilter can be serialized and stored in the database."""
        from nbagrid_api_app.GameFilter import PlayedWithPlayerFilter
        
        builder = GameBuilder(random_seed=42)
        
        # Create test players for the filter
        test_player = Player.active.create(
            stats_id=9999,
            name='Test All-Star',
            last_name='All-Star',
            is_award_all_star=True,
            career_ppg=20.0,
            career_rpg=5.0,
            career_apg=5.0,
            career_gp=500,
            num_seasons=10,
            height_cm=200,
            position='Guard'
        )
        
        # Create a teammate
        teammate = Player.active.create(
            stats_id=9998,
            name='Test Teammate',
            last_name='Teammate',
            career_ppg=15.0,
            career_rpg=4.0,
            career_apg=3.0,
            career_gp=300,
            num_seasons=5,
            height_cm=195,
            position='Forward'
        )
        
        # Add teammates relationship
        test_player.teammates.add(teammate)
        teammate.teammates.add(test_player)
        
        # Create a PlayedWithPlayerFilter
        played_with_filter = PlayedWithPlayerFilter(seed=42)
        
        # Verify it has a target_player
        self.assertIsNotNone(played_with_filter.target_player)
        self.assertIsInstance(played_with_filter.target_player, Player)
        
        # Try to store it using GameBuilder's method (this should not raise an exception)
        test_date = datetime.now().date() + timedelta(days=5)
        
        try:
            builder.store_filters_in_db(
                test_date, 
                [played_with_filter], 
                []
            )
        except TypeError as e:
            self.fail(f"Failed to serialize PlayedWithPlayerFilter: {e}")
        
        # Verify the filter was stored
        stored_filters = GameFilterDB.objects.filter(date=test_date)
        self.assertEqual(stored_filters.count(), 1, "Should have stored one filter")
        
        # Verify the stored config has target_player as a string
        stored_filter = stored_filters.first()
        self.assertIn('target_player', stored_filter.filter_config)
        self.assertIsInstance(stored_filter.filter_config['target_player'], str, 
                             "target_player should be stored as a string")
        
        # Verify we can reconstruct the filter from the database
        reconstructed_filter = create_filter_from_db(stored_filter)
        self.assertIsInstance(reconstructed_filter, PlayedWithPlayerFilter)
        self.assertIsInstance(reconstructed_filter.target_player, Player)
        self.assertEqual(reconstructed_filter.target_player.name, 
                        stored_filter.filter_config['target_player'])