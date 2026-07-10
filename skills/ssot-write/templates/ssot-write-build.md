# ssot-write Build

## Inputs

- Repo root: `<repo_root>`
- App: `<APP>`
- TASK: `<TASK-path>`
- Process dir: `.process/<TASK-stem>/`
- Resume: `<true|false>`

## Agent Contract

| Role | Model | Reads | Writes |
|---|---|---|---|
| Main orchestrator | Opus session | status envelopes only | none |
| Planning thinker | opus | TASK, SSOT, guides/templates | impact/build/progress artifacts only |
| SSOT actor | sonnet | confirmed plan and target inputs | confirmed SSOT targets/action/progress |
| Consistency auditor | opus | TASK, plan, action, changed SSOT/diff | audit/progress artifacts only |

## SSOT Work Plan

Status values are `pending / doing / done / blocked`.

| Stage | Name | Owner | Status | Output |
|---|---|---|---|---|
| 0 | bootstrap / resume | Sonnet actor | pending | Process files and resume stage |
| 1 | TASK 검증 | Opus planner | pending | Validation in impact artifact |
| 2 | 영향 SSOT 분석 | Opus planner | pending | Required SSOT Coverage Matrix |
| 3 | SSOT 수정 계획 확정 | Opus planner | pending | Confirmed SSOT Action Matrix |
| 4 | SSOT 파일 수정 | Sonnet actor | pending | SSOT edits and action artifact |
| 5 | 수정 후 일관성 감사 | Opus auditor | pending | Audit artifact and repair contract |
| 6 | 결과 정리/보고 | Sonnet finalizer / Main orchestrator | pending | Final envelope, UPDATE/CREATE, Process, Audit, Next |

## Confirmed SSOT Action Matrix

The Opus planner writes the final decision here. This matrix is the only authority for Sonnet actor edits and the Opus consistency audit.

| SSOT type | Action | Target path | Existing ID | Edit scope | Reason | Source impact row | User question |
|---|---|---|---|---|---|---|---|
| PRD | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or unresolved question>` |
| FC | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or unresolved question>` |
| FRD | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or unresolved question>` |
| ADR | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or unresolved question>` |
| ADR-CATALOG | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or unresolved question>` |
| ARCHITECTURE | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<content-based reason>` | `<summary>` | `<none or unresolved question>` |

## Handoff Artifacts

| Artifact | Owner | Consumer | Status |
|---|---|---|---|
| `ssot-write-impact.md` | Opus planner | Sonnet actor, Opus auditor | pending |
| `ssot-write-action.md` | Sonnet actor | Opus auditor | pending |
| `ssot-write-audit.md` | Opus auditor | Sonnet repair actor, main envelope | pending |

## Guardrails

- Main orchestrator does not read raw TASK/SSOT/diff content and writes no file.
- Planning thinker and auditor do not modify TASK or permanent SSOT.
- Sonnet actor modifies only `CREATE/UPDATE` targets and scopes in the confirmed matrix.
- Permanent SSOT contains no TASK markdown link or TASK ID citation.
- Ambiguous impact or design blocks for user clarification.
- Final `Next` is `work-packet-write`.
