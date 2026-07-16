---
description: Opus Main이 build/progress를 기준으로 Planner→Writer→Critic을 최대 3회 순환해 요구사항으로 TASK 작업 범위 계약 1개만 생성한다. SSOT 문서는 분석·수정하지 않는다.
argument-hint: "[--app <APP>] [--from <requirements-path>] <작업 요청>"
model: opus
effort: high
---

`${CLAUDE_PLUGIN_ROOT}/skills/task-write/SKILL.md`를 읽고 `$ARGUMENTS`로 그대로 실행한다. 대상 repository에서 상대경로 `skills/task-write/SKILL.md`를 찾으면 **절대로 안 된다.**

- Main은 **무조건 Opus**이며 **완전 비대화형**이다. App·요구사항이 부족하면 질문 없이 `FAILED`로 종료한다.
- Planner(Opus), Writer(Sonnet), Critic(Opus)을 `general-purpose` 실제 독립 에이전트로 호출한다.
- Main은 모든 Agent 호출 직전에 `<process>/build.md`와 `<process>/progress.md`를 다시 읽는다.
- Agent에는 파일 내용이나 수정 힌트 없이 **무조건 경로만 전달한다.**
- TASK 파일 1개만 생성한다. TASK에는 완료 기준, 단위 테스트, 엣지 케이스, 오류 처리를 명확히 작성한다.
- Critic은 `SUCCESS REVIEW_PATH=<path>` 또는 `FAIL REVIEW_PATH=<path>`만 반환한다.
- Critic에게 `PLAN_PATH`를 전달하면 **절대로 안 된다.** 요구사항 핵심 의미와 실제 TASK 파일만 직접 비교하고 `check-task` 구조 검증을 수행한다.
- Critic은 `요구사항 모순`, `핵심 누락`, `범위 위반`, `근거 없는 추가` 네 의미 check를 수행하며 하나라도 실패하면 **무조건 FAIL**이다.
- Critic `FAIL`은 **반드시 Planner부터** 새 cycle을 시작한다. Writer로 바로 돌아가면 **절대로 안 된다.**
- 재계획은 FAIL finding 관련 대상만 포함하는 `REPAIR` 계획이어야 한다. 전체 계획을 반복하면 **절대로 안 된다.**
- Critic 최대 횟수는 3회이며 세 번째 FAIL은 `MANUAL_REQUIRED`다.
- Gate Controller, state, baseline, diff replay, audit, resume, 승인, git stage, git commit을 사용하면 **절대로 안 된다.**
- 모든 자연어는 **반드시 한국어**로 작성한다.

절대 금지:
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE`를 생성·수정·upsert 하지 않는다.
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 같은 영구 SSOT 문서는 분석하지 않는다.
- SSOT 갱신 후보, 영향 후보, 링크 목록, 변경 계획을 TASK 안에 작성하지 않는다.
