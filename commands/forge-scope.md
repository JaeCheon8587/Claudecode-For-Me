---
description: /forge-init 이 만들어 둔 워크트리 안에서 승인된 Intent 를 개발한다. 오케스트레이터 세션(opus/fable-orchestrator) 전용. 매니페스트(.process/forge/handoff.json)를 입력으로 받아 슬라이스마다 coder RED → GREEN → reviewer → 커밋, A-n 증거로 마감. 워크트리는 만들지 않는다.
argument-hint: "[<handoff.json> — 생략 시 .process/forge/handoff.json]"
---

먼저 skills/forge-scope/SKILL.md 파일을 읽고, 해당 스킬의 지침을 수행하라.

이 커맨드는 **워크트리 안에서** 실행한다. 메인 repo 에서 실행하면 스킬의 진입 가드가 중단시키고 `/forge-init` 을 안내한다.

인자: $ARGUMENTS
