"""Tests for codenav delete subcommand."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from codenav import store
from codenav.__main__ import cmd_delete


@pytest.fixture
def repo(tmp_path):
    return tmp_path


def _insert(repo: Path, file: str, class_name: str) -> None:
    conn = store.open_db(repo)
    entry = {
        "file": file,
        "class_name": class_name,
        "namespace": "N",
        "folder": str(Path(file).parent),
        "solution": "",
        "project": "",
        "kind": "class",
        "description": "A class.",
        "tags": ["test"],
        "methods": [],
        "source_hash": f"sha1:{class_name}",
        "stale": 0,
    }
    store.upsert_class(conn, entry)
    conn.close()


def _args(repo, file, yes=False, as_json=False):
    return SimpleNamespace(root=str(repo), file=file, yes=yes, json=as_json)


def test_delete_dry_run_default(repo, capsys):
    target = str(repo / "Foo.cs")
    _insert(repo, target, "FooClass")

    rc = cmd_delete(_args(repo, target, yes=False))
    assert rc == 0

    conn = store.open_db(repo)
    assert store.count_file_classes(conn, "Foo.cs") == 1, "dry-run must not delete"
    conn.close()

    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "1" in out


def test_delete_yes_removes_row(repo):
    target = str(repo / "Bar.cs")
    _insert(repo, target, "BarClass")

    rc = cmd_delete(_args(repo, target, yes=True))
    assert rc == 0

    conn = store.open_db(repo)
    assert store.count_file_classes(conn, "Bar.cs") == 0
    conn.close()


def test_delete_missing_file_returns_zero(repo, capsys):
    rc = cmd_delete(_args(repo, str(repo / "Ghost.cs"), yes=True))
    assert rc == 0
    out = capsys.readouterr().out
    assert "No indexed" in out


def test_delete_json_output(repo):
    target = str(repo / "Baz.cs")
    _insert(repo, target, "BazClass")

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_delete(_args(repo, target, yes=False, as_json=True))
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert "file" in payload
    assert "would_delete" in payload
    assert payload["dry_run"] is True

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        cmd_delete(_args(repo, target, yes=True, as_json=True))
    payload2 = json.loads(buf2.getvalue())
    assert payload2["deleted"] == 1
    assert payload2["dry_run"] is False
