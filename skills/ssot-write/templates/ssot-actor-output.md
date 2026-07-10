# ssot-write Sonnet Action Result

Result: PASS | FAIL | BLOCKED
Mode: apply | repair

## Applied Action Matrix

| SSOT type | Planned action | Target path | Planned scope | Observed edit | Result | Note |
|---|---|---|---|---|---|---|
| `<type>` | CREATE/UPDATE | `<path>` | `<section/table/file>` | `<short content-based summary>` | PASS/FAIL/BLOCKED | `<none or reason>` |

## Changed Paths

- `<path>`

## Actor Checks

- PASS | FAIL: Every edit maps to a `CREATE` or `UPDATE` confirmed row.
- PASS | FAIL: No `SKIP` or unplanned path was modified.
- PASS | FAIL: No architecture, policy, or scope decision was invented.
- PASS | FAIL: Permanent SSOT contains no TASK markdown link.
- PASS | FAIL: Permanent SSOT contains no TASK ID citation.
- PASS | FAIL: Change history uses content-based summaries.
- PASS | FAIL: Required identifier/catalog synchronization was applied.

## Blocking Question

`<one question or none>`

## Verification

- Commands run: `<commands or none>`
- Helper result: `<summary or skipped reason>`
- Diff summary: `<file names and line counts only; no full diff>`

## Repair Log

- `<timestamp, audit fix reference, result; or none>`
