"""docs-check v1 — generic service-aware documentation harness validator.

Validates a repo's per-service `<docs_dir>/` tree (PRD, FC, FRD with 19 sections)
driven by `.claude/docs-harness.config.json`. Single-project repos register a
single service in the config.

Standard library only. Windows PowerShell compatible. No external deps.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    code: str
    docs_dir: str
    app_dir: str = ""


@dataclass(frozen=True)
class HarnessConfig:
    services: tuple[ServiceSpec, ...]
    repo_required_files: tuple[str, ...] = ("CLAUDE.md",)
    repo_required_dirs: tuple[str, ...] = ()
    protected_subpaths: tuple[str, ...] = ("Docs", "docs", "Src", "src", ".git", "scripts")
    excluded_docs_dirs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    level: str
    code: str
    message: str
    path: Path | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


CONFIG_PATH = ".claude/docs-harness.config.json"

CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*$")
EXPECTED_SECTIONS = tuple(range(1, 20))  # 1..19
FRD_ID_ROW_PATTERN = re.compile(r"^\|\s*문서\s*ID\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
FRD_SECTION_PATTERN = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)

_CONFIG_ALLOWED_KEYS = frozenset({
    "services",
    "repo_required_files",
    "repo_required_dirs",
    "protected_subpaths",
    "excluded_docs_dirs",
})
_SERVICE_ALLOWED_KEYS = frozenset({"name", "code", "docs_dir", "app_dir"})
_SERVICE_REQUIRED_KEYS = frozenset({"name", "code", "docs_dir"})


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


class ConfigError(ValueError):
    pass


def _validate_rel_path(value: str, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ConfigError(f"{field_name} must be non-empty string")
    if "\\" in value:
        raise ConfigError(f"{field_name} must not contain backslash: {value}")
    if value.startswith("/"):
        raise ConfigError(f"{field_name} must be relative: {value}")
    if re.match(r"^[A-Za-z]:[\\/]", value):
        raise ConfigError(f"{field_name} must be relative: {value}")
    parts = value.split("/")
    if ".." in parts:
        raise ConfigError(f"{field_name} must not contain '..': {value}")
    return value


def _validate_str_list(raw: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ConfigError(f"{field_name} must be array")
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or item == "":
            raise ConfigError(f"{field_name}[{i}] must be non-empty string")
        out.append(item)
    return tuple(out)


def _parse_service(raw: object, index: int) -> ServiceSpec:
    if not isinstance(raw, dict):
        raise ConfigError(f"services[{index}] must be object")
    unknown = sorted(set(raw) - _SERVICE_ALLOWED_KEYS)
    if unknown:
        raise ConfigError(
            f"services[{index}] unknown keys: {', '.join(unknown)}"
        )
    missing = sorted(_SERVICE_REQUIRED_KEYS - set(raw))
    if missing:
        raise ConfigError(
            f"services[{index}] missing required keys: {', '.join(missing)}"
        )
    name = raw["name"]
    if not isinstance(name, str) or name == "":
        raise ConfigError(f"services[{index}].name must be non-empty string")
    code = raw["code"]
    if not isinstance(code, str) or not CODE_PATTERN.match(code):
        raise ConfigError(
            f"services[{index}].code must match {CODE_PATTERN.pattern}: {code!r}"
        )
    docs_dir = _validate_rel_path(raw["docs_dir"], f"services[{index}].docs_dir")
    app_dir_raw = raw.get("app_dir", "")
    if app_dir_raw == "":
        app_dir = ""
    else:
        app_dir = _validate_rel_path(app_dir_raw, f"services[{index}].app_dir")
    return ServiceSpec(name=name, code=code, docs_dir=docs_dir, app_dir=app_dir)


def parse_config(data: object) -> HarnessConfig:
    if not isinstance(data, dict):
        raise ConfigError("config root must be JSON object")
    unknown = sorted(set(data) - _CONFIG_ALLOWED_KEYS)
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(unknown)}")
    if "services" not in data:
        raise ConfigError("services field is required")
    raw_services = data["services"]
    if not isinstance(raw_services, list) or len(raw_services) == 0:
        raise ConfigError("services must be non-empty array")
    services = tuple(_parse_service(s, i) for i, s in enumerate(raw_services))

    names_seen: set[str] = set()
    codes_seen: set[str] = set()
    docs_dirs_seen: set[str] = set()
    for s in services:
        if s.name in names_seen:
            raise ConfigError(f"duplicate service name: {s.name}")
        names_seen.add(s.name)
        if s.code in codes_seen:
            raise ConfigError(f"duplicate service code: {s.code}")
        codes_seen.add(s.code)
        if s.docs_dir in docs_dirs_seen:
            raise ConfigError(f"duplicate docs_dir: {s.docs_dir}")
        docs_dirs_seen.add(s.docs_dir)

    repo_required_files = (
        _validate_str_list(data["repo_required_files"], "repo_required_files")
        if "repo_required_files" in data
        else ("CLAUDE.md",)
    )
    repo_required_dirs = (
        _validate_str_list(data["repo_required_dirs"], "repo_required_dirs")
        if "repo_required_dirs" in data
        else ()
    )
    protected_subpaths = (
        _validate_str_list(data["protected_subpaths"], "protected_subpaths")
        if "protected_subpaths" in data
        else ("Docs", "docs", "Src", "src", ".git", "scripts")
    )
    excluded_docs_dirs = (
        _validate_str_list(data["excluded_docs_dirs"], "excluded_docs_dirs")
        if "excluded_docs_dirs" in data
        else ()
    )

    return HarnessConfig(
        services=services,
        repo_required_files=repo_required_files,
        repo_required_dirs=repo_required_dirs,
        protected_subpaths=protected_subpaths,
        excluded_docs_dirs=excluded_docs_dirs,
    )


def load_config(repo: Path) -> HarnessConfig:
    config_file = repo / CONFIG_PATH
    if not config_file.is_file():
        raise ConfigError(
            f"missing config: {CONFIG_PATH} not found in {repo}. "
            "Create one with services definitions; see "
            "scripts/docs-harness.config.example.json."
        )
    try:
        text = config_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ConfigError(f"{CONFIG_PATH} must be UTF-8") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{CONFIG_PATH} invalid JSON: {e.msg}") from e
    return parse_config(data)


# ---------------------------------------------------------------------------
# Reader util
# ---------------------------------------------------------------------------


class _Reader:
    def __init__(self) -> None:
        self._cache: dict[Path, str | None] = {}
        self._errors: dict[Path, str] = {}

    def read(self, path: Path) -> str | None:
        key = path.resolve()
        if key in self._cache:
            return self._cache[key]
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._cache[key] = None
            return None
        except (IsADirectoryError, UnicodeDecodeError, PermissionError) as e:
            self._cache[key] = None
            self._errors[key] = type(e).__name__
            return None
        text = text.lstrip("﻿").replace("\r\n", "\n")
        self._cache[key] = text
        return text

    def errors(self) -> dict[Path, str]:
        return self._errors


def rel_path(p: Path, repo: Path) -> str:
    try:
        return p.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# FRD patterns
# ---------------------------------------------------------------------------


def frd_filename_pattern(spec: ServiceSpec) -> re.Pattern[str]:
    return re.compile(rf"^FRD-{spec.code}-F\d{{3}}\.md$")


def frd_id_pattern(spec: ServiceSpec) -> re.Pattern[str]:
    return re.compile(rf"FRD-{spec.code}-F\d{{3}}")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_repo_paths(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    del reader
    results: list[CheckResult] = []
    for rel in config.repo_required_files:
        p = repo / rel
        if p.is_file():
            results.append(CheckResult("PASS", "REPO", "exists", p))
        else:
            results.append(CheckResult("FAIL", "REPO", "missing", p))
    for rel in config.repo_required_dirs:
        p = repo / rel
        if p.is_dir():
            results.append(CheckResult("PASS", "REPO", "directory exists", p))
        else:
            results.append(CheckResult("FAIL", "REPO", "missing", p))
    return results


def check_service_paths(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    del reader
    results: list[CheckResult] = []
    for spec in config.services:
        docs_dir = repo / spec.docs_dir
        prd = docs_dir / f"PRD-{spec.code}-001.md"
        fc = docs_dir / f"FC-{spec.code}-001.md"
        frd_dir = docs_dir / "FRD"

        required_dirs = [docs_dir, frd_dir]
        if spec.app_dir:
            required_dirs.append(repo / spec.app_dir)
        for d in required_dirs:
            if d.is_dir():
                results.append(CheckResult("PASS", "SERVICE_PATH", "exists", d))
            else:
                results.append(CheckResult("FAIL", "SERVICE_PATH", "missing", d))
        for f in (prd, fc):
            if f.is_file():
                results.append(CheckResult("PASS", "SERVICE_PATH", "exists", f))
            else:
                results.append(CheckResult("FAIL", "SERVICE_PATH", "missing", f))
    return results


def check_frd_files(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    del reader
    results: list[CheckResult] = []
    for spec in config.services:
        frd_dir = repo / spec.docs_dir / "FRD"
        if not frd_dir.is_dir():
            continue
        pat = frd_filename_pattern(spec)
        for f in sorted(frd_dir.glob("*.md")):
            if pat.match(f.name):
                results.append(CheckResult("PASS", "FRD_FILE", "valid filename", f))
            else:
                results.append(CheckResult("FAIL", "FRD_FILE", "invalid filename", f))
    return results


def _valid_frd_files(repo: Path, spec: ServiceSpec) -> list[Path]:
    frd_dir = repo / spec.docs_dir / "FRD"
    if not frd_dir.is_dir():
        return []
    pat = frd_filename_pattern(spec)
    return [f for f in sorted(frd_dir.glob("*.md")) if pat.match(f.name)]


def check_frd_ids(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in config.services:
        for f in _valid_frd_files(repo, spec):
            text = reader.read(f)
            if text is None:
                continue
            expected = f.stem
            m = FRD_ID_ROW_PATTERN.search(text)
            if m is None:
                results.append(CheckResult("FAIL", "FRD_ID", "document id row missing", f))
                continue
            found = m.group(1).strip()
            if found != expected:
                results.append(
                    CheckResult(
                        "FAIL",
                        "FRD_ID",
                        f"document id mismatch: expected {expected}, found {found}",
                        f,
                    )
                )
            else:
                results.append(CheckResult("PASS", "FRD_ID", "id matches", f))
    return results


def check_frd_sections(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in config.services:
        for f in _valid_frd_files(repo, spec):
            text = reader.read(f)
            if text is None:
                continue
            actual_nums = [int(n) for n in FRD_SECTION_PATTERN.findall(text)]
            actual_set = set(actual_nums)
            missing = [n for n in EXPECTED_SECTIONS if n not in actual_set]
            for n in missing:
                results.append(
                    CheckResult("FAIL", "FRD_SECTION", f"missing section number: {n}", f)
                )
            present_in_order = [n for n in actual_nums if n in set(EXPECTED_SECTIONS)]
            expected_present = [n for n in EXPECTED_SECTIONS if n in actual_set]
            order_ok = present_in_order == expected_present
            if not order_ok:
                results.append(
                    CheckResult("FAIL", "FRD_SECTION", "section order mismatch", f)
                )
            if not missing and order_ok:
                results.append(
                    CheckResult("PASS", "FRD_SECTION", "all 19 sections in order", f)
                )
    return results


def check_fc_frd_links(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in config.services:
        fc = repo / spec.docs_dir / f"FC-{spec.code}-001.md"
        text = reader.read(fc)
        if text is None:
            continue
        valid_frd_ids = [f.stem for f in _valid_frd_files(repo, spec)]
        if not valid_frd_ids:
            continue
        refs = set(frd_id_pattern(spec).findall(text))
        missing = [fid for fid in valid_frd_ids if fid not in refs]
        if missing:
            for fid in missing:
                results.append(
                    CheckResult("FAIL", "FC_FRD_LINK", f"missing reference: {fid}", fc)
                )
        else:
            results.append(
                CheckResult("PASS", "FC_FRD_LINK", "all service FRD references present", fc)
            )
    return results


def check_claude_index(repo: Path, config: HarnessConfig, reader: _Reader) -> list[CheckResult]:
    results: list[CheckResult] = []
    if "CLAUDE.md" not in config.repo_required_files:
        return results
    claude = repo / "CLAUDE.md"
    text = reader.read(claude)
    if text is None:
        return results
    norm = text.replace("\\", "/")
    required: list[str] = []
    for spec in config.services:
        required.append(f"{spec.docs_dir}/PRD-{spec.code}-001.md")
        required.append(f"{spec.docs_dir}/FC-{spec.code}-001.md")
        required.append(f"{spec.docs_dir}/FRD/")
    missing = [p for p in required if p not in norm]
    if missing:
        for p in missing:
            results.append(
                CheckResult("FAIL", "CLAUDE_INDEX", f"missing reference: {p}", claude)
            )
    else:
        results.append(
            CheckResult("PASS", "CLAUDE_INDEX", "all service doc references present", claude)
        )
    return results


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


_CHECKS = (
    check_repo_paths,
    check_service_paths,
    check_frd_files,
    check_frd_ids,
    check_frd_sections,
    check_fc_frd_links,
    check_claude_index,
)


def run_checks(repo: Path, config: HarnessConfig | None = None) -> list[CheckResult]:
    if config is None:
        config = load_config(repo)
    reader = _Reader()
    results: list[CheckResult] = []
    for fn in _CHECKS:
        try:
            results.extend(fn(repo, config, reader))
        except Exception as e:
            code = fn.__name__.replace("check_", "").upper()
            results.append(CheckResult("FAIL", code, f"check raised exception: {e!r}", None))
    for path in sorted(reader.errors().keys()):
        err = reader.errors()[path]
        results.append(CheckResult("FAIL", "READ_TEXT", f"cannot read file: {err}", path))
    return results


def format_result(result: CheckResult, repo: Path) -> str:
    if result.path is not None:
        return f"{result.level} {result.code} {rel_path(result.path, repo)} {result.message}"
    return f"{result.level} {result.code} {result.message}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate service-aware documentation harness."
    )
    parser.add_argument("--repo", required=True, type=str, help="repo root to validate")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else (e.code or 0)
    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"FAIL invalid --repo: {repo} does not exist")
        return 2
    if not repo.is_dir():
        print(f"FAIL invalid --repo: {repo} is not a directory")
        return 2
    try:
        config = load_config(repo)
    except ConfigError as e:
        print(f"FAIL CONFIG {e}")
        return 2
    results = run_checks(repo, config)
    for r in results:
        print(format_result(r, repo))
    p = sum(1 for r in results if r.level == "PASS")
    w = sum(1 for r in results if r.level == "WARN")
    f = sum(1 for r in results if r.level == "FAIL")
    print(f"Summary: {p} PASS, {w} WARN, {f} FAIL")
    return 1 if f > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
