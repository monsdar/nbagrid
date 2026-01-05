import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests
from django.core.management.base import BaseCommand
from urllib.parse import urljoin

from nbagrid_api_app.models import GameFilterDB, GridMetadata

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Upload grids from local database to remote production API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-url',
            default=os.environ.get('NBAGRID_API_URL', 'http://localhost:8000'),
            help='Remote API base URL (default: from NBAGRID_API_URL env or http://localhost:8000)'
        )
        
        parser.add_argument(
            '--api-key',
            default=os.environ.get('NBAGRID_API_KEY', 'supersecret'),
            help='API authentication key (default: from NBAGRID_API_KEY env or supersecret)'
        )
        
        parser.add_argument(
            '--all-future',
            action='store_true',
            help='Upload all grids from today into the future (not just today)'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Allow overwriting existing grids on remote (only for future dates)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be uploaded without actually uploading'
        )

    def get_grids_from_db(self, target_date) -> Optional[Dict[str, Any]]:
        """
        Query the database for all filters for a specific date and transform them
        into the API format.
        
        Returns:
            Dictionary with grid data ready for API upload, or None if grid doesn't exist
        """
        # Query all filters for the target date
        filters = GameFilterDB.objects.filter(date=target_date).order_by('filter_index')
        
        if not filters.exists():
            return None
        
        # Separate static (row) and dynamic (column) filters
        static_filters = filters.filter(filter_type='static')
        dynamic_filters = filters.filter(filter_type='dynamic')
        
        # Validate we have the correct number of filters
        if static_filters.count() != 3 or dynamic_filters.count() != 3:
            self.stdout.write(
                self.style.WARNING(
                    f"Grid for {target_date} has incomplete filters: "
                    f"{static_filters.count()} static, {dynamic_filters.count()} dynamic"
                )
            )
            return None
        
        # Transform to API format
        row_filters = {}
        for filter_obj in static_filters:
            row_filters[str(filter_obj.filter_index)] = {
                'class': filter_obj.filter_class,
                'config': filter_obj.filter_config
            }
        
        col_filters = {}
        for filter_obj in dynamic_filters:
            col_filters[str(filter_obj.filter_index)] = {
                'class': filter_obj.filter_class,
                'config': filter_obj.filter_config
            }
        
        # Get grid metadata if it exists
        try:
            metadata = GridMetadata.objects.get(date=target_date)
            game_title = metadata.game_title
        except GridMetadata.DoesNotExist:
            game_title = f"Grid for {target_date}"
        
        return {
            'year': target_date.year,
            'month': target_date.month,
            'day': target_date.day,
            'filters': {
                'row': row_filters,
                'col': col_filters
            },
            'game_title': game_title
        }

    def upload_grid(self, grid_data: Dict[str, Any], api_url: str, api_key: str, 
                   force: bool, dry_run: bool) -> Dict[str, Any]:
        """
        Upload a single grid to the remote API.
        
        Returns:
            Dictionary with status and message
        """
        grid_date = f"{grid_data['year']}-{grid_data['month']:02d}-{grid_data['day']:02d}"
        
        if dry_run:
            self.stdout.write(f"[DRY RUN] Would upload grid for {grid_date}")
            self.stdout.write(f"  Title: {grid_data.get('game_title', 'N/A')}")
            self.stdout.write(f"  Static filters: {list(grid_data['filters']['row'].keys())}")
            self.stdout.write(f"  Dynamic filters: {list(grid_data['filters']['col'].keys())}")
            return {'status': 'success', 'message': 'Dry run mode'}
        
        # Prepare payload
        payload = {
            'filters': grid_data['filters'],
            'game_title': grid_data.get('game_title'),
            'force': force
        }
        
        # Make the API request
        try:
            url = urljoin(api_url.rstrip('/'), '/api/upload_prebuilt_game')
            headers = {
                'X-API-Key': api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                message = result.get('message', 'Upload successful')
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully uploaded grid for {grid_date}: {message}")
                )
                return {'status': 'success', 'message': message}
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    error_msg += f" - {response.text}"
                
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to upload grid for {grid_date}: {error_msg}")
                )
                return {'status': 'error', 'message': error_msg, 'status_code': response.status_code}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to upload grid for {grid_date}: {error_msg}")
            )
            return {'status': 'error', 'message': error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to upload grid for {grid_date}: {error_msg}")
            )
            return {'status': 'error', 'message': error_msg}

    def get_dates_to_upload(self, all_future: bool) -> List:
        """
        Get list of dates to upload based on the --all-future flag.
        
        Returns:
            List of date objects to upload
        """
        today = datetime.now().date()
        
        if all_future:
            # Get all dates from today onwards that have grids
            dates = GameFilterDB.objects.filter(
                date__gte=today
            ).values_list('date', flat=True).distinct().order_by('date')
            return list(dates)
        else:
            # Just return today if a grid exists for it
            if GameFilterDB.objects.filter(date=today).exists():
                return [today]
            else:
                return []

    def handle(self, *args, **options):
        api_url = options['api_url']
        api_key = options['api_key']
        all_future = options['all_future']
        force = options['force']
        dry_run = options['dry_run']
        
        # Validate arguments
        if not api_url:
            self.stdout.write(self.style.ERROR("Error: API URL is required"))
            return
        
        if not api_key:
            self.stdout.write(self.style.ERROR("Error: API key is required"))
            return
        
        # Get dates to upload
        dates_to_upload = self.get_dates_to_upload(all_future)
        
        if not dates_to_upload:
            if all_future:
                self.stdout.write(
                    self.style.WARNING("No grids found in the database from today onwards")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"No grid found for today ({datetime.now().date()})")
                )
            return
        
        # Display upload plan
        self.stdout.write("=" * 60)
        self.stdout.write("GRID UPLOAD PLAN")
        self.stdout.write("=" * 60)
        self.stdout.write(f"API URL: {api_url}")
        self.stdout.write(f"Grids to upload: {len(dates_to_upload)}")
        self.stdout.write(f"Date range: {dates_to_upload[0]} to {dates_to_upload[-1]}")
        self.stdout.write(f"Force overwrite: {force}")
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write("-" * 60)
        
        # Upload each grid
        results = {
            'total': len(dates_to_upload),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for i, target_date in enumerate(dates_to_upload, 1):
            self.stdout.write(f"\n[{i}/{len(dates_to_upload)}] Processing grid for {target_date}...")
            
            # Get grid data from database
            grid_data = self.get_grids_from_db(target_date)
            
            if not grid_data:
                self.stdout.write(
                    self.style.WARNING(f"⚠ Skipping {target_date}: Grid not found or incomplete")
                )
                results['failed'] += 1
                results['details'].append({
                    'date': str(target_date),
                    'status': 'error',
                    'message': 'Grid not found or incomplete'
                })
                continue
            
            # Upload the grid
            result = self.upload_grid(grid_data, api_url, api_key, force, dry_run)
            results['details'].append({
                'date': str(target_date),
                'result': result
            })
            
            if result.get('status') == 'success':
                results['successful'] += 1
            else:
                results['failed'] += 1
            
            # Add a small delay between uploads to be respectful to the API
            if not dry_run and i < len(dates_to_upload):
                time.sleep(0.5)
        
        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("UPLOAD SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total grids: {results['total']}")
        self.stdout.write(f"Successful: {results['successful']}")
        self.stdout.write(f"Failed: {results['failed']}")
        
        if results['failed'] > 0:
            self.stdout.write(f"\nFailed uploads:")
            for detail in results['details']:
                if detail.get('result', {}).get('status') != 'success':
                    self.stdout.write(
                        f"  - {detail['date']}: {detail.get('result', {}).get('message', 'Unknown error')}"
                    )
        
        # Log the operation
        if not dry_run:
            logger.info(
                f"Uploaded {results['successful']}/{results['total']} grids to {api_url}"
            )
        
        # Exit with error code if any uploads failed
        if results['failed'] > 0 and not dry_run:
            raise SystemExit(1)

