"""FTS5-based search with BM25 + tag-hit bonus scoring."""

import json
import sqlite3
import sys
from typing import Any

_TAG_BONUS = 2.0  # added per matched tag token


import re as _re
_PASCAL_SPLIT = _re.compile(r"[A-Z][a-z]+|[A-Z]+(?=[A-Z][a-z])|[A-Z]+$|\d+|[a-z]+")


def _query_terms(query: str) -> list[str]:
    terms = []
    for raw in query.split():
        raw = raw.strip()
        if not raw:
            continue
        # PascalCase/camelCase: split and add both original and parts
        parts = _PASCAL_SPLIT.findall(raw)
        if len(parts) > 1:
            terms.extend(p.lower() for p in parts)
        else:
            terms.append(raw.lower())
    return list(dict.fromkeys(terms))  # deduplicate, preserve order


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x1100 <= cp <= 0x11FF or 0xAC00 <= cp <= 0xD7FF or
            0x3130 <= cp <= 0x318F or 0x4E00 <= cp <= 0x9FFF)


def _build_bigrams(text: str) -> list[str]:
    """Bigrams for Korean/CJK only. ASCII words skipped to avoid false positives."""
    tokens = []
    for word in text.split():
        if any(_is_cjk(c) for c in word) and len(word) >= 2:
            tokens.extend(word[i:i+2] for i in range(len(word) - 1))
    return tokens


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 10,
    solution: str | None = None,
    project: str | None = None,
    scope: str = "class",
) -> list[dict[str, Any]]:
    """Search index. Returns list of result dicts ordered by score desc."""
    terms = _query_terms(query)
    if not terms:
        return []

    # Build FTS5 MATCH expression: each term must appear (AND semantics)
    # Search across description, tags, bigram columns
    # FTS5 column filter syntax: {col1 col2 col3}: term
    fts_parts = []
    for term in terms:
        # FTS5 phrase quoting: escape embedded double-quotes by doubling them
        safe = term.replace('"', '""')
        bgrams = _build_bigrams(term)
        term_clause = f'"{safe}"'
        if bgrams:
            safe_bgrams = [b.replace('"', '""') for b in bgrams]
            bigram_clause = " OR ".join(f'bigram:"{b}"' for b in safe_bgrams)
            fts_parts.append(f"( {term_clause} OR {bigram_clause} )")
        else:
            fts_parts.append(term_clause)

    fts_expr = " AND ".join(fts_parts)

    filters = []
    params: list[Any] = []
    if solution:
        filters.append("c.solution = ?")
        params.append(solution)
    if project:
        filters.append("c.project = ?")
        params.append(project)

    where_extra = ("AND " + " AND ".join(filters)) if filters else ""

    sql = f"""
        SELECT
            c.solution, c.project, c.namespace, c.folder, c.file,
            c.class_name, c.kind, c.description, c.tags_json, c.methods_json,
            bm25(classes_fts, 3.0, 2.0, 1.0, 2.0, 1.5) AS bm25_score
        FROM classes_fts
        JOIN classes c ON classes_fts.rowid = c.id
        WHERE classes_fts MATCH ?
          AND c.stale = 0
          {where_extra}
        ORDER BY bm25_score
        LIMIT ?
    """
    # bm25() returns negative values — lower = better match in FTS5
    try:
        rows = conn.execute(sql, [fts_expr, *params, limit]).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[codenav] FTS search error: {exc}", file=sys.stderr)
        return []

    results = []
    for row in rows:
        tags: list[str] = json.loads(row["tags_json"])
        tags_lower = {t.lower() for t in tags}

        hit_count = sum(1 for t in terms if t.lower() in tags_lower)
        # bm25 is negative; invert and add tag bonus
        score = round(-row["bm25_score"] + hit_count * _TAG_BONUS, 4)

        entry: dict[str, Any] = {
            "solution": row["solution"],
            "project": row["project"],
            "namespace": row["namespace"],
            "folder": row["folder"],
            "file": row["file"],
            "class": row["class_name"],
            "kind": row["kind"],
            "score": score,
            "description": row["description"],
            "tags": tags,
        }
        if scope == "method":
            entry["methods"] = json.loads(row["methods_json"])
        results.append(entry)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
