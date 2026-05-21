"""Tests for C# regex parser."""

import textwrap
from pathlib import Path

import pytest

from codenav import parser_cs


def _parse(src: str) -> list[parser_cs.ClassInfo]:
    tmp = Path(__file__).parent / "_tmp_test.cs"
    tmp.write_text(textwrap.dedent(src), encoding="utf-8")
    try:
        return parser_cs.parse_cs_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def test_class_kind_class():
    result = _parse("""
namespace N {
    public class Foo { }
}
    """)
    assert len(result) == 1
    assert result[0].kind == "class"
    assert result[0].class_name == "Foo"


def test_class_kind_interface():
    result = _parse("""
namespace N {
    public interface IFoo {
        void DoIt();
    }
}
    """)
    assert len(result) == 1
    assert result[0].kind == "interface"
    assert result[0].class_name == "IFoo"


def test_interface_name_not_misclassified_as_interface():
    """class IFooInterface should be kind=class, not kind=interface."""
    result = _parse("""
namespace N {
    public class IFooInterface { }
}
    """)
    assert len(result) == 1
    assert result[0].kind == "class"


def test_record_kind():
    result = _parse("""
namespace N {
    public record Point {
        public int X { get; }
    }
}
    """)
    assert result[0].kind == "record"


def test_struct_kind():
    result = _parse("""
namespace N {
    public struct Vec2 {
        public float X;
        public float Y;
    }
}
    """)
    assert len(result) == 1
    assert result[0].kind == "struct"


def test_xml_summary_extraction():
    result = _parse("""
namespace N {
    /// <summary>
    /// 주문 데이터를 저장하는 리포지터리.
    /// </summary>
    public class OrderRepo { }
}
    """)
    assert len(result) == 1
    assert "주문 데이터를 저장" in result[0].xml_summary


def test_brace_in_string_literal_does_not_break_body():
    """Brace inside a string literal must not confuse the body extractor."""
    result = _parse("""
namespace N {
    public class Parser {
        private string _open = "{";
        private string _close = "}";
        public void Parse() { }
    }
    public class Other { }
}
    """)
    assert len(result) == 2
    # Parser should only have Parse, not methods from Other
    parser_class = next(c for c in result if c.class_name == "Parser")
    assert any(m.name == "Parse" for m in parser_class.methods)


def test_namespace_extraction():
    result = _parse("""
namespace OMS.Core.Services {
    public class Svc { }
}
    """)
    assert result[0].namespace == "OMS.Core.Services"


def test_method_not_extracted_from_next_class():
    result = _parse("""
namespace N {
    public class A {
        public void MethodA() { }
    }
    public class B {
        public void MethodB() { }
    }
}
    """)
    a = next(c for c in result if c.class_name == "A")
    b = next(c for c in result if c.class_name == "B")
    assert all(m.name == "MethodA" for m in a.methods)
    assert all(m.name == "MethodB" for m in b.methods)


def test_no_classes_returns_empty():
    result = _parse("""
namespace N { }
    """)
    assert result == []


def test_frontmatter_description_filled():
    result = _parse("""
namespace N {
    // ---
    // description: 문서 처리 서비스
    // ---
    public class DocumentService { }
}
    """)
    assert len(result) == 1
    assert "문서 처리 서비스" in result[0].xml_summary


def test_frontmatter_tags_parsed():
    result = _parse("""
namespace N {
    // ---
    // description: repo
    // tags: [document, repository, persistence]
    // ---
    public class DocumentRepository { }
}
    """)
    assert result[0].frontmatter_tags == ["document", "repository", "persistence"]


def test_xml_doc_wins_over_frontmatter():
    result = _parse("""
namespace N {
    // ---
    // description: ignored
    // ---
    /// <summary>actual description</summary>
    public class Svc { }
}
    """)
    assert "actual description" in result[0].xml_summary
    assert "ignored" not in result[0].xml_summary


def test_frontmatter_quoted_description():
    result = _parse('''
namespace N {
    // ---
    // description: "quoted text"
    // ---
    public class Q { }
}
    ''')
    assert result[0].xml_summary == "quoted text"


def test_frontmatter_unclosed_silently_skipped():
    result = _parse("""
namespace N {
    // ---
    // description: 닫는 마커 누락
    public class Broken { }
}
    """)
    assert result[0].xml_summary == ""
    assert result[0].frontmatter_tags is None


def test_frontmatter_blocked_by_attribute():
    result = _parse("""
namespace N {
    // ---
    // description: 사이 attribute
    // ---

    [Obsolete]
    public class WithAttr { }
}
    """)
    assert result[0].xml_summary == ""


def test_frontmatter_multi_class_each_matches():
    result = _parse("""
namespace N {
    // ---
    // description: 서비스 A
    // ---
    public class A { }

    // ---
    // description: 서비스 B
    // tags: [b, beta]
    // ---
    public class B { }
}
    """)
    by_name = {c.class_name: c for c in result}
    assert "서비스 A" in by_name["A"].xml_summary
    assert "서비스 B" in by_name["B"].xml_summary
    assert by_name["B"].frontmatter_tags == ["b", "beta"]
    assert by_name["A"].frontmatter_tags is None


def test_frontmatter_empty_tags_list():
    result = _parse("""
namespace N {
    // ---
    // description: empty tags
    // tags: []
    // ---
    public class E { }
}
    """)
    assert result[0].frontmatter_tags == []


def test_frontmatter_unknown_key_ignored():
    result = _parse("""
namespace N {
    // ---
    // description: ok
    // owner: jaecheon
    // domain: docs
    // ---
    public class U { }
}
    """)
    assert "ok" in result[0].xml_summary


def test_frontmatter_tags_propagated_to_entries():
    result = _parse("""
namespace N {
    // ---
    // description: r
    // tags: [persist, store]
    // ---
    public class R { }
}
    """)
    tmp = Path(__file__).parent / "_tmp_test.cs"
    tmp.write_text("// ---\n// description: r\n// tags: [persist, store]\n// ---\npublic class R {}\n", encoding="utf-8")
    try:
        entries = parser_cs.classes_to_index_entries(result, tmp)
    finally:
        tmp.unlink(missing_ok=True)
    assert entries[0]["tags"] == ["persist", "store"]


def test_frontmatter_no_tags_falls_back_to_pascal():
    classes = _parse("""
namespace N {
    // ---
    // description: r
    // ---
    public class DocumentRepo { }
}
    """)
    tmp = Path(__file__).parent / "_tmp_test.cs"
    tmp.write_text("public class DocumentRepo {}\n", encoding="utf-8")
    try:
        entries = parser_cs.classes_to_index_entries(classes, tmp)
    finally:
        tmp.unlink(missing_ok=True)
    assert entries[0]["tags"] == ["document", "repo"]


def test_multiple_classes_parsed():
    result = _parse("""
namespace N {
    public class A { }
    public interface IB { }
    public struct S { }
}
    """)
    assert len(result) == 3
    kinds = {c.class_name: c.kind for c in result}
    assert kinds["A"] == "class"
    assert kinds["IB"] == "interface"
    assert kinds["S"] == "struct"
