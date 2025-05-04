from django.core.management.base import BaseCommand
import os
from nbagrid_api_app.metrics import test_pythonanywhere_api

class Command(BaseCommand):
    help = 'Test the PythonAnywhere API connection and metrics'

    def handle(self, *args, **options):
        pa_username = os.environ.get('PYTHONANYWHERE_USERNAME')
        pa_token = os.environ.get('PYTHONANYWHERE_API_TOKEN')
        pa_host = os.environ.get('PYTHONANYWHERE_HOST', 'www.pythonanywhere.com')
        
        if not pa_username or not pa_token:
            self.stdout.write(self.style.ERROR('Missing PYTHONANYWHERE_USERNAME or PYTHONANYWHERE_API_TOKEN environment variables'))
            return
            
        self.stdout.write(self.style.SUCCESS(f'Testing API for user {pa_username} on host {pa_host}...'))
        result = test_pythonanywhere_api(pa_username, pa_token, pa_host)
        
        if result:
            self.stdout.write(self.style.SUCCESS('API test successful!'))
            self.stdout.write(self.style.SUCCESS(f'CPU limit: {result["daily_cpu_limit_seconds"]} seconds'))
            self.stdout.write(self.style.SUCCESS(f'CPU usage: {result["daily_cpu_total_usage_seconds"]} seconds'))
            self.stdout.write(self.style.SUCCESS(f'Next reset: {result["next_reset_time"]}'))
            
            # Calculate percentage
            usage_percent = (result["daily_cpu_total_usage_seconds"] / result["daily_cpu_limit_seconds"]) * 100
            self.stdout.write(self.style.SUCCESS(f'Usage percentage: {usage_percent:.2f}%'))
        else:
            self.stdout.write(self.style.ERROR('API test failed')) 