#!/usr/bin/env python3
"""
Branch Review Chunk Plan — diff 크기 측정 + 모드 판정 + (chunk 모드) 청크 분할 +
청크별 patch 파일 생성.

`branch-review` 스킬의 Step 2를 결정적으로 수행한다. `git diff --numstat`가 rename
파일을 `{old => new}` 압축 표기로 내놓으면 그 문자열을 그대로 pathspec에 넣었을 때
매칭이 조용히 실패한다(청크별 patch가 비어버림) — 이를 `--no-renames`로 우회한다
(rename은 삭제+추가 별도 라인으로 분리되어 집계되므로 `--stat` 요약과 파일/라인 수가
달라질 수 있다 — 이는 버그가 아니라 이 스크립트의 정상 동작이다).

기준(reference)은 호출자가 Step 1에서 이미 확정한 ref 문자열을 그대로 받는다 —
이 스크립트는 merge-base 자동 추정을 하지 않는다(원본 무수정 원칙과 동일하게
관심사를 분리: ref 확정은 SKILL.md Step 1, 크기측정·분할은 이 스크립트).

Usage:
    python3 scripts/branch_review_chunk_plan.py --ref <ref> [--repo-root <path>]
        [--max-lines 1500] [--max-files 30]

Options:
    --ref <ref>          필수. 비교 기준점(브랜치/태그/커밋/merge-base sha). `<ref>...HEAD`로 사용.
    --repo-root <path>   기본 git rev-parse --show-toplevel.
    --max-lines <N>      청크당 라인 상한 (기본 1500).
    --max-files <N>      청크당 파일 상한 (기본 30).

Output:
    stdout — 마크다운. 모드(none/inline/standard/chunk) + (chunk 모드) Chunk Plan 표.
    `.process/branch-review-<slug>/branch-review-build.md`의 `Chunk Plan` 섹션에
    그대로 붙여넣을 수 있는 표 형식.
    부수효과 — 표준/인라인 모드는 `.git/info/branch-review-<short-sha>.patch` 1개,
    chunk 모드는 청크별 `.git/info/branch-review-<short-sha>-<chunk-id>.patch` N개를 생성.
    (`.git/info/`는 항상 ignored — 정리 자동, 커밋 대상 아님.)

Exit codes:
    0   정상
    1   기타 오류 (레포 아님, ref 해석 실패, git 실행 실패 등)
    130 KeyboardInterrupt
"""

import sys

# Encoding bootstrap — FIRST executable code (Windows cp949 콘솔 회피)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

import argparse
import subprocess
from pathlib import Path

EXIT_OK = 0
EXIT_ERR = 1
EXIT_KBI = 130

DEFAULT_MAX_LINES = 1500
DEFAULT_MAX_FILES = 30

# Step 2 제외 패턴과 동일 — 확장자/파일명 기준
EXCLUDE_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
)
EXCLUDE_BASENAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "Cargo.lock", "poetry.lock", "uv.lock", "Gemfile.lock",
}
EXCLUDE_DIR_SEGMENTS = {"dist", "build", "out", "node_modules"}

# 크기 임계값 (SKILL.md Step 2 표와 동일)
INLINE_MAX_LINES = 50
INLINE_MAX_FILES = 2
STANDARD_MAX_LINES = 2000
STANDARD_MAX_FILES = 50


class ChunkPlanError(Exception):
    pass


def run_git(repo_root: Path, args: list) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ChunkPlanError(f"git {' '.join(args)} 실패: {result.stderr.strip()}")
    return result.stdout


def get_short_sha(repo_root: Path) -> str:
    return run_git(repo_root, ["rev-parse", "--short", "HEAD"]).strip()


def is_excluded(path: str) -> bool:
    base = path.rsplit("/", 1)[-1]
    if base in EXCLUDE_BASENAMES:
        return True
    if any(path.endswith(suf) for suf in EXCLUDE_SUFFIXES):
        return True
    segments = path.split("/")
    if any(seg in EXCLUDE_DIR_SEGMENTS for seg in segments):
        return True
    return False


def filter_linguist_generated(repo_root: Path, paths: list) -> set:
    """linguist-generated: set 인 경로 집합을 반환 (배치 check-attr, 대용량 대비 청크 분할)."""
    generated = set()
    if not paths:
        return generated
    batch_size = 200
    for i in range(0, len(paths), batch_size):
        batch = paths[i : i + batch_size]
        try:
            out = run_git(repo_root, ["check-attr", "-a", "--", *batch])
        except ChunkPlanError:
            continue
        for line in out.splitlines():
            # 형식: "<path>: <attr>: <value>"
            parts = line.split(": ", 2)
            if len(parts) != 3:
                continue
            p, attr, value = parts
            if attr == "linguist-generated" and value.strip() == "set":
                generated.add(p)
    return generated


def get_numstat(repo_root: Path, ref: str) -> list:
    """[(add:int, delete:int, path:str), ...] — rename-safe(--no-renames)."""
    out = run_git(repo_root, ["diff", "--no-renames", "--numstat", f"{ref}...HEAD"])
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        add_s, del_s, path = parts
        add = 0 if add_s == "-" else int(add_s)  # binary files show '-'
        delete = 0 if del_s == "-" else int(del_s)
        rows.append((add, delete, path))
    return rows


def decide_mode(total_files: int, total_lines: int) -> str:
    if total_files == 0 and total_lines == 0:
        return "none"
    if total_lines <= INLINE_MAX_LINES and total_files <= INLINE_MAX_FILES:
        return "inline"
    if total_lines <= STANDARD_MAX_LINES and total_files <= STANDARD_MAX_FILES:
        return "standard"
    return "chunk"


def top_dir_key(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else path


def group_into_chunks(rows: list, max_lines: int, max_files: int) -> list:
    """
    1) 최상위 디렉토리(top_dir_key)로 1차 그룹화 (정렬 순서 = 등장 순서 보존, 결정적 재현을 위해 경로 알파벳순 사용).
    2) 그룹이 캡 초과 시 같은 그룹 내에서 파일 단위 greedy bin-packing으로 서브청크 분할.
    반환: [{"id": "C1", "label": "<top-dir>", "files": [path,...], "lines": N}, ...]
    """
    rows_sorted = sorted(rows, key=lambda r: r[2])
    groups = {}
    for add, delete, path in rows_sorted:
        key = top_dir_key(path)
        groups.setdefault(key, []).append((add, delete, path))

    chunks = []
    chunk_num = 0
    for key in sorted(groups.keys()):
        items = groups[key]
        sub_files = []
        sub_lines = 0
        sub_index = 0

        def flush(sub_index):
            nonlocal chunk_num
            if not sub_files:
                return
            chunk_num += 1
            label = key if sub_index == 0 else f"{key} ({sub_index + 1})"
            chunks.append({
                "id": f"C{chunk_num}",
                "label": label,
                "files": list(sub_files),
                "lines": sub_lines,
            })

        for add, delete, path in items:
            item_lines = add + delete
            would_exceed = (
                sub_files
                and (sub_lines + item_lines > max_lines or len(sub_files) + 1 > max_files)
            )
            if would_exceed:
                flush(sub_index)
                sub_index += 1
                sub_files = []
                sub_lines = 0
            sub_files.append(path)
            sub_lines += item_lines
        flush(sub_index)

    return chunks


def write_patch(repo_root: Path, ref: str, files: list, out_path: Path) -> None:
    args = ["diff", "--no-renames", f"{ref}...HEAD"]
    if files:
        args += ["--", *files]
    patch = run_git(repo_root, args)
    out_path.write_text(patch, encoding="utf-8")


def render_markdown(mode: str, total_files: int, total_lines: int,
                     excluded_files: int, excluded_lines: int,
                     chunks: list, patch_paths: dict) -> str:
    lines = []
    lines.append(f"모드: {mode}")
    lines.append(
        f"변경 규모: {total_files} files, {total_lines} lines "
        f"(제외 {excluded_files}파일 {excluded_lines}줄 후, rename 분리 재계산)"
    )
    if mode == "chunk":
        lines.append("")
        lines.append("## Chunk Plan")
        lines.append("| Chunk | 디렉터리/파일 | 파일수 | 라인수 | patch |")
        lines.append("|---|---|---|---|---|")
        for c in chunks:
            patch_name = patch_paths.get(c["id"], "")
            lines.append(
                f"| {c['id']} | {c['label']} | {len(c['files'])} | {c['lines']} | {patch_name} |"
            )
    else:
        patch_name = patch_paths.get("single", "")
        lines.append(f"patch: {patch_name}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="branch-review 청크 계획 산출 + patch 생성")
    parser.add_argument("--ref", required=True, help="비교 기준점 (브랜치/태그/커밋)")
    parser.add_argument("--repo-root", default=None, help="기본 git rev-parse --show-toplevel")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    args = parser.parse_args()

    try:
        repo_root = Path(args.repo_root) if args.repo_root else Path(
            run_git(Path.cwd(), ["rev-parse", "--show-toplevel"]).strip()
        )
        short_sha = get_short_sha(repo_root)

        raw_rows = get_numstat(repo_root, args.ref)
        all_paths = [p for _, _, p in raw_rows]
        generated = filter_linguist_generated(repo_root, all_paths)

        kept_rows = []
        excluded_files = 0
        excluded_lines = 0
        for add, delete, path in raw_rows:
            if is_excluded(path) or path in generated:
                excluded_files += 1
                excluded_lines += add + delete
                continue
            kept_rows.append((add, delete, path))

        total_files = len(kept_rows)
        total_lines = sum(a + d for a, d, _ in kept_rows)
        mode = decide_mode(total_files, total_lines)

        info_dir = repo_root / ".git" / "info"
        info_dir.mkdir(parents=True, exist_ok=True)
        patch_paths = {}
        chunks = []

        if mode == "none":
            pass
        elif mode in ("inline", "standard"):
            patch_file = info_dir / f"branch-review-{short_sha}.patch"
            write_patch(repo_root, args.ref, [p for _, _, p in kept_rows], patch_file)
            patch_paths["single"] = str(patch_file)
        else:  # chunk
            chunks = group_into_chunks(kept_rows, args.max_lines, args.max_files)
            for c in chunks:
                patch_file = info_dir / f"branch-review-{short_sha}-{c['id']}.patch"
                write_patch(repo_root, args.ref, c["files"], patch_file)
                patch_paths[c["id"]] = str(patch_file)

        print(render_markdown(mode, total_files, total_lines,
                               excluded_files, excluded_lines, chunks, patch_paths))
        return EXIT_OK
    except ChunkPlanError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_ERR
    except KeyboardInterrupt:
        return EXIT_KBI


if __name__ == "__main__":
    sys.exit(main())
