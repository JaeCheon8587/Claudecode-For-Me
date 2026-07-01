# ssot-write Impact Audit

Result: PASS | FAIL | AUDIT_BLOCKED

Result rule:
- Use `Result: PASS` only when every SSOT type is judged as `CREATE`, `UPDATE`, or `SKIP`, and there are no `BLOCKED` rows.
- Use `Result: FAIL` when impact is ambiguous, TASK is insufficient, any row is `BLOCKED`, or user clarification is required.
- Use `Result: AUDIT_BLOCKED` only when the read-only auditor could not inspect required inputs.

## Impact Summary

- TASK: `<TASK-path>`
- App: `<APP>`
- Work type: `<feature|refactor|maintenance|migration|setup|investigation|other>`
- Judgment: `<new feature|existing feature change|operational only|mixed|ambiguous>`

## Required SSOT Coverage Matrix

| SSOT type | Judgment | Target path | Existing ID | Edit scope | Evidence from TASK | Evidence from SSOT | Reason | Confidence | Blocking question |
|---|---|---|---|---|---|---|---|---|---|
| PRD | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| FC | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| FRD | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| ADR | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| ADR-CATALOG | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| ARCHITECTURE | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |

## Feature Judgment

- New vs existing: `<new feature|existing feature change|operational only|mixed|ambiguous>`
- Rationale: `<why this judgment follows from TASK and SSOT>`

## Blocking Questions

- `<question or "none">`

## Evidence Summary

- TASK evidence: `<short summary>`
- SSOT evidence: `<short summary>`
- Missing evidence: `<none or gaps>`

## Guardrail Checklist

- PASS | FAIL: Auditor was read-only.
- PASS | FAIL: Auditor made no edit and no write.
- PASS | FAIL: Every SSOT type has exactly one matrix row.
- PASS | FAIL: Each matrix row uses only `CREATE`, `UPDATE`, `SKIP`, or `BLOCKED`.
- PASS | FAIL: `Result: PASS` has no `BLOCKED` rows and no blocking question.
- PASS | FAIL: Recommended SSOT text contains no TASK markdown link.
- PASS | FAIL: Recommended SSOT text contains no TASK ID citation.
- PASS | FAIL: Operational work does not force a new FRD.
- PASS | FAIL: Ambiguous impact is reported as FAIL, not guessed.

## Evidence

- Files read: `<paths>`
- Commands run: `<read-only commands or "none">`
- Notes: `<short evidence summary>`
