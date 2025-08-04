# NBAGrid

![Tests](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/workflows/Run%20Tests/badge.svg)
![Docker Build](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/workflows/Build%20and%20Push%20Docker%20Image/badge.svg)

This is the codebase of NBAGrid, a daily guessing game where the player needs to find correct NBA players matching a number of category filters.

## Development Setup

### Requirements

- Python 3.11+ 
- Django 5.2+
- See `requirements.txt` for full dependencies

### Installation

#### Quick Setup (using Makefile)
```bash
git clone <repository-url>
cd nbagrid
make setup          # Creates virtual environment
source venv/bin/activate  # Activate virtual environment
make install        # Install dependencies
make migrate        # Run database migrations
make runserver      # Start development server
```

#### Manual Setup
1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements-dev.txt`
5. Run migrations: `python manage.py migrate`
6. Start the development server: `python manage.py runserver`

### Admin User Setup

The application supports automatic creation of admin users from environment variables, making it easy to set up admin access in different environments.

#### Using Django's Standard Environment Variables (Recommended)
```bash
export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_PASSWORD=your_secure_password
export DJANGO_SUPERUSER_EMAIL=admin@example.com  # Optional
```

#### Using Custom Environment Variables (Alternative)
```bash
export DJANGO_ADMIN_USER=admin
export DJANGO_ADMIN_PASSWORD=your_secure_password
```

#### Automatic Admin User Creation
When environment variables are set, an admin user will be created automatically when:
- The Django application starts (if no superuser exists)
- You run the management command: `python manage.py create_admin_user`

#### Manual Admin User Creation
You can also create admin users manually using the management command:
```bash
# Create from environment variables
python manage.py create_admin_user

# Force creation even if superuser exists
python manage.py create_admin_user --force

# Traditional Django method
python manage.py createsuperuser
```

#### Available Make Commands
Run `make help` to see all available commands, including:
- `make test` - Run default tests
- `make test-nba` - Run NBA API tests
- `make coverage` - Run tests with coverage
- `make lint` - Run code quality checks
- `make format` - Format code

## Testing

### Running Tests

The project includes comprehensive test coverage with different categories of tests:

#### Default Tests (Recommended)
Run all tests except those requiring external NBA API access:
```bash
python manage.py test
```

#### NBA API Tests
Some tests require access to `stats.nba.com` which may be blocked in cloud environments. These tests are tagged with `nba_api_access` and skipped by default.

To run NBA API tests explicitly (when you have NBA API access):
```bash
python manage.py test --tag=nba_api_access
```

#### Coverage Reports
To run tests with coverage reporting:
```bash
coverage run --source='.' manage.py test
coverage report -m
coverage html  # Generates HTML coverage report in htmlcov/
```

### Code Quality

The project uses several tools to maintain code quality:

#### Code Formatting
```bash
black .                    # Format code
isort .                    # Sort imports
```

#### Linting
```bash
flake8 .                   # Check code style
pylint nbagrid_api_app/    # Detailed code analysis
```

#### Check All Quality Tools
```bash
black --check .
isort --check-only .
flake8 .
```

## Continuous Integration

The project uses GitHub Actions for automated testing and code quality checks:

- **Tests**: Run on Python 3.11, 3.12, and 3.13
- **Code Quality**: Black, isort, and flake8 checks
- **Coverage**: Automatic coverage reporting via Codecov
- **NBA API Tests**: Only run on manual workflow dispatch

Tests run automatically on:
- Push to `main`, `develop`, or `staging` branches
- Pull requests to `main`, `develop`, or `staging` branches