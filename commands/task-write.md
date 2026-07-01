---
description: 요구사항 문서나 자연어 요청으로 TASK 작업 범위 계약만 생성한다. SSOT 문서는 분석·수정하지 않는다.
argument-hint: "[--app <APP>] [--from <requirements-path>] <작업 요청>"
---

$ARGUMENTS 인자로 task-write 스킬을 실행하라.

`skills/task-write/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

- TASK 파일만 생성한다.
- TASK에는 완료 기준, 단위 테스트, 엣지 케이스, 오류 처리를 명확히 작성한다.
- Phase 5 검증은 서브 에이전트에 위임해야 한다. 서브 에이전트는 read-only auditor 로만 동작한다.
- 서브 에이전트 위임 시 `skills/task-write/templates/phase5-auditor-input.md`와 `skills/task-write/templates/phase5-auditor-output.md`를 그대로 사용한다.

절대 금지:
- FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 를 생성하지 않는다.
- FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 를 수정하지 않는다.
- FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 를 upsert 하지 않는다.
- FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 같은 영구 SSOT 문서는 분석하지 않는다.
- SSOT 갱신 후보, 영향 후보, 링크 목록, 변경 계획을 TASK 안에 작성하지 않는다.
