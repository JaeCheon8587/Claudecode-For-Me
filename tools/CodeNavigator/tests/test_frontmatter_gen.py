"""Tests for codenav.frontmatter_gen — target collection + block insertion."""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from codenav import frontmatter_gen, parser_cs


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """Make tmp_path act as a clean git repo so is_git_clean() passes by default."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    return tmp_path


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path.parent, check=False)
    subprocess.run(["git", "commit", "-q", "-m", "init", "--allow-empty"], cwd=path.parent, check=False)
    return path


def test_collect_targets_skips_xml_doc_and_existing_frontmatter(tmp_repo):
    _write(tmp_repo / "a.cs", """
        namespace N {
            /// <summary>has xml</summary>
            public class WithXml { }
        }
        """)
    _write(tmp_repo / "b.cs", """
        namespace N {
            // ---
            // description: has frontmatter
            // ---
            public class WithFm { }
        }
        """)
    _write(tmp_repo / "c.cs", """
        namespace N {
            public class Bare { }
        }
        """)

    subprocess.run(["git", "add", "-A"], cwd=tmp_repo, check=False)
    subprocess.run(["git", "commit", "-q", "-m", "all"], cwd=tmp_repo, check=False)

    targets = frontmatter_gen.collect_targets(tmp_repo, limit=50)
    names = {t.class_name for t in targets}
    assert names == {"Bare"}


def test_collect_targets_respects_limit(tmp_repo):
    _write(tmp_repo / "many.cs", """
        namespace N {
            public class A { }
            public class B { }
            public class C { }
        }
        """)
    targets = frontmatter_gen.collect_targets(tmp_repo, limit=2)
    assert len(targets) == 2


def test_collect_targets_finds_decl_line_and_indent(tmp_repo):
    _write(tmp_repo / "x.cs", """
        namespace N
        {
            public class Foo
            {
            }
        }
        """)
    targets = frontmatter_gen.collect_targets(tmp_repo, limit=10)
    assert len(targets) == 1
    target = targets[0]
    assert target.class_name == "Foo"
    assert target.indent == "    "
    # line numbering is 1-based — class line should be #4 after dedent (first blank line preserved)
    raw = (tmp_repo / "x.cs").read_text(encoding="utf-8")
    expected_line = next(
        i for i, line in enumerate(raw.splitlines(), start=1) if "class Foo" in line
    )
    assert target.decl_line_no == expected_line


def test_render_frontmatter_no_tags_omits_tags_line():
    block = frontmatter_gen.render_frontmatter("    ", "hello", [])
    assert block == ["    // ---", "    // description: hello", "    // ---"]


def test_render_frontmatter_with_tags():
    block = frontmatter_gen.render_frontmatter("", "desc", ["a", "b", "c"])
    assert block == ["// ---", "// description: desc", "// tags: [a, b, c]", "// ---"]


def test_insert_frontmatter_preserves_existing_content_and_parser_re_extracts(tmp_repo):
    file = _write(tmp_repo / "f.cs", """
        namespace N {
            public class Bare {
                public void Hello() { }
            }
        }
        """)
    raw_before = file.read_text(encoding="utf-8")
    decl_line = next(
        i for i, line in enumerate(raw_before.splitlines(), start=1) if "class Bare" in line
    )
    frontmatter_gen.insert_frontmatter_into_file(
        file,
        [(decl_line, "    ", "정해진 설명", ["bare", "test"])],
    )

    parsed = parser_cs.parse_cs_file(file)
    assert len(parsed) == 1
    assert parsed[0].xml_summary == "정해진 설명"
    assert parsed[0].frontmatter_tags == ["bare", "test"]
    assert "public void Hello()" in file.read_text(encoding="utf-8")


def test_insert_frontmatter_multiple_classes_bottom_up(tmp_repo):
    file = _write(tmp_repo / "multi.cs", """
        namespace N {
            public class A { }
            public class B { }
        }
        """)
    raw = file.read_text(encoding="utf-8")
    lines = raw.splitlines()
    line_a = next(i for i, ln in enumerate(lines, start=1) if "class A" in ln)
    line_b = next(i for i, ln in enumerate(lines, start=1) if "class B" in ln)

    frontmatter_gen.insert_frontmatter_into_file(
        file,
        [
            (line_a, "    ", "service A", ["a"]),
            (line_b, "    ", "service B", ["b"]),
        ],
    )

    parsed = {p.class_name: p for p in parser_cs.parse_cs_file(file)}
    assert parsed["A"].xml_summary == "service A"
    assert parsed["B"].xml_summary == "service B"
    assert parsed["A"].frontmatter_tags == ["a"]
    assert parsed["B"].frontmatter_tags == ["b"]


def test_insert_preserves_crlf_line_endings(tmp_repo):
    file = tmp_repo / "crlf.cs"
    content = "namespace N {\r\n    public class CR { }\r\n}\r\n"
    file.write_bytes(content.encode("utf-8"))
    subprocess.run(["git", "add", "-A"], cwd=tmp_repo, check=False)
    subprocess.run(["git", "commit", "-q", "-m", "crlf"], cwd=tmp_repo, check=False)

    raw = file.read_text(encoding="utf-8")
    decl_line = next(i for i, ln in enumerate(raw.splitlines(), start=1) if "class CR" in ln)
    frontmatter_gen.insert_frontmatter_into_file(
        file, [(decl_line, "    ", "crlf test", [])]
    )
    after = file.read_bytes()
    assert b"\r\n" in after
    assert b"// description: crlf test" in after


def test_insert_preserves_bom(tmp_repo):
    file = tmp_repo / "bom.cs"
    content = "﻿namespace N {\n    public class B { }\n}\n"
    file.write_bytes(content.encode("utf-8"))
    subprocess.run(["git", "add", "-A"], cwd=tmp_repo, check=False)
    subprocess.run(["git", "commit", "-q", "-m", "bom"], cwd=tmp_repo, check=False)

    raw_decoded = file.read_text(encoding="utf-8-sig")
    decl_line = next(
        i for i, ln in enumerate(raw_decoded.splitlines(), start=1) if "class B" in ln
    )
    frontmatter_gen.insert_frontmatter_into_file(
        file, [(decl_line, "    ", "bom test", [])]
    )
    after_bytes = file.read_bytes()
    assert after_bytes.startswith(b"\xef\xbb\xbf")


def test_run_dry_run_does_not_modify_files(tmp_repo, monkeypatch):
    file = _write(tmp_repo / "dryrun.cs", """
        namespace N {
            public class Dry { }
        }
        """)
    before = file.read_bytes()
    monkeypatch.setenv("CODENAV_FRONTMATTER_MOCK", "stub")

    result = frontmatter_gen.run(tmp_repo, limit=10, apply=False, allow_dirty=False)

    assert result.candidates == 1
    assert result.generated == 1
    assert result.written == 0
    assert file.read_bytes() == before


def test_run_apply_writes_block(tmp_repo, monkeypatch):
    file = _write(tmp_repo / "apply.cs", """
        namespace N {
            public class Apply { }
        }
        """)
    monkeypatch.setenv("CODENAV_FRONTMATTER_MOCK", "stub")

    result = frontmatter_gen.run(tmp_repo, limit=10, apply=True, allow_dirty=True)

    assert result.written == 1
    parsed = parser_cs.parse_cs_file(file)
    assert parsed[0].xml_summary  # description filled by mock stub


def test_run_refuses_dirty_tree(tmp_repo, monkeypatch):
    _write(tmp_repo / "dirty.cs", "namespace N { public class D { } }\n")
    # leave uncommitted modification
    (tmp_repo / "dirty.cs").write_text(
        "namespace N { public class D { } }\n// extra\n", encoding="utf-8"
    )
    monkeypatch.setenv("CODENAV_FRONTMATTER_MOCK", "stub")

    with pytest.raises(RuntimeError):
        frontmatter_gen.run(tmp_repo, limit=10, apply=True, allow_dirty=False)


def test_run_allow_dirty_overrides(tmp_repo, monkeypatch):
    file = _write(tmp_repo / "force.cs", """
        namespace N {
            public class F { }
        }
        """)
    # induce a dirty tree
    file.write_text(file.read_text(encoding="utf-8") + "// dirty\n", encoding="utf-8")
    monkeypatch.setenv("CODENAV_FRONTMATTER_MOCK", "stub")

    result = frontmatter_gen.run(tmp_repo, limit=10, apply=False, allow_dirty=True)
    assert result.candidates >= 1


def test_run_ai_failure_yields_no_writes(tmp_repo, monkeypatch):
    _write(tmp_repo / "fail.cs", """
        namespace N {
            public class X { }
        }
        """)
    monkeypatch.setenv("CODENAV_FRONTMATTER_MOCK", "fail")

    result = frontmatter_gen.run(tmp_repo, limit=10, apply=True, allow_dirty=True)
    assert result.written == 0
    assert len(result.failures) == 1
