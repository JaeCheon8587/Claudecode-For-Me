# work-packet-write Phase 5 Audit

Result: PASS | FAIL | AUDIT_BLOCKED

Result rule:
- Use `Result: PASS` only when every File/Section Audit row and every checklist item is PASS.
- Use `Result: FAIL` if any File/Section Audit row or checklist item is FAIL.
- Use `Result: AUDIT_BLOCKED` only when the read-only auditor could not inspect required inputs.

## File/Section Audit

| Target | Expected | Observed | Result | Required fix |
|---|---|---|---|---|
| Work Packet metadata | `<expected path, document ID, Draft/Ready status>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| TASK link | `<expected TASK link>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| Execution Gate | `<Ready only when no blocking, Required SSOT target paths exist, and scope is clear; Draft = do not implement>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| Required SSOT Execution Matrix | `<Expected Required SSOT Execution Matrix>` | `<observed Work Packet matrix>` | PASS / FAIL | `<section-specific fix or none>` |
| Authority inputs/instructions | `<handoff authority_paths are Required; action instructions are execution rules>` | `<observed matrix and execution rule>` | PASS / FAIL | `<section-specific fix or none>` |
| Blocking / Open Questions | `<none for Ready, issue rows for Draft>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| Execution rules and boundaries | `<non-empty rules/bounds matching TASK and SSOT>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| Validation inputs and readiness checklist | `<TASK §9/§9.1/§9.2/§9.3 plus actual matrix state>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| Implementation Output Contract | `<Changed files, Scope match, Tests run, Not run, Deviations>` | `<observed>` | PASS / FAIL | `<section-specific fix or none>` |
| Changed files | `<only Work Packet changed by this skill run>` | `<observed git status/diff>` | PASS / FAIL | `<section-specific fix or none>` |

## Checklist

- PASS | FAIL: Auditor was read-only.
- PASS | FAIL: Auditor made no edit and no write.
- PASS | FAIL: Work Packet path and document ID use `<APP>-WP-<NNN>`.
- PASS | FAIL: Work Packet creation status is limited to `Draft` or `Ready`.
- PASS | FAIL: Execution Gate is present.
- PASS | FAIL: Gate consistency is correct: `Ready` has no blocking and all Required SSOT target paths exist.
- PASS | FAIL: Gate consistency is correct: `Draft` is not written as implementable.
- PASS | FAIL: Linked TASK exists and matches the input TASK.
- PASS | FAIL: `handoff.json` actions were compared to the expected matrix.
- PASS | FAIL: Expected Required SSOT Execution Matrix uses the same columns as the Work Packet matrix.
- PASS | FAIL: Expected matrix and observed Work Packet matrix were compared table to table.
- PASS | FAIL: Required SSOT Execution Matrix matches expected CREATE/UPDATE coverage.
- PASS | FAIL: Required SSOT Execution Matrix links exist.
- PASS | FAIL: Required SSOT Execution Matrix read ranges are narrow and implementation-relevant.
- PASS | FAIL: Missing `CREATE/UPDATE target path` handling is Draft + Blocking, not guessed link or Ready.
- PASS | FAIL: Every handoff authority path is Required and no unrelated authority was added.
- PASS | FAIL: Every downstream Work Packet instruction is present in execution rules.
- PASS | FAIL: Ambiguous precedence is Draft + Blocking, not an invented Ready decision.
- PASS | FAIL: Source matrix row values trace to the confirmed matrix or a blocking note.
- PASS | FAIL: Blocking / Open Questions is present and consistent with Draft/Ready.
- PASS | FAIL: Work Packet contains links/read ranges, not long TASK or SSOT body copies.
- PASS | FAIL: Execution rules are present.
- PASS | FAIL: Execution boundary is present.
- PASS | FAIL: Validation inputs are present.
- PASS | FAIL: Readiness checklist reflects actual state.
- PASS | FAIL: Implementation Output Contract is present.
- PASS | FAIL: Implementation Output Contract requires `Changed files`, `Scope match`, `Tests run`, `Not run`, and `Deviations`.
- PASS | FAIL: No `{...}` placeholder remains.
- PASS | FAIL: No `TEMPLATE` warning remains.
- PASS | FAIL: Only the Work Packet file was created or modified by this skill run.

## Required Fixes

- `<Work Packet section: fix summary, or "none">`

## Evidence

- Files read: `<paths>`
- Changed files observed: `<git status/diff summary>`
- Notes: `<short evidence summary>`
