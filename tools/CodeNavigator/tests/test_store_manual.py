"""Tests for manual metadata persistence and listing helpers."""

from pathlib import Path

from codenav import store


def _auto_entry(file: str, class_name: str, *, solution: str = "Sol", project: str = "Proj") -> dict:
    return {
        "file": file,
        "class_name": class_name,
        "namespace": "N.Core",
        "folder": str(Path(file).parent),
        "solution": solution,
        "project": project,
        "kind": "class",
        "description": "Auto description",
        "tags": ["auto", "tag"],
        "methods": [{"name": "Run", "description": "", "tags": ["run"]}],
        "source_hash": f"sha1:{class_name}",
        "stale": 0,
    }


def test_manual_metadata_survives_auto_reindex(tmp_path):
    conn = store.open_db(tmp_path)
    file = str(tmp_path / "A.cs")
    store.upsert_class(conn, _auto_entry(file, "A"))

    row = conn.execute("SELECT id FROM classes WHERE file=? AND class_name=?", (file, "A")).fetchone()
    assert row is not None
    store.save_manual_metadata(conn, int(row["id"]), description="Manual description", tags=["manual"])

    updated = store.get_entry(conn, int(row["id"]))
    assert updated is not None
    assert updated["description"] == "Manual description"
    assert updated["tags"] == ["manual"]

    next_entry = _auto_entry(file, "A")
    next_entry["description"] = "Fresh auto description"
    next_entry["tags"] = ["fresh", "auto"]
    next_entry["source_hash"] = "sha1:new"
    store.upsert_class(conn, next_entry)

    persisted = store.get_entry(conn, int(row["id"]))
    assert persisted is not None
    assert persisted["description"] == "Manual description"
    assert persisted["tags"] == ["manual"]
    assert persisted["auto_description"] == "Fresh auto description"
    assert persisted["auto_tags"] == ["fresh", "auto"]


def test_manual_entry_can_be_filtered_by_project(tmp_path):
    conn = store.open_db(tmp_path)
    store.create_manual_entry(
        conn,
        {
            "solution": "SolA",
            "project": "ProjA",
            "namespace": "N.A",
            "folder": str(tmp_path),
            "file": str((tmp_path / "ManualA.cs").resolve()),
            "class_name": "ManualA",
            "kind": "class",
            "description": "Manual A",
            "tags": ["manual"],
        },
    )
    store.create_manual_entry(
        conn,
        {
            "solution": "SolB",
            "project": "ProjB",
            "namespace": "N.B",
            "folder": str(tmp_path),
            "file": str((tmp_path / "ManualB.cs").resolve()),
            "class_name": "ManualB",
            "kind": "class",
            "description": "Manual B",
            "tags": ["manual"],
        },
    )

    filtered = store.list_entries(conn, project="ProjA")
    assert len(filtered) == 1
    assert filtered[0]["project"] == "ProjA"
    assert filtered[0]["source_type"] == "manual"
