import json
import os
import random
from django.core.management.base import BaseCommand
from django.conf import settings
from nbagrid_api_app.models import Player, Team


class Command(BaseCommand):
    help = "Import test data for teams and players from JSON files"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force import even if data already exists',
        )

    def handle(self, *args, **options):
        # Check if we should import test data
        import_test_data = os.environ.get('IMPORT_TEST_DATA', '0').lower() in ('1', 'true', 'yes')
        
        if not import_test_data and not options['force']:
            # Check if database is empty
            if Player.active.exists() or Team.objects.exists():
                self.stdout.write(
                    self.style.WARNING('Database already contains data. Use --force to override or set IMPORT_TEST_DATA=1')
                )
                return
        
        if not options['force'] and not import_test_data:
            self.stdout.write(
                self.style.WARNING('IMPORT_TEST_DATA environment variable not set. Use --force to import anyway.')
            )
            return

        self.stdout.write(self.style.SUCCESS('Starting test data import...'))
        
        # Import teams
        self.import_teams()
        
        # Import players
        self.import_players()
        
        self.stdout.write(self.style.SUCCESS('Test data import completed successfully!'))

    def import_teams(self):
        """Import teams from JSON file"""
        teams_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'teams.json'
        )
        
        if not os.path.exists(teams_file):
            self.stdout.write(self.style.ERROR(f'Teams JSON file not found: {teams_file}'))
            return
        
        with open(teams_file, 'r') as f:
            teams_data = json.load(f)
        
        created_count = 0
        updated_count = 0
        
        for team_data in teams_data:
            team, created = Team.objects.get_or_create(
                stats_id=team_data['stats_id'],
                defaults={
                    'name': team_data['name'],
                    'abbr': team_data['abbr']
                }
            )
            
            if created:
                created_count += 1
            else:
                # Update existing team
                team.name = team_data['name']
                team.abbr = team_data['abbr']
                team.save()
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Teams: {created_count} created, {updated_count} updated')
        )

    def import_players(self):
        """Import players based on archetypes from JSON file"""
        archetypes_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'player_archetypes.json'
        )
        
        if not os.path.exists(archetypes_file):
            self.stdout.write(self.style.ERROR(f'Player archetypes JSON file not found: {archetypes_file}'))
            return
        
        with open(archetypes_file, 'r') as f:
            archetypes_data = json.load(f)
        
        # Get all teams for assignment
        all_teams = list(Team.objects.all())
        if not all_teams:
            self.stdout.write(self.style.ERROR('No teams found. Please import teams first.'))
            return
        
        # Set random seed for reproducible results
        random.seed(42)
        
        created_count = 0
        updated_count = 0
        
        # Generate 500 players from 10 archetypes (50 players per archetype)
        for i in range(500):
            archetype = archetypes_data[i % len(archetypes_data)]
            
            # Create variations of the archetype
            player_name = self.generate_player_name(archetype['name'], i)
            stats_id = 1000000 + i  # Use high stats_id to avoid conflicts
            
            # Add some variation to the stats (±10% variation)
            varied_stats = self.add_stat_variation(archetype)
            
            player, created = Player.active.get_or_create(
                stats_id=stats_id,
                defaults={
                    'name': player_name,
                    'position': archetype['position'],
                    'height_cm': varied_stats['height_cm'],
                    'weight_kg': varied_stats['weight_kg'],
                    'career_ppg': varied_stats['career_ppg'],
                    'career_apg': varied_stats['career_apg'],
                    'career_rpg': varied_stats['career_rpg'],
                    'career_bpg': varied_stats['career_bpg'],
                    'career_spg': varied_stats['career_spg'],
                    'career_tpg': varied_stats['career_tpg'],
                    'career_fgp': varied_stats['career_fgp'],
                    'career_3gp': varied_stats['career_3gp'],
                    'career_ftp': varied_stats['career_ftp'],
                    'career_fga': varied_stats['career_fga'],
                    'career_3pa': varied_stats['career_3pa'],
                    'career_fta': varied_stats['career_fta'],
                    'career_high_pts': varied_stats['career_high_pts'],
                    'career_high_ast': varied_stats['career_high_ast'],
                    'career_high_reb': varied_stats['career_high_reb'],
                    'career_high_stl': varied_stats['career_high_stl'],
                    'career_high_blk': varied_stats['career_high_blk'],
                    'career_high_to': varied_stats['career_high_to'],
                    'career_high_fg': varied_stats['career_high_fg'],
                    'career_high_3p': varied_stats['career_high_3p'],
                    'career_high_ft': varied_stats['career_high_ft'],
                    'draft_year': varied_stats['draft_year'],
                    'draft_round': varied_stats['draft_round'],
                    'draft_number': varied_stats['draft_number'],
                    'country': archetype['country'],
                    'career_gp': random.randint(200, 800),
                    'num_seasons': random.randint(3, 18),
                }
            )
            
            if created:
                # Set awards based on archetype
                for award_field in ['is_greatest_75', 'is_award_mvp', 'is_award_finals_mvp', 
                                  'is_award_champ', 'is_award_all_star', 'is_award_all_nba_first',
                                  'is_award_all_defensive', 'is_award_dpoy', 'is_award_rookie_of_the_year',
                                  'is_award_all_rookie', 'is_award_olympic_gold_medal']:
                    if award_field in archetype and archetype[award_field]:
                        setattr(player, award_field, True)
                
                # Assign player to 1-3 random teams
                num_teams = random.randint(1, 3)
                selected_teams = random.sample(all_teams, num_teams)
                player.teams.set(selected_teams)
                
                player.save()
                created_count += 1
            else:
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Players: {created_count} created, {updated_count} updated')
        )

    def generate_player_name(self, archetype_name, index):
        """Generate a unique player name based on archetype and index"""
        first_names = [
            'LeBron', 'Stephen', 'Kevin', 'Giannis', 'Luka', 'Jayson', 'Nikola', 'Joel',
            'Kawhi', 'Jimmy', 'Russell', 'Damian', 'Anthony', 'Zion', 'Ja', 'Trae',
            'Devin', 'Donovan', 'Bam', 'Khris', 'CJ', 'Tyler', 'Pascal', 'Fred',
            'Kyle', 'DeMar', 'Chris', 'Blake', 'Andre', 'Draymond', 'Klay', 'Paul',
            'James', 'Rudy', 'Clint', 'Myles', 'Brook', 'Al', 'Marcus', 'Jrue',
            'Malcolm', 'Terry', 'Duncan', 'Mikal', 'OG', 'Robert', 'Derrick', 'Lonzo',
            'Josh', 'RJ', 'Cade', 'Evan', 'Scottie', 'Franz', 'Paolo', 'Victor'
        ]
        
        last_names = [
            'James', 'Curry', 'Durant', 'Antetokounmpo', 'Doncic', 'Tatum', 'Jokic', 'Embiid',
            'Leonard', 'Butler', 'Westbrook', 'Lillard', 'Davis', 'Williamson', 'Morant', 'Young',
            'Booker', 'Mitchell', 'Adebayo', 'Middleton', 'McCollum', 'Herro', 'Siakam', 'VanVleet',
            'Lowry', 'DeRozan', 'Paul', 'Griffin', 'Drummond', 'Green', 'Thompson', 'George',
            'Harden', 'Gobert', 'Capela', 'Turner', 'Lopez', 'Horford', 'Smart', 'Holiday',
            'Brogdon', 'Rozier', 'Robinson', 'Bridges', 'Anunoby', 'Williams', 'White', 'Ball',
            'Hart', 'Barrett', 'Cunningham', 'Mobley', 'Barnes', 'Wagner', 'Banchero', 'Wembanyama'
        ]
        
        # Use index to ensure uniqueness while maintaining some randomness
        random.seed(index + 1000)  # Different seed for names
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        
        # Add suffix if it's a variation of the archetype
        variation_num = (index // len(first_names)) + 1
        if variation_num > 1:
            return f"{first_name} {last_name} {variation_num}"
        else:
            return f"{first_name} {last_name}"

    def add_stat_variation(self, archetype):
        """Add random variation to archetype stats (±10%)"""
        varied_stats = {}
        
        for key, value in archetype.items():
            if key.startswith('career_') and isinstance(value, (int, float)):
                # Add ±10% variation
                variation = random.uniform(0.9, 1.1)
                if isinstance(value, int):
                    varied_stats[key] = max(0, int(value * variation))
                else:
                    varied_stats[key] = max(0.0, round(value * variation, 3))
            elif key in ['height_cm', 'weight_kg', 'draft_year', 'draft_round', 'draft_number']:
                if isinstance(value, int):
                    variation = random.uniform(0.95, 1.05)
                    varied_stats[key] = max(1, int(value * variation))
                else:
                    varied_stats[key] = value
            else:
                varied_stats[key] = value
        
        return varied_stats