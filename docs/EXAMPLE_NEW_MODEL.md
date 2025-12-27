# Example: Adding a New Model with Alembic

This document demonstrates the complete workflow for adding a new model to AniBridge using SQLModel and Alembic migrations.

## Scenario

We want to add a `UserPreferences` model to store user-specific settings.

## Step 1: Define the Model

Edit `app/db/models.py` and add the new model:

```python
class UserPreferences(ModelBase, table=True):
    """User preferences and settings.
    
    Stores user-specific configuration like theme, language, notification settings.
    """
    
    id: int = Field(primary_key=True)
    user_id: str = Field(index=True, unique=True)
    theme: str = Field(default="dark")
    language: str = Field(default="en")
    notifications_enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
```

## Step 2: Generate Migration

Run Alembic's autogenerate to create the migration:

```bash
alembic revision --autogenerate -m "Add UserPreferences table"
```

Output:
```
INFO  [alembic.autogenerate.compare] Detected added table 'userpreferences'
INFO  [alembic.autogenerate.compare] Detected added index 'ix_userpreferences_user_id' on '('user_id',)'
Generating /path/to/alembic/versions/abc123_add_userpreferences_table.py ...  done
```

## Step 3: Review the Generated Migration

Open the generated file in `alembic/versions/abc123_add_userpreferences_table.py`:

```python
"""Add UserPreferences table

Revision ID: abc123
Revises: 397fa0304f9f
Create Date: 2025-10-22 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'abc123'
down_revision: Union[str, Sequence[str], None] = '397fa0304f9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    # Create userpreferences table
    op.create_table('userpreferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('theme', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('notifications_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index
    with op.batch_alter_table('userpreferences', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_userpreferences_user_id'), 
            ['user_id'], 
            unique=True
        )


def downgrade() -> None:
    """Rollback the migration."""
    with op.batch_alter_table('userpreferences', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_userpreferences_user_id'))
    
    op.drop_table('userpreferences')
```

**Review checklist:**
- ✅ All columns are present
- ✅ Data types are correct
- ✅ Indexes are created
- ✅ Primary key is defined
- ✅ Downgrade properly reverses upgrade

## Step 4: Apply the Migration

### Option A: Manual Application

```bash
alembic upgrade head
```

Output:
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 397fa0304f9f -> abc123, Add UserPreferences table
```

### Option B: Automatic on Startup

Simply start the application - migrations run automatically:

```bash
python -m app.main
```

The application will detect and apply the pending migration.

## Step 5: Add CRUD Functions

Add helper functions to `app/db/models.py`:

```python
def create_user_preferences(
    session: Session,
    *,
    user_id: str,
    theme: str = "dark",
    language: str = "en",
    notifications_enabled: bool = True,
) -> UserPreferences:
    """Create user preferences record."""
    prefs = UserPreferences(
        user_id=user_id,
        theme=theme,
        language=language,
        notifications_enabled=notifications_enabled,
    )
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return prefs


def get_user_preferences(session: Session, user_id: str) -> Optional[UserPreferences]:
    """Get user preferences by user_id."""
    return session.exec(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    ).first()


def update_user_preferences(
    session: Session, user_id: str, **fields: Any
) -> Optional[UserPreferences]:
    """Update user preferences."""
    prefs = get_user_preferences(session, user_id)
    if not prefs:
        return None
    
    for key, value in fields.items():
        setattr(prefs, key, value)
    
    prefs.updated_at = utcnow()
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return prefs
```

## Step 6: Write Tests

Add tests to `tests/test_models.py`:

```python
def test_user_preferences_crud(client):
    """Test UserPreferences CRUD operations."""
    from sqlmodel import Session
    from app.db import (
        engine,
        create_user_preferences,
        get_user_preferences,
        update_user_preferences,
    )
    
    with Session(engine) as session:
        # Create
        prefs = create_user_preferences(
            session,
            user_id="user123",
            theme="light",
            language="de",
        )
        assert prefs.id is not None
        assert prefs.theme == "light"
        
        # Read
        retrieved = get_user_preferences(session, "user123")
        assert retrieved is not None
        assert retrieved.theme == "light"
        
        # Update
        updated = update_user_preferences(
            session,
            "user123",
            theme="dark",
            notifications_enabled=False,
        )
        assert updated.theme == "dark"
        assert updated.notifications_enabled is False
```

## Step 7: Verify Database Schema

```bash
sqlite3 data/anibridge_jobs.db ".schema userpreferences"
```

Output:
```sql
CREATE TABLE userpreferences (
    id INTEGER NOT NULL,
    user_id VARCHAR NOT NULL,
    theme VARCHAR NOT NULL,
    language VARCHAR NOT NULL,
    notifications_enabled BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_userpreferences_user_id ON userpreferences (user_id);
```

## Step 8: Check Migration Status

```bash
alembic current
```

Output:
```
abc123 (head)
```

```bash
alembic history
```

Output:
```
397fa0304f9f -> abc123 (head), Add UserPreferences table
<base> -> 397fa0304f9f, Initial migration with existing schema
```

## Testing Rollback

Always test that rollback works:

```bash
# Rollback the migration
alembic downgrade -1

# Verify table is gone
sqlite3 data/anibridge_jobs.db "SELECT name FROM sqlite_master WHERE name='userpreferences'"
# (Should return nothing)

# Re-apply
alembic upgrade head
```

## Complex Example: Data Migration

If you need to transform existing data, create a manual migration:

```python
def upgrade() -> None:
    """Add new column with data migration."""
    # Add nullable column first
    op.add_column('job', sa.Column('priority', sa.Integer(), nullable=True))
    
    # Set default values for existing rows
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE job SET priority = 5 WHERE priority IS NULL")
    )
    
    # Make column non-nullable
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.alter_column('priority', nullable=False)


def downgrade() -> None:
    """Remove the column."""
    op.drop_column('job', 'priority')
```

## Best Practices

1. **Always review autogenerated migrations** - They might not capture all your intent
2. **Test both upgrade and downgrade** - Ensure rollback works
3. **Use descriptive migration messages** - Makes history readable
4. **Add data migrations when needed** - Transform existing data appropriately
5. **Keep migrations atomic** - One logical change per migration
6. **Don't modify applied migrations** - Create new ones to fix issues
7. **Document complex migrations** - Explain non-obvious logic

## Troubleshooting

### Migration Not Detected

If Alembic doesn't detect your model changes:

1. Ensure model inherits from `ModelBase`
2. Verify `table=True` is set
3. Check that the model is imported in `app/db/models.py`
4. Try: `alembic revision --autogenerate -m "Message" --verbose`

### Table Already Exists

If running migration fails with "table already exists":

```bash
# Mark the migration as applied without running it
alembic stamp abc123
```

### Merge Conflicts

If multiple migrations exist:

```bash
alembic merge abc123 def456 -m "Merge migrations"
```

## Summary

Adding a new model with Alembic is straightforward:

1. **Define model** in `app/db/models.py`
2. **Generate migration**: `alembic revision --autogenerate -m "Message"`
3. **Review migration** in `alembic/versions/`
4. **Apply**: `alembic upgrade head` or let app auto-apply
5. **Add CRUD functions** (optional)
6. **Write tests**
7. **Verify** database schema

The migration system ensures schema consistency across all environments automatically!
