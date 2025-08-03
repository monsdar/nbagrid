from django.test import TestCase

from ..models import Player


class PlayerModelTests(TestCase):
    def setUp(self):
        # Create test players with a mix of short and long names
        test_players = [
            "LeBron James",  # Short name
            "Giannis Antetokounmpo",  # Long name
            "Stephen Curry",  # Short name
            "Kevin Durant",  # Short name
            "Nikola Jokic",  # Short name
            "Joel Embiid",  # Short name
            "Luka Doncic",  # Short name
            "Jayson Tatum",  # Short name
            "Devin Booker",  # Short name
            "Donovan Mitchell",  # Long name
        ]

        for i, name in enumerate(test_players):
            Player.objects.create(stats_id=i + 1, name=name, display_name=name)

    def test_generate_random_name_consistency(self):
        """Test that the same seed always generates the same name"""
        seed = "test_seed_123"
        name1 = Player.generate_random_name(seed)
        name2 = Player.generate_random_name(seed)
        self.assertEqual(name1, name2, "Same seed should generate same name")

    def test_generate_random_name_different_seeds(self):
        """Test that different seeds generate different names"""
        name1 = Player.generate_random_name("seed1")
        name2 = Player.generate_random_name("seed2")
        self.assertNotEqual(name1, name2, "Different seeds should generate different names")

    def test_generate_random_name_length(self):
        """Test that generated names are never longer than 14 characters"""
        for i in range(10):  # Test multiple random seeds
            name = Player.generate_random_name(f"seed_{i}")
            self.assertLessEqual(len(name), 14, f"Generated name '{name}' is longer than 14 characters")

    def test_generate_random_name_format(self):
        """Test that generated names follow the expected format (First Last)"""
        name = Player.generate_random_name("test_seed")
        parts = name.split()
        self.assertEqual(len(parts), 2, "Generated name should have exactly two parts")
        self.assertTrue(all(part[0].isupper() for part in parts), "Each part should start with uppercase")

    def test_generate_random_name_with_long_names(self):
        """Test that the method handles long names correctly by truncating if necessary"""
        # Create a player with a very long name to force truncation
        Player.objects.all().delete()
        Player.objects.create(
            stats_id=999,
            name="Supercalifragilisticexpialidocious Basketballplayer",
            display_name="Supercalifragilisticexpialidocious Basketballplayer",
        )

        # Use a seed that will likely pick the long name
        name = Player.generate_random_name("long_name_seed")
        self.assertLessEqual(len(name), 14, "Long name should be truncated to 14 characters")
