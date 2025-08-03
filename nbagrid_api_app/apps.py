import os
from django.apps import AppConfig
from django.core.management import call_command


class NbagridApiAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nbagrid_api_app"
    
    def ready(self):
        """
        Called when Django starts up. Check if we should automatically import test data.
        """
        # Only run this in the main Django process, not in migrations or other commands
        if os.environ.get('RUN_MAIN') != 'true' and 'runserver' in os.sys.argv:
            return
            
        # Check if IMPORT_TEST_DATA environment variable is set
        import_test_data = os.environ.get('IMPORT_TEST_DATA', '0').lower() in ('1', 'true', 'yes')
        
        if import_test_data:
            try:
                # Import the models here to avoid circular imports
                from .models import Player, Team
                
                # Check if database is empty (no players or teams)
                if not Player.objects.exists() and not Team.objects.exists():
                    print("IMPORT_TEST_DATA is set and database is empty. Importing test data...")
                    call_command('import_test_data', '--force')
                    print("Test data import completed automatically.")
                else:
                    print("IMPORT_TEST_DATA is set but database already contains data. Skipping automatic import.")
            except Exception as e:
                print(f"Error during automatic test data import: {e}")
                # Don't raise the exception to avoid breaking Django startup
