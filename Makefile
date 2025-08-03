.PHONY: help install test test-nba lint format clean coverage migrate runserver

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	pip install -r requirements-dev.txt

test:  ## Run default tests (excluding NBA API tests)
	python manage.py test --verbosity=2

test-nba:  ## Run NBA API tests (requires NBA API access)
	python manage.py test --tag=nba_api_access --verbosity=2

test-all:  ## Run all tests including NBA API tests
	python manage.py test --verbosity=2
	python manage.py test --tag=nba_api_access --verbosity=2

coverage:  ## Run tests with coverage reporting
	coverage run --source='.' manage.py test
	coverage report -m
	coverage html

lint:  ## Run all linting tools
	black --check .
	isort --check-only .
	flake8 .

format:  ## Format code with black and isort
	black .
	isort .

migrate:  ## Run Django migrations
	python manage.py migrate

runserver:  ## Start Django development server
	python manage.py runserver

clean:  ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf htmlcov/
	rm -f .coverage
	rm -f coverage.xml

setup:  ## Initial project setup
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate     (Windows)"
	@echo "Then run: make install && make migrate"