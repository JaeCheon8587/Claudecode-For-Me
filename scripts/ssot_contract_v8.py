"""Pure validation and deterministic rendering contracts for ssot-write v8.

This module deliberately has no runner state transitions or filesystem writes.
It validates model-produced artifacts against packet-bound inputs and compiles
new FRD documents from structured claims.  The runner remains responsible for
dispatch, persistence, staging, gates, approval, and commit.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONTRACT_VERSION = 8

SSOT_TYPES = ("PRD", "FC", "FRD", "ADR", "ADR-CATALOG", "ARCHITECTURE")
AUTHORITY_CHECK_IDS = (
    "AUTH-TASK-GOVERNANCE",
    "AUTH-ADR-STATUS",
    "AUTH-DDD-LAYER",
    "AUTH-DOC-GOVERNANCE",
    "AUTH-SCOPE",
)
CHANGE_CHECK_IDS = (
    "CHANGE-SIX-TYPE-COVERAGE",
    "CHANGE-CLAIM-BINDING",
    "CHANGE-PREVIEW-EXACTNESS",
    "CHANGE-CROSS-DOC",
    "CHANGE-NO-FULL-PROSE",
)
OUTCOME_CHECK_IDS = (
    "OUTCOME-CLAIM-SATISFACTION",
    "OUTCOME-AUTHORITY-PRESERVATION",
    "OUTCOME-CROSS-DOC",
    "OUTCOME-RENDER-BOUNDS",
    "OUTCOME-MECHANICAL-GATES",
)

CLAIM_KINDS = {
    "REQUIREMENT",
    "CONSTRAINT",
    "SCOPE",
    "EXCLUSION",
    "ACCEPTANCE",
    "TEST",
    "OPERATIONAL",
    "AUTHORITY",
}
DISPOSITIONS = {
    "ACTIVE",
    "NOOP",
    "OBSOLETE",
    "MANUAL_REQUIRED",
    "REWRITE_REQUIRED",
    "BLOCKED",
}
MUTATION_OPERATIONS = {
    "REPLACE_EXACT",
    "INSERT_BEFORE_EXACT",
    "INSERT_AFTER_EXACT",
}
CREATE_APPLY_MODE = "RUNNER_CREATE_FROM_CLAIMS"
UPDATE_APPLY_MODE = "RUNNER_PATCH"

FRD_SECTION_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("SEC-001", "feature_summary", "기능 요약"),
    ("SEC-002", "scope", "범위"),
    ("SEC-003", "user_roles", "사용자 역할"),
    ("SEC-004", "preconditions", "사전 조건"),
    ("SEC-005", "basic_flow", "기본 흐름"),
    ("SEC-006", "alternate_flows", "대안 흐름"),
    ("SEC-007", "exception_flows", "예외 흐름"),
    ("SEC-008", "functional_requirements", "상세 기능 요구사항"),
    ("SEC-009", "inputs_outputs", "입출력 개념"),
    ("SEC-010", "states", "상태 정의"),
    ("SEC-011", "permissions", "권한 조건"),
    ("SEC-012", "data_principles", "데이터 처리 원칙"),
    ("SEC-013", "nonfunctional_requirements", "비기능 요구사항"),
    ("SEC-014", "logging_alert_history", "로그 / 알림 / 이력 정책"),
    ("SEC-015", "ui_external_impacts", "UI / 외부 연계 영향"),
    ("SEC-016", "ssot_reflection", "FC / ADR-CATALOG / ADR 반영 여부"),
    ("SEC-017", "acceptance_criteria", "수용 기준"),
    ("SEC-018", "test_perspectives", "테스트 관점"),
    ("SEC-019", "rationale", "요구 근거"),
    ("SEC-020", "open_questions", "미확인 사항"),
)
FRD_SECTION_IDS = tuple(row[0] for row in FRD_SECTION_SLOTS)
FRD_SECTION_SLOT_BY_ID = {row[0]: row[1] for row in FRD_SECTION_SLOTS}
FRD_SECTION_TITLE_BY_ID = {row[0]: row[2] for row in FRD_SECTION_SLOTS}
CANONICAL_FRD_TEMPLATE_PATH = "Docs/.templates/App/FRD/APP-FRD-001-TEMPLATE.md"
OPTIONAL_PROSE_SECTION_IDS = {
    "SEC-001",
    "SEC-002",
    "SEC-003",
    "SEC-004",
    "SEC-005",
    "SEC-006",
    "SEC-007",
    "SEC-008",
    "SEC-009",
    "SEC-010",
    "SEC-012",
    "SEC-013",
    "SEC-014",
    "SEC-015",
    "SEC-019",
    "SEC-020",
}

_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_FEATURE_ID = re.compile(r"^F\d{3,}$")
_DOCUMENT_ID = re.compile(r"^[A-Za-z][A-Za-z0-9]*-FRD-\d{3,}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MARKDOWN_HEADING = re.compile(r"(?m)^#{1,6}\s+\S")
_TASK_REFERENCE = re.compile(
    r"(?:\[[^\]]*\]\([^)]*/TASK/[^)]*\)|\b[A-Z][A-Z0-9]*-TASK-\d{3}\b)",
    re.IGNORECASE,
)
_NUMBERED_FRD_HEADING = re.compile(r"(?m)^##\s+(\d+)\.\s+(.+?)\s*$")
_RENDER_GUARDED_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"\d+(?:[._:/-]\d+)*[A-Za-z]*"
    r"|[A-Za-z]*\d+[A-Za-z0-9_.:/-]*"
    r"|[A-Za-z][A-Za-z0-9]*(?:[_.:/-][A-Za-z0-9]+)+"
    r"|[A-Z]{2,}"
    r"|[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+"
    r")(?![A-Za-z0-9_])"
)


class ContractV8Error(RuntimeError):
    """A stable, machine-routable Contract v8 validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _error(code: str, message: str) -> None:
    raise ContractV8Error(code, message)


def _require_exact_fields(value: Any, fields: set[str], code: str, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _error(code, f"{label} must be an object")
    actual = set(value)
    if actual != fields:
        _error(code, f"{label} fields mismatch: {sorted(actual ^ fields)}")
    return value


def _require_nonempty_string(value: Any, code: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(code, f"{label} must be a non-empty string")
    return value


def _require_string_list(
    value: Any,
    code: str,
    label: str,
    *,
    nonempty: bool = False,
    unique: bool = True,
) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        _error(code, f"{label} must be {'a non-empty' if nonempty else 'a'} string list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        _error(code, f"{label} contains an invalid string")
    if unique and len(set(value)) != len(value):
        _error(code, f"{label} contains duplicates")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractV8Error("EVIDENCE_INPUT_MISSING", f"Cannot read bound input: {path}: {exc}") from exc


def _normal_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").casefold()


def _hash_value(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping) and isinstance(raw.get("sha256"), str):
        return str(raw["sha256"])
    _error("EVIDENCE_INPUT_HASH", "input_hashes values must be SHA-256 strings or objects with sha256")
    raise AssertionError


def _bound_path_candidates(
    evidence_path: str,
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
) -> list[tuple[str, Path, str]]:
    if "\x00" in evidence_path or any(part == ".." for part in Path(evidence_path).parts):
        _error("EVIDENCE_PATH_UNBOUND", f"Evidence path is unsafe: {evidence_path}")
    wanted = _normal_path(evidence_path)
    rooted: str | None = None
    path_value = Path(evidence_path)
    if repo_root is not None and not path_value.is_absolute():
        rooted = _normal_path(str((Path(repo_root).resolve() / path_value).resolve()))
    matches: list[tuple[str, Path, str]] = []
    for key, raw_hash in input_hashes.items():
        if not isinstance(key, str) or not key:
            _error("EVIDENCE_INPUT_HASH", "input_hashes keys must be non-empty paths")
        key_norm = _normal_path(key)
        boundary_suffix = key_norm == wanted or key_norm.endswith("/" + wanted)
        if key_norm == wanted or (rooted is not None and key_norm == rooted) or boundary_suffix:
            bound_path = Path(key)
            if not bound_path.is_absolute() and repo_root is not None:
                bound_path = Path(repo_root).resolve() / bound_path
            matches.append((key, bound_path, _hash_value(raw_hash)))
    return matches


def validate_evidence(
    evidence: Mapping[str, Any],
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate one `{path,line,quote}` citation against packet-bound bytes.

    `path` may be the bound absolute key, a repo-relative path, or an
    unambiguous process-relative suffix.  The bound SHA-256 is rechecked before
    line lookup, preventing a citation from surviving input mutation.
    """

    row = _require_exact_fields(
        evidence,
        {"path", "line", "quote"},
        "EVIDENCE_SCHEMA",
        "evidence",
    )
    path_value = _require_nonempty_string(row["path"], "EVIDENCE_SCHEMA", "evidence.path")
    line = row["line"]
    if isinstance(line, bool) or not isinstance(line, int) or line < 1:
        _error("EVIDENCE_LINE", "evidence.line must be a positive 1-based integer")
    quote = _require_nonempty_string(row["quote"], "EVIDENCE_SCHEMA", "evidence.quote")
    if "\n" in quote or "\r" in quote:
        _error("EVIDENCE_QUOTE_MISMATCH", "evidence.quote must be a substring of one line")
    if sum(character.isalnum() for character in quote) < 4:
        _error(
            "EVIDENCE_QUOTE_TOO_WEAK",
            "evidence.quote must contain at least four alphanumeric or Hangul characters",
        )
    matches = _bound_path_candidates(path_value, input_hashes, repo_root)
    if not matches:
        _error("EVIDENCE_PATH_UNBOUND", f"Evidence path is not dispatch-bound: {path_value}")
    if len(matches) != 1:
        _error("EVIDENCE_PATH_AMBIGUOUS", f"Evidence path matches multiple bound inputs: {path_value}")
    bound_key, bound_path, expected_hash = matches[0]
    if not _HEX_SHA256.fullmatch(expected_hash):
        _error("EVIDENCE_INPUT_HASH", f"Invalid bound SHA-256 for {bound_key}")
    actual_hash = _sha256(bound_path)
    if actual_hash.casefold() != expected_hash.casefold():
        _error("EVIDENCE_INPUT_CHANGED", f"Bound input changed after dispatch: {bound_key}")
    try:
        lines = bound_path.read_bytes().decode("utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractV8Error("EVIDENCE_INPUT_ENCODING", f"Bound input is not UTF-8: {bound_key}: {exc}") from exc
    if line > len(lines):
        _error("EVIDENCE_LINE", f"Evidence line {line} exceeds {len(lines)} lines: {bound_key}")
    if quote not in lines[line - 1]:
        _error("EVIDENCE_QUOTE_MISMATCH", f"Evidence quote does not match {bound_key}:{line}")
    return {"path": path_value, "line": line, "quote": quote}


def _resolved_evidence_path(
    evidence: Mapping[str, Any],
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
) -> Path:
    """Return the unique bound file backing an already validated citation."""

    path_value = str(evidence["path"])
    matches = _bound_path_candidates(path_value, input_hashes, repo_root)
    if not matches:
        _error("EVIDENCE_PATH_UNBOUND", f"Evidence path is not dispatch-bound: {path_value}")
    if len(matches) != 1:
        _error("EVIDENCE_PATH_AMBIGUOUS", f"Evidence path matches multiple bound inputs: {path_value}")
    return matches[0][1].resolve()


def _same_bound_path(left: Path, right: Any, repo_root: str | Path | None) -> bool:
    if not isinstance(right, (str, Path)) or not str(right):
        return False
    candidate = Path(right)
    if not candidate.is_absolute() and repo_root is not None:
        candidate = Path(repo_root).resolve() / candidate
    try:
        return left.resolve() == candidate.resolve()
    except OSError:
        return False


def _is_task_source(path: Path) -> bool:
    normalized = path.as_posix().upper()
    return "/TASK/" in normalized or bool(re.fullmatch(r"[A-Z][A-Z0-9]*-TASK-\d{3,}\.MD", path.name.upper()))


def _is_governance_source(path: Path) -> bool:
    normalized = path.as_posix().casefold()
    name = path.name.casefold()
    return (
        name in {
            "governance.json",
            "document_guide.md",
            "ddd_architecture_rules.md",
            "object_oriented_design_rules.md",
            "logging_rules.md",
            "claude.md",
            "agents.md",
        }
        or "/.claude/" in normalized
        or "/.codex/" in normalized
    )


def _is_adr_source(path: Path) -> bool:
    name = path.name.upper()
    return bool(
        re.fullmatch(r"[A-Z][A-Z0-9]*-ADR-\d{3,}\.MD", name)
        or re.fullmatch(r"[A-Z][A-Z0-9]*-ADR-CATALOG\.MD", name)
    )


def _source_presence(
    evidence_paths: Sequence[Path],
    predicate: Any,
) -> bool:
    return any(predicate(path) for path in evidence_paths)


def _require_check_sources(
    check_id: str,
    evidence_paths: Sequence[Path],
    requirements: Sequence[tuple[str, Any]],
) -> None:
    missing = [label for label, predicate in requirements if not _source_presence(evidence_paths, predicate)]
    if missing:
        _error(
            "CERTIFICATE_EVIDENCE_SOURCE",
            f"{check_id} lacks required evidence source(s): {', '.join(missing)}",
        )


def _require_quote_token_coverage(
    check_id: str,
    check: Mapping[str, Any],
    tokens: Iterable[str],
    label: str,
    *,
    source_path: Any = None,
    input_hashes: Mapping[str, Any] | None = None,
    repo_root: str | Path | None = None,
) -> None:
    evidence_rows = list(check.get("evidence", []))
    if source_path is not None:
        if input_hashes is None:
            _error("CERTIFICATE_DISPATCH", "Token coverage source validation requires input hashes")
        evidence_rows = [
            evidence
            for evidence in evidence_rows
            if _same_bound_path(
                _resolved_evidence_path(evidence, input_hashes, repo_root),
                source_path,
                repo_root,
            )
        ]
    quotes = [str(evidence.get("quote", "")) for evidence in evidence_rows]
    missing = [token for token in tokens if not any(token in quote for quote in quotes)]
    if missing:
        _error(
            "CERTIFICATE_EVIDENCE_COVERAGE",
            f"{check_id} does not cite every {label}: {missing}",
        )


def _require_evidence_path_coverage(
    check_id: str,
    check: Mapping[str, Any],
    required_paths: Iterable[str],
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
) -> None:
    cited = [
        _resolved_evidence_path(evidence, input_hashes, repo_root)
        for evidence in check.get("evidence", [])
    ]
    missing = [
        path
        for path in required_paths
        if not any(_same_bound_path(cited_path, path, repo_root) for cited_path in cited)
    ]
    if missing:
        _error(
            "CERTIFICATE_EVIDENCE_COVERAGE",
            f"{check_id} does not cite every changed path: {missing}",
        )


def _validate_certificate_evidence_sources(
    kind: str,
    checks: Mapping[str, Mapping[str, Any]],
    dispatch: Mapping[str, Any],
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
) -> None:
    """Enforce semantic source classes for each mandatory certificate check."""

    cited: dict[str, list[Path]] = {
        check_id: [
            _resolved_evidence_path(evidence, input_hashes, repo_root)
            for evidence in check["evidence"]
        ]
        for check_id, check in checks.items()
    }

    def dispatch_path(field: str) -> Any:
        return dispatch.get(field)

    def exact(field: str) -> Any:
        return lambda path: _same_bound_path(path, dispatch_path(field), repo_root)

    if kind == "authority":
        _require_check_sources(
            "AUTH-TASK-GOVERNANCE",
            cited["AUTH-TASK-GOVERNANCE"],
            (("TASK", _is_task_source), ("governance", _is_governance_source)),
        )
        bound_paths = [
            (Path(path) if Path(path).is_absolute() else Path(repo_root or ".").resolve() / path).resolve()
            for path in input_hashes
        ]
        adr_requirements: list[tuple[str, Any]] = [
            (
                "authority.json",
                lambda path: path.name.casefold() == "authority.json",
            )
        ]
        if any(_is_adr_source(path) for path in bound_paths):
            adr_requirements.append(("ADR/ADR-CATALOG", _is_adr_source))
        _require_check_sources("AUTH-ADR-STATUS", cited["AUTH-ADR-STATUS"], adr_requirements)
        _require_evidence_path_coverage(
            "AUTH-ADR-STATUS",
            checks["AUTH-ADR-STATUS"],
            [str(value) for value in dispatch.get("required_adr_paths", [])],
            input_hashes,
            repo_root,
        )
        ddd_bound = any(path.name.casefold() == "ddd_architecture_rules.md" for path in bound_paths)
        if not ddd_bound and checks["AUTH-DDD-LAYER"]["verdict"] != "BLOCKED":
            _error(
                "CERTIFICATE_EVIDENCE_SOURCE",
                "AUTH-DDD-LAYER cannot PASS/FAIL without a bound DDD_ARCHITECTURE_RULES source",
            )
        _require_check_sources(
            "AUTH-DDD-LAYER",
            cited["AUTH-DDD-LAYER"],
            (
                ("TASK", _is_task_source),
                (
                    "DDD_ARCHITECTURE_RULES" if ddd_bound else "governance manifest",
                    (lambda path: path.name.casefold() == "ddd_architecture_rules.md")
                    if ddd_bound else (lambda path: path.name.casefold() == "governance.json"),
                ),
            ),
        )
        _require_check_sources(
            "AUTH-DOC-GOVERNANCE",
            cited["AUTH-DOC-GOVERNANCE"],
            (
                (
                    "DOCUMENT_GUIDE/governance",
                    lambda path: path.name.casefold() in {"document_guide.md", "governance.json"},
                ),
            ),
        )
        scope_requirements: list[tuple[str, Any]] = [("TASK", _is_task_source)]
        if dispatch.get("decision_has_answers"):
            scope_requirements.append(("user decision", exact("decision")))
        _require_check_sources("AUTH-SCOPE", cited["AUTH-SCOPE"], scope_requirements)
        return

    if kind == "change":
        requirements = {
            "CHANGE-SIX-TYPE-COVERAGE": (("proposal", exact("proposal")),),
            "CHANGE-CLAIM-BINDING": (
                ("proposal", exact("proposal")),
                ("authority certificate", exact("authority_certificate")),
            ),
            "CHANGE-PREVIEW-EXACTNESS": (
                ("compiled contract", exact("compiled_contract")),
                ("operation receipts", exact("operation_receipts")),
            ),
            "CHANGE-CROSS-DOC": (
                ("proposal", exact("proposal")),
                ("compiled contract", exact("compiled_contract")),
            ),
            "CHANGE-NO-FULL-PROSE": (
                ("proposal", exact("proposal")),
                ("compiled contract", exact("compiled_contract")),
            ),
        }
        for check_id, needed in requirements.items():
            _require_check_sources(check_id, cited[check_id], needed)
        _require_quote_token_coverage(
            "CHANGE-CLAIM-BINDING",
            checks["CHANGE-CLAIM-BINDING"],
            [str(value) for value in dispatch.get("required_action_ids", [])],
            "action_id",
            source_path=dispatch.get("proposal"),
            input_hashes=input_hashes,
            repo_root=repo_root,
        )
        _require_quote_token_coverage(
            "CHANGE-PREVIEW-EXACTNESS",
            checks["CHANGE-PREVIEW-EXACTNESS"],
            [
                str(value)
                for value in (
                    *dispatch.get("required_action_paths", []),
                    *dispatch.get("required_receipt_ids", []),
                )
            ],
            "action path/receipt",
            source_path=dispatch.get("operation_receipts"),
            input_hashes=input_hashes,
            repo_root=repo_root,
        )
        return

    if kind == "outcome":
        staged_values = dispatch.get("staged_paths", [])
        if not isinstance(staged_values, list):
            staged_values = []

        def staged(path: Path) -> bool:
            if any(_same_bound_path(path, value, repo_root) for value in staged_values):
                return True
            normalized = path.as_posix().casefold()
            return "/staging/" in normalized and path.suffix.casefold() == ".md"

        for check_id in (
            "OUTCOME-CLAIM-SATISFACTION",
            "OUTCOME-AUTHORITY-PRESERVATION",
            "OUTCOME-CROSS-DOC",
        ):
            _require_check_sources(
                check_id,
                cited[check_id],
                (("approved contract", exact("approved_contract")), ("staged changed file", staged)),
            )
        _require_check_sources(
            "OUTCOME-RENDER-BOUNDS",
            cited["OUTCOME-RENDER-BOUNDS"],
            (
                ("approved contract", exact("approved_contract")),
                ("staged changed file", staged),
                ("render receipt", exact("render_receipt")),
            ),
        )
        _require_check_sources(
            "OUTCOME-MECHANICAL-GATES",
            cited["OUTCOME-MECHANICAL-GATES"],
            (("checks summary", exact("checks")),),
        )
        _require_evidence_path_coverage(
            "OUTCOME-CROSS-DOC",
            checks["OUTCOME-CROSS-DOC"],
            [str(value) for value in staged_values],
            input_hashes,
            repo_root,
        )
        return

    _error("CERTIFICATE_KIND", f"Unknown certificate evidence-source kind: {kind}")


def _validate_evidence_list(
    value: Any,
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
    *,
    code: str = "CERTIFICATE_EVIDENCE_REQUIRED",
    label: str = "evidence",
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _error(code, f"{label} must contain at least one exact citation")
    return [validate_evidence(item, input_hashes, repo_root) for item in value]


def _validate_check_rows(
    rows: Any,
    mandatory_ids: Sequence[str],
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(rows, list):
        _error("CERTIFICATE_SCHEMA", "checks must be a list")
    ids = [row.get("check_id") if isinstance(row, Mapping) else None for row in rows]
    if ids != list(mandatory_ids):
        _error(
            "CERTIFICATE_CHECK_COVERAGE",
            f"checks must contain mandatory IDs exactly once and in order: {list(mandatory_ids)}",
        )
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        checked = _require_exact_fields(
            row,
            {"check_id", "verdict", "finding", "evidence"},
            "CERTIFICATE_CHECK_SCHEMA",
            f"check {row.get('check_id') if isinstance(row, Mapping) else '?'}",
        )
        if checked["verdict"] not in {"PASS", "FAIL", "BLOCKED"}:
            _error("CERTIFICATE_CHECK_SCHEMA", f"Invalid verdict for {checked['check_id']}")
        _require_nonempty_string(checked["finding"], "CERTIFICATE_CHECK_SCHEMA", "check.finding")
        _validate_evidence_list(checked["evidence"], input_hashes, repo_root)
        result[str(checked["check_id"])] = checked
    return result


def _validate_question(
    question: Any,
    input_hashes: Mapping[str, Any],
    repo_root: str | Path | None,
    *,
    allow_null: bool,
) -> Mapping[str, Any] | None:
    if question is None and allow_null:
        return None
    row = _require_exact_fields(
        question,
        {"question_id", "question", "evidence"},
        "CERTIFICATE_QUESTION_SCHEMA",
        "question",
    )
    _require_nonempty_string(row["question_id"], "CERTIFICATE_QUESTION_SCHEMA", "question_id")
    _require_nonempty_string(row["question"], "CERTIFICATE_QUESTION_SCHEMA", "question")
    _validate_evidence_list(row["evidence"], input_hashes, repo_root)
    return row


def _enforce_overall_verdict(
    overall: str,
    checks: Mapping[str, Mapping[str, Any]],
    *,
    pass_token: str,
    fail_token: str,
    has_defects: bool,
    question_present: bool,
) -> None:
    states = [str(row["verdict"]) for row in checks.values()]
    if overall == pass_token:
        if any(state != "PASS" for state in states) or has_defects or question_present:
            _error("CERTIFICATE_VERDICT_CONTRADICTION", f"{pass_token} requires all checks PASS and no defects/question")
    elif overall == fail_token:
        if "FAIL" not in states or not has_defects or question_present:
            _error("CERTIFICATE_VERDICT_CONTRADICTION", f"{fail_token} requires a failed check and defects")
    elif overall == "BLOCKED":
        if "FAIL" in states or "BLOCKED" not in states or has_defects or not question_present:
            _error("CERTIFICATE_VERDICT_CONTRADICTION", "BLOCKED requires a blocked check, no failed check/defects, and one question")
    else:
        _error("CERTIFICATE_VERDICT", f"Invalid overall verdict: {overall}")


def validate_authority_certificate(
    certificate: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    hard_checks: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate an Authority Critic certificate and detector consistency."""

    value = copy.deepcopy(certificate)
    row = _require_exact_fields(
        value,
        {
            "contract_version",
            "certificate_id",
            "input_digest",
            "verdict",
            "checks",
            "authority_facts",
            "prohibitions",
            "questions",
        },
        "CERTIFICATE_SCHEMA",
        "authority certificate",
    )
    if row["contract_version"] != CONTRACT_VERSION:
        _error("CERTIFICATE_IDENTITY", "Authority certificate contract_version mismatch")
    if row["certificate_id"] != dispatch.get("dispatch_id") or row["input_digest"] != dispatch.get("input_digest"):
        _error("CERTIFICATE_IDENTITY", "Authority certificate identity/digest mismatch")
    input_hashes = dispatch.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        _error("CERTIFICATE_DISPATCH", "Dispatch input_hashes are missing")
    root = repo_root if repo_root is not None else dispatch.get("repo_root")
    checks = _validate_check_rows(row["checks"], AUTHORITY_CHECK_IDS, input_hashes, root)
    _validate_certificate_evidence_sources("authority", checks, dispatch, input_hashes, root)
    if not isinstance(row["authority_facts"], list) or not isinstance(row["prohibitions"], list):
        _error("CERTIFICATE_SCHEMA", "authority_facts and prohibitions must be lists")
    passing = {check_id for check_id, check in checks.items() if check["verdict"] == "PASS"}
    seen_ids: set[str] = set()
    decision_bound_authority = False
    for kind, rows, id_field in (
        ("authority fact", row["authority_facts"], "authority_id"),
        ("prohibition", row["prohibitions"], "prohibition_id"),
    ):
        for item in rows:
            fact = _require_exact_fields(
                item,
                {id_field, "statement", "check_ids", "evidence"},
                "CERTIFICATE_AUTHORITY_SCHEMA",
                kind,
            )
            identity = _require_nonempty_string(fact[id_field], "CERTIFICATE_AUTHORITY_SCHEMA", id_field)
            if identity in seen_ids:
                _error("CERTIFICATE_AUTHORITY_SCHEMA", f"Duplicate authority/prohibition ID: {identity}")
            seen_ids.add(identity)
            _require_nonempty_string(fact["statement"], "CERTIFICATE_AUTHORITY_SCHEMA", "statement")
            check_ids = _require_string_list(
                fact["check_ids"], "CERTIFICATE_AUTHORITY_SCHEMA", "check_ids", nonempty=True
            )
            if not set(check_ids).issubset(passing):
                _error("CERTIFICATE_AUTHORITY_SCHEMA", f"{identity} is not established by passing checks")
            fact_evidence = _validate_evidence_list(fact["evidence"], input_hashes, root)
            if dispatch.get("decision_has_answers"):
                decision_bound_authority = decision_bound_authority or any(
                    _same_bound_path(
                        _resolved_evidence_path(evidence, input_hashes, root),
                        dispatch.get("decision"),
                        root,
                    )
                    for evidence in fact_evidence
                )
    if not isinstance(row["questions"], list):
        _error("CERTIFICATE_QUESTION_SCHEMA", "questions must be a list")
    questions = row["questions"]
    for question in questions:
        _validate_question(question, input_hashes, root, allow_null=False)
    overall = row["verdict"]
    states = [str(check["verdict"]) for check in checks.values()]
    if overall == "PASS":
        if any(state != "PASS" for state in states) or questions:
            _error("CERTIFICATE_VERDICT_CONTRADICTION", "Authority PASS requires all checks PASS and no questions")
    elif overall == "FAIL":
        if "FAIL" not in states or questions:
            _error("CERTIFICATE_VERDICT_CONTRADICTION", "Authority FAIL requires a failed check and no questions")
    elif overall == "BLOCKED":
        if "FAIL" in states or "BLOCKED" not in states or len(questions) != 1:
            _error("CERTIFICATE_VERDICT_CONTRADICTION", "Authority BLOCKED requires one question and no failed check")
    else:
        _error("CERTIFICATE_VERDICT", f"Invalid Authority verdict: {overall}")
    if (
        dispatch.get("decision_has_answers")
        and overall in {"PASS", "FAIL"}
        and not decision_bound_authority
    ):
        _error(
            "CERTIFICATE_DECISION_BINDING",
            "A resolved user answer must be bound into an authority fact or prohibition",
        )

    failures: Sequence[Any]
    if hard_checks is None:
        failures = ()
    elif isinstance(hard_checks, Mapping):
        raw = hard_checks.get("failures", [])
        if not isinstance(raw, list):
            _error("HARD_GATE_SCHEMA", "hard_checks.failures must be a list")
        failures = raw
    elif isinstance(hard_checks, Sequence) and not isinstance(hard_checks, (str, bytes)):
        failures = hard_checks
    else:
        _error("HARD_GATE_SCHEMA", "hard_checks must be a detector object or sequence")
    for failure in failures:
        if not isinstance(failure, Mapping) or failure.get("check_id") not in AUTHORITY_CHECK_IDS:
            _error("HARD_GATE_SCHEMA", "Every hard detector failure needs a mandatory authority check_id")
        check_id = str(failure["check_id"])
        if checks[check_id]["verdict"] != "FAIL" or overall != "FAIL":
            _error(
                "CERTIFICATE_CONTRADICTS_HARD_GATE",
                f"Authority certificate contradicts hard detector failure: {check_id}: {failure.get('code', 'unknown')}",
            )
    return value


def authority_terminal_disposition(certificate: Mapping[str, Any]) -> str | None:
    """Map a validated authority verdict to its only legal terminal route."""

    verdict = certificate.get("verdict")
    if verdict == "PASS":
        return None
    if verdict == "FAIL":
        return "REWRITE_REQUIRED"
    if verdict == "BLOCKED":
        return "BLOCKED"
    _error("CERTIFICATE_VERDICT", f"Invalid Authority verdict: {verdict}")
    raise AssertionError


def _validate_defects(
    defects: Any,
    checks: Mapping[str, Mapping[str, Any]],
    input_hashes: Mapping[str, Any],
    root: str | Path | None,
    *,
    outcome: bool,
) -> list[Mapping[str, Any]]:
    if not isinstance(defects, list):
        _error("CERTIFICATE_DEFECT_SCHEMA", "defects must be a list")
    seen: set[str] = set()
    covered_failed: set[str] = set()
    fields = (
        {"defect_id", "check_ids", "class", "affected_paths", "render_ids", "description", "evidence"}
        if outcome
        else {"defect_id", "check_ids", "affected_paths", "description", "evidence"}
    )
    result: list[Mapping[str, Any]] = []
    for item in defects:
        defect = _require_exact_fields(item, fields, "CERTIFICATE_DEFECT_SCHEMA", "defect")
        defect_id = _require_nonempty_string(defect["defect_id"], "CERTIFICATE_DEFECT_SCHEMA", "defect_id")
        if defect_id in seen:
            _error("CERTIFICATE_DEFECT_SCHEMA", f"Duplicate defect_id: {defect_id}")
        seen.add(defect_id)
        check_ids = _require_string_list(
            defect["check_ids"], "CERTIFICATE_DEFECT_SCHEMA", "defect.check_ids", nonempty=True
        )
        if not set(check_ids).issubset(checks):
            _error("CERTIFICATE_DEFECT_SCHEMA", f"Defect {defect_id} references an unknown check")
        if not any(checks[check_id]["verdict"] == "FAIL" for check_id in check_ids):
            _error("CERTIFICATE_DEFECT_SCHEMA", f"Defect {defect_id} is not tied to a failed check")
        covered_failed.update(check_ids)
        _require_string_list(defect["affected_paths"], "CERTIFICATE_DEFECT_SCHEMA", "affected_paths")
        _require_nonempty_string(defect["description"], "CERTIFICATE_DEFECT_SCHEMA", "description")
        _validate_evidence_list(defect["evidence"], input_hashes, root)
        if outcome:
            if defect["class"] not in {"PLAN", "EXECUTION"}:
                _error("CERTIFICATE_DEFECT_SCHEMA", f"Invalid defect class: {defect['class']}")
            _require_string_list(defect["render_ids"], "CERTIFICATE_DEFECT_SCHEMA", "render_ids")
            if defect["class"] == "EXECUTION" and not defect["render_ids"]:
                _error("CERTIFICATE_DEFECT_SCHEMA", "EXECUTION defects require approved render_ids")
            if defect["class"] == "PLAN" and defect["render_ids"]:
                _error("CERTIFICATE_DEFECT_SCHEMA", "PLAN defects cannot be scoped to renderer repair")
        result.append(defect)
    failed = {check_id for check_id, check in checks.items() if check["verdict"] == "FAIL"}
    if not failed.issubset(covered_failed):
        _error("CERTIFICATE_DEFECT_COVERAGE", f"Failed checks lack defects: {sorted(failed - covered_failed)}")
    return result


def validate_change_certificate(
    certificate: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the mandatory pre-staging Change Critic certificate."""

    value = copy.deepcopy(certificate)
    row = _require_exact_fields(
        value,
        {
            "contract_version",
            "critique_id",
            "authority_certificate_sha256",
            "proposal_sha256",
            "preview_sha256",
            "verdict",
            "checks",
            "defects",
            "risk_level",
            "question",
        },
        "CERTIFICATE_SCHEMA",
        "change certificate",
    )
    if row["contract_version"] != CONTRACT_VERSION or row["critique_id"] != dispatch.get("dispatch_id"):
        _error("CERTIFICATE_IDENTITY", "Change certificate identity mismatch")
    for field in ("authority_certificate_sha256", "proposal_sha256", "preview_sha256"):
        expected = dispatch.get(field)
        if expected is not None and row[field] != expected:
            _error("CERTIFICATE_IDENTITY", f"Change certificate {field} mismatch")
    input_hashes = dispatch.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        _error("CERTIFICATE_DISPATCH", "Dispatch input_hashes are missing")
    root = repo_root if repo_root is not None else dispatch.get("repo_root")
    checks = _validate_check_rows(row["checks"], CHANGE_CHECK_IDS, input_hashes, root)
    _validate_certificate_evidence_sources("change", checks, dispatch, input_hashes, root)
    defects = _validate_defects(row["defects"], checks, input_hashes, root, outcome=False)
    if row["risk_level"] not in {"LOW", "MEDIUM", "HIGH"}:
        _error("CERTIFICATE_SCHEMA", "risk_level must be LOW, MEDIUM, or HIGH")
    question = _validate_question(row["question"], input_hashes, root, allow_null=True)
    _enforce_overall_verdict(
        row["verdict"],
        checks,
        pass_token="APPROVE",
        fail_token="REJECT",
        has_defects=bool(defects),
        question_present=question is not None,
    )
    return value


def validate_outcome_certificate(
    certificate: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the mandatory pre-commit Outcome Critic certificate."""

    value = copy.deepcopy(certificate)
    row = _require_exact_fields(
        value,
        {
            "contract_version",
            "review_id",
            "contract_sha256",
            "verdict",
            "failure_class",
            "checks",
            "defects",
            "question",
        },
        "CERTIFICATE_SCHEMA",
        "outcome certificate",
    )
    if row["contract_version"] != CONTRACT_VERSION or row["review_id"] != dispatch.get("dispatch_id"):
        _error("CERTIFICATE_IDENTITY", "Outcome certificate identity mismatch")
    expected_contract = dispatch.get("contract_sha256")
    if expected_contract is not None and row["contract_sha256"] != expected_contract:
        _error("CERTIFICATE_IDENTITY", "Outcome certificate contract_sha256 mismatch")
    input_hashes = dispatch.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        _error("CERTIFICATE_DISPATCH", "Dispatch input_hashes are missing")
    root = repo_root if repo_root is not None else dispatch.get("repo_root")
    checks = _validate_check_rows(row["checks"], OUTCOME_CHECK_IDS, input_hashes, root)
    _validate_certificate_evidence_sources("outcome", checks, dispatch, input_hashes, root)
    defects = _validate_defects(row["defects"], checks, input_hashes, root, outcome=True)
    question = _validate_question(row["question"], input_hashes, root, allow_null=True)
    _enforce_overall_verdict(
        row["verdict"],
        checks,
        pass_token="PASS",
        fail_token="FAIL",
        has_defects=bool(defects),
        question_present=question is not None,
    )
    if row["verdict"] in {"PASS", "BLOCKED"} and row["failure_class"] != "NONE":
        _error("CERTIFICATE_FAILURE_CLASS", f"{row['verdict']} requires failure_class NONE")
    if row["verdict"] == "FAIL":
        classes = {str(defect["class"]) for defect in defects}
        expected = next(iter(classes)) if len(classes) == 1 else "PLAN"
        if row["failure_class"] not in {"PLAN", "EXECUTION"} or row["failure_class"] != expected:
            _error("CERTIFICATE_FAILURE_CLASS", "Outcome failure_class does not match defect routing")
    return value


def validate_certificate(
    kind: str,
    certificate: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    hard_checks: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Dispatch to one of the three certificate validators."""

    if kind == "authority":
        return validate_authority_certificate(
            certificate, dispatch, repo_root=repo_root, hard_checks=hard_checks
        )
    if kind == "change":
        return validate_change_certificate(certificate, dispatch, repo_root=repo_root)
    if kind == "outcome":
        return validate_outcome_certificate(certificate, dispatch, repo_root=repo_root)
    _error("CERTIFICATE_KIND", f"Unknown certificate kind: {kind}")
    raise AssertionError


def _repo_relative(repo_root: Path, value: str, code: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise ContractV8Error(code, f"Path escapes repository: {value}") from exc
    return relative


def _classify_ssot_path(app: str, path: str) -> str | None:
    normalized = path.replace("\\", "/")
    upper = normalized.upper()
    prefix = f"DOCS/{app.upper()}/"
    if not upper.startswith(prefix) or "/TASK/" in upper:
        return None
    name = Path(normalized).name.upper()
    if name == f"{app.upper()}-ADR-CATALOG.MD":
        return "ADR-CATALOG"
    if name == f"{app.upper()}-ARCHITECTURE.MD":
        return "ARCHITECTURE"
    if name == f"{app.upper()}-PRD.MD":
        return "PRD"
    if name == f"{app.upper()}-FC.MD":
        return "FC"
    if re.fullmatch(rf"{re.escape(app.upper())}-FRD-\d{{3,}}\.MD", name) and "/FRD/" in upper:
        return "FRD"
    if re.fullmatch(rf"{re.escape(app.upper())}-ADR-\d{{3,}}\.MD", name) and "/ADR/" in upper:
        return "ADR"
    return None


def _validate_bound_ids(
    values: Any,
    known: set[str],
    code: str,
    label: str,
    *,
    nonempty: bool = True,
) -> list[str]:
    result = _require_string_list(values, code, label, nonempty=nonempty)
    if not set(result).issubset(known):
        _error(code, f"{label} references unknown IDs: {sorted(set(result) - known)}")
    return result


def _looks_like_full_document(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    headings = _MARKDOWN_HEADING.findall(text)
    return len(headings) >= 2 or (len(text) > 12000 and "## " in text)


def _reject_fulltext_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_norm = str(key).casefold().replace("-", "_")
            if key_norm in {"document_body", "full_document", "full_text", "markdown_body", "create_exact"}:
                _error("FRD_FULLTEXT_PROHIBITED", f"Whole-document proposal field is prohibited: {key}")
            if key == "operation" and item == "CREATE_EXACT":
                _error("FRD_FULLTEXT_PROHIBITED", "CREATE_EXACT is prohibited in Contract v8")
            if key == "apply_mode" and item in {"RUNNER_CREATE", "RUNNER_CREATE_WITH_RENDER", "RUNNER_FRD_CLAIM_CREATE"}:
                _error("FRD_FULLTEXT_PROHIBITED", f"Legacy full-document CREATE mode is prohibited: {item}")
            _reject_fulltext_payload(item)
    elif isinstance(value, list):
        for item in value:
            _reject_fulltext_payload(item)


def _certificate_bindings(authority_certificate: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    checks = authority_certificate.get("checks")
    if not isinstance(checks, list):
        _error("PROPOSAL_AUTHORITY", "Validated Authority Certificate is required")
    passing = {
        str(row.get("check_id"))
        for row in checks
        if isinstance(row, Mapping) and row.get("verdict") == "PASS" and row.get("check_id") in AUTHORITY_CHECK_IDS
    }
    if passing != set(AUTHORITY_CHECK_IDS):
        _error("PROPOSAL_AUTHORITY", "ClaimSpec requires a PASS Authority Certificate")
    authority_ids: set[str] = set()
    for key, id_field in (("authority_facts", "authority_id"), ("prohibitions", "prohibition_id")):
        rows = authority_certificate.get(key, [])
        if not isinstance(rows, list):
            _error("PROPOSAL_AUTHORITY", f"Authority Certificate {key} is invalid")
        for row in rows:
            if isinstance(row, Mapping) and isinstance(row.get(id_field), str):
                authority_ids.add(str(row[id_field]))
    return passing, authority_ids


def _validate_canonical_frd_template(repo_root: Path, template_path: str) -> str:
    template_rel = _repo_relative(repo_root, template_path, "CREATION_SPEC_SCHEMA")
    if template_rel.casefold() != CANONICAL_FRD_TEMPLATE_PATH.casefold():
        _error(
            "FRD_TEMPLATE_PATH",
            f"template_path must be the repository canonical template: {CANONICAL_FRD_TEMPLATE_PATH}",
        )
    template_file = repo_root / template_rel
    if not template_file.is_file() or template_file.is_symlink():
        _error("FRD_TEMPLATE_PATH", "Canonical repository FRD template is missing or unsafe")
    try:
        template_text = template_file.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractV8Error(
            "FRD_TEMPLATE_SHAPE",
            f"Canonical repository FRD template is not valid UTF-8: {exc}",
        ) from exc
    expected = [
        (str(index), title)
        for index, (_, _, title) in enumerate(FRD_SECTION_SLOTS, start=1)
    ]
    actual = [(number, title.strip()) for number, title in _NUMBERED_FRD_HEADING.findall(template_text)]
    if actual != expected:
        _error(
            "FRD_TEMPLATE_SHAPE",
            "Canonical repository FRD template must contain exactly the 20 canonical numbered headings in order",
        )
    return template_rel


def _validate_creation_spec(
    spec: Any,
    action: Mapping[str, Any],
    claims: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> str:
    creation = _require_exact_fields(
        spec,
        {"document_id", "feature_id", "title", "template_path", "metadata", "sections"},
        "CREATION_SPEC_SCHEMA",
        "creation_spec",
    )
    document_id = _require_nonempty_string(creation["document_id"], "CREATION_SPEC_SCHEMA", "document_id")
    if not _DOCUMENT_ID.fullmatch(document_id) or Path(str(action["path"])).stem != document_id:
        _error("CREATION_SPEC_SCHEMA", "document_id must match the target FRD filename")
    feature_id = _require_nonempty_string(creation["feature_id"], "CREATION_SPEC_SCHEMA", "feature_id")
    if not _FEATURE_ID.fullmatch(feature_id):
        _error("CREATION_SPEC_SCHEMA", "feature_id must use FNNN form")
    title = _require_nonempty_string(creation["title"], "CREATION_SPEC_SCHEMA", "title")
    if "\n" in title or _MARKDOWN_HEADING.search(title):
        _error("FRD_FULLTEXT_PROHIBITED", "FRD title cannot contain Markdown document prose")
    template_path = _require_nonempty_string(
        creation["template_path"], "CREATION_SPEC_SCHEMA", "template_path"
    )
    normalized_template = _validate_canonical_frd_template(repo_root, template_path)
    metadata = _require_exact_fields(
        creation["metadata"],
        {"version", "status", "date"},
        "CREATION_SPEC_SCHEMA",
        "creation_spec.metadata",
    )
    version = _require_nonempty_string(metadata["version"], "CREATION_SPEC_SCHEMA", "metadata.version")
    status = _require_nonempty_string(metadata["status"], "CREATION_SPEC_SCHEMA", "metadata.status")
    date = _require_nonempty_string(metadata["date"], "CREATION_SPEC_SCHEMA", "metadata.date")
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version):
        _error("CREATION_SPEC_SCHEMA", "metadata.version must be a numeric dotted version")
    if status not in {"Draft", "Ready", "In Progress", "Done", "Dropped"}:
        _error("CREATION_SPEC_SCHEMA", "metadata.status is not an allowed FRD status")
    if not _ISO_DATE.fullmatch(date):
        _error("CREATION_SPEC_SCHEMA", "metadata.date must be YYYY-MM-DD")
    sections = creation["sections"]
    if not isinstance(sections, list) or not 1 <= len(sections) <= len(FRD_SECTION_SLOTS):
        _error("CREATION_SECTION_COVERAGE", "creation_spec must map at least one canonical FRD section")
    section_ids: set[str] = set()
    union_claims: set[str] = set()
    for index, section in enumerate(sections):
        section_row = _require_exact_fields(
            section,
            {"section_id", "template_slot", "claim_ids", "render_mode"},
            "CREATION_SPEC_SCHEMA",
            f"creation_spec.sections[{index}]",
        )
        section_id = section_row["section_id"]
        if section_id not in FRD_SECTION_SLOT_BY_ID or section_id in section_ids:
            _error(
                "CREATION_SECTION_COVERAGE",
                f"Section mapping must use a unique canonical section_id: {section_id}",
            )
        expected_slot = FRD_SECTION_SLOT_BY_ID[section_id]
        if section_row["template_slot"] != expected_slot:
            _error("CREATION_SECTION_COVERAGE", f"{section_id} must map to template_slot {expected_slot}")
        if section_row["render_mode"] != "DETERMINISTIC":
            _error("CREATION_SPEC_SCHEMA", "Every canonical section render_mode must be DETERMINISTIC")
        claim_ids = _validate_bound_ids(
            section_row["claim_ids"], set(claims), "CREATION_CLAIM_BINDING", f"{section_id}.claim_ids", nonempty=False
        )
        section_ids.add(section_id)
        union_claims.update(claim_ids)
        if section_id == "SEC-017" and not any(claims[claim_id]["kind"] == "ACCEPTANCE" for claim_id in claim_ids):
            _error("CREATION_CLAIM_BINDING", "SEC-017 requires at least one ACCEPTANCE claim")
        if section_id == "SEC-018" and not any(claims[claim_id]["kind"] == "TEST" for claim_id in claim_ids):
            _error("CREATION_CLAIM_BINDING", "SEC-018 requires at least one TEST claim")
    action_claim_ids = set(action["claim_ids"])
    if union_claims != action_claim_ids:
        _error(
            "CREATION_CLAIM_BINDING",
            f"FRD action claims and section claims differ: missing={sorted(action_claim_ids - union_claims)}, extra={sorted(union_claims - action_claim_ids)}",
        )
    return normalized_template


def validate_claim_spec(
    proposal: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    authority_certificate: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    app: str | None = None,
) -> dict[str, Any]:
    """Validate the v8 ClaimSpec and normalize repository-relative paths.

    No document prose is compiled here.  Call :func:`render_frd_from_claims`
    after validation for every FRD CREATE action.
    """

    value = copy.deepcopy(proposal)
    _reject_fulltext_payload(value)
    row = _require_exact_fields(
        value,
        {
            "contract_version",
            "proposal_id",
            "authority_certificate_sha256",
            "disposition",
            "claims",
            "actions",
            "skips",
            "relations",
            "risk_flags",
            "questions",
            "unsupported_changes",
        },
        "PROPOSAL_SCHEMA",
        "ClaimSpec",
    )
    if row["contract_version"] != CONTRACT_VERSION or row["proposal_id"] != dispatch.get("dispatch_id"):
        _error("PROPOSAL_IDENTITY", "ClaimSpec identity mismatch")
    expected_authority = dispatch.get("authority_certificate_sha256")
    if expected_authority is not None and row["authority_certificate_sha256"] != expected_authority:
        _error("PROPOSAL_IDENTITY", "ClaimSpec authority_certificate_sha256 mismatch")
    if row["disposition"] not in DISPOSITIONS:
        _error("PROPOSAL_DISPOSITION", f"Invalid disposition: {row['disposition']}")
    for field in ("claims", "actions", "skips", "relations", "risk_flags", "questions", "unsupported_changes"):
        if not isinstance(row[field], list):
            _error("PROPOSAL_SCHEMA", f"ClaimSpec {field} must be a list")
    input_hashes = dispatch.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        _error("PROPOSAL_DISPATCH", "Dispatch input_hashes are missing")
    root_value = repo_root if repo_root is not None else dispatch.get("repo_root")
    if root_value is None:
        _error("PROPOSAL_DISPATCH", "repo_root is required")
    root = Path(root_value).resolve()
    app_value = app if app is not None else dispatch.get("app")
    app_name = _require_nonempty_string(app_value, "PROPOSAL_DISPATCH", "app")
    passing_checks, known_authority_ids = _certificate_bindings(authority_certificate)

    claims: dict[str, Mapping[str, Any]] = {}
    claim_fields = {
        "claim_id",
        "kind",
        "statement",
        "authority_ids",
        "authority_check_ids",
        "evidence",
        "target_types",
    }
    for item in row["claims"]:
        claim = _require_exact_fields(item, claim_fields, "PROPOSAL_CLAIM", "claim")
        claim_id = _require_nonempty_string(claim["claim_id"], "PROPOSAL_CLAIM", "claim_id")
        if claim_id in claims:
            _error("PROPOSAL_CLAIM", f"Duplicate claim_id: {claim_id}")
        if claim["kind"] not in CLAIM_KINDS:
            _error("PROPOSAL_CLAIM", f"Invalid claim kind: {claim['kind']}")
        statement = _require_nonempty_string(claim["statement"], "PROPOSAL_CLAIM", "claim.statement")
        if "\n" in statement or len(statement) > 2000 or _MARKDOWN_HEADING.search(statement):
            _error("PROPOSAL_CLAIM", f"Claim {claim_id} must be one atomic, single-line statement")
        authority_ids = _require_string_list(
            claim["authority_ids"], "PROPOSAL_CLAIM", "claim.authority_ids"
        )
        if not set(authority_ids).issubset(known_authority_ids):
            _error("PROPOSAL_CLAIM", f"Claim {claim_id} references unknown authority IDs")
        _validate_bound_ids(
            claim["authority_check_ids"], passing_checks, "PROPOSAL_CLAIM", "claim.authority_check_ids"
        )
        _validate_evidence_list(
            claim["evidence"], input_hashes, root, code="PROPOSAL_CLAIM", label=f"{claim_id}.evidence"
        )
        target_types = _require_string_list(
            claim["target_types"], "PROPOSAL_CLAIM", "claim.target_types", nonempty=True
        )
        if not set(target_types).issubset(SSOT_TYPES):
            _error("PROPOSAL_CLAIM", f"Claim {claim_id} has an unknown target type")
        claims[claim_id] = claim

    relation_fields = {
        "relation_id",
        "kind",
        "source_path",
        "target_path",
        "feature_id",
        "authority_ids",
        "outcome",
        "requirement",
        "verification",
        "claim_ids",
        "authority_check_ids",
    }
    relations: dict[str, Mapping[str, Any]] = {}
    for item in row["relations"]:
        relation = _require_exact_fields(item, relation_fields, "PROPOSAL_RELATION", "relation")
        relation_id = _require_nonempty_string(relation["relation_id"], "PROPOSAL_RELATION", "relation_id")
        if relation_id in relations:
            _error("PROPOSAL_RELATION", f"Duplicate relation_id: {relation_id}")
        if relation["kind"] not in {"FC_FRD_TRACE", "ADR_DISPOSITION", "SEMANTIC"}:
            _error("PROPOSAL_RELATION", f"Invalid relation kind: {relation['kind']}")
        for path_field in ("source_path", "target_path"):
            path_value = relation[path_field]
            if path_value is not None:
                normalized = _repo_relative(
                    root, _require_nonempty_string(path_value, "PROPOSAL_RELATION", path_field), "PROPOSAL_RELATION"
                )
                if not normalized.casefold().startswith(f"docs/{app_name}/".casefold()):
                    _error("PROPOSAL_RELATION", f"Relation {path_field} is outside the App")
                relation[path_field] = normalized
        if relation["feature_id"] is not None:
            feature = _require_nonempty_string(relation["feature_id"], "PROPOSAL_RELATION", "feature_id")
            if not _FEATURE_ID.fullmatch(feature):
                _error("PROPOSAL_RELATION", "relation.feature_id is invalid")
        _require_string_list(relation["authority_ids"], "PROPOSAL_RELATION", "relation.authority_ids")
        _validate_bound_ids(relation["claim_ids"], set(claims), "PROPOSAL_RELATION", "relation.claim_ids")
        _validate_bound_ids(
            relation["authority_check_ids"], passing_checks, "PROPOSAL_RELATION", "relation.authority_check_ids"
        )
        _require_nonempty_string(relation["outcome"], "PROPOSAL_RELATION", "relation.outcome")
        _require_nonempty_string(relation["requirement"], "PROPOSAL_RELATION", "relation.requirement")
        if relation["verification"] not in {"MECHANICAL", "SEMANTIC"}:
            _error("PROPOSAL_RELATION", "relation.verification must be MECHANICAL or SEMANTIC")
        if relation["kind"] == "ADR_DISPOSITION" and not relation["authority_ids"]:
            _error("PROPOSAL_RELATION", "ADR_DISPOSITION requires explicit ADR authority_ids")
        relations[relation_id] = relation

    action_fields = {
        "action_id",
        "ssot_type",
        "action",
        "path",
        "reason",
        "claim_ids",
        "relation_ids",
        "authority_check_ids",
        "apply_mode",
        "mutations",
        "creation_spec",
        "render_blocks",
    }
    mutation_fields = {
        "mutation_id",
        "operation",
        "old",
        "anchor",
        "value",
        "expected_count",
        "claim_ids",
        "authority_check_ids",
    }
    render_fields = {
        "render_id",
        "section_id",
        "purpose",
        "claim_ids",
        "required_literals",
        "forbidden_literals",
        "max_chars",
    }
    action_ids: set[str] = set()
    action_paths: set[str] = set()
    action_types: set[str] = set()
    all_mutation_ids: set[str] = set()
    for item in row["actions"]:
        action = _require_exact_fields(item, action_fields, "PROPOSAL_ACTION", "action")
        action_id = _require_nonempty_string(action["action_id"], "PROPOSAL_ACTION", "action_id")
        if action_id in action_ids:
            _error("PROPOSAL_ACTION", f"Duplicate action_id: {action_id}")
        action_ids.add(action_id)
        ssot_type = action["ssot_type"]
        if ssot_type not in SSOT_TYPES or action["action"] not in {"CREATE", "UPDATE"}:
            _error("PROPOSAL_ACTION", f"Invalid action/type: {action['action']}/{ssot_type}")
        path_value = _repo_relative(
            root, _require_nonempty_string(action["path"], "PROPOSAL_ACTION", "action.path"), "PROPOSAL_ACTION"
        )
        if _classify_ssot_path(app_name, path_value) != ssot_type:
            _error("TARGET_TYPE_MISMATCH", f"Target path/type mismatch: {ssot_type}: {path_value}")
        path_key = path_value.casefold()
        if path_key in action_paths:
            _error("PROPOSAL_ACTION", f"Duplicate action path: {path_value}")
        action_paths.add(path_key)
        action["path"] = path_value
        target = root / path_value
        if action["action"] == "UPDATE" and not target.is_file():
            _error("PROPOSAL_ACTION", f"UPDATE target does not exist: {path_value}")
        if action["action"] == "CREATE" and target.exists():
            _error("PROPOSAL_ACTION", f"CREATE target already exists: {path_value}")
        _require_nonempty_string(action["reason"], "PROPOSAL_ACTION", "action.reason")
        action_claim_ids = _validate_bound_ids(
            action["claim_ids"], set(claims), "PROPOSAL_ACTION", "action.claim_ids"
        )
        for claim_id in action_claim_ids:
            if ssot_type not in claims[claim_id]["target_types"]:
                _error("PROPOSAL_ACTION", f"Claim {claim_id} does not target {ssot_type}")
        _validate_bound_ids(
            action["relation_ids"], set(relations), "PROPOSAL_ACTION", "action.relation_ids", nonempty=False
        )
        _validate_bound_ids(
            action["authority_check_ids"], passing_checks, "PROPOSAL_ACTION", "action.authority_check_ids"
        )
        if not isinstance(action["mutations"], list) or not isinstance(action["render_blocks"], list):
            _error("PROPOSAL_ACTION", "mutations and render_blocks must be lists")
        if action["action"] == "UPDATE":
            if action["apply_mode"] != UPDATE_APPLY_MODE or not action["mutations"]:
                _error("ACTION_IMPLEMENTATION_MISSING", "UPDATE requires RUNNER_PATCH with exact mutations")
            if action["creation_spec"] is not None or action["render_blocks"]:
                _error("PROPOSAL_ACTION", "UPDATE prohibits creation_spec and render_blocks")
        else:
            if ssot_type != "FRD":
                _error("MANUAL_REQUIRED", "Contract v8 automatic CREATE supports FRD only")
            if action["apply_mode"] != CREATE_APPLY_MODE:
                if action["apply_mode"] in {"RUNNER_CREATE", "RUNNER_CREATE_WITH_RENDER", "RUNNER_FRD_CLAIM_CREATE"}:
                    _error("FRD_FULLTEXT_PROHIBITED", "FRD CREATE must use RUNNER_CREATE_FROM_CLAIMS")
                _error("PROPOSAL_ACTION", "FRD CREATE has an invalid apply_mode")
            if action["mutations"]:
                _error("FRD_FULLTEXT_PROHIBITED", "FRD CREATE cannot contain mutations or full document prose")

        mutation_ids: set[str] = set()
        for mutation_value in action["mutations"]:
            mutation = _require_exact_fields(
                mutation_value, mutation_fields, "PROPOSAL_MUTATION", "mutation"
            )
            mutation_id = _require_nonempty_string(
                mutation["mutation_id"], "PROPOSAL_MUTATION", "mutation_id"
            )
            if mutation_id in mutation_ids:
                _error("PROPOSAL_MUTATION", f"Duplicate mutation_id in {action_id}: {mutation_id}")
            if mutation_id in all_mutation_ids:
                _error("PROPOSAL_MUTATION", f"mutation_id must be globally unique: {mutation_id}")
            mutation_ids.add(mutation_id)
            all_mutation_ids.add(mutation_id)
            operation = mutation["operation"]
            if operation == "CREATE_EXACT":
                _error("FRD_FULLTEXT_PROHIBITED", "CREATE_EXACT is prohibited")
            if operation not in MUTATION_OPERATIONS:
                _error("PROPOSAL_MUTATION", f"Unsupported mutation operation: {operation}")
            if not isinstance(mutation["value"], str):
                _error("PROPOSAL_MUTATION", "mutation.value must be a string")
            _validate_bound_ids(
                mutation["claim_ids"], set(action_claim_ids), "MUTATION_BINDING", "mutation.claim_ids"
            )
            _validate_bound_ids(
                mutation["authority_check_ids"], passing_checks, "MUTATION_BINDING", "mutation.authority_check_ids"
            )
            expected = mutation["expected_count"]
            if isinstance(expected, bool) or expected != 1:
                _error("PROPOSAL_MUTATION", "Every exact UPDATE mutation requires expected_count 1")
            if operation == "REPLACE_EXACT":
                if not isinstance(mutation["old"], str) or not mutation["old"] or mutation["anchor"] is not None:
                    _error("PROPOSAL_MUTATION", "REPLACE_EXACT requires old and null anchor")
            else:
                if mutation["old"] is not None or not isinstance(mutation["anchor"], str) or not mutation["anchor"]:
                    _error("PROPOSAL_MUTATION", f"{operation} requires null old and a non-empty anchor")
            if ssot_type == "FRD" and (
                _looks_like_full_document(mutation["value"])
                or _looks_like_full_document(mutation.get("old"))
            ):
                _error("FRD_FULLTEXT_PROHIBITED", "Whole or multi-section FRD mutation is prohibited")

        if action["action"] == "CREATE":
            action["creation_spec"]["template_path"] = _validate_creation_spec(
                action["creation_spec"], action, claims, root
            )
        elif action["creation_spec"] is not None:
            _error("PROPOSAL_ACTION", "UPDATE creation_spec must be null")

        render_ids: set[str] = set()
        sections_by_id = {
            section["section_id"]: set(section["claim_ids"])
            for section in (action["creation_spec"] or {}).get("sections", [])
        }
        for block_value in action["render_blocks"]:
            block = _require_exact_fields(
                block_value, render_fields, "PROPOSAL_RENDER", "render block"
            )
            render_id = _require_nonempty_string(block["render_id"], "PROPOSAL_RENDER", "render_id")
            if render_id in render_ids:
                _error("PROPOSAL_RENDER", f"Duplicate render_id: {render_id}")
            render_ids.add(render_id)
            section_id = block["section_id"]
            if section_id not in OPTIONAL_PROSE_SECTION_IDS:
                _error("PROPOSAL_RENDER", f"Optional prose is forbidden in canonical section: {section_id}")
            block_claims = _validate_bound_ids(
                block["claim_ids"], sections_by_id.get(section_id, set()), "PROPOSAL_RENDER", "render_block.claim_ids"
            )
            _require_nonempty_string(block["purpose"], "PROPOSAL_RENDER", "render_block.purpose")
            required = _require_string_list(
                block["required_literals"], "PROPOSAL_RENDER", "required_literals", nonempty=True
            )
            forbidden = _require_string_list(
                block["forbidden_literals"], "PROPOSAL_RENDER", "forbidden_literals"
            )
            if set(required) & set(forbidden):
                _error("PROPOSAL_RENDER", "required_literals and forbidden_literals overlap")
            if isinstance(block["max_chars"], bool) or not isinstance(block["max_chars"], int) or not 1 <= block["max_chars"] <= 2000:
                _error("PROPOSAL_RENDER", "max_chars must be in 1..2000")
            bound_text = "\n".join(str(claims[claim_id]["statement"]) for claim_id in block_claims)
            if any(literal not in bound_text for literal in required):
                _error("PROPOSAL_RENDER", "Every required literal must already occur in bound claims")
        action_types.add(str(ssot_type))

    skip_fields = {"ssot_type", "reason", "claim_ids", "authority_check_ids"}
    skip_types: set[str] = set()
    for item in row["skips"]:
        skip = _require_exact_fields(item, skip_fields, "PROPOSAL_SKIP", "skip")
        ssot_type = skip["ssot_type"]
        if ssot_type not in SSOT_TYPES or ssot_type in skip_types:
            _error("PROPOSAL_SKIP", f"Invalid or duplicate skip type: {ssot_type}")
        _require_nonempty_string(skip["reason"], "PROPOSAL_SKIP", "skip.reason")
        skip_claims = _validate_bound_ids(
            skip["claim_ids"], set(claims), "PROPOSAL_SKIP", "skip.claim_ids", nonempty=False
        )
        for claim_id in skip_claims:
            if ssot_type not in claims[claim_id]["target_types"]:
                _error("PROPOSAL_SKIP", f"Skip claim {claim_id} does not target {ssot_type}")
        _validate_bound_ids(
            skip["authority_check_ids"], passing_checks, "PROPOSAL_SKIP", "skip.authority_check_ids"
        )
        skip_types.add(str(ssot_type))

    if action_types & skip_types:
        _error("PROPOSAL_COVERAGE", "An SSOT type cannot be both changed and skipped")
    if row["disposition"] in {"ACTIVE", "NOOP", "OBSOLETE"} and action_types | skip_types != set(SSOT_TYPES):
        _error("PROPOSAL_COVERAGE", "ClaimSpec must cover all six SSOT types by action(s) or one skip")

    risk_ids: set[str] = set()
    risk_fields = {"risk_id", "description", "claim_ids", "authority_check_ids", "evidence"}
    for item in row["risk_flags"]:
        risk = _require_exact_fields(item, risk_fields, "PROPOSAL_RISK", "risk flag")
        risk_id = _require_nonempty_string(risk["risk_id"], "PROPOSAL_RISK", "risk_id")
        if risk_id in risk_ids:
            _error("PROPOSAL_RISK", f"Duplicate risk_id: {risk_id}")
        risk_ids.add(risk_id)
        _require_nonempty_string(risk["description"], "PROPOSAL_RISK", "risk.description")
        _validate_bound_ids(risk["claim_ids"], set(claims), "PROPOSAL_RISK", "risk.claim_ids", nonempty=False)
        _validate_bound_ids(
            risk["authority_check_ids"], passing_checks, "PROPOSAL_RISK", "risk.authority_check_ids"
        )
        _validate_evidence_list(risk["evidence"], input_hashes, root, code="PROPOSAL_RISK")

    if row["questions"]:
        if row["disposition"] != "BLOCKED" or len(row["questions"]) != 1:
            _error("PROPOSAL_QUESTION", "Only BLOCKED may contain exactly one question")
        _validate_question(row["questions"][0], input_hashes, root, allow_null=False)
    elif row["disposition"] == "BLOCKED":
        _error("PROPOSAL_QUESTION", "BLOCKED requires exactly one question")

    unsupported_ids: set[str] = set()
    for item in row["unsupported_changes"]:
        unsupported = _require_exact_fields(
            item, {"change_id", "path", "claim_ids", "reason"}, "PROPOSAL_UNSUPPORTED", "unsupported change"
        )
        change_id = _require_nonempty_string(
            unsupported["change_id"], "PROPOSAL_UNSUPPORTED", "change_id"
        )
        if change_id in unsupported_ids:
            _error("PROPOSAL_UNSUPPORTED", f"Duplicate change_id: {change_id}")
        unsupported_ids.add(change_id)
        unsupported["path"] = _repo_relative(
            root,
            _require_nonempty_string(unsupported["path"], "PROPOSAL_UNSUPPORTED", "unsupported.path"),
            "PROPOSAL_UNSUPPORTED",
        )
        _validate_bound_ids(
            unsupported["claim_ids"], set(claims), "PROPOSAL_UNSUPPORTED", "unsupported.claim_ids"
        )
        _require_nonempty_string(unsupported["reason"], "PROPOSAL_UNSUPPORTED", "unsupported.reason")

    disposition = row["disposition"]
    if disposition == "ACTIVE" and not row["actions"]:
        _error("PROPOSAL_DISPOSITION", "ACTIVE requires actions")
    if disposition != "ACTIVE" and row["actions"]:
        _error("PROPOSAL_DISPOSITION", f"{disposition} prohibits actions")
    if disposition == "MANUAL_REQUIRED" and not row["unsupported_changes"]:
        _error("PROPOSAL_UNSUPPORTED", "MANUAL_REQUIRED requires unsupported_changes")
    if row["unsupported_changes"] and disposition != "MANUAL_REQUIRED":
        _error("PROPOSAL_UNSUPPORTED", "unsupported_changes require MANUAL_REQUIRED")

    for action in row["actions"]:
        if action["ssot_type"] == "FRD" and action["action"] == "CREATE":
            matches = [
                relation
                for relation in row["relations"]
                if relation["kind"] == "FC_FRD_TRACE" and relation["target_path"] == action["path"]
            ]
            if len(matches) != 1:
                _error("PLAN_INVARIANT_FAILED", "Every FRD CREATE requires exactly one FC_FRD_TRACE")
            relation = matches[0]
            fc_actions = [
                candidate
                for candidate in row["actions"]
                if candidate["ssot_type"] == "FC" and candidate["path"] == relation["source_path"]
            ]
            if (
                not fc_actions
                or relation["relation_id"] not in action["relation_ids"]
                or relation["relation_id"] not in fc_actions[0]["relation_ids"]
            ):
                _error("PLAN_INVARIANT_FAILED", "FC_FRD_TRACE must bind both FC and created FRD actions")
    adr_actions = [action for action in row["actions"] if action["ssot_type"] in {"ADR", "ADR-CATALOG"}]
    if adr_actions:
        disposition_relations = [relation for relation in row["relations"] if relation["kind"] == "ADR_DISPOSITION"]
        for action in adr_actions:
            if not any(relation["relation_id"] in action["relation_ids"] for relation in disposition_relations):
                _error("PLAN_INVARIANT_FAILED", "ADR/ADR-CATALOG actions require ADR_DISPOSITION binding")
    return value


def _claim_map(claims: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if isinstance(claims, Mapping):
        if all(isinstance(value, Mapping) and value.get("claim_id") == key for key, value in claims.items()):
            return {str(key): value for key, value in claims.items()}
        if "claims" in claims and isinstance(claims["claims"], list):
            claims = claims["claims"]
        else:
            _error("FRD_RENDER_CLAIMS", "claims mapping must be keyed by claim_id")
    result: dict[str, Mapping[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, Mapping) or not isinstance(claim.get("claim_id"), str):
            _error("FRD_RENDER_CLAIMS", "Every rendered claim requires claim_id")
        claim_id = str(claim["claim_id"])
        if claim_id in result or not isinstance(claim.get("statement"), str) or not str(claim["statement"]).strip():
            _error("FRD_RENDER_CLAIMS", f"Invalid or duplicate rendered claim: {claim_id}")
        result[claim_id] = claim
    return result


def validate_rendered_prose_tokens(
    markdown: str,
    claim_texts: Iterable[str],
    required_literals: Iterable[str],
) -> None:
    """Reject model-invented numeric and identifier-like tokens mechanically.

    Ordinary connective prose remains renderer-owned.  Tokens that commonly
    carry executable meaning (numbers, IDs, paths, acronyms, and code-like
    names) must already occur in the approved claim statements or in the
    runner-bound required literals.
    """

    allowed_text = "\n".join([*claim_texts, *required_literals])
    allowed = {match.group(0).casefold() for match in _RENDER_GUARDED_TOKEN.finditer(allowed_text)}
    produced = {match.group(0).casefold() for match in _RENDER_GUARDED_TOKEN.finditer(markdown)}
    invented = sorted(produced - allowed)
    if invented:
        _error(
            "RENDER_INVENTED_TOKEN",
            f"Rendered prose introduced unapproved numeric/identifier token(s): {invented}",
        )


def _render_claim_bullets(section: Mapping[str, Any], claims: Mapping[str, Mapping[str, Any]]) -> list[str]:
    ids = sorted(section["claim_ids"])
    return [f"- {claims[claim_id]['statement']}" for claim_id in ids] if ids else ["- 없음"]


def render_frd_from_claims(
    action: Mapping[str, Any],
    claims: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    relations: Iterable[Mapping[str, Any]] = (),
    coverage: Mapping[str, str] | None = None,
    rendered_blocks: Mapping[str, str] | None = None,
) -> str:
    """Render canonical FRD Markdown from one validated CREATE action.

    The same action/claim values always produce identical UTF-8 text.  Claim
    and section ordering is canonicalized; model-supplied whole-document prose
    is never accepted.  Optional rendered blocks, if provided, are inserted
    only after the runner-owned deterministic content of their approved slot.
    """

    if action.get("action") != "CREATE" or action.get("ssot_type") != "FRD":
        _error("FRD_RENDER_ACTION", "Canonical FRD rendering requires an FRD CREATE action")
    if action.get("apply_mode") != CREATE_APPLY_MODE or action.get("mutations"):
        _error("FRD_FULLTEXT_PROHIBITED", "Canonical FRD rendering requires RUNNER_CREATE_FROM_CLAIMS and no mutations")
    spec = action.get("creation_spec")
    if not isinstance(spec, Mapping):
        _error("CREATION_SPEC_SCHEMA", "FRD creation_spec is missing")
    claim_by_id = _claim_map(claims)
    sections = spec.get("sections")
    if not isinstance(sections, list) or not sections:
        _error("CREATION_SECTION_COVERAGE", "FRD renderer requires at least one canonical section mapping")
    sections_by_id: dict[str, Mapping[str, Any]] = {}
    for section in sections:
        if not isinstance(section, Mapping):
            _error("CREATION_SECTION_COVERAGE", "FRD section mapping must be an object")
        section_id = section.get("section_id")
        if section_id not in FRD_SECTION_SLOT_BY_ID or section_id in sections_by_id:
            _error("CREATION_SECTION_COVERAGE", f"Invalid or duplicate canonical section: {section_id}")
        if section.get("template_slot") != FRD_SECTION_SLOT_BY_ID[str(section_id)] or section.get("render_mode") != "DETERMINISTIC":
            _error("CREATION_SECTION_COVERAGE", f"Invalid canonical section mapping: {section_id}")
        ids = section.get("claim_ids")
        if not isinstance(ids, list) or not all(isinstance(item, str) and item in claim_by_id for item in ids):
            _error("CREATION_CLAIM_BINDING", f"Section {section_id} contains unknown claims")
        sections_by_id[str(section_id)] = section
    document_id = str(spec.get("document_id", ""))
    feature_id = str(spec.get("feature_id", ""))
    title = str(spec.get("title", ""))
    metadata = spec.get("metadata")
    if not document_id or not feature_id or not title or not isinstance(metadata, Mapping):
        _error("CREATION_SPEC_SCHEMA", "FRD renderer metadata is incomplete")
    version = str(metadata.get("version", ""))
    status = str(metadata.get("status", ""))
    date = str(metadata.get("date", ""))
    app_name = document_id.split("-FRD-", 1)[0]
    related: set[str] = set()
    for relation in relations:
        if not isinstance(relation, Mapping):
            continue
        for field in ("source_path", "target_path"):
            path = relation.get(field)
            if isinstance(path, str) and path and Path(path).stem != document_id and "/TASK/" not in path.replace("\\", "/").upper():
                related.add(path.replace("\\", "/"))
    if not related:
        related.update(
            {
                f"Docs/{app_name}/{app_name}-PRD.md",
                f"Docs/{app_name}/{app_name}-FC.md",
                f"Docs/{app_name}/{app_name}-ARCHITECTURE.md",
                f"Docs/{app_name}/{app_name}-ADR-CATALOG.md",
            }
        )
    lines = [
        f"# {document_id} — {feature_id} {title}",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 문서 ID | {document_id} |",
        f"| 버전 | {version} ({status}) |",
        f"| 기능 ID | {feature_id} |",
        f"| 상태 | {status} |",
        "| 작성 가정 | 승인된 ClaimSpec의 요구·제약만 사용 |",
        "| 관련 문서 | " + " · ".join(f"`{path}`" for path in sorted(related, key=str.casefold)) + " |",
        "",
        "## 변경 이력",
        "",
        "| 버전 | 일자 | 변경 요약 | 작성자 |",
        "|---|---|---|---|",
        f"| {version} | {date} | ClaimSpec 기반 최초 생성 | ssot-write runner |",
        "",
    ]
    block_values = rendered_blocks or {}
    block_specs: dict[str, list[Mapping[str, Any]]] = {}
    for block in action.get("render_blocks", []):
        if isinstance(block, Mapping):
            block_specs.setdefault(str(block.get("section_id")), []).append(block)
    matrix = coverage or {}
    for number, (section_id, _, heading) in enumerate(FRD_SECTION_SLOTS, start=1):
        section = sections_by_id.get(
            section_id,
            {"section_id": section_id, "template_slot": FRD_SECTION_SLOT_BY_ID[section_id], "claim_ids": [], "render_mode": "DETERMINISTIC"},
        )
        lines.extend([f"## {number}. {heading}", ""])
        claim_ids = sorted(section["claim_ids"])
        if section_id == "SEC-005":
            lines.extend(
                [f"{index}. {claim_by_id[claim_id]['statement']}" for index, claim_id in enumerate(claim_ids, start=1)]
                or ["1. 없음"]
            )
        elif section_id == "SEC-016":
            lines.extend(["| 문서 | 반영 |", "|---|---|"])
            for ssot_type in ("FC", "ADR", "ADR-CATALOG"):
                lines.append(f"| {ssot_type} | {matrix.get(ssot_type, 'ClaimSpec 참조')} |")
            if claim_ids:
                lines.append("")
                lines.extend(_render_claim_bullets(section, claim_by_id))
        elif section_id == "SEC-017":
            lines.extend(["| ID | 기준 | 확인 방법 |", "|---|---|---|"])
            for index, claim_id in enumerate(claim_ids, start=1):
                lines.append(
                    f"| AC-{feature_id}-{index:03d} | {claim_by_id[claim_id]['statement']} | 기준 충족 여부 확인 |"
                )
            if not claim_ids:
                lines.append(f"| AC-{feature_id}-001 | 없음 | 문서 리뷰 |")
        elif section_id == "SEC-018":
            lines.extend(["| ID | 테스트 관점 | 확인 방식 |", "|---|---|---|"])
            for index, claim_id in enumerate(claim_ids, start=1):
                lines.append(
                    f"| TC-{feature_id}-{index:03d} | {claim_by_id[claim_id]['statement']} | 자동 또는 수동 검증 |"
                )
            if not claim_ids:
                lines.append(f"| TC-{feature_id}-001 | 없음 | 문서 리뷰 |")
        elif section_id == "SEC-020":
            lines.extend(["| ID | 항목 | 상태 |", "|---|---|---|"])
            for index, claim_id in enumerate(claim_ids, start=1):
                lines.append(f"| Q-{feature_id}-{index:03d} | {claim_by_id[claim_id]['statement']} | Open |")
            if not claim_ids:
                lines.append(f"| Q-{feature_id}-001 | 없음 | Resolved |")
        else:
            lines.extend(_render_claim_bullets(section, claim_by_id))
        for block in sorted(block_specs.get(section_id, []), key=lambda row: str(row.get("render_id"))):
            render_id = str(block.get("render_id"))
            if render_id in block_values:
                prose = block_values[render_id]
                if not isinstance(prose, str) or not prose.strip():
                    _error("FRD_RENDER_BLOCK", f"Rendered block is empty: {render_id}")
                if len(prose) > int(block.get("max_chars", 0)):
                    _error("FRD_RENDER_BLOCK", f"Rendered block exceeds max_chars: {render_id}")
                if _MARKDOWN_HEADING.search(prose) or "```" in prose or "{{RENDER:" in prose:
                    _error("FRD_RENDER_BLOCK", f"Rendered block contains prohibited structure: {render_id}")
                if any(literal not in prose for literal in block.get("required_literals", [])):
                    _error("FRD_RENDER_BLOCK", f"Rendered block lacks a required literal: {render_id}")
                if any(literal in prose for literal in block.get("forbidden_literals", [])):
                    _error("FRD_RENDER_BLOCK", f"Rendered block contains a forbidden literal: {render_id}")
                lines.extend(["", prose.strip()])
            else:
                lines.extend(["", f"{{{{RENDER:{render_id}}}}}"])
        lines.append("")
    rendered = "\n".join(lines).rstrip() + "\n"
    if _TASK_REFERENCE.search(rendered):
        _error("FRD_TASK_LEAK", "Canonical FRD output contains a prohibited TASK reference")
    return rendered


def _render_frd_from_claims(
    action: Mapping[str, Any],
    claims: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> str:
    """Compatibility helper used by the v8 runner and contract tests."""

    return render_frd_from_claims(action, claims)


def canonical_json_sha256(value: Any) -> str:
    """Return the stable digest used to bind pure contract values."""

    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "AUTHORITY_CHECK_IDS",
    "CHANGE_CHECK_IDS",
    "CLAIM_KINDS",
    "CONTRACT_VERSION",
    "CREATE_APPLY_MODE",
    "ContractV8Error",
    "DISPOSITIONS",
    "FRD_SECTION_IDS",
    "FRD_SECTION_SLOTS",
    "MUTATION_OPERATIONS",
    "OPTIONAL_PROSE_SECTION_IDS",
    "OUTCOME_CHECK_IDS",
    "SSOT_TYPES",
    "UPDATE_APPLY_MODE",
    "_render_frd_from_claims",
    "authority_terminal_disposition",
    "canonical_json_sha256",
    "render_frd_from_claims",
    "validate_authority_certificate",
    "validate_certificate",
    "validate_change_certificate",
    "validate_claim_spec",
    "validate_evidence",
    "validate_outcome_certificate",
]
