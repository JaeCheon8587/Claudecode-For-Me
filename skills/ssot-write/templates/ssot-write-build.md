# ssot-write Build

## Inputs

- Repo root: `<repo_root>`
- App: `<APP>`
- TASK: `<TASK-path>`
- Process dir: `.process/<TASK-stem>/`
- Resume: `<true|false>`

## SSOT Work Plan

| Stage | Name | Status | Output |
|---|---|---|---|
| 1 | TASK 검증 | pending | TASK path/app/check-task validation |
| 2 | 영향 SSOT 분석 | pending | Read-only impact auditor summary |
| 3 | SSOT 수정 계획 확정 | pending | CREATE/UPDATE target list and edit scope |
| 4 | SSOT 파일 수정 | pending | Main-agent SSOT edits only |
| 5 | 수정 후 일관성 감사 | pending | Read-only consistency audit result |
| 6 | 결과 보고 | pending | UPDATE/CREATE, Process, Audit, Next |

## Confirmed SSOT Action Matrix

Phase 3 writes the final main-agent decision here after reviewing the impact auditor output. Use this matrix as the source of truth for Phase 4 edits and Phase 5 consistency audit input.

| SSOT type | Action | Target path | Existing ID | Edit scope | Reason | Source impact row | User question |
|---|---|---|---|---|---|---|---|
| PRD | CREATE/UPDATE/SKIP | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or resolved question>` |
| FC | CREATE/UPDATE/SKIP | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or resolved question>` |
| FRD | CREATE/UPDATE/SKIP | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or resolved question>` |
| ADR | CREATE/UPDATE/SKIP | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or resolved question>` |
| ADR-CATALOG | CREATE/UPDATE/SKIP | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or resolved question>` |
| ARCHITECTURE | CREATE/UPDATE/SKIP | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or resolved question>` |

## Guardrails

- Status values are `pending / doing / done / blocked`.
- Subagents are read-only and must not edit files.
- Main agent is the only writer for PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE.
- Do not leave TASK markdown links or TASK ID citations in permanent SSOT bodies.
- Ambiguous SSOT impact or new/existing feature judgment blocks for user clarification.
- Final `Next` is `work-packet-write`.
