---
description: requirement-spec 으로 쓰거나 고친 Intent 들의 바뀐 항목을 애자일 자르기 기준으로 개발 단위 Task n 개로 나누는 스킬 — 변경 목록 추출(스크립트) → 자르기 제안 → Task 작성 · 진행 표시 · 검사 → 일괄 승인 1회 → 개발 프롬프트. Intent : Task 는 1:1 · 1:N · N:N 모두 된다. "Task 로 잘라줘", "작업 나눠줘", "task-split" 요청 시 트리거
argument-hint: "[<Intent ID 또는 경로> ...] [--type 기능개발|버그수정|리팩토링]"
---

$ARGUMENTS 를 인자로 task-split 스킬을 실행하라.

skills/task-split/SKILL.md 파일을 읽고, 그 안의 지침을 그대로 따라 수행하라.

- 산출물은 `.task/TSK-<NNN>.md` n 개와 대상 Intent 의 진행 표시, 생성물 카탈로그다. 코드 · 브랜치 · 워크트리를 만들지 않고, 문서를 커밋하지 않는다.
- Phase 4 의 일괄 승인에서 멈추고, 승인하면 개발 프롬프트를 내고 끝낸다. 후속 커맨드(`/worktree-init` 등)를 자동으로 실행하지 않는다.
