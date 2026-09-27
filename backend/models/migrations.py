"""Preserve existing garden IDs and scan links while making species optional."""
import sqlite3
from datetime import datetime, timezone


def allow_unknown_species(path):
    conn = sqlite3.connect(str(path))
    try:
        columns = conn.execute("PRAGMA table_info(garden)").fetchall()
        if not any(row[1] == "plant_id" and row[3] for row in columns):
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = str(path) + ".before-optional-species-" + stamp + ".bak"
        with sqlite3.connect(backup) as saved:
            conn.backup(saved)
        # Disable outside the transaction: dropping the old parent must NOT
        # trigger ON DELETE SET NULL on existing photo_assessments.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        original = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='garden'").fetchone()[0]
        import re
        replacement, count = re.subn(r"\bplant_id\s+INTEGER\s+NOT\s+NULL\b", "plant_id INTEGER", original, count=1, flags=re.I)
        if count != 1:
            raise RuntimeError("Unrecognized garden schema; migration rolled back")
        replacement = re.sub(r"CREATE TABLE(?: IF NOT EXISTS)?\s+[\"`\[]?garden[\"`\]]?", "CREATE TABLE garden_optional_species", replacement, count=1, flags=re.I)
        extras = conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name='garden' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
        seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='garden'").fetchone()
        names = ', '.join('"' + row[1].replace('"', '""') + '"' for row in columns)
        conn.execute(replacement)
        conn.execute(f"INSERT INTO garden_optional_species ({names}) SELECT {names} FROM garden")
        conn.execute("DROP TABLE garden")
        conn.execute("ALTER TABLE garden_optional_species RENAME TO garden")
        for (sql,) in extras:
            conn.execute(sql)
        if seq:
            conn.execute("UPDATE sqlite_sequence SET seq = max(seq, ?) WHERE name='garden'", (seq[0],))
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Foreign-key validation failed; migration rolled back")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
