# Pipeline Progress — {{SLUG}}

<!-- Template Contract:
- Keep every heading and table header in this template.
- Do not rename, omit, collapse, or replace required sections with free-form prose.
- Fill unavailable values with none, pending, skipped, or AUDIT_BLOCKED.
- Remove all double-brace placeholders before passing Template Contract Gate.
-->

## Current State
<!-- Status allowed values: pending | in-progress | done | blocked. -->
- Status: pending
- Current Step: approval
- Last Updated: {{LAST_UPDATED}}

## Step Status
<!-- Step Status allowed values: pending | doing | done | blocked | skipped. -->

| Order | Skill | Status | Input | Output | Notes |
|---:|---|---|---|---|---|
{{STEP_STATUS_ROWS}}

## Output Registry
- TASK: pending
- SSOT: none
- SSOT Process: none
- Work Packet: none
- Forge Slug: pending
- Forge Branch: pending
- DDR Result: skipped
- Branch Review: pending

## Decisions / Deviations
- none

## Append-only Log
<!-- Event format:
- <event>: <skill-or-gate> — <start|result|blocked|skipped> — <one-line evidence>
-->
- initialized: pipeline build/progress created; waiting for approval.

## Final Output
<!-- Fill only after every selected step is done/skipped/blocked and no step remains doing. -->
- TASK: pending
- SSOT: none
- Work Packet: none
- Forge Branch: pending
- DDR Result: skipped
- Branch Review: pending
