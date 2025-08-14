#!/usr/bin/env python3
"""
Demo script showing the admin user creation feature.

This script demonstrates how to use environment variables to automatically
create Django admin users.
"""

import os
import subprocess
import sys


def run_command(cmd, env_vars=None):
    """Run a command with optional environment variables."""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    
    print(f"Running: {cmd}")
    if env_vars:
        print(f"With environment: {env_vars}")
    print("-" * 50)
    
    result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("=" * 50)
    return result.returncode == 0


def main():
    """Demonstrate the admin user creation functionality."""
    print("Django Admin User Creation Demo")
    print("=" * 50)
    
    # Activate virtual environment first
    venv_activate = "source venv/bin/activate"
    
    print("\n1. Testing without environment variables (should show warning)")
    run_command(f"{venv_activate} && python manage.py create_admin_user")
    
    print("\n2. Creating admin user with Django standard environment variables")
    env_vars = {
        'DJANGO_SUPERUSER_USERNAME': 'demo_admin',
        'DJANGO_SUPERUSER_PASSWORD': 'demo_secure_123',
        'DJANGO_SUPERUSER_EMAIL': 'demo@example.com'
    }
    run_command(f"{venv_activate} && python manage.py create_admin_user", env_vars)
    
    print("\n3. Trying to create another admin user (should skip)")
    env_vars = {
        'DJANGO_SUPERUSER_USERNAME': 'another_admin',
        'DJANGO_SUPERUSER_PASSWORD': 'another_pass_123'
    }
    run_command(f"{venv_activate} && python manage.py create_admin_user", env_vars)
    
    print("\n4. Creating admin user with custom environment variables and --force")
    env_vars = {
        'DJANGO_ADMIN_USER': 'custom_admin',
        'DJANGO_ADMIN_PASSWORD': 'custom_pass_123'
    }
    run_command(f"{venv_activate} && python manage.py create_admin_user --force", env_vars)
    
    print("\n5. Listing all superusers")
    run_command(f'{venv_activate} && python manage.py shell -c "from django.contrib.auth.models import User; users = User.objects.filter(is_superuser=True); print(\'Superusers:\'); [print(f\'- {{u.username}} ({{u.email}})\') for u in users]"')
    
    print("\nDemo completed!")
    print("\nTo use this feature in your Django project:")
    print("1. Set environment variables:")
    print("   export DJANGO_SUPERUSER_USERNAME=admin")
    print("   export DJANGO_SUPERUSER_PASSWORD=your_secure_password")
    print("   export DJANGO_SUPERUSER_EMAIL=admin@example.com")
    print("2. Run: python manage.py create_admin_user")
    print("3. Or the admin user will be created automatically when Django starts")


if __name__ == "__main__":
    main()