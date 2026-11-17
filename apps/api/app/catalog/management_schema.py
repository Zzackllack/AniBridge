"""Private management status state added by migration 0005.

``catalog_control`` stays in the frozen schema for compatibility with existing
databases, but no code reads its epoch counter. Management resources carry their
own ETag versions, so writing this row on every mutation was dead write
amplification. Do not drop the table in a routine migration.
"""

STATEMENTS = (
    "CREATE TABLE catalog_control(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)",
    "INSERT INTO catalog_control VALUES(1,1)",
    "CREATE TABLE catalog_update(provider TEXT PRIMARY KEY,state TEXT NOT NULL,error TEXT)",
)
