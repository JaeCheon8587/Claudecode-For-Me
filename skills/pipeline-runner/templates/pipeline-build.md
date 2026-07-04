# Pipeline Build — {{SLUG}}

<!-- Template Contract:
- Keep every heading and table header in this template.
- Do not rename, omit, collapse, or replace required sections with free-form prose.
- Fill unavailable values with none, pending, skipped, or AUDIT_BLOCKED.
- Remove all double-brace placeholders before passing Template Contract Gate.
-->

## Input
- Requirement Spec: {{REQUIREMENT_PATH}}
- Source Request: {{SOURCE_REQUEST}}
- App: {{APP}}
- Slug: {{SLUG}}
- Process Dir: `.process/pipeline-{{SLUG}}/`

## Scale Assessment

| Axis | Score | Evidence |
|---|---:|---|
| 변경 범위 | {{SCOPE_SCORE}} | {{SCOPE_EVIDENCE}} |
| SSOT 영향도 | {{SSOT_SCORE}} | {{SSOT_EVIDENCE}} |
| 데이터/API/계약 영향도 | {{CONTRACT_SCORE}} | {{CONTRACT_EVIDENCE}} |
| 테스트/검증 난이도 | {{VALIDATION_SCORE}} | {{VALIDATION_EVIDENCE}} |
| 실패 리스크 | {{RISK_SCORE}} | {{RISK_EVIDENCE}} |
| 의존성/불확실성 | {{DEPENDENCY_SCORE}} | {{DEPENDENCY_EVIDENCE}} |
| 작업 분할 필요성 | {{SPLIT_SCORE}} | {{SPLIT_EVIDENCE}} |

## Routing Decision
- Total Score: {{TOTAL_SCORE}}
- Size: {{SIZE_BAND}}
- Forced Conditions: {{FORCED_CONDITIONS}}
- Selected Pipeline: `{{SELECTED_PIPELINE}}`

## Step Parameters

| Order | Skill | Input | Required Params | Expected Output | Gate | Next Input |
|---:|---|---|---|---|---|---|
{{STEP_PARAMETER_ROWS}}

## Approval
<!-- Status allowed values: pending | approved | rejected. Phase 4 is forbidden unless Status is approved. -->
- Status: pending
- Approved Pipeline: `{{SELECTED_PIPELINE}}`
- Approved By: pending
- Approved At: pending

## Risk Notes
<!-- Record routing overrides, skipped step reasons, and any SSOT/Work Packet enforcement risk. -->
- {{RISK_NOTES}}
