"""Tests for local web UI routes."""

from io import BytesIO
from pathlib import Path

from codenav import app as web_app
from codenav import store


def _insert(repo: Path, file: str, class_name: str, *, solution: str = "Sol", project: str = "Proj") -> int:
    conn = store.open_db(repo)
    entry = {
        "file": file,
        "class_name": class_name,
        "namespace": "N.Core",
        "folder": str(Path(file).parent),
        "solution": solution,
        "project": project,
        "kind": "class",
        "description": "A class.",
        "tags": ["tag"],
        "methods": [{"name": "Run", "description": "", "tags": ["run"]}],
        "source_hash": f"sha1:{class_name}",
        "stale": 0,
    }
    store.upsert_class(conn, entry)
    row = conn.execute("SELECT id FROM classes WHERE file=? AND class_name=?", (file, class_name)).fetchone()
    conn.close()
    assert row is not None
    return int(row["id"])


def _request(app, path: str, *, method: str = "GET", body: str = "", query: str = ""):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body.encode("utf-8"))),
        "wsgi.input": BytesIO(body.encode("utf-8")),
    }
    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], dict(captured["headers"]), response


def test_dashboard_shows_solution_and_project_filters(tmp_path):
    file = str((tmp_path / "A.cs").resolve())
    _insert(tmp_path, file, "ClassA", solution="SolA", project="ProjA")
    app = web_app.CodeNavWebApp(tmp_path)

    status, _, response = _request(app, "/")

    assert status.startswith("200")
    assert "Solution" in response
    assert "Project" in response
    assert "ClassA" in response
    assert "ProjA" in response


def test_entry_detail_shows_file_and_methods(tmp_path):
    file = str((tmp_path / "B.cs").resolve())
    entry_id = _insert(tmp_path, file, "ClassB")
    app = web_app.CodeNavWebApp(tmp_path)

    status, _, response = _request(app, f"/classes/{entry_id}")

    assert status.startswith("200")
    assert "Source Hash" in response
    assert file in response
    assert "Run" in response


def test_create_manual_entry_redirects(tmp_path):
    app = web_app.CodeNavWebApp(tmp_path)
    body = (
        "solution=Sol&project=Proj&namespace=N.Manual&class_name=ManualClass&kind=class"
        "&folder=&file=ManualClass.cs&description=Manual+description&tags=manual"
    )

    status, headers, _ = _request(app, "/classes/new", method="POST", body=body)

    assert status.startswith("303")
    assert headers["Location"].startswith("/classes/")
