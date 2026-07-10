# ssot-write Opus Consistency Audit

Result: PASS | FAIL | BLOCKED
Iteration: `<1|2|3>`

## File Audit

| Path | Expected change | Observed change | Scope match | Semantic consistency | Result | Required fix |
|---|---|---|---|---|---|---|
| `<SSOT path>` | `<confirmed action and scope>` | `<observed summary or missing>` | PASS/FAIL | PASS/FAIL | PASS/FAIL/BLOCKED | `<file-specific executable fix or none>` |

## Cross-Document Audit

| Relationship | Expected | Observed | Result | Required fix |
|---|---|---|---|---|
| FC ↔ FRD | `<expected IDs/meaning>` | `<observed>` | PASS/FAIL/BLOCKED | `<fix or none>` |
| ADR ↔ ADR-CATALOG | `<expected ID/status>` | `<observed>` | PASS/FAIL/BLOCKED | `<fix or none>` |
| PRD ↔ FC/FRD | `<expected feature summary>` | `<observed>` | PASS/FAIL/BLOCKED | `<fix or none>` |
| ARCHITECTURE ↔ ADR/FRD | `<expected boundary/flow>` | `<observed>` | PASS/FAIL/BLOCKED | `<fix or none>` |

## Checklist

- PASS | FAIL: TASK and permanent SSOT files were not modified by the auditor.
- PASS | FAIL: Only owned `.process` artifacts were written by the auditor.
- PASS | FAIL: Changed paths match the confirmed matrix.
- PASS | FAIL: No confirmed target is missing.
- PASS | FAIL: No unplanned scope or design decision was introduced.
- PASS | FAIL: FC/FRD identifiers and meaning are consistent.
- PASS | FAIL: ADR/ADR-CATALOG identifiers and statuses are consistent.
- PASS | FAIL: Permanent SSOT contains no TASK markdown link or TASK ID citation.
- PASS | FAIL: Change history uses content-based summaries.
- PASS | FAIL: Build, progress, impact, and action artifacts agree.

## Repair Contract

List only mechanical, file-specific fixes. A Sonnet actor must be able to execute each row without a new architectural judgment.

| Fix ID | Path | Exact scope | Required change | Verification |
|---|---|---|---|---|
| FIX-001 | `<path>` | `<section/table/row>` | `<directly executable fix>` | `<specific check>` |

## Blocking Question

`<one question or none>`

## Evidence

- Files read: `<paths>`
- Changed files observed: `<git status/diff summary>`
- Helper result: `<check summary or skipped reason>`
- Notes: `<short evidence summary>`
