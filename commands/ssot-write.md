---
description: Opus Main이 build/progress를 기준으로 Planner→Writer→Critic을 최대 3회 순환해 TASK 기반 SSOT를 갱신한다.
argument-hint: "<TASK-path> [--app <APP>] [--process <path>]"
model: opus
effort: high
---

`${CLAUDE_PLUGIN_ROOT}/skills/ssot-write/SKILL.md`를 읽고 `$ARGUMENTS`로 그대로 실행한다. 대상 repository에서 상대경로 `skills/ssot-write/SKILL.md`를 찾으면 **절대로 안 된다.**

- Main은 **무조건 Opus**다.
- Planner(Opus), Writer(Sonnet), Critic(Opus)을 `general-purpose` 실제 독립 에이전트로 호출한다.
- Main은 모든 Agent 호출 직전에 `<process>/build.md`와 `<process>/progress.md`를 다시 읽는다.
- Agent에는 파일 내용이나 수정 힌트 없이 **무조건 경로만 전달한다.**
- Critic은 `SUCCESS REVIEW_PATH=<path>` 또는 `FAIL REVIEW_PATH=<path>`만 반환한다.
- Critic에게 `PLAN_PATH`를 전달하면 **절대로 안 된다.** TASK 핵심 의미와 Writer가 만든 실제 SSOT 투영만 직접 비교한다.
- Critic은 `모순`, `핵심 누락`, `금지 범위 포함`, `근거 없는 추가 결정` 네 의미 check만 수행하며 하나라도 실패하면 **무조건 FAIL**이다.
- 코드·테스트·빌드 세부를 SSOT에 그대로 복제하지 않았다는 이유만으로 FAIL하면 **절대로 안 된다.** 핵심 제품 동작·운영 정책·아키텍처 결정의 의미만 보존 여부를 판단한다.
- Critic `FAIL`은 **반드시 Planner부터** 새 cycle을 시작한다. Writer로 바로 돌아가면 **절대로 안 된다.**
- 재계획은 FAIL finding 관련 target만 포함하는 `REPAIR` 계획이어야 한다. 전체 계획을 반복하면 **절대로 안 된다.**
- Critic 최대 횟수는 3회이며 세 번째 FAIL은 `MANUAL_REQUIRED`다.
- NOOP도 Critic 검토를 **반드시** 거친다.
- Gate Controller, state, baseline, diff replay, audit, resume, 승인, git stage, git commit을 사용하면 **절대로 안 된다.**
- 모든 자연어는 **반드시 한국어**로 작성한다.
