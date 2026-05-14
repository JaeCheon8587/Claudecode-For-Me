#!/usr/bin/env python3
"""레이어 의존성 검사기 — Src/**/*.csproj 그래프가 Docs/ARCHITECTURE.md 의
§3.2 / §4.4 / §6 / §6.1 / §7.1 을 준수하는지 검사한다.

Rule SSOT: Docs/ARCHITECTURE.md §3.2 §4.4 §6.1 §7.1.
위 섹션이 갱신되면 본 파일의 FOLDER_TO_LAYER / FORBIDDEN_MATRIX /
DOMAIN_CARVEOUT_SUBKINDS / SERVICE_HOST_* / OPS_LAYERS_FOR_TESTS_BAN 도
같은 PR 에서 갱신할 것.

exit code:
  0 = 위반 0건
  1 = 레이어 위반 발견 (stderr 에 누적 위반 + 표준 3줄 형식)
  2 = csproj XML 파싱 실패 또는 Src/ 미존재 등 검사 진행 불가
  3 = 예상치 못한 검사기 실행 오류

usage: python tools/quality/dependency_check.py
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Windows cp949 콘솔에서도 §, → 등이 안전히 나가도록 모듈 import 시점에 강제 교체.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# ── §7.1 폴더 → 레이어 매핑 ────────────────────────────────────
# (prefix, (layer, subkind))  prefix 는 repo 기준 슬래시 종결 경로
FOLDER_TO_LAYER = [
    ("Src/Domain/", ("Domain", None)),
    ("Src/Application/", ("Application", None)),
    ("Src/Infrastructure/", ("Infrastructure", None)),
    ("Src/Shared/", ("Shared", "Shared")),
    ("Src/Constants/", ("Shared", "Constants")),
    ("Src/ServiceModule/", ("Shared", "ServiceModule")),
    ("Src/UIModule/", ("Shared", "UIModule")),
    ("Src/Tests/", ("Tests", None)),
]
# Src/App/<host>/ — host 식별자(디렉터리명)를 subkind 로 보존.
PRESENTATION_HOST_RE = re.compile(r"^Src/App/(?P<host>OrderManagingSystem\.[^/]+)/")

# ── §6.1 매트릭스 본체 (금지 조합) ──────────────────────────────
FORBIDDEN_MATRIX = {
    ("Domain", "Application"),
    ("Domain", "Infrastructure"),
    ("Domain", "Presentation"),
    ("Application", "Infrastructure"),
    ("Application", "Presentation"),
    ("Infrastructure", "Presentation"),
    ("Presentation", "Domain"),
    ("Shared", "Domain"),
    ("Shared", "Application"),
    ("Shared", "Infrastructure"),
    ("Shared", "Presentation"),
}

# ── §6.1 예외 (Domain 순수성 carve-out) ─────────────────────────
DOMAIN_CARVEOUT_SUBKINDS = {"ServiceModule", "UIModule"}

# ── §3.2 Service 호스트 carve-out ──────────────────────────────
SERVICE_HOST_RE = re.compile(r"\.Service$")
SERVICE_HOST_BANNED_SHARED_SUBKINDS = {"UIModule"}

# ── §7.1 운영 레이어 → Tests 참조 절대 금지 ─────────────────────
OPS_LAYERS_FOR_TESTS_BAN = {"Domain", "Application", "Infrastructure", "Presentation"}


def repo_root() -> Path:
    out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    return Path(out)


def normpath_posix(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/")


def layer_of(repo_relpath: str):
    rel = repo_relpath.replace("\\", "/")
    m = PRESENTATION_HOST_RE.match(rel)
    if m:
        return ("Presentation", m.group("host"))
    for prefix, (layer, sub) in FOLDER_TO_LAYER:
        if rel.startswith(prefix):
            return (layer, sub)
    return ("Unknown", None)


def parse_refs(csproj: Path):
    """ProjectReference Include 문자열 리스트(원형) 반환.
    파싱 실패 시 ET.ParseError 그대로 전파."""
    tree = ET.parse(str(csproj))
    root = tree.getroot()
    refs = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag != "ProjectReference":
            continue
        inc = elem.attrib.get("Include")
        if inc:
            refs.append(inc)
    return refs


def verdict(from_layer, from_sub, to_layer, to_sub):
    """판정 결과 = 'OK' | '§6.1' | '§6.1-exc' | '§3.2' | '§4.4' | '§7.1-tests'.

    순서: §6.1 매트릭스 → §6.1 carve-out → §3.2 → §4.4 → §7.1-tests.
    """
    if from_layer == "Unknown" or to_layer == "Unknown":
        return "OK"
    if from_layer == to_layer and from_sub == to_sub:
        return "OK"

    # §6.1 매트릭스 본체
    if (from_layer, to_layer) in FORBIDDEN_MATRIX:
        return "§6.1"

    # §6.1 예외 (Domain → Shared(ServiceModule|UIModule))
    if from_layer == "Domain" and to_layer == "Shared" and to_sub in DOMAIN_CARVEOUT_SUBKINDS:
        return "§6.1-exc"

    # §3.2 Service 호스트 → UIModule
    if (
        from_layer == "Presentation"
        and from_sub
        and SERVICE_HOST_RE.search(from_sub)
        and to_layer == "Shared"
        and to_sub in SERVICE_HOST_BANNED_SHARED_SUBKINDS
    ):
        return "§3.2"

    # §4.4 Presentation 호스트 간 직접 csproj 참조
    if from_layer == "Presentation" and to_layer == "Presentation" and from_sub != to_sub:
        return "§4.4"

    # §7.1 운영 레이어 → Tests
    if to_layer == "Tests" and from_layer in OPS_LAYERS_FOR_TESTS_BAN:
        return "§7.1-tests"

    return "OK"


def fmt_node(layer, sub):
    return f"{layer}({sub})" if sub else layer


def main() -> int:
    debug = os.environ.get("HOOKS_DEBUG") == "1"
    root = repo_root()
    src_dir = root / "Src"
    if not src_dir.is_dir():
        print("WARN: layer-dependency: Src/ not found — skipping layer check", file=sys.stderr)
        return 0

    csprojs = sorted(src_dir.rglob("*.csproj"))
    if not csprojs:
        print("WARN: layer-dependency: no csproj under Src/ — skipping layer check", file=sys.stderr)
        return 0

    # proj_map: 정규화된 repo-기준 POSIX 경로 → (layer, sub)
    proj_map = {}
    by_basename = {}
    for csproj in csprojs:
        rel = normpath_posix(str(csproj.relative_to(root)))
        layer, sub = layer_of(rel)
        proj_map[rel] = (layer, sub)
        by_basename.setdefault(csproj.name, []).append(rel)

    if debug:
        for k, v in proj_map.items():
            print(f"DEBUG: {k} → {v}", file=sys.stderr)

    violations = []  # (from_rel, to_rel, fl, fs, tl, ts, section)
    unresolved_warns = []  # (target_str, from_rel, note)

    for csproj in csprojs:
        from_rel = normpath_posix(str(csproj.relative_to(root)))
        from_layer, from_sub = proj_map[from_rel]

        try:
            includes = parse_refs(csproj)
        except ET.ParseError as e:
            print("FAIL: csproj-parse", file=sys.stderr)
            print(f"target: {from_rel}", file=sys.stderr)
            print(f"next: csproj XML 구문 확인 ({e})", file=sys.stderr)
            return 2

        for inc in includes:
            inc_norm = inc.replace("\\", "/")
            joined = os.path.join(str(csproj.parent), inc_norm)
            try:
                rel_to_root = os.path.relpath(joined, str(root))
            except ValueError:
                # 다른 드라이브 등 — 미해결 처리
                unresolved_warns.append((joined, from_rel, "outside repo root"))
                continue
            to_rel = normpath_posix(rel_to_root)

            if to_rel in proj_map:
                to_layer, to_sub = proj_map[to_rel]
            else:
                # basename fallback 1회
                base = os.path.basename(to_rel)
                cands = by_basename.get(base, [])
                if len(cands) == 1:
                    to_rel = cands[0]
                    to_layer, to_sub = proj_map[to_rel]
                    unresolved_warns.append((rel_to_root, from_rel, "basename fallback OK"))
                else:
                    unresolved_warns.append(
                        (rel_to_root, from_rel, "fallback failed" if not cands else "ambiguous basename")
                    )
                    continue

            v = verdict(from_layer, from_sub, to_layer, to_sub)
            if v != "OK":
                violations.append((from_rel, to_rel, from_layer, from_sub, to_layer, to_sub, v))

    for tgt, frm, note in unresolved_warns:
        print(f"WARN: layer-dependency: unresolved ref {tgt} from {frm} — {note}", file=sys.stderr)

    if not violations:
        return 0

    print(f"WARN: layer-dependency violations ({len(violations)}):", file=sys.stderr)
    for from_rel, to_rel, fl, fs, tl, ts, sec in violations:
        f_lbl = fmt_node(fl, fs)
        t_lbl = fmt_node(tl, ts)
        print(f"  {from_rel}  ->  {to_rel}  ({f_lbl} -> {t_lbl}: {sec})", file=sys.stderr)

    first = violations[0]
    print("FAIL: layer-dependency", file=sys.stderr)
    print(f"target: {first[0]} -> {first[1]}", file=sys.stderr)
    next_msg = (
        "Docs/ARCHITECTURE.md §6.1 (필요 시 §3.2/§4.4/§7.1) 참조 방향에 맞게 ProjectReference 제거 또는 의존 방향 수정"
    )
    print(f"next: {next_msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - hook diagnostics must stay standardized.
        print("FAIL: dependency_check.py", file=sys.stderr)
        print(f"target: {type(exc).__name__}", file=sys.stderr)
        print(f"next: tools/quality/dependency_check.py 실행 오류 확인 ({exc})", file=sys.stderr)
        sys.exit(3)
