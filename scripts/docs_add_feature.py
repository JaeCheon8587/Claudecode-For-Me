"""docs-add-feature v1 — generic preview-only feature documentation generator.

Adds 1 new FRD + 1 FC `## 추가 기능` row deterministically to a preview-dir for a
service registered in `.claude/docs-harness.config.json`. Self-validates via
`docs_check.run_checks`. The source repo is never modified.

Standard library only. Windows PowerShell compatible. No external deps.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Dynamic docs_check load (avoids sys.path pollution)
# ---------------------------------------------------------------------------


def _load_docs_check():
    mod_name = "docs_check"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name, Path(__file__).with_name("docs_check.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot locate docs_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


docs_check = _load_docs_check()
ServiceSpec = docs_check.ServiceSpec
HarnessConfig = docs_check.HarnessConfig
ConfigError = docs_check.ConfigError
load_config = docs_check.load_config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


FEATURE_REQUIRED_KEYS = ("name", "summary", "actor")
FEATURE_OPTIONAL_LIST_KEYS = (
    "preconditions",
    "main_flow",
    "alternative_flow",
    "exception_flow",
    "acceptance_criteria",
    "data_entities",
    "ui_surfaces",
    "api_paths",
    "notes",
)
FEATURE_FORBIDDEN_KEYS = ("service", "id", "project_code")
FEATURE_ALLOWED_KEYS = set(FEATURE_REQUIRED_KEYS) | set(FEATURE_OPTIONAL_LIST_KEYS)

ADD_FEATURE_HEADING_PATTERN = re.compile(r"^##\s+추가\s+기능\s*$", re.MULTILINE)
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|[-:\s|]+\|\s*$")
_WS_RUN = re.compile(r"\s+")

FRD_SECTION_TITLES: tuple[tuple[int, str], ...] = (
    (1, "기능 개요"),
    (2, "사용자 역할"),
    (3, "사전 조건"),
    (4, "기본 흐름"),
    (5, "대안 흐름"),
    (6, "예외 흐름"),
    (7, "상세 기능 요구사항"),
    (8, "입력값"),
    (9, "출력값"),
    (10, "상태 정의"),
    (11, "권한 조건"),
    (12, "데이터 처리 규칙"),
    (13, "로그 / 알림 / 이력 처리"),
    (14, "관련 API"),
    (15, "관련 UI"),
    (16, "관련 설정값"),
    (17, "테스트 기준"),
    (18, "구현 근거"),
    (19, "미확인 사항"),
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureInput:
    name: str
    summary: str
    actor: str
    preconditions: tuple[str, ...] = ()
    main_flow: tuple[str, ...] = ()
    alternative_flow: tuple[str, ...] = ()
    exception_flow: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    data_entities: tuple[str, ...] = ()
    ui_surfaces: tuple[str, ...] = ()
    api_paths: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanItem:
    level: str
    path: Path
    message: str = ""


class ArgsError(ValueError):
    pass


class FeatureError(ValueError):
    pass


class RepoError(ValueError):
    pass


class PreviewDirError(ValueError):
    pass


class PreviewBuildError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------


def _md_inline(value: str) -> str:
    return _WS_RUN.sub(" ", value.replace("\r", " ").replace("\n", " ")).strip()


def _md_table_cell(value: str) -> str:
    s = _md_inline(value).replace("`", "")
    return s.replace("|", "\\|")


def _mask_code_blocks(text: str) -> str:
    parts = text.split("```")
    masked = [parts[0]]
    for i, seg in enumerate(parts[1:], 1):
        masked.append(" " * len(seg) if i % 2 == 1 else seg)
    text2 = "```".join(masked)
    text2 = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group()), text2)
    return text2


# ---------------------------------------------------------------------------
# Feature validation
# ---------------------------------------------------------------------------


def _required_text(d: dict, key: str) -> str:
    if key not in d:
        raise FeatureError(f"missing required field: {key}")
    raw = d[key]
    if not isinstance(raw, str):
        raise FeatureError(f"field must be non-empty string: {key}")
    v = raw.strip()
    if v == "":
        raise FeatureError(f"field must be non-empty string: {key}")
    if "{" in v or "}" in v:
        raise FeatureError(f"field must not contain braces: {key}")
    if "\n" in v or "\r" in v:
        raise FeatureError(f"field must not contain newline: {key}")
    return v


def _validate_text_list(
    d: dict, key: str, *, allow_braces: bool
) -> tuple[str, ...]:
    if key not in d:
        return ()
    raw = d[key]
    if not isinstance(raw, list):
        raise FeatureError(f"field must be list: {key}")
    seen: set[str] = set()
    out: list[str] = []
    for i, item in enumerate(raw):
        path = f"{key}[{i}]"
        if not isinstance(item, str):
            raise FeatureError(f"{path} must be non-empty string")
        v = item.strip()
        if v == "":
            raise FeatureError(f"{path} must be non-empty string")
        if not allow_braces and ("{" in v or "}" in v):
            raise FeatureError(f"{path} must not contain braces")
        if "|" in v:
            raise FeatureError(f"{path} must not contain pipe")
        if "\n" in v or "\r" in v:
            raise FeatureError(f"{path} must not contain newline")
        if "`" in v:
            raise FeatureError(f"{path} must not contain backtick")
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return tuple(out)


def validate_feature(data: object) -> FeatureInput:
    if not isinstance(data, dict):
        raise FeatureError("root must be JSON object")
    unknown = sorted(set(data) - FEATURE_ALLOWED_KEYS - set(FEATURE_FORBIDDEN_KEYS))
    if unknown:
        raise FeatureError("unknown feature key: " + ", ".join(unknown))
    for k in FEATURE_FORBIDDEN_KEYS:
        if k in data:
            raise FeatureError(f"forbidden key in feature JSON: {k}")
    return FeatureInput(
        name=_required_text(data, "name"),
        summary=_required_text(data, "summary"),
        actor=_required_text(data, "actor"),
        preconditions=_validate_text_list(data, "preconditions", allow_braces=False),
        main_flow=_validate_text_list(data, "main_flow", allow_braces=False),
        alternative_flow=_validate_text_list(data, "alternative_flow", allow_braces=False),
        exception_flow=_validate_text_list(data, "exception_flow", allow_braces=False),
        acceptance_criteria=_validate_text_list(data, "acceptance_criteria", allow_braces=False),
        data_entities=_validate_text_list(data, "data_entities", allow_braces=False),
        ui_surfaces=_validate_text_list(data, "ui_surfaces", allow_braces=False),
        api_paths=_validate_text_list(data, "api_paths", allow_braces=True),
        notes=_validate_text_list(data, "notes", allow_braces=False),
    )


def load_feature(path: Path) -> FeatureInput:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise FeatureError("feature file must be UTF-8") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise FeatureError(f"invalid JSON: {e.msg}") from e
    return validate_feature(data)


# ---------------------------------------------------------------------------
# Service / repo / preview-dir validation
# ---------------------------------------------------------------------------


def lookup_service(config: HarnessConfig, name: str) -> ServiceSpec:
    for s in config.services:
        if s.name == name:
            return s
    allowed = ", ".join(s.name for s in config.services)
    raise ArgsError(f"invalid service: {name} (allowed: {allowed})")


def validate_repo(repo: Path, config: HarnessConfig) -> None:
    if not repo.exists():
        raise ArgsError(f"--repo does not exist: {repo}")
    if not repo.is_dir():
        raise ArgsError(f"--repo is not a directory: {repo}")
    for rel in config.repo_required_files:
        if not (repo / rel).is_file():
            raise RepoError(f"missing required path: {rel}")
    for rel in config.repo_required_dirs:
        if not (repo / rel).is_dir():
            raise RepoError(f"missing required path: {rel}")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_preview_dir(
    repo: Path, preview_dir: Path, config: HarnessConfig
) -> Path:
    repo_resolved = repo.resolve()
    preview_resolved = preview_dir.resolve()
    if preview_resolved.is_file():
        raise PreviewDirError(
            f"--preview-dir must be a directory path: {preview_dir}"
        )
    if preview_resolved == repo_resolved or _is_relative_to(
        preview_resolved, repo_resolved
    ):
        raise PreviewDirError(
            f"--preview-dir must be outside --repo: {preview_dir}"
        )
    for rel in config.protected_subpaths:
        try:
            protected = (repo_resolved / rel).resolve()
        except OSError:
            continue
        if preview_resolved == protected:
            raise PreviewDirError(
                f"--preview-dir must not target protected repo path: {preview_dir}"
            )
    if preview_resolved.is_dir() and any(preview_resolved.iterdir()):
        raise PreviewDirError(
            f"--preview-dir must be empty or not exist: {preview_dir}"
        )
    return preview_resolved


def create_preview_dir(preview: Path) -> None:
    try:
        preview.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PreviewBuildError(
            f"cannot create preview dir: {type(e).__name__}: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Preview repo assembly
# ---------------------------------------------------------------------------


def copy_docs_subset(repo: Path, preview: Path, config: HarnessConfig) -> None:
    """Copy minimal source files needed for self-check into preview-dir."""
    try:
        for rel in config.repo_required_files:
            src = repo / rel
            if src.is_file():
                dst = preview / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        config_src = repo / docs_check.CONFIG_PATH
        if config_src.is_file():
            config_dst = preview / docs_check.CONFIG_PATH
            config_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(config_src, config_dst)

        for spec in config.services:
            src_docs = repo / spec.docs_dir
            dst_docs = preview / spec.docs_dir
            if src_docs.is_dir():
                shutil.copytree(src_docs, dst_docs)
            else:
                dst_docs.mkdir(parents=True, exist_ok=True)
            if spec.app_dir:
                (preview / spec.app_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PreviewBuildError(
            f"cannot copy source docs: {type(e).__name__}: {e}"
        ) from e


# ---------------------------------------------------------------------------
# FRD numbering
# ---------------------------------------------------------------------------


_FRD_NUM_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _frd_num_pattern(spec: ServiceSpec) -> re.Pattern[str]:
    if spec.code not in _FRD_NUM_PATTERN_CACHE:
        _FRD_NUM_PATTERN_CACHE[spec.code] = re.compile(
            rf"^FRD-{spec.code}-F(\d{{3}})\.md$"
        )
    return _FRD_NUM_PATTERN_CACHE[spec.code]


def next_frd_number(repo: Path, spec: ServiceSpec) -> int:
    frd_dir = repo / spec.docs_dir / "FRD"
    if not frd_dir.is_dir():
        return 1
    pat = _frd_num_pattern(spec)
    nums: list[int] = []
    for f in frd_dir.glob("*.md"):
        m = pat.match(f.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def format_frd_id(spec: ServiceSpec, n: int) -> str:
    return f"FRD-{spec.code}-F{n:03d}"


def format_feature_id(n: int) -> str:
    return f"F{n:03d}"


# ---------------------------------------------------------------------------
# FRD renderer
# ---------------------------------------------------------------------------


def _frd_section_body(n: int, f: FeatureInput) -> list[str]:
    if n == 1:
        return [_md_inline(f.summary)]
    if n == 2:
        return [f"- {_md_inline(f.actor)}"]
    if n == 3:
        return [f"- {_md_inline(p)}" for p in f.preconditions]
    if n == 4:
        return [f"{i + 1}. {_md_inline(s)}" for i, s in enumerate(f.main_flow)]
    if n == 5:
        return [f"- {_md_inline(s)}" for s in f.alternative_flow]
    if n == 6:
        return [f"- {_md_inline(s)}" for s in f.exception_flow]
    if n == 12:
        return [f"- {_md_inline(s)}" for s in f.data_entities]
    if n == 14:
        return [f"- `{p}`" for p in f.api_paths]
    if n == 15:
        return [f"- {_md_inline(s)}" for s in f.ui_surfaces]
    if n == 17:
        return [f"- {_md_inline(s)}" for s in f.acceptance_criteria]
    if n == 19:
        return [f"- {_md_inline(s)}" for s in f.notes]
    return []


def render_frd(spec: ServiceSpec, fid: str, feature_id: str, f: FeatureInput) -> str:
    fc_link = f"[FC-{spec.code}-001](../FC-{spec.code}-001.md)"
    prd_link = f"[PRD-{spec.code}-001](../PRD-{spec.code}-001.md)"
    lines = [
        f"# {fid} — {_md_inline(f.name)}",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 문서 ID | {fid} |",
        f"| 기능 ID | {feature_id} |",
        f"| 관련 문서 | {fc_link} · {prd_link} |",
        "",
    ]
    for n, title in FRD_SECTION_TITLES:
        lines.append(f"## {n}. {title}")
        lines.append("")
        body = _frd_section_body(n, f)
        lines.extend(body if body else ["없음"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Feature Catalog upsert
# ---------------------------------------------------------------------------


def _fc_row(spec: ServiceSpec, fid: str, feature_id: str, f: FeatureInput) -> str:
    return (
        f"| {feature_id} | {_md_table_cell(f.name)} | {_md_table_cell(f.summary)} | "
        f"[{fid}](FRD/{fid}.md) |"
    )


def _find_line_index(lines: list[str], char_offset: int) -> int:
    n = 0
    for i, ln in enumerate(lines):
        n2 = n + len(ln)
        if n <= char_offset < n2:
            return i
        n = n2
    return len(lines) - 1


def _find_table_in_section(section: list[str]) -> tuple[int | None, int | None]:
    for i in range(len(section) - 1):
        if section[i].lstrip().startswith("|") and TABLE_SEPARATOR_PATTERN.match(
            section[i + 1]
        ):
            j = i + 2
            while j < len(section) and section[j].lstrip().startswith("|"):
                j += 1
            return i, j - 1
    return None, None


def upsert_feature_catalog(
    text: str, spec: ServiceSpec, fid: str, feature_id: str, f: FeatureInput
) -> str:
    new_row = _fc_row(spec, fid, feature_id, f)
    masked = _mask_code_blocks(text)
    m = ADD_FEATURE_HEADING_PATTERN.search(masked)

    if m is None:
        sep = "" if text.endswith("\n") else "\n"
        appendix = (
            f"{sep}\n## 추가 기능\n\n"
            "| 기능 ID | 기능명 | 요약 | FRD |\n"
            "|---|---|---|---|\n"
            f"{new_row}\n"
        )
        return text + appendix

    lines = text.splitlines(keepends=True)
    masked_lines = masked.splitlines(keepends=True)
    heading_line_idx = _find_line_index(masked_lines, m.start())

    end_idx = len(lines)
    for j in range(heading_line_idx + 1, len(masked_lines)):
        if masked_lines[j].startswith("## "):
            end_idx = j
            break

    section = lines[heading_line_idx + 1 : end_idx]
    table_start, table_end = _find_table_in_section(section)

    if table_start is None:
        insert = (
            "\n| 기능 ID | 기능명 | 요약 | FRD |\n"
            "|---|---|---|---|\n"
            f"{new_row}\n"
        )
        return "".join(lines[:end_idx]) + insert + "".join(lines[end_idx:])

    abs_table_end = heading_line_idx + 1 + table_end
    last_line = lines[abs_table_end]
    suffix = "" if last_line.endswith("\n") else "\n"
    return (
        "".join(lines[: abs_table_end + 1])
        + suffix
        + new_row
        + "\n"
        + "".join(lines[abs_table_end + 1 :])
    )


# ---------------------------------------------------------------------------
# Conflict detection + build preview
# ---------------------------------------------------------------------------


def detect_conflicts(
    repo: Path, spec: ServiceSpec, fid: str
) -> list[PlanItem]:
    items: list[PlanItem] = []
    frd_rel = Path(spec.docs_dir) / "FRD" / f"{fid}.md"
    if (repo / frd_rel).is_file():
        items.append(PlanItem("CONFLICT", frd_rel, "already exists"))
    fc_rel = Path(spec.docs_dir) / f"FC-{spec.code}-001.md"
    src_fc = repo / fc_rel
    if src_fc.is_file():
        try:
            text = src_fc.read_text(encoding="utf-8")
        except OSError:
            return items
        if fid in _mask_code_blocks(text):
            items.append(PlanItem("CONFLICT", fc_rel, f"already references {fid}"))
    return items


def build_preview(
    repo: Path,
    preview: Path,
    spec: ServiceSpec,
    feature: FeatureInput,
) -> tuple[list[PlanItem], str]:
    n = next_frd_number(repo, spec)
    fid = format_frd_id(spec, n)
    feature_id = format_feature_id(n)

    plan: list[PlanItem] = list(detect_conflicts(repo, spec, fid))

    try:
        frd_rel = Path(spec.docs_dir) / "FRD" / f"{fid}.md"
        frd_path = preview / frd_rel
        frd_path.parent.mkdir(parents=True, exist_ok=True)
        frd_path.write_text(
            render_frd(spec, fid, feature_id, feature), encoding="utf-8"
        )
        plan.append(PlanItem("CREATE", frd_rel, ""))

        fc_rel = Path(spec.docs_dir) / f"FC-{spec.code}-001.md"
        fc_path = preview / fc_rel
        existing = (
            fc_path.read_text(encoding="utf-8") if fc_path.is_file() else ""
        )
        new_text = upsert_feature_catalog(existing, spec, fid, feature_id, feature)
        fc_path.parent.mkdir(parents=True, exist_ok=True)
        fc_path.write_text(new_text, encoding="utf-8")
        plan.append(PlanItem("UPDATE", fc_rel, ""))
    except OSError as e:
        raise PreviewBuildError(
            f"cannot write generated docs: {type(e).__name__}: {e}"
        ) from e

    return plan, fid


# ---------------------------------------------------------------------------
# Output + orchestration
# ---------------------------------------------------------------------------


def _emit(preview: Path, plan: list[PlanItem], config: HarnessConfig) -> int:
    print(f"Preview Dir: {preview}")
    for item in plan:
        tail = f" {item.message}" if item.message else ""
        print(f"{item.level} {item.path.as_posix()}{tail}")
    results = docs_check.run_checks(preview, config)
    for r in results:
        print(f"CHECK {docs_check.format_result(r, preview)}")
    p_count = sum(1 for r in results if r.level == "PASS")
    w_count = sum(1 for r in results if r.level == "WARN")
    f_count = sum(1 for r in results if r.level == "FAIL")
    print(f"Summary: {p_count} PASS, {w_count} WARN, {f_count} FAIL")
    c = sum(1 for i in plan if i.level == "CREATE")
    u = sum(1 for i in plan if i.level == "UPDATE")
    x = sum(1 for i in plan if i.level == "CONFLICT")
    print(
        f"Preview Summary: {c} CREATE, {u} UPDATE, {x} CONFLICT, 0 SKIP, "
        f"{f_count} CHECK_FAIL"
    )
    return 1 if (x > 0 or f_count > 0) else 0


def run_preview(
    repo: Path, service_name: str, feature_path: Path, preview_dir: Path
) -> int:
    try:
        config = load_config(repo)
    except ConfigError as e:
        print(f"FAIL CONFIG {e}")
        return 2

    try:
        spec = lookup_service(config, service_name)
    except ArgsError as e:
        print(f"FAIL ARGS {e}")
        return 2

    try:
        validate_repo(repo, config)
    except ArgsError as e:
        print(f"FAIL ARGS {e}")
        return 2
    except RepoError as e:
        print(f"FAIL REPO {e}")
        return 2

    if not feature_path.is_file():
        print(f"FAIL ARGS feature not found: {feature_path}")
        return 2
    try:
        feature = load_feature(feature_path)
    except FeatureError as e:
        print(f"FAIL FEATURE {e}")
        return 2

    try:
        preview = validate_preview_dir(repo, preview_dir, config)
    except PreviewDirError as e:
        print(f"FAIL ARGS {e}")
        return 2

    try:
        create_preview_dir(preview)
        copy_docs_subset(repo, preview, config)
        plan, _fid = build_preview(repo, preview, spec, feature)
        return _emit(preview, plan, config)
    except PreviewBuildError as e:
        print(f"FAIL PREVIEW {e}")
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Add a feature to service-aware docs harness (preview-only)."
    )
    parser.add_argument("--repo", required=True, type=str)
    parser.add_argument("--service", required=True, type=str)
    parser.add_argument("--feature", required=True, type=str)
    parser.add_argument("--preview-dir", required=True, type=str)
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else (e.code or 0)
    return run_preview(
        Path(args.repo),
        args.service,
        Path(args.feature),
        Path(args.preview_dir),
    )


if __name__ == "__main__":
    sys.exit(main())
