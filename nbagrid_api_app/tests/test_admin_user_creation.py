import os
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command
from io import StringIO


class AdminUserCreationTest(TestCase):
    """Test the automatic admin user creation functionality."""

    def setUp(self):
        """Clean up any existing superusers before each test."""
        User.objects.filter(is_superuser=True).delete()

    def test_create_admin_user_with_django_standard_env_vars(self):
        """Test creating admin user with Django's standard environment variables."""
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'testadmin',
            'DJANGO_SUPERUSER_PASSWORD': 'testpass123',
            'DJANGO_SUPERUSER_EMAIL': 'test@example.com'
        }):
            out = StringIO()
            call_command('create_admin_user', stdout=out)
            
            # Check that user was created
            user = User.objects.get(username='testadmin')
            self.assertTrue(user.is_superuser)
            self.assertTrue(user.is_staff)
            self.assertTrue(user.is_active)
            self.assertEqual(user.email, 'test@example.com')
            
            # Check command output
            output = out.getvalue()
            self.assertIn('Successfully created admin user "testadmin"', output)

    def test_create_admin_user_with_custom_env_vars(self):
        """Test creating admin user with custom environment variables."""
        with patch.dict(os.environ, {
            'DJANGO_ADMIN_USER': 'customadmin',
            'DJANGO_ADMIN_PASSWORD': 'custompass123'
        }):
            out = StringIO()
            call_command('create_admin_user', stdout=out)
            
            # Check that user was created
            user = User.objects.get(username='customadmin')
            self.assertTrue(user.is_superuser)
            self.assertTrue(user.is_staff)
            self.assertTrue(user.is_active)
            
            # Check command output
            output = out.getvalue()
            self.assertIn('Successfully created admin user "customadmin"', output)

    def test_no_env_vars_warning(self):
        """Test that appropriate warning is shown when no environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            out = StringIO()
            call_command('create_admin_user', stdout=out)
            
            output = out.getvalue()
            self.assertIn('No admin user credentials provided', output)
            self.assertIn('DJANGO_SUPERUSER_USERNAME', output)
            self.assertIn('DJANGO_ADMIN_USER', output)

    def test_superuser_already_exists(self):
        """Test behavior when a superuser already exists."""
        # Create a superuser first
        User.objects.create_superuser('existing', 'existing@example.com', 'existingpass')
        
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'newadmin',
            'DJANGO_SUPERUSER_PASSWORD': 'newpass123'
        }):
            out = StringIO()
            call_command('create_admin_user', stdout=out)
            
            output = out.getvalue()
            self.assertIn('Admin user already exists', output)
            
            # Verify new user was not created
            self.assertFalse(User.objects.filter(username='newadmin').exists())

    def test_force_create_when_superuser_exists(self):
        """Test creating admin user with --force flag when superuser already exists."""
        # Create a superuser first
        User.objects.create_superuser('existing', 'existing@example.com', 'existingpass')
        
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'newadmin',
            'DJANGO_SUPERUSER_PASSWORD': 'newpass123'
        }):
            out = StringIO()
            call_command('create_admin_user', '--force', stdout=out)
            
            output = out.getvalue()
            self.assertIn('Successfully created admin user "newadmin"', output)
            
            # Verify new user was created
            self.assertTrue(User.objects.filter(username='newadmin').exists())

    def test_update_existing_user_with_force(self):
        """Test updating an existing user with --force flag."""
        # Create a regular user first
        user = User.objects.create_user('regularuser', 'regular@example.com', 'regularpass')
        self.assertFalse(user.is_superuser)
        
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'regularuser',
            'DJANGO_SUPERUSER_PASSWORD': 'newpass123',
            'DJANGO_SUPERUSER_EMAIL': 'updated@example.com'
        }):
            out = StringIO()
            call_command('create_admin_user', '--force', stdout=out)
            
            output = out.getvalue()
            self.assertIn('Successfully updated admin user "regularuser"', output)
            
            # Verify user was updated
            user.refresh_from_db()
            self.assertTrue(user.is_superuser)
            self.assertTrue(user.is_staff)
            self.assertTrue(user.is_active)
            self.assertEqual(user.email, 'updated@example.com')

    def test_django_standard_vars_take_precedence(self):
        """Test that Django standard environment variables take precedence over custom ones."""
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'djangoadmin',
            'DJANGO_SUPERUSER_PASSWORD': 'djangopass',
            'DJANGO_ADMIN_USER': 'customadmin',
            'DJANGO_ADMIN_PASSWORD': 'custompass'
        }):
            out = StringIO()
            call_command('create_admin_user', stdout=out)
            
            # Should create user with Django standard variables
            user = User.objects.get(username='djangoadmin')
            self.assertTrue(user.is_superuser)
            
            # Should not create user with custom variables
            self.assertFalse(User.objects.filter(username='customadmin').exists())