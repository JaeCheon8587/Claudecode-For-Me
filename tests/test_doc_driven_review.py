"""
doc_driven_review.py 단위 테스트.

실행:
    pytest tests/test_doc_driven_review.py -v
    pytest tests/test_doc_driven_review.py -v -k "validate"
"""

import subprocess
import sys
from pathlib import Path

import pytest

# scripts/ 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import doc_driven_review as ddr


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """
    임시 git 레포 fixture.
    git init + 더미 README 초기 커밋. CI hermetic (GPG signing 비활성, autocrlf=false).
    """
    import subprocess as sp

    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.email", "ddr-test@example.invalid"],
           cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "DDR Test"],
           cwd=tmp_path, check=True)
    sp.run(["git", "config", "commit.gpgsign", "false"],
           cwd=tmp_path, check=True)
    sp.run(["git", "config", "core.autocrlf", "false"],
           cwd=tmp_path, check=True)

    readme = tmp_path / "README.md"
    readme.write_text("# Test repo\n", encoding="utf-8")
    sp.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-q", "-m", "initial"], cwd=tmp_path, check=True)

    return tmp_path


# ─── TestValidateCodexOutputV2 ───────────────────────────────────────────────

VALID_OUTPUT_V2 = """\
# Code Review: spec-calculator

## Summary
- **무엇을 하는 코드인지**: Calculator 클래스 구현. Add/Subtract/Multiply 연산 제공.
- **핵심 문제**: namespace 불일치, Add 음수 validation 누락.
- **핵심 장점**: Multiply 정상 구현.

## Severity 기준
- **Critical**: 장애, 보안, 데이터 손실 가능성 (또는 문서 핵심 요구 완전 누락)
- **Major**: 구조/성능/유지보수 큰 영향 (또는 문서 명시 요구 미충족)
- **Minor**: 가독성, 네이밍, 스타일 개선 (또는 문서 부수 요구)
- **Suggestion**: 더 나은 대안 제안 (문서 외 권장 사항)

## Requirements Coverage
| § | 요구사항 | 상태 | 코드 위치 | 비고 |
|---|---|---|---|---|
| 1 | Models 네임스페이스 | ✗ | Calculator.cs:1 | SimpleCalc로 잘못됨 |
| 2 | Add 양수 검증 | ⚠ | Calculator.cs:6-8 | validation 누락 |
| 3 | Subtract 메서드 | ✓ | Calculator.cs:11-14 | 정상 구현 |
| 4 | Multiply 메서드 | ✓ | Calculator.cs:16-19 | 정상 구현 |
| 5 | Program.cs 출력 | ✓ | Program.cs:3 | 정상 출력 |

## Top Priorities
1. [MAJOR] namespace 불일치 — 런타임 참조 오류 가능
2. [MAJOR] Add validation 누락 — 음수 입력 시 예외 미발생

## Review Comments

### 1. [MAJOR] namespace SimpleCalc.Models 미적용

**Location**
`Calculator.cs:1`

**Issue**
`namespace SimpleCalc`로 선언됨. 문서 §1은 `SimpleCalc.Models` 요구.

**Why it matters**
문서: "Calculator 클래스는 SimpleCalc.Models 네임스페이스 하위에 위치."
namespace 불일치 시 외부 참조 코드에서 컴파일 오류 발생.

**Suggestion**
`namespace SimpleCalc.Models` 로 변경.

**Example**
```csharp
namespace SimpleCalc.Models
{
    public class Calculator { ... }
}
```

### 2. [MAJOR] Add 음수 validation 누락

**Location**
`Calculator.cs:6-8`

**Issue**
음수 입력 시 ArgumentException 미발생. 단순 합산만 수행.

**Why it matters**
문서 §2: "음수 입력 시 ArgumentException 던짐."
잘못된 입력이 그대로 통과되어 계산 결과 오염 가능.

**Suggestion**
`if (a <= 0 || b <= 0)` 조건 추가 후 `ArgumentException` 던지기.

**Example**
```csharp
public int Add(int a, int b)
{
    if (a <= 0 || b <= 0)
        throw new ArgumentException("Both arguments must be positive.");
    return a + b;
}
```

## Overengineered
| 항목 | 코드 위치 | 설명 |
|---|---|---|
| Divide | Calculator.cs:22-28 | 문서 미명시 메서드 |

## Conformance
Counts: Critical: 0, Major: 2, Minor: 0, Suggestion: 0
namespace 불일치 + Add validation 부재로 2개 요구사항 미충족.

Conformance: 70%"""


class TestValidateCodexOutputV2:
    def test_정상_v2_통과(self):
        ok, errors, pct = ddr.validate_codex_output(VALID_OUTPUT_V2)
        assert ok, errors
        assert errors == []
        assert pct == 70

    def test_h1_누락_위반(self):
        bad = VALID_OUTPUT_V2.replace("# Code Review: spec-calculator\n", "")
        ok, errors, _ = ddr.validate_codex_output(bad)
        assert not ok
        assert any("Code Review" in e for e in errors)

    def test_섹션_누락_위반(self):
        bad = VALID_OUTPUT_V2.replace("## Top Priorities\n", "").replace(
            "1. [MAJOR] namespace 불일치 — 런타임 참조 오류 가능\n"
            "2. [MAJOR] Add validation 누락 — 음수 입력 시 예외 미발생\n\n",
            "",
        )
        ok, errors, _ = ddr.validate_codex_output(bad)
        assert not ok
        assert any("Top Priorities" in e for e in errors)

    def test_Conformance_누락(self):
        lines = VALID_OUTPUT_V2.splitlines()
        bad = "\n".join(ln for ln in lines if not ln.startswith("Conformance: "))
        ok, errors, pct = ddr.validate_codex_output(bad)
        assert not ok
        assert pct is None
        assert any("Conformance" in e for e in errors)

    def test_Conformance_범위밖_101(self):
        bad = VALID_OUTPUT_V2.replace("Conformance: 70%", "Conformance: 101%")
        ok, errors, pct = ddr.validate_codex_output(bad)
        assert not ok
        assert pct is None
        assert any("범위" in e for e in errors)

    def test_Counts_4항목_위반(self):
        bad = VALID_OUTPUT_V2.replace(
            "Counts: Critical: 0, Major: 2, Minor: 0, Suggestion: 0",
            "Counts: Critical: 0, Major: 2, Minor: 0",
        )
        ok, errors, _ = ddr.validate_codex_output(bad)
        assert not ok
        assert any("Counts" in e for e in errors)

    def test_review_comments_20개초과(self):
        extra_blocks = "\n".join(
            f"### {i}. [MINOR] 제목 {i}\n\n**Location**\n`file.cs:{i}`\n\n"
            f"**Issue**\n이슈.\n\n**Why it matters**\n이유.\n\n"
            f"**Suggestion**\n제안.\n\n**Example**\n```csharp\n// example\n```"
            for i in range(3, 24)
        )
        bad = VALID_OUTPUT_V2.replace(
            "## Overengineered",
            extra_blocks + "\n\n## Overengineered",
        )
        ok, errors, _ = ddr.validate_codex_output(bad)
        assert not ok
        assert any("Review Comments" in e and "20" in e for e in errors)

    def test_severity_SUGGESTION_허용(self):
        with_suggestion = VALID_OUTPUT_V2.replace(
            "### 2. [MAJOR] Add 음수 validation 누락",
            "### 2. [SUGGESTION] 로깅 추가 권장",
        ).replace(
            "Counts: Critical: 0, Major: 2, Minor: 0, Suggestion: 0",
            "Counts: Critical: 0, Major: 1, Minor: 0, Suggestion: 1",
        )
        ok, errors, pct = ddr.validate_codex_output(with_suggestion)
        assert ok, errors
        assert pct == 70


# ─── TestBuildPrompt ──────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_단일_doc_block(self, tmp_path):
        doc = tmp_path / "spec.md"
        doc.write_text("# Spec\n함수 A 구현", encoding="utf-8")
        patch = tmp_path / ".git" / "info" / "test.patch"
        patch.parent.mkdir(parents=True)
        patch.write_text("", encoding="utf-8")

        prompt = ddr.build_prompt(
            [(doc, "# Spec\n함수 A 구현")],
            patch,
            "working-tree",
            None,
            tmp_path,
        )

        assert "## DOC:" in prompt
        assert "spec.md" in prompt
        assert "함수 A 구현" in prompt
        assert "## Review Comments" in prompt
        assert "Conformance: <integer 0-100>%" in prompt
        # v1.2.1 강화 규칙 키워드
        assert "Exact-string fidelity" in prompt
        assert "Compilable Example" in prompt
        assert "비고 column" in prompt
        assert "Cross-file ripple" in prompt
        assert "passed_weight" in prompt
        assert "Critical=4" in prompt
        # v1.2.2 강화 규칙 키워드
        assert "상태 기호 판정 기준" in prompt
        assert "연관 요구 통합" in prompt
        assert "Overengineered 범위 제한" in prompt
        assert "UNCHANGED CONTEXT" in prompt
        assert "Use UNCHANGED CONTEXT" in prompt

    def test_여러_doc_block(self, tmp_path):
        doc1 = tmp_path / "a.md"
        doc2 = tmp_path / "b.md"
        doc1.write_text("doc1 내용", encoding="utf-8")
        doc2.write_text("doc2 내용", encoding="utf-8")
        patch = tmp_path / "fake.patch"
        patch.write_text("", encoding="utf-8")

        prompt = ddr.build_prompt(
            [(doc1, "doc1 내용"), (doc2, "doc2 내용")],
            patch,
            "branch",
            "abc1234",
            tmp_path,
        )

        assert "a.md" in prompt
        assert "b.md" in prompt
        assert "doc1 내용" in prompt
        assert "doc2 내용" in prompt
        assert "Base ref: abc1234" in prompt

    def test_strict_schema_키워드_포함(self, tmp_path):
        doc = tmp_path / "x.md"
        doc.write_text("x", encoding="utf-8")
        patch = tmp_path / "x.patch"
        patch.write_text("", encoding="utf-8")

        prompt = ddr.build_prompt([(doc, "x")], patch, "working-tree", None, tmp_path)

        for keyword in (
            "OUTPUT FORMAT — STRICT",
            "FIELD RULES",
            "CONFORMANCE RUBRIC",
            "CONSTRAINTS",
            "Severity 기준",
            "Requirements Coverage",
            "Top Priorities",
            "Review Comments",
            "Overengineered",
            "Conformance",
            "UNCHANGED CONTEXT",
            "상태 기호 판정 기준",
            "연관 요구 통합",
            "Overengineered 범위 제한",
            "Use UNCHANGED CONTEXT",
        ):
            assert keyword in prompt, f"키워드 누락: {keyword!r}"


# ─── TestInvokeCodex ──────────────────────────────────────────────────────────

class TestInvokeCodex:
    def test_codex_미설치_CodexUnavailableError(self, monkeypatch, tmp_path):
        monkeypatch.setattr("shutil.which", lambda name: None)
        with pytest.raises(ddr.CodexUnavailableError):
            ddr.invoke_codex_foreground("prompt", None, None, tmp_path)

    def test_foreground_stdout_캡처(self, monkeypatch, tmp_path):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codex")

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="## Missing\n- (none)\n\n## Improve\n- (none)\n\n## Overengineered\n- (none)\n\n## Conformance\nCounts: Critical: 0, Major: 0, Minor: 0\n\nConformance: 100%",
            stderr="",
        )

        def fake_run(*args, **kwargs):
            return fake_result

        monkeypatch.setattr(subprocess, "run", fake_run)

        rc, stdout, stderr = ddr.invoke_codex_foreground("prompt", None, None, tmp_path)
        assert rc == 0
        assert "Conformance: 100%" in stdout

    def test_windows_cmd_경로_cmd_래핑(self, monkeypatch, tmp_path):
        monkeypatch.setattr("shutil.which", lambda name: "C:\\npm\\codex.CMD")
        monkeypatch.setattr("os.name", "nt")

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="## Missing\n- (none)\n\n## Improve\n- (none)\n\n## Overengineered\n- (none)\n\n## Conformance\nCounts: Critical: 0, Major: 0, Minor: 0\n\nConformance: 100%",
            stderr="",
        )
        captured = {}

        def fake_run(*args, **kwargs):
            captured["cmd"] = args[0] if args else kwargs.get("args")
            return fake_result

        monkeypatch.setattr(subprocess, "run", fake_run)

        ddr.invoke_codex_foreground("prompt", None, None, tmp_path)
        cmd = captured["cmd"]
        assert cmd[0] == "cmd"
        assert cmd[1] == "/c"
        assert "codex.CMD" in cmd[2]

    def test_background_PID_출력(self, monkeypatch, tmp_path):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codex")

        class FakePopen:
            pid = 12345
            stdin = type("FakeStdin", (), {
                "write": lambda self, x: None,
                "close": lambda self: None,
            })()

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakePopen())

        # background 경로: _git_info_dir monkeypatch (tmp_path은 real git 레포 아님)
        fake_info_dir = tmp_path / "fake-git-info"
        fake_info_dir.mkdir(parents=True)
        monkeypatch.setattr(ddr, "_git_info_dir", lambda repo_root: fake_info_dir)

        rc, stdout, stderr = ddr.invoke_codex_background("prompt", None, None, tmp_path)
        assert rc == ddr.EXIT_OK
        assert "12345" in stdout
        assert "Background" in stdout


# ─── TestScopeAuto ────────────────────────────────────────────────────────────

class TestScopeAuto:
    def test_변경있으면_working_tree(self, monkeypatch, tmp_path):
        def fake_has_changes(repo_root):
            return True

        monkeypatch.setattr(ddr, "_has_working_tree_changes", fake_has_changes)

        scope, base = ddr.determine_scope(tmp_path, "auto", None)
        assert scope == "working-tree"
        assert base is None

    def test_변경없으면_branch_로_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ddr, "_has_working_tree_changes", lambda r: False)
        monkeypatch.setattr(ddr, "resolve_base_ref", lambda r, b: "abc1234")

        scope, base = ddr.determine_scope(tmp_path, "auto", None)
        assert scope == "branch"
        assert base == "abc1234"

    def test_working_tree_명시(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ddr, "_has_working_tree_changes", lambda r: False)

        scope, base = ddr.determine_scope(tmp_path, "working-tree", None)
        assert scope == "working-tree"
        assert base is None


# ─── TestReadAttachedDocuments ─────────────────────────────────────────────────────

class TestReadAttachedDocuments:
    def test_정상_읽기(self, tmp_path):
        doc = tmp_path / "spec.md"
        doc.write_text("# Hello", encoding="utf-8")

        result = ddr.read_attached_docs([doc])
        assert len(result) == 1
        assert result[0][0] == doc
        assert result[0][1] == "# Hello"

    def test_파일없음_에러(self, tmp_path):
        with pytest.raises(ddr.DocReviewError, match="문서 파일 없음"):
            ddr.read_attached_docs([tmp_path / "nonexistent.md"])

    def test_단일_100KB_초과(self, tmp_path):
        doc = tmp_path / "big.md"
        doc.write_bytes(b"x" * (ddr.SINGLE_DOC_BYTES_LIMIT + 1))
        with pytest.raises(ddr.DocTooBigError):
            ddr.read_attached_docs([doc])

    def test_합산_200KB_초과(self, tmp_path):
        docs = []
        for i in range(3):
            d = tmp_path / f"doc{i}.md"
            d.write_bytes(b"x" * 80_000)
            docs.append(d)
        with pytest.raises(ddr.DocTooBigError):
            ddr.read_attached_docs(docs)


# ─── TestIsBinaryPath ─────────────────────────────────────────────────────────

class TestIsBinaryPath:
    def test_png_확장자(self, tmp_path):
        p = tmp_path / "img.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        assert ddr.is_binary_path(p, tmp_path) is True

    def test_null_byte_포함(self, tmp_path):
        p = tmp_path / "data.bin"
        p.write_bytes(b"hello\x00world")
        assert ddr.is_binary_path(p, tmp_path) is True

    def test_텍스트_파일(self, tmp_path):
        p = tmp_path / "source.py"
        p.write_text("def main(): pass\n", encoding="utf-8")
        assert ddr.is_binary_path(p, tmp_path) is False


# ─── TestFormatViolationLine ──────────────────────────────────────────────────

class TestFormatViolationLine:
    def test_단일_에러(self):
        line = ddr.format_violation_line(["section order 위반"])
        assert line.startswith("[doc-driven-review] OUTPUT-SCHEMA-VIOLATION:")
        assert "section order 위반" in line

    def test_복수_에러_세미콜론_구분(self):
        line = ddr.format_violation_line(["에러1", "에러2", "에러3"])
        assert "에러1" in line
        assert "에러2" in line
        assert ";" in line


# ─── TestExtractIdentifiers ───────────────────────────────────────────────────

class TestExtractIdentifiers:
    """식별자 추출: 언어별 정규식 패턴 + stopword + 길이 필터."""

    def test_csharp_namespace_class_method_추출(self, tmp_git_repo):
        f = tmp_git_repo / "Foo.cs"
        f.write_text(
            "namespace MyApp.Models\n"
            "{\n"
            "    public class FooBar\n"
            "    {\n"
            "        public int ComputeValue(int x) { return x * 2; }\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        idents = ddr.extract_identifiers_from_changed(
            tmp_git_repo, "working-tree", None, [Path("Foo.cs")]
        )
        assert "MyApp.Models" in idents
        assert "FooBar" in idents
        assert "ComputeValue" in idents

    def test_python_def_class_추출(self, tmp_git_repo):
        f = tmp_git_repo / "helper.py"
        f.write_text(
            "class DataPipeline:\n"
            "    pass\n"
            "\n"
            "def transform_records(items):\n"
            "    return items\n",
            encoding="utf-8",
        )
        idents = ddr.extract_identifiers_from_changed(
            tmp_git_repo, "working-tree", None, [Path("helper.py")]
        )
        assert "DataPipeline" in idents
        assert "transform_records" in idents

    def test_stopword_제외(self, tmp_git_repo):
        f = tmp_git_repo / "p.cs"
        f.write_text(
            "namespace App\n{\n  public class Program { }\n  public class Test { }\n}\n",
            encoding="utf-8",
        )
        idents = ddr.extract_identifiers_from_changed(
            tmp_git_repo, "working-tree", None, [Path("p.cs")]
        )
        assert "Program" not in idents  # stopword
        assert "Test" not in idents     # stopword
        assert "App" not in idents      # 길이 3 < MIN_IDENT_LEN(4)

    def test_바이너리_파일_skip(self, tmp_git_repo):
        f = tmp_git_repo / "blob.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        idents = ddr.extract_identifiers_from_changed(
            tmp_git_repo, "working-tree", None, [Path("blob.png")]
        )
        assert idents == set()


# ─── TestFindCallerCandidates ─────────────────────────────────────────────────

class TestFindCallerCandidates:
    """unchanged caller 탐지: git grep + score + size cap."""

    def test_caller_탐지_기본(self, tmp_git_repo):
        changed = tmp_git_repo / "calculator.cs"
        changed.write_text("public class Calculator { }\n", encoding="utf-8")
        caller = tmp_git_repo / "main.cs"
        caller.write_text("var c = new Calculator();\n", encoding="utf-8")
        ddr._git(["add", "main.cs"], cwd=tmp_git_repo)
        ddr._git(["commit", "-q", "-m", "add caller"], cwd=tmp_git_repo)

        result = ddr.find_caller_candidates(
            tmp_git_repo, {"Calculator"}, exclude_paths={"calculator.cs"}
        )
        paths = [p.as_posix() for p, _ in result]
        assert "main.cs" in paths
        body = dict(result)[Path("main.cs")]
        assert "new Calculator()" in body

    def test_빈_식별자_빈리스트(self, tmp_git_repo):
        assert ddr.find_caller_candidates(tmp_git_repo, set(), set()) == []

    def test_exclude_paths_적용(self, tmp_git_repo):
        f = tmp_git_repo / "self.cs"
        f.write_text("public class Calculator { Calculator c; }\n", encoding="utf-8")
        ddr._git(["add", "self.cs"], cwd=tmp_git_repo)
        ddr._git(["commit", "-q", "-m", "self"], cwd=tmp_git_repo)

        result = ddr.find_caller_candidates(
            tmp_git_repo, {"Calculator"}, exclude_paths={"self.cs"}
        )
        assert result == []

    def test_size_cap_max_files(self, tmp_git_repo):
        n = ddr.AUTO_CONTEXT_MAX_FILES + 2
        for i in range(n):
            f = tmp_git_repo / f"caller_{i:02d}.cs"
            f.write_text(f"// file {i}\nvar x = new MyClass();\n", encoding="utf-8")
            ddr._git(["add", f.name], cwd=tmp_git_repo)
        ddr._git(["commit", "-q", "-m", "bulk"], cwd=tmp_git_repo)

        result = ddr.find_caller_candidates(
            tmp_git_repo, {"MyClass"}, exclude_paths=set()
        )
        assert len(result) <= ddr.AUTO_CONTEXT_MAX_FILES


# ─── linked_worktree fixture ──────────────────────────────────────────────────

@pytest.fixture
def linked_worktree(tmp_git_repo, tmp_path):
    """
    tmp_git_repo 기반 linked worktree 생성. fixture teardown 시 자동 정리.

    Yields:
        tuple[Path, Path, str]: (main_repo, linked_path, branch_name)
    """
    import subprocess as sp
    linked = tmp_path / "linked-wt"
    branch = "feat-fixture-linked"
    sp.run(
        ["git", "worktree", "add", "-b", branch, str(linked), "HEAD"],
        cwd=tmp_git_repo, check=True, capture_output=True,
    )
    try:
        yield tmp_git_repo, linked, branch
    finally:
        sp.run(
            ["git", "worktree", "remove", "--force", str(linked)],
            cwd=tmp_git_repo, check=False, capture_output=True,
        )
        sp.run(
            ["git", "branch", "-D", branch],
            cwd=tmp_git_repo, check=False, capture_output=True,
        )


# ─── TestGitInfoDir ───────────────────────────────────────────────────────────

class TestGitInfoDir:
    """linked worktree 호환 .git/info 경로 해석."""

    def test_main_worktree_정상_경로(self, tmp_git_repo):
        info = ddr._git_info_dir(tmp_git_repo)
        assert info.is_dir()
        assert info.name == "info"
        assert (tmp_git_repo / ".git" / "info").resolve() == info.resolve()

    def test_linked_worktree_main_info_공유(self, linked_worktree):
        """linked worktree에서 _git_info_dir이 main repo .git/info 반환."""
        main, linked, _ = linked_worktree
        info_main = ddr._git_info_dir(main)
        info_linked = ddr._git_info_dir(linked)
        assert info_main.resolve() == info_linked.resolve()

    def test_linked_worktree_patch_쓰기_가능(self, linked_worktree):
        """회귀 방지: linked worktree에서도 patch 파일 생성 정상."""
        _, linked, _ = linked_worktree
        info = ddr._git_info_dir(linked)
        test_patch = info / "doc-review-test-write.patch"
        test_patch.write_text("test content", encoding="utf-8")
        try:
            assert test_patch.read_text(encoding="utf-8") == "test content"
        finally:
            test_patch.unlink(missing_ok=True)


# ─── TestWorktreeFlag ─────────────────────────────────────────────────────────

class TestWorktreeFlag:
    """--worktree 플래그 token 해석."""

    def test_절대경로_해석(self, tmp_git_repo):
        resolved = ddr.resolve_worktree(str(tmp_git_repo), cwd=tmp_git_repo)
        assert resolved.resolve() == tmp_git_repo.resolve()

    def test_상대경로_해석(self, tmp_git_repo, tmp_path, monkeypatch):
        """./ 접두 경로도 정상 해석."""
        monkeypatch.chdir(tmp_path)
        # tmp_git_repo는 tmp_path 하위 디렉토리가 아닐 수 있어 절대경로로 테스트
        rel = f"./{tmp_git_repo.name}"
        # tmp_path 안에 심볼릭 링크 또는 경로가 없으면 절대경로 fallback
        target = tmp_path / tmp_git_repo.name
        if not target.exists():
            pytest.skip("relative path test requires same parent dir")
        resolved = ddr.resolve_worktree(rel, cwd=tmp_path)
        assert resolved.resolve() == tmp_git_repo.resolve()

    def test_branch명_해석(self, linked_worktree):
        main, linked, branch = linked_worktree
        resolved = ddr.resolve_worktree(branch, cwd=main)
        assert resolved.resolve() == linked.resolve()

    def test_refs_heads_접두_해석(self, linked_worktree):
        """refs/heads/<branch> 풀네임 입력도 정상."""
        main, linked, branch = linked_worktree
        resolved = ddr.resolve_worktree(f"refs/heads/{branch}", cwd=main)
        assert resolved.resolve() == linked.resolve()

    def test_매칭_실패_에러(self, tmp_git_repo):
        with pytest.raises(ddr.DocReviewError, match="매칭 안 됨"):
            ddr.resolve_worktree("nonexistent-branch-xyz", cwd=tmp_git_repo)

    def test_존재하지_않는_경로_에러(self, tmp_git_repo):
        with pytest.raises(ddr.DocReviewError, match="존재하지 않음"):
            ddr.resolve_worktree("./does-not-exist-dir", cwd=tmp_git_repo)

    def test_git_레포_아닌_경로_에러(self, tmp_path):
        """경로는 존재하나 git 레포 아닌 디렉토리 거부."""
        non_git = tmp_path / "plain-dir"
        non_git.mkdir()
        with pytest.raises(ddr.DocReviewError, match="git 레포 아님"):
            ddr.resolve_worktree(str(non_git), cwd=non_git)


# ─── TestWorktreeMainIntegration ─────────────────────────────────────────────

class TestWorktreeMainIntegration:
    """main() 진입점에서 --worktree / --repo-root mutex 동작."""

    def test_worktree_와_repo_root_동시_지정_에러(
        self, tmp_git_repo, capsys, tmp_path
    ):
        """둘 다 지정하면 명확한 에러 + EXIT_ERR."""
        doc = tmp_path / "spec.md"
        doc.write_text("# spec\n", encoding="utf-8")
        argv = [
            "--docs", str(doc),
            "--worktree", str(tmp_git_repo),
            "--repo-root", str(tmp_git_repo),
            "--dry-run",
        ]
        rc = ddr.main(argv)
        captured = capsys.readouterr()
        assert rc == ddr.EXIT_ERR
        assert "동시 지정 불가" in captured.err

    def test_worktree_해석_실패_exit_6(
        self, tmp_git_repo, capsys, tmp_path, monkeypatch
    ):
        """잘못된 worktree 토큰 → EXIT_WORKTREE(6)."""
        monkeypatch.chdir(tmp_git_repo)
        doc = tmp_path / "spec.md"
        doc.write_text("# spec\n", encoding="utf-8")
        argv = [
            "--docs", str(doc),
            "--worktree", "nonexistent-branch-xyz",
            "--dry-run",
        ]
        rc = ddr.main(argv)
        captured = capsys.readouterr()
        assert rc == ddr.EXIT_WORKTREE
        assert "매칭 안 됨" in captured.err
