# work-packet-write Phase 5 Auditor Input

You are a read-only auditor for a generated Work Packet.

## Audit Target

- Repo root: `<repo_root>`
- App: `<APP>`
- TASK file: `<TASK-path>`
- Work Packet file: `<WORK_PACKET-path>`
- Process build file: `<process build path or none>`

## Source Expectations

### Confirmed SSOT Action Matrix

`<render handoff.json actions as a matrix, or "none">`

### Authority Inputs and Instructions

`<paste each handoff action_id, authority_paths, instruction, acceptance_criteria, or "none">`

### Expected Required SSOT Execution Matrix

Use the same columns as the Work Packet matrix. Derive Required rows from CREATE/UPDATE rows plus every approved ADR/authority relation. Include only justified Optional rows.

| SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority |
|---|---|---|---|---|---|---|
| `<type>` | `<CREATE / UPDATE>` | `<expected existing target path or MISSING target path>` | `<expected narrow range>` | `<why implementation must read it>` | `<Confirmed SSOT Action Matrix row>` | `Required` |
| `<type>` | `<optional action>` | `<expected existing target path>` | `<expected narrow range>` | `<why this exception helps implementation judgment>` | `<Confirmed SSOT Action Matrix row or explicit basis>` | `Optional` |
| `ADR` | `AUTHORITY` | `<controlling ADR path>` | `<controlling decision range>` | `<why current truth controls implementation>` | `handoff action <Action ID> authority` | `Required` |

### Impact / source summary

`<short summary of TASK scope, source matrix impact, and any blocking assumptions>`

## Allowed Actions

- Read the Work Packet file.
- Read the linked TASK file.
- Read Required SSOT Execution Matrix files linked by the Work Packet only to verify existence and narrow relevance.
- Read the process build file if present.
- Run read-only commands such as `git status` and `git diff --name-only`.

## Prohibited Actions

- Read-only only: no edit, no write, no delete, no move.
- Do not modify Work Packet, TASK, SSOT, or code files.
- Do not create fix commits or patches.
- Do not expand the Work Packet by copying SSOT body text.

## Audit Rules

- Verify the Work Packet path and document ID use `<APP>-WP-<NNN>`.
- Verify the linked TASK path exists and matches the input TASK.
- Verify the Work Packet's Required SSOT Execution Matrix matches the Expected Required SSOT Execution Matrix by same-column table comparison.
- Verify every `CREATE` / `UPDATE` action from `handoff.json` is present unless a section-specific blocking note explains why not.
- Verify `CREATE/UPDATE target path` missing or nonexistent means `Draft` + `Blocking / Open Questions`; do not accept guessed links.
- Verify ordinary `SKIP` rows are not Required. A `SKIP` authority referenced by an approved downstream relation is the only exception and must be Required.
- Verify every handoff `authority_paths` entry appears as Required and each Action `instruction` appears in execution rules.
- Verify ambiguous or non-explicit precedence conflicts produce `Draft` + blocking, never an invented Ready precedence.
- Verify Optional rows are justified by TASK execution needs.
- Verify Required SSOT Execution Matrix links exist and read ranges are narrow enough to avoid whole-document overreach.
- Verify `Source matrix row` values trace back to a `handoff.json` action ID or to an explicit blocking note.
- Verify `Execution Gate` exists and is consistent: `Draft` means do not implement, `Ready` means no blocking, Required SSOT exists, and scope is clear.
- FAIL if the Work Packet is `Draft` but written as implementable.
- FAIL if the Work Packet is `Ready` but has blocking issues.
- FAIL if a `CREATE/UPDATE target path` is missing or nonexistent but the Work Packet is `Ready`.
- Verify `Blocking / Open Questions` exists, is `none` for `Ready`, and contains issue/source/impact/required decision rows for `Draft`.
- Verify `Implementation Output Contract` exists and requires `Changed files`, `Scope match`, `Tests run`, `Not run`, and `Deviations`.
- Verify the Work Packet is a context router: links and read ranges are present, but long TASK/SSOT body copies are absent.
- Verify execution rules, execution boundary, validation inputs, and readiness checklist are not empty.
- Verify no `{...}` placeholders or `TEMPLATE` warning remain.
- Verify only the Work Packet file was created or modified for this skill run.

Return only the output template in `templates/phase5-auditor-output.md`.
