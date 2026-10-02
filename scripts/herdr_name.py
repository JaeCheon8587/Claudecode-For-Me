#!/usr/bin/env python3
"""herdr_name — herdr 에이전트 이름 정규화.

herdr 는 에이전트 이름을 `^[a-z][a-z0-9_-]{0,31}$` 로 제한하고, 살아 있는
에이전트 사이에서 유일할 것을 요구한다. 그런데 이름의 출처가 되는 값(워크트리
slug, 브랜치명, 문서 ID)은 대문자와 점을 그대로 갖는다 — 예를 들어
`worktree_setup.py` 의 `_slugify` 는 `[^A-Za-z0-9._-]` 만 치환하므로
`MyApp-INT-007` 이 그대로 나온다. 그걸 `agent start` 에 넘기면 거부된다.

이 규칙을 산문으로 두면 오적용되므로 결정적 함수로 고정한다.

CLI
---
    python herdr_name.py <raw> [--taken a,b,c]   정규화한 이름 한 줄
    python herdr_name.py <raw> --strict          raw 가 이미 유효할 때만 출력

표준 라이브러리만 사용한다 (Python 3.10+).
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable

MAX_LEN = 32
VALID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
MAX_SUFFIX = 100


def is_valid(name: str) -> bool:
    """herdr 가 받아들이는 이름인가."""
    return bool(VALID.match(name))


def normalize(raw: str, taken: Iterable[str] = ()) -> str:
    """raw 를 herdr 에이전트 이름으로 바꾼다. taken 과 겹치면 접미를 붙인다.

    `MyApp-INT-007` → `myapp-int-007`
    """
    taken = set(taken)

    s = re.sub(r"[^a-z0-9_-]+", "-", raw.lower()).strip("-_")
    s = re.sub(r"^[^a-z]+", "", s)          # 선두는 알파벳이어야 한다
    s = s.strip("-_")[:MAX_LEN].rstrip("-_") or "agent"

    if s not in taken:
        return s

    for n in range(2, MAX_SUFFIX):
        suffix = f"-{n}"
        stem = s[: MAX_LEN - len(suffix)].rstrip("-_") or "agent"
        cand = f"{stem}{suffix}"
        if cand not in taken:
            return cand

    raise ValueError(f"이름 충돌을 해소할 수 없다 ({MAX_SUFFIX - 2}회 시도): {raw!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="herdr_name", description="herdr 에이전트 이름 정규화")
    p.add_argument("raw", help="정규화할 원본 (워크트리 slug 등)")
    p.add_argument("--taken", default="", help="이미 쓰이는 이름 (쉼표 구분) — `herdr agent list` 결과")
    p.add_argument("--strict", action="store_true",
                   help="raw 가 이미 유효할 때만 출력한다 (사용자가 --name 으로 준 값 검증용)")
    args = p.parse_args(argv)

    # 진단 메시지가 한글이다. Windows 기본 콘솔 코드페이지(cp949)로 나가면
    # 호출자가 UTF-8 로 읽을 때 깨진다.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    taken = [t.strip() for t in args.taken.split(",") if t.strip()]

    if args.strict:
        if not is_valid(args.raw):
            print(f"ERROR: herdr 이름 규칙 위반 — ^[a-z][a-z0-9_-]{{0,31}}$ : {args.raw!r}",
                  file=sys.stderr)
            return 2
        if args.raw in taken:
            print(f"ERROR: 이미 쓰이는 이름이다: {args.raw!r}", file=sys.stderr)
            return 2
        print(args.raw)
        return 0

    try:
        print(normalize(args.raw, taken))
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
