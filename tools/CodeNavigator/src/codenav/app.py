"""Local web UI for CodeNavigator."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import make_server

from codenav import services


def run_ui_server(root: Path, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    app = CodeNavWebApp(root)
    with make_server(host, port, app) as server:
        print(f"CodeNavigator UI running at http://{host}:{port}")
        server.serve_forever()


class CodeNavWebApp:
    def __init__(self, root: Path):
        self.root = root

    def __call__(self, environ: dict, start_response: Callable):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/") or "/"
        try:
            if method == "GET" and path == "/":
                return self._ok(start_response, self.render_dashboard(environ))
            if method == "GET" and path == "/classes/new":
                return self._ok(start_response, self.render_new_entry(environ))
            if method == "POST" and path == "/classes/new":
                return self.create_entry(environ, start_response)
            if method == "POST" and path == "/reindex":
                return self.run_reindex(start_response)
            if method == "POST" and path == "/files/delete":
                return self.delete_file(environ, start_response)
            if path.startswith("/classes/"):
                suffix = path.removeprefix("/classes/")
                if suffix.endswith("/edit") and method == "POST":
                    return self.update_entry(int(suffix.removesuffix("/edit")), environ, start_response)
                if suffix.endswith("/delete") and method == "POST":
                    return self.delete_entry(int(suffix.removesuffix("/delete")), start_response)
                if method == "GET":
                    return self._ok(start_response, self.render_entry_detail(int(suffix), environ))
            return self._not_found(start_response)
        except ValueError:
            return self._not_found(start_response)
        except Exception as exc:  # pragma: no cover - defensive UI error page
            return self._server_error(start_response, str(exc))

    def _query(self, environ: dict) -> dict[str, str]:
        raw = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in raw.items()}

    def _post(self, environ: dict) -> dict[str, str]:
        size = int(environ.get("CONTENT_LENGTH") or "0")
        body = environ["wsgi.input"].read(size).decode("utf-8") if size else ""
        raw = parse_qs(body, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in raw.items()}

    def _redirect(self, start_response: Callable, location: str):
        start_response("303 See Other", [("Location", location)])
        return [b""]

    def _ok(self, start_response: Callable, html: str):
        payload = html.encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))])
        return [payload]

    def _not_found(self, start_response: Callable):
        return self._ok(start_response, self._layout("Not Found", "<section><h1>Not found</h1></section>"))

    def _server_error(self, start_response: Callable, message: str):
        html = self._layout("Error", f"<section><h1>Error</h1><p>{escape(message)}</p></section>")
        payload = html.encode("utf-8")
        start_response("500 Internal Server Error", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))])
        return [payload]

    def _layout(self, title: str, body: str, *, message: str = "") -> str:
        banner = f'<div class="notice">{escape(message)}</div>' if message else ""
        return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - CodeNavigator</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --line: #d8dee6;
      --text: #16202a;
      --muted: #5b6b79;
      --accent: #1f6feb;
      --accent-soft: #e8f0fe;
      --warn: #b54708;
      --warn-soft: #fff1e6;
      --danger: #b42318;
      --danger-soft: #fdecea;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }}
    .shell {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 20px 24px 40px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 24px;
      max-width: 1400px;
      margin: 0 auto;
    }}
    .brand h1 {{
      margin: 0;
      font-size: 24px;
    }}
    .brand p {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    nav a, .button, button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
    }}
    .button.primary, button.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }}
    .notice {{
      margin-bottom: 18px;
      border: 1px solid var(--accent);
      background: var(--accent-soft);
      color: var(--text);
      padding: 12px 14px;
      border-radius: 8px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 18px;
    }}
    h2, h3 {{
      margin: 0 0 14px;
      font-size: 18px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .stat {{
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
      margin-top: 8px;
    }}
    .muted {{
      color: var(--muted);
    }}
    form.inline {{
      display: flex;
      gap: 10px;
      align-items: end;
      flex-wrap: wrap;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    label {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }}
    input, select, textarea {{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      font: inherit;
      color: var(--text);
      background: #fff;
    }}
    textarea {{
      min-height: 120px;
      resize: vertical;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      table-layout: fixed;
    }}
    th, td {{
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #fbfcfd;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      background: #eef2f6;
      color: var(--text);
    }}
    .badge.warn {{
      background: var(--warn-soft);
      color: var(--warn);
    }}
    .badge.manual {{
      background: #ece8ff;
      color: #5a35b0;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .stack {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .table-wrap {{
      width: 100%;
      overflow-x: auto;
    }}
    .col-solution {{ min-width: 120px; }}
    .col-project {{ min-width: 120px; }}
    .col-namespace {{ min-width: 180px; }}
    .col-class {{ min-width: 140px; }}
    .col-kind {{ width: 90px; }}
    .col-file {{ min-width: 320px; }}
    .col-description {{ min-width: 260px; }}
    .col-tags {{ min-width: 180px; }}
    .col-state {{ width: 90px; }}
    .col-source {{ width: 90px; }}
    .meta {{
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 10px 14px;
      font-size: 14px;
    }}
    .meta dt {{
      color: var(--muted);
    }}
    .meta dd {{
      margin: 0;
      word-break: break-word;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      font-family: Consolas, monospace;
      background: #fbfcfd;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div class="brand">
        <h1>CodeNavigator</h1>
        <p>{escape(str(self.root))}</p>
      </div>
      <nav>
        <a href="/">Dashboard</a>
        <a href="/classes/new">Manual Entry</a>
      </nav>
    </div>
  </header>
  <main class="shell">
    {banner}
    {body}
  </main>
</body>
</html>"""

    def render_dashboard(self, environ: dict) -> str:
        query = self._query(environ)
        filters = {
            "query": query.get("query", ""),
            "solution": query.get("solution", ""),
            "project": query.get("project", ""),
            "namespace": query.get("namespace", ""),
            "kind": query.get("kind", ""),
            "stale": query.get("stale", ""),
            "source_type": query.get("source_type", ""),
        }
        stats = services.get_status(self.root)
        options = services.distinct_filter_values(self.root)
        entries = services.list_entries(self.root, **filters)
        body = f"""
<section>
  <h2>Overview</h2>
  <div class="stats">
    <div class="stat"><span class="muted">Classes</span><strong>{stats['total_classes']}</strong></div>
    <div class="stat"><span class="muted">Manual</span><strong>{stats['manual_classes']}</strong></div>
    <div class="stat"><span class="muted">Stale</span><strong>{stats['stale_classes']}</strong></div>
    <div class="stat"><span class="muted">Last indexed</span><strong style="font-size:16px">{escape(stats['last_indexed'] or 'never')}</strong></div>
  </div>
  <p class="muted" style="margin-top:12px">DB: {escape(stats['db_path'])}</p>
  <div class="actions">
    <form method="post" action="/reindex">
      <button class="primary" type="submit">Run Full Reindex</button>
    </form>
  </div>
</section>
<section>
  <h2>Filters</h2>
  <form method="get" action="/" class="stack">
    <div class="grid">
      <label>Query
        <input name="query" value="{escape(filters['query'])}">
      </label>
      <label>Solution
        {self._select('solution', options['solution'], filters['solution'])}
      </label>
      <label>Project
        {self._select('project', options['project'], filters['project'])}
      </label>
      <label>Namespace
        {self._select('namespace', options['namespace'], filters['namespace'])}
      </label>
      <label>Kind
        {self._select('kind', options['kind'], filters['kind'])}
      </label>
      <label>Stale
        {self._select('stale', [('','All'),('0','Fresh'),('1','Stale')], filters['stale'])}
      </label>
      <label>Source
        {self._select('source_type', options['source_type'], filters['source_type'])}
      </label>
    </div>
    <div class="actions">
      <button class="primary" type="submit">Apply</button>
      <a class="button" href="/">Reset</a>
    </div>
  </form>
</section>
<section>
  <h2>Entries</h2>
  {self._entries_table(entries)}
</section>
<section>
  <h2>Delete File Index</h2>
  <form method="post" action="/files/delete" class="inline">
    <label style="min-width:420px">File path
      <input name="file" placeholder="D:\\path\\to\\file.cs">
    </label>
    <button type="submit">Delete Indexed File</button>
  </form>
</section>
"""
        return self._layout("Dashboard", body, message=query.get("message", ""))

    def render_new_entry(self, environ: dict) -> str:
        query = self._query(environ)
        body = f"""
<section>
  <h2>New Manual Entry</h2>
  <form method="post" action="/classes/new" class="stack">
    <div class="grid">
      <label>Solution<input name="solution"></label>
      <label>Project<input name="project"></label>
      <label>Namespace<input name="namespace"></label>
      <label>Class<input name="class_name" required></label>
      <label>Kind
        <select name="kind">
          <option value="class">class</option>
          <option value="interface">interface</option>
          <option value="struct">struct</option>
          <option value="record">record</option>
        </select>
      </label>
      <label>Folder<input name="folder"></label>
      <label style="grid-column: 1 / -1">File<input name="file" required></label>
    </div>
    <label>Description<textarea name="description" required></textarea></label>
    <label>Tags (comma separated)<textarea name="tags"></textarea></label>
    <div class="actions">
      <button class="primary" type="submit">Create</button>
      <a class="button" href="/">Cancel</a>
    </div>
  </form>
</section>
"""
        return self._layout("New Manual Entry", body, message=query.get("message", ""))

    def render_entry_detail(self, entry_id: int, environ: dict) -> str:
        query = self._query(environ)
        entry = services.get_entry(self.root, entry_id)
        if not entry:
            return self._layout("Not Found", "<section><h2>Entry not found</h2></section>")
        tags_text = ", ".join(
            entry["manual_tags"]
            if entry["source_type"] == "manual" or entry["manual_tags_is_set"]
            else entry["tags"]
        )
        description = entry["manual_description"] if entry["manual_description_is_set"] else entry["description"]
        delete_button = ""
        if entry["source_type"] == "manual":
            delete_button = f"""
            <form method="post" action="/classes/{entry_id}/delete">
              <button type="submit">Delete Manual Entry</button>
            </form>
            """
        body = f"""
<section>
  <div class="actions" style="justify-content:space-between">
    <div>
      <h2 style="margin-bottom:6px">{escape(entry['class_name'])}</h2>
      <div class="actions">
        <span class="badge">{escape(entry['kind'])}</span>
        <span class="badge {'manual' if entry['source_type'] == 'manual' else ''}">{escape(entry['source_type'])}</span>
        <span class="badge {'warn' if entry['stale'] else ''}">{'stale' if entry['stale'] else 'fresh'}</span>
      </div>
    </div>
    <a class="button" href="/">Back</a>
  </div>
</section>
<section>
  <h2>Metadata</h2>
  <dl class="meta">
    <dt>Solution</dt><dd>{escape(entry['solution'])}</dd>
    <dt>Project</dt><dd>{escape(entry['project'])}</dd>
    <dt>Namespace</dt><dd>{escape(entry['namespace'])}</dd>
    <dt>Folder</dt><dd>{escape(entry['folder'])}</dd>
    <dt>File</dt><dd>{escape(entry['file'])}</dd>
    <dt>Indexed At</dt><dd>{escape(entry['indexed_at'])}</dd>
    <dt>Source Hash</dt><dd>{escape(entry['source_hash'])}</dd>
  </dl>
</section>
<section>
  <h2>Edit Description and Tags</h2>
  <form method="post" action="/classes/{entry_id}/edit" class="stack">
    <label>Description<textarea name="description" required>{escape(description)}</textarea></label>
    <label>Tags (comma separated)<textarea name="tags">{escape(tags_text)}</textarea></label>
    <div class="actions">
      <button class="primary" type="submit">Save</button>
      {delete_button}
    </div>
  </form>
</section>
<section>
  <h2>Methods</h2>
  <pre>{escape(self._methods_text(entry['methods']))}</pre>
</section>
"""
        return self._layout(entry["class_name"], body, message=query.get("message", ""))

    def create_entry(self, environ: dict, start_response: Callable):
        payload = self._post(environ)
        if not payload.get("class_name", "").strip() or not payload.get("description", "").strip() or not payload.get("file", "").strip():
            return self._redirect(start_response, "/classes/new?" + urlencode({"message": "Class, file, description are required."}))
        try:
            entry_id = services.create_manual_entry(self.root, payload)
        except ValueError as exc:
            return self._redirect(start_response, "/classes/new?" + urlencode({"message": str(exc)}))
        return self._redirect(start_response, f"/classes/{entry_id}?" + urlencode({"message": "Manual entry created."}))

    def update_entry(self, entry_id: int, environ: dict, start_response: Callable):
        payload = self._post(environ)
        description = payload.get("description", "").strip()
        if not description:
            return self._redirect(start_response, f"/classes/{entry_id}?" + urlencode({"message": "Description is required."}))
        services.save_manual_metadata(self.root, entry_id, description=description, tags_text=payload.get("tags", ""))
        return self._redirect(start_response, f"/classes/{entry_id}?" + urlencode({"message": "Entry updated."}))

    def delete_entry(self, entry_id: int, start_response: Callable):
        deleted = services.delete_manual_entry(self.root, entry_id)
        message = "Manual entry deleted." if deleted else "Only manual entries can be deleted here."
        return self._redirect(start_response, "/?" + urlencode({"message": message}))

    def run_reindex(self, start_response: Callable):
        result = services.run_reindex(self.root, full=True)
        return self._redirect(start_response, "/?" + urlencode({"message": result["message"]}))

    def delete_file(self, environ: dict, start_response: Callable):
        payload = self._post(environ)
        file = payload.get("file", "").strip()
        if not file:
            return self._redirect(start_response, "/?" + urlencode({"message": "File path is required."}))
        result = services.delete_file_index(self.root, file, confirm=True)
        message = f"Deleted {result.get('deleted', 0)} class(es) for {result['file']}"
        return self._redirect(start_response, "/?" + urlencode({"message": message}))

    def _select(self, name: str, options, selected: str) -> str:
        if not options:
            normalized = [("", "All")]
        elif isinstance(options[0], str):
            normalized = [("", "All"), *[(value, value) for value in options]]
        elif isinstance(options, list):
            normalized = options
        else:
            normalized = [("", "All")]
        html = [f'<select name="{escape(name)}">']
        if normalized[0][0] != "":
            html.append('<option value="">All</option>')
        for value, label in normalized:
            is_selected = ' selected' if value == selected else ''
            html.append(f'<option value="{escape(value)}"{is_selected}>{escape(label)}</option>')
        html.append("</select>")
        return "".join(html)

    def _entries_table(self, entries: list[dict]) -> str:
        if not entries:
            return "<p class=\"muted\">No entries found.</p>"
        rows = []
        for entry in entries:
            rows.append(
                "<tr>"
                f"<td class=\"col-solution\">{escape(entry['solution'])}</td>"
                f"<td class=\"col-project\">{escape(entry['project'])}</td>"
                f"<td class=\"col-namespace\">{escape(entry['namespace'])}</td>"
                f"<td class=\"col-class\"><a href=\"/classes/{entry['id']}\">{escape(entry['class_name'])}</a></td>"
                f"<td class=\"col-kind\">{escape(entry['kind'])}</td>"
                f"<td class=\"col-file\">{escape(entry['file'])}</td>"
                f"<td class=\"col-description\">{escape(entry['description'])}</td>"
                f"<td class=\"col-tags\">{escape(', '.join(entry['tags']))}</td>"
                f"<td class=\"col-state\"><span class=\"badge {'warn' if entry['stale'] else ''}\">{'stale' if entry['stale'] else 'fresh'}</span></td>"
                f"<td class=\"col-source\"><span class=\"badge {'manual' if entry['source_type'] == 'manual' else ''}\">{escape(entry['source_type'])}</span></td>"
                "</tr>"
            )
        return (
            "<div class=\"table-wrap\"><table><thead><tr>"
            "<th class=\"col-solution\">Solution</th><th class=\"col-project\">Project</th>"
            "<th class=\"col-namespace\">Namespace</th><th class=\"col-class\">Class</th>"
            "<th class=\"col-kind\">Kind</th><th class=\"col-file\">File</th>"
            "<th class=\"col-description\">Description</th><th class=\"col-tags\">Tags</th>"
            "<th class=\"col-state\">State</th><th class=\"col-source\">Source</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )

    def _methods_text(self, methods: list[dict]) -> str:
        if not methods:
            return "No methods indexed."
        return "\n".join(
            f"{item.get('name', '')}: {item.get('description', '')}".strip()
            for item in methods
        )
