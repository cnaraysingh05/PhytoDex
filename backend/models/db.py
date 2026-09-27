"""SQLite connection helper for PhytoDex.

This file was missing from this branch even though nine other files import
from it (backend/routes/plants.py, garden.py, capture.py, photo_bridge.py,
backend/services/assistant_logs.py, system_status.py, database/seed.py, and
the test suite) -- the app could not boot without it. Root cause: a bare
`models/` line in .gitignore matched backend/models/ as well as the
intended ml/train.py output folder, so `git add -A` silently skipped this
whole directory. Fixed alongside this file (.gitignore now uses /models/,
anchored to repo root).

Contract this matches (see conftest.py's autouse isolate_runtime fixture
and tests/test_integration.py):
- database_path() resolves PHYTODEX_DB_PATH at CALL time, not import time,
  so tests that set the env var after this module is imported still take
  effect. Falls back to database/phytodex.db under the project root.
- database_path() must not have side effects -- backend/services/
  system_status.py calls database_path().is_file() to report
  'not_initialized' without ever creating the file.
"""
import os
import sqlite3
from pathlib import Path

from backend.settings import ROOT

SCHEMA_PATH = ROOT / "database" / "schema.sql"


def database_path():
    """Resolve the effective DB file path. Read fresh every call -- do not
    cache this in a module-level constant, or env-var overrides set after
    import (as tests do) would be silently ignored."""
    override = os.getenv("PHYTODEX_DB_PATH")
    return Path(override) if override else ROOT / "database" / "phytodex.db"


def get_db():
    """Return a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(str(database_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables from schema.sql if they don't exist yet. Safe to re-run."""
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    from backend.models.migrations import allow_unknown_species
    allow_unknown_species(path)


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {database_path()}")
