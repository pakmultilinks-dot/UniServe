# UniServe API

FastAPI backend for the UniServe university cafeteria management system.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run migrations, then seed today's Student Cafeteria menu
alembic upgrade head
python scripts/seed_student_cafeteria.py

# Run the server
uvicorn app.main:app --reload

# Run tests
pytest

# Lint and format
ruff check .
ruff format .

# Type checking
mypy app/
```

## Project Structure

```
apps/api/
├── app/
│   ├── core/           # Core configuration, database, security
│   ├── db/             # Database models and session management
│   ├── api/            # API routers and dependencies
│   ├── modules/        # Business domain modules
│   └── main.py         # Application entry point
├── tests/
├── migrations/         # Alembic migrations
├── pyproject.toml
└── README.md
```
