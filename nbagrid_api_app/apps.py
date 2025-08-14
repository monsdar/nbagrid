import os
from django.apps import AppConfig
from django.core.management import call_command


class NbagridApiAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nbagrid_api_app"
    
    def ready(self):
        """
        Called when Django starts up. Check if we should automatically import test data
        and create admin user from environment variables.
        """
        # Skip database operations during migrations or when running management commands
        # that don't need this functionality
        if any(cmd in os.sys.argv for cmd in ['migrate', 'makemigrations', 'collectstatic']):
            return
        
        # Check if we should create an admin user from environment variables
        self._create_admin_user_if_needed()
            
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
    
    def _create_admin_user_if_needed(self):
        """
        Create an admin user from environment variables if no superuser exists.
        Uses Django's standard environment variables or custom fallbacks.
        """
        try:
            from django.contrib.auth.models import User
            
            # Check if we should use Django's standard environment variables or custom ones
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME') or os.environ.get('DJANGO_ADMIN_USER')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD') or os.environ.get('DJANGO_ADMIN_PASSWORD')
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

            # Only proceed if both username and password are provided
            if not username or not password:
                return

            # Check if any superuser already exists
            if User.objects.filter(is_superuser=True).exists():
                return

            # Check if user with this username already exists
            if User.objects.filter(username=username).exists():
                # Update existing user to be a superuser
                user = User.objects.get(username=username)
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                if email:
                    user.email = email
                user.save()
                print(f"Updated existing user '{username}' with admin privileges from environment variables.")
            else:
                # Create new superuser
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                print(f"Created admin user '{username}' with full admin privileges from environment variables.")
                
        except Exception as e:
            print(f"Error during automatic admin user creation: {e}")
            # Don't raise the exception to avoid breaking Django startup
