"""Tests for CodeNavigator service orchestration."""

from pathlib import Path

from codenav import parser_cs, services, store


def _write_project(root: Path, solution: str, class_name: str) -> Path:
    project_dir = root / "Src" / solution
    project_dir.mkdir(parents=True)
    (project_dir / f"{solution}.sln").write_text("", encoding="utf-8")
    (project_dir / f"{solution}.csproj").write_text("<Project />", encoding="utf-8")
    file = project_dir / f"{class_name}.cs"
    file.write_text(
        f"""
namespace {solution}.Core;

/// <summary>Indexes {class_name}.</summary>
public class {class_name}
{{
    public void Run() {{ }}
}}
""".strip(),
        encoding="utf-8",
    )
    return file


def test_detect_solution_for_file_uses_nearest_ancestor_sln(tmp_path):
    update_file = _write_project(tmp_path, "Mirero.PCC.UpdateHub", "UpdateJob")
    xlab_file = _write_project(tmp_path, "Mirero.PCC.XLab", "RCSJobNotify")

    assert services.detect_solution_for_file(tmp_path, update_file) == "Mirero.PCC.UpdateHub"
    assert services.detect_solution_for_file(tmp_path, xlab_file) == "Mirero.PCC.XLab"


def test_reindex_preserves_solution_per_file_under_multi_solution_root(tmp_path):
    _write_project(tmp_path, "Mirero.PCC.UpdateHub", "UpdateJob")
    _write_project(tmp_path, "Mirero.PCC.XLab", "RCSJobNotify")

    result = services.run_reindex(tmp_path, full=True)

    assert result["code"] == 0
    conn = store.open_db(tmp_path)
    rows = conn.execute(
        "SELECT class_name, solution, file FROM classes ORDER BY class_name"
    ).fetchall()
    conn.close()
    assert [(row["class_name"], row["solution"]) for row in rows] == [
        ("RCSJobNotify", "Mirero.PCC.XLab"),
        ("UpdateJob", "Mirero.PCC.UpdateHub"),
    ]
    assert all(not Path(row["file"]).is_absolute() for row in rows)


def test_reindex_repairs_solution_metadata_when_source_hash_is_unchanged(tmp_path):
    xlab_file = _write_project(tmp_path, "Mirero.PCC.XLab", "RCSJobNotify")
    old_entry = {
        "file": str(xlab_file.resolve()),
        "class_name": "RCSJobNotify",
        "namespace": "Mirero.PCC.XLab.Core",
        "folder": str(xlab_file.parent.resolve()),
        "solution": "Mirero.PCC.UpdateHub",
        "project": "Mirero.PCC.XLab",
        "kind": "class",
        "description": "Indexes RCSJobNotify.",
        "tags": ["rcs", "job", "notify"],
        "methods": [{"name": "Run", "description": "", "tags": ["run"]}],
        "source_hash": "will-be-replaced",
        "stale": 0,
    }

    conn = store.open_db(tmp_path)
    old_entry["source_hash"] = parser_cs.file_hash(xlab_file)
    assert store.upsert_class(conn, old_entry)
    conn.close()

    result = services.run_reindex(tmp_path, full=True)

    assert result["code"] == 0
    conn = store.open_db(tmp_path)
    row = conn.execute(
        "SELECT solution, file, folder FROM classes WHERE class_name='RCSJobNotify'"
    ).fetchone()
    conn.close()
    assert row["solution"] == "Mirero.PCC.XLab"
    assert row["file"] == str(Path("Src") / "Mirero.PCC.XLab" / "RCSJobNotify.cs")
    assert row["folder"] == str(Path("Src") / "Mirero.PCC.XLab")


def test_delete_file_index_accepts_absolute_path_with_relative_storage(tmp_path):
    source = _write_project(tmp_path, "Mirero.PCC.XLab", "RCSJobNotify")
    result = services.run_reindex(tmp_path, full=True)
    assert result["code"] == 0

    dry_run = services.delete_file_index(tmp_path, str(source.resolve()), confirm=False)
    assert dry_run["file"] == str(Path("Src") / "Mirero.PCC.XLab" / "RCSJobNotify.cs")
    assert dry_run["would_delete"] == 1


def test_create_manual_entry_stores_relative_paths(tmp_path):
    entry_id = services.create_manual_entry(
        tmp_path,
        {
            "solution": "Sol",
            "project": "Proj",
            "namespace": "N",
            "class_name": "ManualClass",
            "kind": "class",
            "folder": str((tmp_path / "Src" / "Proj").resolve()),
            "file": str((tmp_path / "Src" / "Proj" / "ManualClass.cs").resolve()),
            "description": "Manual description.",
            "tags": "manual",
        },
    )

    entry = services.get_entry(tmp_path, entry_id)

    assert entry["file"] == str(Path("Src") / "Proj" / "ManualClass.cs")
    assert entry["folder"] == str(Path("Src") / "Proj")


def test_full_reindex_prunes_auto_entries_outside_collection_scope(tmp_path):
    _write_project(tmp_path, "Mirero.PCC.XLab", "RCSJobNotify")
    excluded = (
        tmp_path
        / ".claire"
        / "worktrees"
        / "Loader"
        / "Src"
        / "Mirero.PCC.XLab"
        / "Application"
        / "ToolGroupBuilder.cs"
    )
    excluded.parent.mkdir(parents=True)
    excluded.write_text("namespace Hidden; public class ToolGroupBuilder { }", encoding="utf-8")

    conn = store.open_db(tmp_path)
    store.upsert_class(
        conn,
        {
            "file": str(excluded.resolve()),
            "class_name": "ToolGroupBuilder",
            "namespace": "Hidden",
            "folder": str(excluded.parent.resolve()),
            "solution": "",
            "project": "",
            "kind": "class",
            "description": "Hidden worktree class.",
            "tags": ["hidden"],
            "methods": [],
            "source_hash": parser_cs.file_hash(excluded),
            "stale": 0,
        },
    )
    conn.close()

    result = services.run_reindex(tmp_path, full=True)

    assert result["deleted_count"] == 1
    conn = store.open_db(tmp_path)
    names = [
        row["class_name"]
        for row in conn.execute("SELECT class_name FROM classes ORDER BY class_name").fetchall()
    ]
    conn.close()
    assert names == ["RCSJobNotify"]
