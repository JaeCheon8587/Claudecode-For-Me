---
description: TASK와 반영된 SSOT를 연결하는 실행용 Work Packet 문서만 생성한다.
argument-hint: "<TASK-path> [--app <APP>] [--process <process-dir>] [--name <title>]"
---

$ARGUMENTS 인자로 work-packet-write 스킬을 실행하라.

`skills/work-packet-write/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

인자 규칙:
- `<TASK-path>`는 필수다.
- TASK 경로는 `docs/<App>/TASK/<App>-TASK-<NNN>.md` 형식이어야 한다.
- `--app <APP>`가 있으면 TASK 경로의 App 과 일치해야 한다.
- `--process <process-dir>`가 있으면 해당 `ssot-write-build.md`를 우선 사용한다.
- `--name <title>`이 있으면 Work Packet 제목으로 사용한다.

필수 절차:
- `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md` 파일만 생성한다.
- TASK와 Required SSOT 링크/읽을 범위/실행 경계/검증 입력을 작성한다.
- Phase 5 검증은 read-only auditor 에 위임한다.
- auditor 위임 시 `skills/work-packet-write/templates/phase5-auditor-input.md`와 `skills/work-packet-write/templates/phase5-auditor-output.md`를 그대로 사용한다.

절대 금지:
- TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일을 수정하지 않는다.
- Work Packet 안에 SSOT 본문을 길게 복제하지 않는다.
- TASK/SSOT 충돌이 명백한데 임의로 실행 가능하다고 쓰지 않는다.

결과 보고 형식:

```text
CREATE docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md
Task: docs/<App>/TASK/<App>-TASK-<NNN>.md
Audit: PASS | FAIL | AUDIT_BLOCKED - read-only subagent unavailable
Next: forge-scope
```
