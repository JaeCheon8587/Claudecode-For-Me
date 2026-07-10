# ssot-write Progress

Progress file for `.process/<TASK-stem>/`.

Status values: `pending / doing / done / blocked`

## Stage Status

Latest resume snapshot. The assigned subagent updates these rows in place; the main orchestrator does not read or edit this file.

| Stage | Name | Owner | Status | Last Update | Notes |
|---|---|---|---|---|---|
| 0 | bootstrap / resume | Sonnet actor | pending | - | - |
| 1 | TASK 검증 | Opus planner | pending | - | - |
| 2 | 영향 SSOT 분석 | Opus planner | pending | - | - |
| 3 | SSOT 수정 계획 확정 | Opus planner | pending | - | - |
| 4 | SSOT 파일 수정 | Sonnet actor | pending | - | - |
| 5 | 수정 후 일관성 감사 | Opus auditor | pending | - | - |
| 6 | 결과 정리/보고 | Sonnet finalizer / Main orchestrator | pending | - | - |

## Log

Append-only log. Assigned agents add compact entries; do not rewrite previous entries.

### `<YYYY-MM-DD HH:mm>` - Stage 0 bootstrap / resume - pending

- Actor: `sonnet`
- Summary: `<path/helper/process initialization summary>`
- Resume from: `<stage or new run>`
- Decision: `<continue|blocked>`

### `<YYYY-MM-DD HH:mm>` - Stage 1-3 planning - pending

- Thinker: `opus`
- Result: `<READY|BLOCKED|FAIL>`
- Impact artifact: `ssot-write-impact.md`
- Impact audit digest: `<maximum 5 bullets>`
- Matrix digest: `<CREATE/UPDATE/SKIP/BLOCKED counts and targets only>`
- Blocking question: `<none or one question>`

### `<YYYY-MM-DD HH:mm>` - Stage 4 action - pending

- Actor: `sonnet`
- Mode: `<apply|repair>`
- Result: `<PASS|BLOCKED|FAIL>`
- Action artifact: `ssot-write-action.md`
- Changed paths: `<paths or none>`
- Summary: `<maximum 5 bullets>`

### `<YYYY-MM-DD HH:mm>` - Stage 5 audit - pending

- Auditor: `opus`
- Iteration: `<1|2|3>`
- Result: `<PASS|FAIL|BLOCKED>`
- Audit artifact: `ssot-write-audit.md`
- Consistency audit digest: `<maximum 5 bullets>`
- Repair contract: `<fix count or none>`

### `<YYYY-MM-DD HH:mm>` - Stage 6 finalize - pending

- Actor: `sonnet`
- Audit: `<PASS>`
- Final changed SSOT paths: `<paths>`
- Decision: `<ready to report|blocked>`
