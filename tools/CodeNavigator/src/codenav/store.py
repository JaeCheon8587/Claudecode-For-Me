"""SQLite FTS5-backed index store for CodeNavigator."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_SIMPLE = """
CREATE TABLE IF NOT EXISTS classes (
    id                  INTEGER PRIMARY KEY,
    solution            TEXT NOT NULL DEFAULT '',
    project             TEXT NOT NULL DEFAULT '',
    namespace           TEXT NOT NULL DEFAULT '',
    folder              TEXT NOT NULL DEFAULT '',
    file                TEXT NOT NULL,
    class_name          TEXT NOT NULL,
    kind                TEXT NOT NULL DEFAULT 'class',
    description         TEXT NOT NULL DEFAULT '',
    tags                TEXT NOT NULL DEFAULT '',
    tags_json           TEXT NOT NULL DEFAULT '[]',
    methods_json        TEXT NOT NULL DEFAULT '[]',
    source_hash         TEXT NOT NULL DEFAULT '',
    indexed_at          TEXT NOT NULL DEFAULT '',
    stale               INTEGER NOT NULL DEFAULT 0,
    source_type         TEXT NOT NULL DEFAULT 'auto',
    auto_description    TEXT NOT NULL DEFAULT '',
    auto_tags_json      TEXT NOT NULL DEFAULT '[]',
    manual_description  TEXT NOT NULL DEFAULT '',
    manual_tags_json    TEXT NOT NULL DEFAULT '',
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

_MIGRATION_COLUMNS = {
    "source_type": "ALTER TABLE classes ADD COLUMN source_type TEXT NOT NULL DEFAULT 'auto'",
    "auto_description": "ALTER TABLE classes ADD COLUMN auto_description TEXT NOT NULL DEFAULT ''",
    "auto_tags_json": "ALTER TABLE classes ADD COLUMN auto_tags_json TEXT NOT NULL DEFAULT '[]'",
    "manual_description": "ALTER TABLE classes ADD COLUMN manual_description TEXT NOT NULL DEFAULT ''",
    "manual_tags_json": "ALTER TABLE classes ADD COLUMN manual_tags_json TEXT NOT NULL DEFAULT ''",
}


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


def _load_json_list(raw: str, default: list[str] | None = None) -> list[str]:
    if not raw:
        return list(default or [])
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return list(default or [])
    if not isinstance(parsed, list):
        return list(default or [])
    return [str(v) for v in parsed]


def _json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _effective_tags(auto_tags: list[str], manual_tags_json: str, source_type: str) -> list[str]:
    if source_type == "manual":
        return auto_tags
    if manual_tags_json != "":
        return _load_json_list(manual_tags_json)
    return auto_tags


def _effective_description(auto_description: str, manual_description: str, source_type: str) -> str:
    if source_type == "manual":
        return auto_description
    return manual_description or auto_description


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    tags = _load_json_list(row["tags_json"])
    methods = _load_json_list(row["methods_json"], default=[])
    if methods and isinstance(methods[0], str):
        methods = json.loads(row["methods_json"])
    return {
        "id": row["id"],
        "solution": row["solution"],
        "project": row["project"],
        "namespace": row["namespace"],
        "folder": row["folder"],
        "file": row["file"],
        "class_name": row["class_name"],
        "kind": row["kind"],
        "description": row["description"],
        "tags": tags,
        "methods": json.loads(row["methods_json"]),
        "source_hash": row["source_hash"],
        "indexed_at": row["indexed_at"],
        "stale": int(row["stale"]),
        "source_type": row["source_type"],
        "auto_description": row["auto_description"],
        "auto_tags": _load_json_list(row["auto_tags_json"]),
        "manual_description": row["manual_description"],
        "manual_tags": _load_json_list(row["manual_tags_json"]),
        "manual_tags_is_set": row["manual_tags_json"] != "",
        "manual_description_is_set": row["manual_description"] != "",
        "has_manual_override": bool(row["manual_description"] or row["manual_tags_json"] != ""),
    }


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SIMPLE)
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(classes)").fetchall()
    }
    for column, ddl in _MIGRATION_COLUMNS.items():
        if column not in existing_columns:
            conn.execute(ddl)
    conn.execute(
        """
        UPDATE classes
           SET source_type = CASE WHEN source_type = '' THEN 'auto' ELSE source_type END,
               auto_description = CASE WHEN auto_description = '' THEN description ELSE auto_description END,
               auto_tags_json = CASE
                   WHEN auto_tags_json = '' OR auto_tags_json = '[]' THEN tags_json
                   ELSE auto_tags_json
               END
        """
    )
    conn.commit()


def open_db(root: Path | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = _db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    uri = f"file:{path}?mode={'ro' if readonly else 'rwc'}"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    if not readonly:
        _ensure_schema(conn)
    return conn


def upsert_class(conn: sqlite3.Connection, entry: dict[str, Any]) -> bool:
    """Insert or update a class entry. Returns True if actually written."""
    file = entry["file"]
    class_name = entry["class_name"]
    source_type = entry.get("source_type", "auto")
    new_hash = entry.get("source_hash", "")
    stale_val = 1 if entry.get("stale") else 0

    methods_json = json.dumps(entry.get("methods", []), ensure_ascii=False)

    row = conn.execute(
        """
        SELECT id, source_hash, solution, project, namespace, folder, kind,
               description, tags, methods_json,
               source_type, auto_description, auto_tags_json,
               manual_description, manual_tags_json
          FROM classes
         WHERE file=? AND class_name=?
        """,
        (file, class_name),
    ).fetchone()

    if source_type == "auto":
        auto_description = entry.get("description", "")
        auto_tags_list = [str(v) for v in entry.get("tags", [])]
        manual_description = row["manual_description"] if row else ""
        manual_tags_json = row["manual_tags_json"] if row else ""
        effective_description = _effective_description(auto_description, manual_description, source_type)
        effective_tags_list = _effective_tags(auto_tags_list, manual_tags_json, source_type)
    else:
        auto_description = entry.get("description", "")
        auto_tags_list = [str(v) for v in entry.get("tags", [])]
        manual_description = entry.get("manual_description", auto_description)
        manual_tags_json = entry.get("manual_tags_json", _json_list(auto_tags_list))
        effective_description = auto_description
        effective_tags_list = auto_tags_list

    effective_tags_json = _json_list(effective_tags_list)
    effective_tags_str = " ".join(effective_tags_list)
    auto_tags_json = _json_list(auto_tags_list)
    bigram_str = _bigrams(effective_description + " " + effective_tags_str)

    if (
        row
        and source_type == "auto"
        and row["source_hash"] == new_hash
        and not stale_val
        and row["solution"] == entry.get("solution", "")
        and row["project"] == entry.get("project", "")
        and row["namespace"] == entry.get("namespace", "")
        and row["folder"] == entry.get("folder", "")
        and row["kind"] == entry.get("kind", "class")
        and row["methods_json"] == methods_json
        and row["auto_description"] == auto_description
        and row["auto_tags_json"] == auto_tags_json
    ):
        return False

    now = _now()
    if row:
        old_namespace = row["namespace"]
        old_description = row["description"]
        old_tags = row["tags"]
        conn.execute(
            """
            UPDATE classes SET
                solution=?, project=?, namespace=?, folder=?,
                kind=?, description=?, tags=?, tags_json=?, methods_json=?,
                source_hash=?, indexed_at=?, stale=?, source_type=?,
                auto_description=?, auto_tags_json=?, manual_description=?, manual_tags_json=?
             WHERE id=?
            """,
            (
                entry.get("solution", ""),
                entry.get("project", ""),
                entry.get("namespace", ""),
                entry.get("folder", ""),
                entry.get("kind", "class"),
                effective_description,
                effective_tags_str,
                effective_tags_json,
                methods_json,
                new_hash,
                now,
                stale_val,
                source_type,
                auto_description,
                auto_tags_json,
                manual_description,
                manual_tags_json,
                row["id"],
            ),
        )
        row_id = row["id"]
        conn.execute(
            "INSERT INTO classes_fts(classes_fts, rowid, class_name, namespace, description, tags, bigram) VALUES('delete',?,?,?,?,?,'')",
            (row_id, class_name, old_namespace, old_description, old_tags),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO classes
               (solution, project, namespace, folder, file, class_name,
                kind, description, tags, tags_json, methods_json,
                source_hash, indexed_at, stale, source_type,
                auto_description, auto_tags_json, manual_description, manual_tags_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                entry.get("solution", ""),
                entry.get("project", ""),
                entry.get("namespace", ""),
                entry.get("folder", ""),
                file,
                class_name,
                entry.get("kind", "class"),
                effective_description,
                effective_tags_str,
                effective_tags_json,
                methods_json,
                new_hash,
                now,
                stale_val,
                source_type,
                auto_description,
                auto_tags_json,
                manual_description,
                manual_tags_json,
            ),
        )
        row_id = cur.lastrowid

    conn.execute(
        "INSERT INTO classes_fts(rowid, class_name, namespace, description, tags, bigram) VALUES(?,?,?,?,?,?)",
        (row_id, class_name, entry.get("namespace", ""), effective_description, effective_tags_str, bigram_str),
    )
    conn.commit()
    return True


def count_file_classes(conn: sqlite3.Connection, file: str) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM classes WHERE file=?", (file,)).fetchone()
    return int(row["n"]) if row else 0


def delete_file(conn: sqlite3.Connection, file: str, *, source_type: str | None = None) -> int:
    filters = ["file=?"]
    params: list[Any] = [file]
    if source_type is not None:
        filters.append("source_type=?")
        params.append(source_type)
    where = " AND ".join(filters)
    rows = conn.execute(
        f"SELECT id, class_name, namespace, description, tags FROM classes WHERE {where}",
        params,
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO classes_fts(classes_fts, rowid, class_name, namespace, description, tags, bigram) VALUES('delete',?,?,?,?,?,'')",
            (row["id"], row["class_name"], row["namespace"], row["description"], row["tags"]),
        )
    conn.execute(f"DELETE FROM classes WHERE {where}", params)
    conn.commit()
    return len(rows)


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    row = conn.execute(
        "SELECT id, class_name, namespace, description, tags FROM classes WHERE id=?",
        (entry_id,),
    ).fetchone()
    if not row:
        return False
    conn.execute(
        "INSERT INTO classes_fts(classes_fts, rowid, class_name, namespace, description, tags, bigram) VALUES('delete',?,?,?,?,?,'')",
        (row["id"], row["class_name"], row["namespace"], row["description"], row["tags"]),
    )
    conn.execute("DELETE FROM classes WHERE id=?", (entry_id,))
    conn.commit()
    return True


def get_entry(conn: sqlite3.Connection, entry_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM classes WHERE id=?", (entry_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_entries(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    solution: str = "",
    project: str = "",
    namespace: str = "",
    kind: str = "",
    stale: str = "",
    source_type: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if query:
        filters.append(
            "(class_name LIKE ? OR namespace LIKE ? OR file LIKE ? OR description LIKE ? OR tags LIKE ? OR solution LIKE ? OR project LIKE ?)"
        )
        q = f"%{query}%"
        params.extend([q, q, q, q, q, q, q])
    if solution:
        filters.append("solution = ?")
        params.append(solution)
    if project:
        filters.append("project = ?")
        params.append(project)
    if namespace:
        filters.append("namespace = ?")
        params.append(namespace)
    if kind:
        filters.append("kind = ?")
        params.append(kind)
    if stale == "1":
        filters.append("stale = 1")
    elif stale == "0":
        filters.append("stale = 0")
    if source_type:
        filters.append("source_type = ?")
        params.append(source_type)

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = conn.execute(
        f"""
        SELECT *
          FROM classes
          {where}
         ORDER BY stale DESC, solution, project, namespace, class_name
         LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def distinct_values(conn: sqlite3.Connection, column: str) -> list[str]:
    allowed = {"solution", "project", "namespace", "kind", "source_type"}
    if column not in allowed:
        raise ValueError(f"Unsupported column: {column}")
    rows = conn.execute(
        f"SELECT DISTINCT {column} AS value FROM classes WHERE {column} <> '' ORDER BY {column}"
    ).fetchall()
    return [str(row["value"]) for row in rows]


def save_manual_metadata(
    conn: sqlite3.Connection,
    entry_id: int,
    *,
    description: str,
    tags: list[str],
) -> bool:
    row = conn.execute("SELECT * FROM classes WHERE id=?", (entry_id,)).fetchone()
    if not row:
        return False

    if row["source_type"] == "manual":
        return upsert_class(
            conn,
            {
                "solution": row["solution"],
                "project": row["project"],
                "namespace": row["namespace"],
                "folder": row["folder"],
                "file": row["file"],
                "class_name": row["class_name"],
                "kind": row["kind"],
                "description": description,
                "tags": tags,
                "methods": json.loads(row["methods_json"]),
                "source_hash": row["source_hash"],
                "stale": row["stale"],
                "source_type": "manual",
                "manual_description": description,
                "manual_tags_json": _json_list(tags),
            },
        )

    auto_description = row["auto_description"] or row["description"]
    auto_tags = _load_json_list(row["auto_tags_json"], default=_load_json_list(row["tags_json"]))
    effective_tags_json = _json_list(tags)
    effective_tags_str = " ".join(tags)
    bigram_str = _bigrams(description + " " + effective_tags_str)

    conn.execute(
        "INSERT INTO classes_fts(classes_fts, rowid, class_name, namespace, description, tags, bigram) VALUES('delete',?,?,?,?,?,'')",
        (row["id"], row["class_name"], row["namespace"], row["description"], row["tags"]),
    )
    conn.execute(
        """
        UPDATE classes SET
            description=?, tags=?, tags_json=?,
            manual_description=?, manual_tags_json=?, indexed_at=?
         WHERE id=?
        """,
        (description, effective_tags_str, effective_tags_json, description, effective_tags_json, _now(), entry_id),
    )
    conn.execute(
        "INSERT INTO classes_fts(rowid, class_name, namespace, description, tags, bigram) VALUES(?,?,?,?,?,?)",
        (row["id"], row["class_name"], row["namespace"], description, effective_tags_str, bigram_str),
    )
    conn.commit()
    return True


def create_manual_entry(conn: sqlite3.Connection, entry: dict[str, Any]) -> int:
    existing = conn.execute(
        "SELECT id FROM classes WHERE file=? AND class_name=?",
        (entry["file"], entry["class_name"]),
    ).fetchone()
    if existing:
        raise ValueError("An indexed entry already exists for the same file and class.")

    values = {
        "solution": entry.get("solution", ""),
        "project": entry.get("project", ""),
        "namespace": entry.get("namespace", ""),
        "folder": entry.get("folder", ""),
        "file": entry["file"],
        "class_name": entry["class_name"],
        "kind": entry.get("kind", "class"),
        "description": entry["description"],
        "tags": [str(v) for v in entry.get("tags", [])],
        "methods": entry.get("methods", []),
        "source_hash": entry.get("source_hash", "manual"),
        "stale": 0,
        "source_type": "manual",
        "manual_description": entry["description"],
        "manual_tags_json": _json_list([str(v) for v in entry.get("tags", [])]),
    }
    upsert_class(conn, values)
    row = conn.execute(
        "SELECT id FROM classes WHERE file=? AND class_name=?",
        (values["file"], values["class_name"]),
    ).fetchone()
    if not row:
        raise ValueError("Failed to create manual entry")
    return int(row["id"])


def get_stats(conn: sqlite3.Connection, root: Path | None = None) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    stale = conn.execute("SELECT COUNT(*) FROM classes WHERE stale=1").fetchone()[0]
    manual = conn.execute("SELECT COUNT(*) FROM classes WHERE source_type='manual'").fetchone()[0]
    last_row = conn.execute("SELECT MAX(indexed_at) FROM classes").fetchone()[0]
    stale_files = [
        r[0] for r in conn.execute("SELECT DISTINCT file FROM classes WHERE stale=1").fetchall()
    ]
    db_path = _db_path(root)
    return {
        "total_classes": total,
        "stale_classes": stale,
        "manual_classes": manual,
        "stale_files": stale_files,
        "last_indexed": last_row,
        "db_path": str(db_path),
    }
