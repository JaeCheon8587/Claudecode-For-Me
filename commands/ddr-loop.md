---
description: doc-driven-review(검증) ↔ fix(claude 수정) 수렴 루프. 임계(기본 99%) 또는 cap(기본 3회)까지 반복
argument-hint: "<doc-path> [추가 doc-path...] [--worktree <ref>|--commit <ref>] [--scope auto|working-tree|branch] [--base <ref>] [--max-iter N] [--threshold P] [--commit-each] [--model <name>] [--effort <level>] [--fix-model <name>] [--dry-run]"
---

$ARGUMENTS 인자로 ddr-loop 스킬을 실행하라.

`skills/ddr-loop/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

- 첫 doc 경로 인자 비어있으면 "문서 경로 1개 이상 필수" 안내 후 종료.
- 첫 호출 시 `scripts/ddr_loop.py` + 의존 스크립트(`doc_driven_review.py`, `forge_scope.py`)를 부트스트랩(존재 시 skip).
- 자동 수정을 위해 항상 `--trust --quiet` 첨가.
- 수 분~수십 분 소요 → `run_in_background=true`로 실행하고 즉시 turn 종료. 완료 알림 후 수렴 리포트 + `.review/` 1회 read 보고.
- exit code별 한국어 안내: 0=임계 도달 / 7=cap 도달·임계 미달 / 2=codex 미설치 / 3=리뷰할 변경 없음.
- 스크립트 종료 리포트(conformance 궤적) verbatim 노출.
