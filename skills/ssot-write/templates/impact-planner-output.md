# ssot-write Impact Plan

Result: READY | BLOCKED | FAIL

## Input Validation

- TASK: `<TASK-path>`
- App: `<APP>`
- Work type: `<feature|refactor|maintenance|migration|setup|investigation|other>`
- TASK structure: `<PASS|FAIL and short evidence>`
- Permanent SSOT link guard: `<PASS|FAIL and location if failed>`

## Required SSOT Coverage Matrix

| SSOT type | Judgment | Target path | Existing ID | Edit scope | Evidence from TASK | Evidence from SSOT | Reason | Confidence | Blocking question |
|---|---|---|---|---|---|---|---|---|---|
| PRD | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| FC | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| FRD | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| ADR | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| ADR-CATALOG | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |
| ARCHITECTURE | CREATE/UPDATE/SKIP/BLOCKED | `<path or none>` | `<ID or none>` | `<section/table/file or none>` | `<TASK evidence>` | `<SSOT evidence>` | `<content-based reason>` | high/medium/low | `<question or none>` |

## Actor-Ready Decision

- New vs existing: `<new feature|existing feature change|operational only|mixed|ambiguous>`
- Number allocation: `<method for every new ID or none>`
- Required template paths: `<paths or none>`
- Edit ordering constraints: `<ordered paths or none>`
- Prohibited scope expansion: `<paths/sections the actor must not touch>`

## Blocking Question

`<one highest-priority question or none>`

## Evidence

- Files read: `<paths>`
- Commands run: `<read-only commands or none>`
- Missing evidence: `<none or gaps>`

## Guardrail Checklist

- PASS | FAIL: TASK and permanent SSOT files were not modified.
- PASS | FAIL: Only owned `.process` artifacts were written.
- PASS | FAIL: Every SSOT type has exactly one matrix row.
- PASS | FAIL: `READY` has no `BLOCKED` row or blocking question.
- PASS | FAIL: Every `CREATE/UPDATE` row has an exact target and edit scope.
- PASS | FAIL: Proposed permanent SSOT text contains no TASK link or ID citation.
