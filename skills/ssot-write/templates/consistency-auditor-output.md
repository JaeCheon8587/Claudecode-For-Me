# ssot-write Consistency Audit

Result: PASS | FAIL | AUDIT_BLOCKED

Result rule:
- Use `Result: PASS` only when every File Audit row and every Checklist item is PASS.
- Use `Result: FAIL` if any File Audit row or Checklist item is FAIL.
- Use `Result: AUDIT_BLOCKED` only when the read-only auditor could not inspect required inputs.

## File Audit

| Path | Expected change | Observed change | Result | Required fix |
|---|---|---|---|---|
| `<SSOT path>` | `<expected CREATE/UPDATE/SKIP and scope from confirmed matrix>` | `<observed change or missing>` | PASS/FAIL/BLOCKED | `<file-specific fix or none>` |

## Checklist

- PASS | FAIL: Auditor was read-only.
- PASS | FAIL: Auditor made no edit and no write.
- PASS | FAIL: Changed SSOT paths match the confirmed plan.
- PASS | FAIL: No SSOT file expected by the confirmed matrix is missing from changed paths.
- PASS | FAIL: FC and FRD identifiers are consistent where applicable.
- PASS | FAIL: ADR and ADR-CATALOG identifiers/statuses are consistent where applicable.
- PASS | FAIL: SSOT bodies contain no TASK markdown link.
- PASS | FAIL: SSOT bodies contain no TASK ID citation.
- PASS | FAIL: SSOT change history uses content-based summaries instead of TASK IDs.
- PASS | FAIL: `.process` build/progress reflects TASK 검증, 영향 SSOT 분석, SSOT 파일 수정, 일관성 감사.

## Required Fixes

- `<SSOT path>`: `<required file-specific fix, or "none">`

If `Result: FAIL`, every failed File Audit row or checklist item must be grounded in a file-specific required fix or a blocking note here.

## Evidence

- Files read: `<paths>`
- Changed files observed: `<git status/diff summary>`
- Helper result: `<check summary or skipped reason>`
- Notes: `<short evidence summary>`
