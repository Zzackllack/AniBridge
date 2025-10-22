# AniBridge Database Management Guide

## Overview

AniBridge uses SQLModel (built on SQLAlchemy) for ORM and Alembic for database schema migrations. This guide explains the database architecture, migration workflow, and best practices.

## Architecture

### Database Components

1. **Database Engine** (`app/db/session.py`)
   - SQLite database at `data/anibridge_jobs.db`
   - Connection pooling with NullPool (ensures connections close properly)
   - Configured for multi-threaded access

2. **Base Model** (`app/db/base.py`)
   - `ModelBase` class for all table models
   - Private registry to avoid test contamination
   - Metadata used by Alembic for autogenerate

3. **Table Models** (`app/db/models.py`)
   - `Job`: Download job tracking
   - `EpisodeAvailability`: Episode availability cache
   - `ClientTask`: qBittorrent torrent mapping
   - CRUD helper functions

4. **Migration Utilities** (`app/db/migrations.py`)
   - Automatic migration execution
   - Status checking
   - Revision management

## Database Models

### Job Model

Tracks download operations with progress, status, and metadata.

```python
class Job(ModelBase, table=True):
    id: str                    # Unique hex UUID
    status: str               # queued|downloading|completed|failed|cancelled
    progress: float           # 0-100 percentage
    downloaded_bytes: int     # Current download size
    total_bytes: Optional[int]  # Total file size
    speed: Optional[float]    # Download speed (bytes/sec)
    eta: Optional[int]        # Estimated completion time (seconds)
    message: Optional[str]    # Status or error message
    result_path: Optional[str]  # Downloaded file path
    source_site: str          # Origin site (e.g., "aniworld.to")
    created_at: datetime      # Job creation timestamp
    updated_at: datetime      # Last update timestamp
```

### EpisodeAvailability Model

Caches episode availability information to reduce external API calls.

```python
class EpisodeAvailability(ModelBase, table=True):
    # Composite primary key
    slug: str                 # Series identifier
    season: int               # Season number
    episode: int              # Episode number
    language: str             # Audio/subtitle language
    site: str                 # Source site
    
    # Metadata
    available: bool           # Is episode available?
    height: Optional[int]     # Video resolution (pixels)
    vcodec: Optional[str]     # Video codec
    provider: Optional[str]   # Hosting provider
    checked_at: datetime      # Last check timestamp
    extra: Optional[dict]     # Additional JSON metadata
    
    @property
    def is_fresh(self) -> bool:
        """Check if cache is within TTL."""
        # Returns True if checked_at is within AVAILABILITY_TTL_HOURS
```

### ClientTask Model

Maps qBittorrent-style torrent hashes to internal job IDs for the qBittorrent API shim.

```python
class ClientTask(ModelBase, table=True):
    hash: str                 # Torrent info hash (BTIH)
    name: str                 # Display name
    slug: str                 # Series identifier
    season: int               # Season number
    episode: int              # Episode number
    language: str             # Audio/subtitle language
    site: str                 # Source site
    job_id: Optional[str]     # Reference to Job.id
    save_path: Optional[str]  # Download destination
    category: Optional[str]   # Download category
    added_on: datetime        # Task creation timestamp
    completion_on: Optional[datetime]  # Completion timestamp
    state: str                # Current state
```

## Migration Workflow

### Automatic Migrations on Startup

The application automatically applies pending migrations when it starts:

1. FastAPI lifespan context calls `run_migrations()`
2. Alembic checks for pending migrations
3. All pending migrations are applied
4. Application continues startup

This ensures:
- Database schema is always current
- No manual steps required
- Consistent across all environments

### Creating New Migrations

#### 1. Add or Modify Models

Edit `app/db/models.py`:

```python
class NewFeature(ModelBase, table=True):
    """New model for tracking features."""
    id: int = Field(primary_key=True)
    name: str = Field(index=True)
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
```

#### 2. Generate Migration

```bash
# Auto-detect model changes and create migration
alembic revision --autogenerate -m "Add NewFeature table"
```

This creates a new file in `alembic/versions/` with:
- Detected table/column/index changes
- Upgrade function (apply changes)
- Downgrade function (rollback changes)

#### 3. Review Migration

Always review the generated migration file:

```python
# alembic/versions/abc123_add_newfeature_table.py

def upgrade() -> None:
    op.create_table('newfeature',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_newfeature_name', 'newfeature', ['name'])

def downgrade() -> None:
    op.drop_index('ix_newfeature_name', 'newfeature')
    op.drop_table('newfeature')
```

Check for:
- Missing columns or indexes
- Incorrect types or constraints
- Need for data migrations

#### 4. Apply Migration

```bash
# Apply all pending migrations
alembic upgrade head
```

Or let the application apply it automatically on next startup.

#### 5. Test Rollback

```bash
# Test downgrade
alembic downgrade -1

# Re-apply
alembic upgrade head
```

### Manual Migrations

For complex changes requiring data transformations:

```bash
# Create empty migration
alembic revision -m "Migrate legacy data"
```

Edit the generated file:

```python
def upgrade() -> None:
    # Add new column
    op.add_column('job', sa.Column('new_field', sa.String(), nullable=True))
    
    # Migrate existing data
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE job SET new_field = 'default' WHERE new_field IS NULL")
    )
    
    # Make non-nullable
    op.alter_column('job', 'new_field', nullable=False)

def downgrade() -> None:
    op.drop_column('job', 'new_field')
```

## Development Workflow

### Local Development

1. **Set up environment:**
   ```bash
   pip install -r requirements-dev.txt
   export DATA_DIR=./data
   ```

2. **Run migrations:**
   ```bash
   # Automatic on app startup, or manually:
   alembic upgrade head
   ```

3. **Make model changes:**
   - Edit `app/db/models.py`
   - Add/modify table models

4. **Generate migration:**
   ```bash
   alembic revision --autogenerate -m "Description"
   ```

5. **Test:**
   ```bash
   pytest tests/test_models.py
   ```

### Testing Migrations

Tests use a temporary database and run migrations automatically:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    # Set temporary data directory
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    
    # Migrations run automatically via run_migrations()
    # in test setup
    ...
```

## Production Deployment

### Initial Deployment

```bash
# Database is created and migrated on first startup
docker-compose up -d
```

### Updating with Schema Changes

1. **Pull new code** with migrations
2. **Restart application** - migrations run automatically
3. **Monitor logs** for migration success

```bash
docker-compose pull
docker-compose up -d
```

### Backup Strategy

Before major updates:

```bash
# Backup database
docker-compose exec anibridge cp /data/anibridge_jobs.db /data/backup_$(date +%Y%m%d).db

# Or from host
cp ./data/anibridge_jobs.db ./data/backup_$(date +%Y%m%d).db
```

### Rollback Procedure

If deployment fails:

1. **Stop application**
2. **Restore database backup**
3. **Rollback code** to previous version
4. **Restart application**

```bash
docker-compose down
cp ./data/backup_20251022.db ./data/anibridge_jobs.db
git checkout previous-tag
docker-compose up -d
```

## Common Tasks

### Check Current Schema Version

```bash
alembic current
```

### View Migration History

```bash
alembic history --verbose
```

### Migrate to Specific Revision

```bash
alembic upgrade <revision_id>
alembic downgrade <revision_id>
```

### Generate SQL Without Executing

```bash
alembic upgrade head --sql
```

### Check for Model/Migration Drift

```bash
# This would fail if models don't match migrations
alembic check
```

## Troubleshooting

### "Table already exists" Error

If you have an existing database without migrations:

```bash
# Mark current schema as migrated
alembic stamp head
```

### Migration Conflicts

If multiple branches have migrations:

```bash
# Merge migration branches
alembic merge heads -m "Merge migrations"
```

### Reset Database (Development Only)

```bash
rm data/anibridge_jobs.db
alembic upgrade head
```

### Migration Fails

1. **Check logs** for specific error
2. **Review migration SQL** in generated file
3. **Test in clean environment**
4. **Rollback** and fix migration

```bash
# Rollback failed migration
alembic downgrade -1

# Fix migration file
# Re-apply
alembic upgrade head
```

## Best Practices

1. **Always review autogenerated migrations** - Add necessary data migrations
2. **Test both upgrade and downgrade** - Ensure rollback works
3. **Keep migrations atomic** - One logical change per migration
4. **Never modify applied migrations** - Create new migrations to fix issues
5. **Document complex migrations** - Explain non-obvious transformations
6. **Backup before major changes** - Especially in production
7. **Use descriptive migration messages** - Makes history readable
8. **Test migrations in staging** - Before production deployment

## File Reference

```
app/db/
├── __init__.py          # Package exports
├── base.py              # ModelBase definition
├── session.py           # Engine and session management
├── models.py            # Table models and CRUD
└── migrations.py        # Migration utilities

alembic/
├── versions/            # Migration files
├── env.py              # Alembic configuration
├── script.py.mako      # Migration template
└── MIGRATIONS.md       # Detailed migration guide

alembic.ini              # Alembic settings
```

## Further Reading

- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Core](https://docs.sqlalchemy.org/en/14/core/)
- [Database Migration Patterns](https://www.martinfowler.com/articles/evodb.html)
