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
- 같은 Contract v8 process의 `state.json`이 `run_status=terminal`, `terminal_result=DONE|NOOP`, `disposition=ACTIVE|NOOP`, `downstream=WORK_PACKET`이 아니면 실행하지 않는다. 기존 v5/v6/v7 process는 해당 runner의 성공 상태 계약을 따른다.
- `--name <title>`이 있으면 Work Packet 제목으로 사용한다.

필수 절차:
- `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md` 파일만 생성한다.
- TASK와 Required SSOT Execution Matrix 링크/읽을 범위/Execution Gate/실행 경계/검증 입력을 작성한다.
- process build의 `Input Precedence and Downstream Constraints`를 읽고 v8 approved Authority Certificate/ClaimSpec relation, 기존 v7/v6 relation 또는 legacy v5 `CURRENT_SSOT_WINS` authority를 Required 입력과 실행 규칙에 반영한다. 명시적 권위 근거 없는 충돌은 `Draft`로 둔다.
- `Ready`는 blocking 없음 + Required SSOT target path 존재 + 구현 범위 명확일 때만 사용하고, `Draft`는 구현 금지로 쓴다.
- `Implementation Output Contract`에 `Changed files`, `Scope match`, `Tests run`, `Not run`, `Deviations`를 포함한다.
- Phase 5 검증은 read-only auditor 에 위임한다.
- auditor 위임 시 `skills/work-packet-write/templates/phase5-auditor-input.md`와 `skills/work-packet-write/templates/phase5-auditor-output.md`를 그대로 사용한다.
- auditor input에는 `Confirmed SSOT Action Matrix`, `Input Precedence and Downstream Constraints`, `Expected Required SSOT Execution Matrix`, `Impact / source summary`를 채워 전달한다.
- auditor input의 `Expected Required SSOT Execution Matrix`는 Work Packet matrix와 동일 컬럼으로 작성한다.
- 감사 기준은 Work Packet에 적힌 링크 자체가 아니라 expected matrix 대비 실제 Work Packet의 누락/불필요/범위 과대 여부다.

절대 금지:
- TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일을 수정하지 않는다.
- Work Packet 안에 SSOT 본문을 길게 복제하지 않는다.
- TASK/SSOT 충돌이 명백한데 임의로 실행 가능하다고 쓰지 않는다.
- `CREATE/UPDATE target path` 누락 또는 파일 미존재가 있는데 임의 링크를 만들거나 Ready 로 쓰지 않는다.

결과 보고 형식:

```text
CREATE docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md
Task: docs/<App>/TASK/<App>-TASK-<NNN>.md
Audit: PASS | FAIL | AUDIT_BLOCKED - read-only subagent unavailable
Next: forge-scope
```
