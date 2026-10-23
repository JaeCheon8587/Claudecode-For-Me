---
description: grill-me 인터뷰로 기능 문서(Intent)를 새로 쓰거나 고치는 스킬 — App 마다 Intent 1개, 계약이 바뀌면 호출하는 App · 제공하는 App 둘 다. Part 1(왜 · 무엇 · 결정)을 쓰고 Part 2(테스트할 수 있는 동작 FR · E · X)를 파생한 뒤, 코드 생성 체크리스트 + opus 판정 루프(Intent 마다 최대 3회)로 검증하고 품질 지표를 남겨 사용자 확정 1회로 끝낸다. 고칠 때는 고치기 전 사본(기준선)을 남겨 /task-split 이 바뀐 항목을 Task 로 자르게 한다. "요구사항 정리해서 명세까지", "기능 명세 만들어줘", "Intent 작성", "Intent 수정", "requirement-spec" 요청 시 트리거
argument-hint: "[<Intent ID 또는 경로> ...] [--app <app> ...] [--no-gate]"
---

$ARGUMENTS 를 인자로 requirement-spec 스킬을 실행하라.

skills/requirement-spec/SKILL.md 파일을 읽고, 그 안의 지침을 그대로 따라 수행하라.

- 산출물은 대상 Intent(`intent/<app>/<app>-int-<NNN>.md`)다 — App 마다 1개, 새로 쓰거나 고친다. Task · 코드 · 브랜치를 만들지 않는다.
- 고치는 Intent 는 고치기 전 사본(기준선 `.process/intent-base/<ID>.md`)을 먼저 남긴다 — `/task-split` 이 바뀐 항목을 뽑는 기준이다.
- 문서 폴더 · `intent/` · `.process/` 는 커밋하지 않는다(`.git/info/exclude`).
- Phase 5 의 사용자 확정에서 멈춘다. 확정 후에도 `/task-split` 을 자동으로 실행하지 않는다.
- 검증 임시 파일은 `.process/intent-check/<실행>/` 에만 쓴다.
