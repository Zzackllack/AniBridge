# Database Schema Management

AniBridge uses **Alembic** for database schema management with **SQLModel** as the ORM. This provides version-controlled, reproducible database migrations.

## Quick Start

### For Users

No action needed! Migrations run automatically when the application starts.

```bash
# Just start the app
docker-compose up -d

# Or run directly
python -m app.main
```

The database schema is automatically created and updated on startup.

### For Developers

#### Adding a New Model

1. **Define the model** in `app/db/models.py`:

```python
from app.db.base import ModelBase
from sqlmodel import Field

class MyModel(ModelBase, table=True):
    id: int = Field(primary_key=True)
    name: str
    description: Optional[str] = None
```

2. **Generate migration**:

```bash
alembic revision --autogenerate -m "Add MyModel table"
```

3. **Review** the generated migration in `alembic/versions/`

4. **Apply** (or just restart the app):

```bash
alembic upgrade head
```

#### Checking Migration Status

```bash
# Current version
alembic current

# History
alembic history

# Pending migrations
alembic heads
```

#### Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

## Database Architecture

```
app/db/
├── base.py          # ModelBase for all table models
├── session.py       # Engine and session management
├── models.py        # Table models (Job, EpisodeAvailability, ClientTask)
└── migrations.py    # Alembic utilities and auto-execution

alembic/
├── versions/        # Migration files
├── env.py          # Alembic environment config
└── MIGRATIONS.md   # Detailed migration guide
```

## Current Models

- **Job**: Download job tracking with status and progress
- **EpisodeAvailability**: Episode availability cache with TTL
- **ClientTask**: qBittorrent torrent mapping

## Migration Workflow

```
┌─────────────────┐
│ Modify models   │
│ in models.py    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ alembic         │
│ revision        │
│ --autogenerate  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Review          │
│ migration file  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ alembic         │
│ upgrade head    │
│ (or restart app)│
└─────────────────┘
```

## Documentation

- **[docs/DATABASE.md](docs/DATABASE.md)** - Complete database management guide
- **[alembic/MIGRATIONS.md](alembic/MIGRATIONS.md)** - Migration workflow details
- **[docs/EXAMPLE_NEW_MODEL.md](docs/EXAMPLE_NEW_MODEL.md)** - Step-by-step example

## Features

✅ Automatic migrations on startup  
✅ Version-controlled schema changes  
✅ Safe rollback capability  
✅ Autogenerate from model changes  
✅ Production-ready configuration  
✅ Comprehensive test coverage  

## Troubleshooting

### Migration not detected?

Ensure:
- Model inherits from `ModelBase`
- `table=True` is set
- Model is imported in `app/db/models.py`

### Table already exists?

Mark the migration as applied without running it:
```bash
alembic stamp head
```

### Need to reset database? (Development only)

```bash
rm data/anibridge_jobs.db
alembic upgrade head
```

## Testing

Tests automatically run migrations:

```bash
# Test migrations specifically
pytest tests/test_migrations.py

# All tests
pytest tests/
```

## Production Deployment

Migrations run automatically on container startup. No manual intervention needed!

```bash
docker-compose pull
docker-compose up -d
```

For more details, see the full [Database Management Guide](docs/DATABASE.md).
