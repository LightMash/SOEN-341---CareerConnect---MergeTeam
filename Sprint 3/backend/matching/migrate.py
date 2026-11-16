"""
Applies migrations/001_matching_tables.sql to a LOCAL database.

Run from Sprint 3/backend:
    $env:DATABASE_URL='postgresql+pg8000://postgres:postgres@localhost:5432/careerconnect_local'; python -m matching.migrate

The SQL only creates the three new tables (IF NOT EXISTS), so it is safe to
run more than once. The users and jobs tables must already exist (start the
app once, or run the demo script, which creates them).

For the shared database, the team applies the same .sql file through the
Supabase SQL editor instead; this script refuses any non-local host.
"""

import os

from .local_only import require_local_database_url

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def statements(sql: str) -> list[str]:
    """Split a migration file into single statements (no ; inside strings here)."""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main() -> None:
    url = require_local_database_url()

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    with engine.begin() as conn:
        for name in files:
            with open(os.path.join(MIGRATIONS_DIR, name), encoding="utf-8") as f:
                for statement in statements(f.read()):
                    conn.execute(text(statement))
            print(f"Applied {name}")
    engine.dispose()


if __name__ == "__main__":
    main()
