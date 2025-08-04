import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import IntegrityError


class Command(BaseCommand):
    help = 'Create an admin user from environment variables if no such user exists'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force creation even if a superuser already exists',
        )

    def handle(self, *args, **options):
        # Check if we should use Django's standard environment variables or custom ones
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME') or os.environ.get('DJANGO_ADMIN_USER')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD') or os.environ.get('DJANGO_ADMIN_PASSWORD')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    'No admin user credentials provided via environment variables.\n'
                    'Set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD (Django standard)\n'
                    'or DJANGO_ADMIN_USER and DJANGO_ADMIN_PASSWORD (custom) to create an admin user.'
                )
            )
            return

        # Check if any superuser already exists (unless --force is used)
        if not options['force'] and User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    'Admin user already exists. Use --force to create anyway.'
                )
            )
            return

        # Check if user with this username already exists
        if User.objects.filter(username=username).exists():
            if not options['force']:
                self.stdout.write(
                    self.style.WARNING(
                        f'User "{username}" already exists. Use --force to update password.'
                    )
                )
                return
            else:
                # Update existing user
                user = User.objects.get(username=username)
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                if email:
                    user.email = email
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated admin user "{username}" with full admin privileges.'
                    )
                )
                return

        try:
            # Create new superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created admin user "{username}" with full admin privileges.'
                )
            )
        except IntegrityError as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to create admin user: {e}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Unexpected error creating admin user: {e}'
                )
            )