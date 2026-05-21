"""SQLite FTS5-backed index store for CodeNavigator."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_SIMPLE = """
CREATE TABLE IF NOT EXISTS classes (
    id          INTEGER PRIMARY KEY,
    solution    TEXT NOT NULL DEFAULT '',
    project     TEXT NOT NULL DEFAULT '',
    namespace   TEXT NOT NULL DEFAULT '',
    folder      TEXT NOT NULL DEFAULT '',
    file        TEXT NOT NULL,
    class_name  TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'class',
    description TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    tags_json   TEXT NOT NULL DEFAULT '[]',
    methods_json TEXT NOT NULL DEFAULT '[]',
    source_hash TEXT NOT NULL DEFAULT '',
    indexed_at  TEXT NOT NULL DEFAULT '',
    stale       INTEGER NOT NULL DEFAULT 0,
    UNIQUE(file, class_name)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS classes_fts USING fts5(
    class_name,
    namespace,
    description,
    tags,
    bigram,
    content='classes',
    content_rowid='id',
    tokenize='unicode61'
);
"""


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x1100 <= cp <= 0x11FF or 0xAC00 <= cp <= 0xD7FF or
            0x3130 <= cp <= 0x318F or 0x4E00 <= cp <= 0x9FFF)


def _bigrams(text: str) -> str:
    """Character bigrams for Korean/CJK only. ASCII words skipped (too noisy)."""
    tokens = []
    for word in text.split():
        if any(_is_cjk(c) for c in word) and len(word) >= 2:
            tokens.extend(word[i:i+2] for i in range(len(word) - 1))
    return " ".join(tokens)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db_path(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / ".codenav" / "index.sqlite"


def open_db(root: Path | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = _db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    uri = f"file:{path}?mode={'ro' if readonly else 'rwc'}"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    if not readonly:
        conn.executescript(SCHEMA_SIMPLE)
        conn.commit()
    return conn


def upsert_class(conn: sqlite3.Connection, entry: dict[str, Any]) -> bool:
    """Insert or update a class entry. Returns True if actually written (hash changed)."""
    file = entry["file"]
    class_name = entry["class_name"]
    new_hash = entry.get("source_hash", "")
    tags_list: list[str] = entry.get("tags", [])
    tags_str = " ".join(tags_list)
    bigram_str = _bigrams(entry.get("description", "") + " " + tags_str)

    row = conn.execute(
        "SELECT id, source_hash, namespace, description, tags FROM classes WHERE file=? AND class_name=?",
        (file, class_name),
    ).fetchone()

    stale_val = 1 if entry.get("stale") else 0
    if row and row["source_hash"] == new_hash and not stale_val:
        return False  # unchanged

    now = _now()
    if row:
        # Capture OLD FTS tokens before overwriting (external-content delete requires old values)
        old_namespace = row["namespace"]
        old_description = row["description"]
        old_tags = row["tags"]

        conn.execute(
            """UPDATE classes SET
                solution=?, project=?, namespace=?, folder=?,
                kind=?, description=?, tags=?, tags_json=?, methods_json=?,
                source_hash=?, indexed_at=?, stale=?
               WHERE id=?""",
            (
                entry.get("solution", ""),
                entry.get("project", ""),
                entry.get("namespace", ""),
                entry.get("folder", ""),
                entry.get("kind", "class"),
                entry.get("description", ""),
                tags_str,
                json.dumps(tags_list, ensure_ascii=False),
                json.dumps(entry.get("methods", []), ensure_ascii=False),
                new_hash,
                now,
                stale_val,
                row["id"],
            ),
        )
        row_id = row["id"]
        # FTS delete must use OLD row values to correctly remove prior index entry
        conn.execute(
            "INSERT INTO classes_fts(classes_fts, rowid, class_name, namespace, description, tags, bigram) VALUES('delete',?,?,?,?,?,'')",
            (row_id, class_name, old_namespace, old_description, old_tags),
        )
    else:
        cur = conn.execute(
            """INSERT INTO classes
               (solution, project, namespace, folder, file, class_name,
                kind, description, tags, tags_json, methods_json,
                source_hash, indexed_at, stale)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry.get("solution", ""),
                entry.get("project", ""),
                entry.get("namespace", ""),
                entry.get("folder", ""),
                file,
                class_name,
                entry.get("kind", "class"),
                entry.get("description", ""),
                tags_str,
                json.dumps(tags_list, ensure_ascii=False),
                json.dumps(entry.get("methods", []), ensure_ascii=False),
                new_hash,
                now,
                stale_val,
            ),
        )
        row_id = cur.lastrowid

    conn.execute(
        "INSERT INTO classes_fts(rowid, class_name, namespace, description, tags, bigram) VALUES(?,?,?,?,?,?)",
        (row_id, class_name, entry.get("namespace", ""), entry.get("description", ""), tags_str, bigram_str),
    )
    conn.commit()
    return True


def count_file_classes(conn: sqlite3.Connection, file: str) -> int:
    """Return number of indexed classes for a given file path."""
    row = conn.execute("SELECT COUNT(*) AS n FROM classes WHERE file=?", (file,)).fetchone()
    return int(row["n"]) if row else 0


def delete_file(conn: sqlite3.Connection, file: str) -> int:
    """Remove all classes for a deleted file from both content and FTS tables. Returns deleted count."""
    rows = conn.execute(
        "SELECT id, class_name, namespace, description, tags FROM classes WHERE file=?", (file,)
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO classes_fts(classes_fts, rowid, class_name, namespace, description, tags, bigram) VALUES('delete',?,?,?,?,?,'')",
            (row["id"], row["class_name"], row["namespace"], row["description"], row["tags"]),
        )
    conn.execute("DELETE FROM classes WHERE file=?", (file,))
    conn.commit()
    return len(rows)


def get_stats(conn: sqlite3.Connection, root: Path | None = None) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    stale = conn.execute("SELECT COUNT(*) FROM classes WHERE stale=1").fetchone()[0]
    last_row = conn.execute("SELECT MAX(indexed_at) FROM classes").fetchone()[0]
    stale_files = [
        r[0] for r in conn.execute("SELECT DISTINCT file FROM classes WHERE stale=1").fetchall()
    ]
    db_path = _db_path(root)
    return {
        "total_classes": total,
        "stale_classes": stale,
        "stale_files": stale_files,
        "last_indexed": last_row,
        "db_path": str(db_path),
    }
