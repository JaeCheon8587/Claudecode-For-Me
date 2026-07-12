# Outcome Critic — Contract v7

Falsify the complete runner-staged outcome before commit. Use a fresh Opus
context. Review the approved ChangeSpec, compiled preview, TASK/source,
authority, governance manifest and documents, staged documents, patch, and
mechanical checks. Do not read Thinker/renderer conversation, private
reasoning, or prior critic conversation. Do not edit files or runner state.

Verify:

- every fact, action, exact mutation, relation, and render constraint is
  satisfied in staged content;
- no approved fact, target, governance obligation, or cross-document effect
  is omitted or contradicted;
- FC↔FRD IDs, links, acceptance, tests, and completion pointers agree;
- ADR status, supersession, catalog, and FRD disposition agree;
- all `SKIP` types remain complete;
- no render placeholder, TASK citation, invented prose fact, unauthorized
  scope, dangling link, stale count, stale version/history, `검토 필요`, or
  downstream contradiction remains;
- every mechanical check passes. An LLM verdict can never override a failed
  gate.

Write only the packet `artifact` as exactly:

```json
{
  "contract_version": 7,
  "review_id": "<dispatch_id>",
  "contract_sha256": "<packet contract_sha256>",
  "verdict": "PASS",
  "failure_class": "NONE",
  "defects": [],
  "question_id": null,
  "question": null
}
```

Use `PASS`, `FAIL`, or `BLOCKED`.

- `PASS`: `failure_class: NONE`, no defects, no question.
- `FAIL`: `failure_class: PLAN` or `EXECUTION`, with defects.
- `BLOCKED`: one genuine authority question and no speculative decision.

Use `PLAN` when the approved ChangeSpec, facts, scope, authority, governance
binding, mutation design, or deterministic runner output is incomplete or
wrong. Deterministic `RUNNER_PATCH`/`RUNNER_CREATE` content is never repaired
by Sonnet; such a defect is `PLAN` and returns to ChangeSpec planning.

Use `EXECUTION` only for a defect confined to prose produced by an approved
`RUNNER_CREATE_WITH_RENDER` block and repairable by re-rendering that same
block without changing facts, authority, structure, or scope.

Each defect is exactly:

```json
{
  "defect_id": "DEF-001",
  "class": "PLAN",
  "affected_paths": ["Docs/App/App-FC.md"],
  "render_ids": [],
  "description": "specific falsifiable defect",
  "evidence": ["staged excerpt", "contract mutation or governance ID"]
}
```

For `EXECUTION`, `render_ids` must name only the defective approved blocks.
For `PLAN`, use an empty list unless a render specification itself is the
planning defect.

Do not write `result_path`. The runner derives status, failure class, affected
paths, retry routing, and the completion envelope from this artifact.
