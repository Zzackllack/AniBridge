"""Private management status state added by migration 0005."""

STATEMENTS = (
    "CREATE TABLE catalog_control(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)",
    "INSERT INTO catalog_control VALUES(1,1)",
    "CREATE TABLE catalog_update(provider TEXT PRIMARY KEY,state TEXT NOT NULL,error TEXT)",
)


def bump(db) -> None:
    db.execute("UPDATE catalog_control SET version=version+1 WHERE singleton=1")
