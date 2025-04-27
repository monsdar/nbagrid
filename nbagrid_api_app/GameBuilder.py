from .models import Player, GameFilterDB
from nbagrid_api_app.GameFilter import GameFilter, get_dynamic_filters, get_static_filters, create_filter_from_db
from django.db.models import Manager

from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class GameBuilder(object):
    def __init__(self, random_seed: int = 0):
        self.random_seed = random_seed
        self.dynamic_filters = get_dynamic_filters(self.random_seed)
        self.static_filters = get_static_filters(self.random_seed)
        self.min_num_results = 5
        self.max_num_results = 40
        self.max_tuning_attempts = 20
        self.num_statics = 3
        self.num_dynamics = 3
        
    def tune_filter(self, dynamic_filter:GameFilter, static_filters:list[GameFilter], all_players:Manager[Player]):
        num_results = []
        success = True
        last_action = None
        for static_filter in static_filters:
            num_results.append(len(static_filter.apply_filter(dynamic_filter.apply_filter(all_players))))
            logger.debug(f"...filter [{static_filter.get_desc()}] x [{dynamic_filter.get_desc()}] returned {num_results[-1]} results")
        
        # if some results are higher than the max, but others are lower we can skip tuning
        if any(n > self.max_num_results for n in num_results) and any(n < self.min_num_results for n in num_results):
            logger.debug(f"...filter [{dynamic_filter.get_desc()}] returned results out of range")
            return (False, None)
            
        # if one of the results is higher than the max, we need to narrow the filter
        if any(n > self.max_num_results for n in num_results):
            if last_action == 'widen':
                logger.debug(f"...filter [{dynamic_filter.get_desc()}] is oscillating, giving up")
                return (False, None)
            dynamic_filter.narrow_filter()
            logger.debug(f"...narrowed filter to [{dynamic_filter.get_desc()}]")
            last_action = 'narrow'
            success = False
        elif any(n < self.min_num_results for n in num_results):
            if last_action == 'narrow':
                logger.debug(f"...filter [{dynamic_filter.get_desc()}] is oscillating, giving up")
                return (False, None)
            dynamic_filter.widen_filter()
            logger.debug(f"...widened filter to [{dynamic_filter.get_desc()}]")
            last_action = 'widen'
            success = False
        return (success, dynamic_filter)
            
    def get_tuned_filters(self, requested_date, num_iterations:int=10):
        # Check if filters already exist in database for today
        existing_filters = GameFilterDB.objects.filter(date=requested_date)
        
        if existing_filters.exists():
            # Reconstruct filters from database
            static_filters = []
            dynamic_filters = []
            
            for db_filter in existing_filters.order_by('filter_index'):
                filter_obj = create_filter_from_db(db_filter)
                if db_filter.filter_type == 'static':
                    static_filters.append(filter_obj)
                else:
                    dynamic_filters.append(filter_obj)
            
            if len(static_filters) == self.num_statics and len(dynamic_filters) == self.num_dynamics:
                return (static_filters, dynamic_filters)
        
        # If no filters exist or they're incomplete, generate new ones
        for _ in range(num_iterations):
            static_filters, dynamic_filters = self.generate_grid()
            if len(dynamic_filters) < self.num_dynamics:
                logger.warning(f"Failed to generate a grid with {self.num_dynamics} dynamic filters. Static filters: {static_filters}")
                continue
            if len(static_filters) == self.num_statics:
                # Save filters to database
                for idx, filter_obj in enumerate(static_filters):
                    GameFilterDB.objects.create(
                        date=requested_date,
                        filter_type='static',
                        filter_class=filter_obj.__class__.__name__,
                        filter_config=filter_obj.__dict__,
                        filter_index=idx
                    )
                
                for idx, filter_obj in enumerate(dynamic_filters):
                    GameFilterDB.objects.create(
                        date=requested_date,
                        filter_type='dynamic',
                        filter_class=filter_obj.__class__.__name__,
                        filter_config=filter_obj.__dict__,
                        filter_index=idx
                    )
                
                return (static_filters, dynamic_filters)
        raise Exception(f"Failed to generate a grid with {self.num_dynamics} dynamic filters and {self.num_statics} static filters")
        
    def generate_grid(self):
        # Get 3 random static filters for X-axis
        row_filters = random.sample(self.static_filters + self.dynamic_filters, self.num_statics)
        column_filters = []
        
        # Go through the list of dynamic filters and tune them to the static filters
        # Randomize the order of dynamic filters before iteration
        all_players = Player.objects.all()
        for column_filter in random.sample(self.dynamic_filters, len(self.dynamic_filters)):
            # Do not use the same dynamic filter twice
            curr_filter_name = column_filter.__class__.__name__
            if column_filter in column_filters:
                continue
            if column_filter in row_filters:
                continue
            
            num_tuning_attempts = 0
            found_filter = False
            while num_tuning_attempts < self.max_tuning_attempts:
                success, column_filter = self.tune_filter(column_filter, row_filters, all_players)
                if column_filter is None:
                    break
                if success:
                    column_filters.append(column_filter)
                    found_filter = True
                    break
                num_tuning_attempts += 1
            # Continue with the next dynamic filter if we did not find a suitable filter
            if not found_filter:
                logger.warning(f"Failed to tune filter {curr_filter_name}. Filters: ['{row_filters[0].get_desc()}'] and ['{row_filters[1].get_desc()}'] and ['{row_filters[2].get_desc()}']")
                continue  
            # Check if we already have the required number of dynamic filters            
            if len(column_filters) == self.num_dynamics:
                break
        
        return (row_filters, column_filters)
                