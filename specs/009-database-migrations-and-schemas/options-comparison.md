# Options Comparison

## Summary Table

| Option | Fit for Current Stack | Pros | Cons | Notes |
| --- | --- | --- | --- | --- |
| Alembic + SQLModel | Excellent | Native SQLAlchemy migrations, supports autogenerate, mature tooling, works with SQLite batch mode | Requires migration setup and discipline | Standard choice for SQLAlchemy stacks. [Alembic docs](https://alembic.sqlalchemy.org/en/latest/) |
| Atlas (schema-as-code) | Good | Declarative workflow, drift detection, CI-friendly | New toolchain, more setup, less integrated with SQLModel metadata | Best when the team already uses Atlas. [Atlas docs](https://atlasgo.io/) |
| Yoyo (SQL/Python migrations) | Good | Lightweight, SQL-first, simple CLI | Limited autogenerate, less ORM awareness | Works well for manual SQL migration flows. [Yoyo docs](https://github.com/coobas/yoyo-migrations) |
| Raw SQL migrations | Fair | Minimal dependencies, total control | Manual tracking, fragile rollbacks, no auto diff | Suitable only for very small schemas |

## SQLite Constraints

SQLite has limited `ALTER TABLE` support. Schema changes often require table rebuilds, which Alembic supports via batch mode. This constraint strongly favors a migration tool that can automate table rebuilds for SQLite.

## Recommendation Context

Given the project already uses SQLModel, Alembic is the most compatible choice and aligns with established SQLAlchemy practices. It minimizes refactor risk and supports database evolution while keeping SQLite.
