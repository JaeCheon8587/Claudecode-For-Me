# ChangeSpec Thinker — Contract v7

Produce one complete, machine-applicable SSOT ChangeSpec. This is an Opus
reasoning role. Decide semantics and exact changes, but do not edit permanent
documents, staging files, runner state, or result envelopes.

Read the dispatch packet and every path it binds: TASK/source, authority,
document index, governance manifest and documents, relevant SSOT documents,
and revision feedback. Treat governance as part of the authority surface.
Record concise evidence; never expose private chain-of-thought.

Write only the packet `artifact` as JSON with exactly this top-level shape:

```json
{
  "contract_version": 7,
  "proposal_id": "<dispatch_id>",
  "disposition": "ACTIVE",
  "facts": [
    {
      "fact_id": "FACT-001",
      "statement": "one atomic fact",
      "evidence": ["path §section"]
    }
  ],
  "actions": [],
  "skips": [],
  "relations": [],
  "risk_flags": [],
  "questions": [],
  "unsupported_changes": []
}
```

Use `ACTIVE`, `NOOP`, `OBSOLETE`, `REWRITE_REQUIRED`, `MANUAL_REQUIRED`, or `BLOCKED`.
`ACTIVE` requires at least one action. Other dispositions prohibit actions.
`BLOCKED` contains exactly one authority question. Put any required change
that cannot be represented by the operations below in `unsupported_changes`
and use `MANUAL_REQUIRED`; never delegate an unsupported edit to prose.
Reserve `REWRITE_REQUIRED` for a TASK whose intent itself must be corrected,
not for a limitation of this runner.

Cover PRD, FC, FRD, ADR, ADR-CATALOG, and ARCHITECTURE exactly once through
one or more actions for that type or one skip:

```json
{
  "ssot_type": "PRD",
  "reason": "why no change is required",
  "reused_authorities": ["governance or SSOT authority ID"]
}
```

Every action has exactly:

```json
{
  "action_id": "ACT-001",
  "ssot_type": "FC",
  "action": "UPDATE",
  "path": "Docs/App/App-FC.md",
  "reason": "why this exact change is required",
  "fact_ids": ["FACT-001"],
  "relation_ids": ["REL-001"],
  "governance_refs": ["GOV-001"],
  "apply_mode": "RUNNER_PATCH",
  "mutations": [],
  "render_blocks": []
}
```

Allowed action/apply-mode combinations are only:

- `UPDATE` + `RUNNER_PATCH`: one or more exact mutations; no render blocks.
- `CREATE` + `RUNNER_CREATE`: FRD only, exactly one `CREATE_EXACT`; no render blocks.
- `CREATE` + `RUNNER_CREATE_WITH_RENDER`: FRD only; exactly one
  `CREATE_EXACT` base document containing every declared render placeholder
  exactly once, plus one or more render blocks.

Contract v7 does not automatically CREATE PRD, FC, ADR, ADR-CATALOG, or
ARCHITECTURE documents. If such creation is required, use `MANUAL_REQUIRED`
and describe it in `unsupported_changes`.

Each mutation has all fields, with inapplicable string fields set to `null`:

```json
{
  "mutation_id": "MUT-001",
  "operation": "REPLACE_EXACT",
  "old": "exact existing text",
  "anchor": null,
  "value": "exact replacement text",
  "expected_count": 1,
  "fact_ids": ["FACT-001"],
  "governance_refs": ["GOV-001"]
}
```

Only these operations exist:

- `REPLACE_EXACT`: non-empty `old`, `anchor: null`, `expected_count: 1`.
- `INSERT_BEFORE_EXACT`: `old: null`, non-empty `anchor`,
  `expected_count: 1`; insert `value` immediately before the anchor.
- `INSERT_AFTER_EXACT`: `old: null`, non-empty `anchor`,
  `expected_count: 1`; insert `value` immediately after the anchor.
- `CREATE_EXACT`: `old: null`, `anchor: null`, `expected_count: 0`; `value`
  is the complete base document and the target must not exist.

Do not use regexes, line numbers, fuzzy anchors, scripts, generic rewrite
instructions, or multiple-match expectations. Every action and mutation must
bind at least one known `fact_id` and one governance ID from the manifest.

Use render blocks only for prose that cannot be usefully expressed as an
exact structured block in a newly created FRD:

```json
{
  "render_id": "RB-001",
  "placeholder": "{{RENDER:RB-001}}",
  "purpose": "bounded prose purpose",
  "fact_ids": ["FACT-001"],
  "governance_refs": ["GOV-001"],
  "required_literals": ["literal that must appear"],
  "forbidden_literals": ["검토 필요"],
  "max_chars": 1200
}
```

The renderer may phrase only the bound facts. Therefore include every literal,
limit, identifier, and prohibition necessary to make the block deterministic.
Do not use render blocks for headings, IDs, links, tables, status, versions,
history, acceptance criteria, tests, authority decisions, or cross-document
relations; encode those in `CREATE_EXACT` or exact mutations.

Relations must be structured and fact-bound. FRD creation requires an
`FC_FRD_TRACE` relation. ADR decisions require an `ADR_DISPOSITION` relation
with explicit authority IDs and catalog outcome. Do not leave stale
`검토 필요`, `미작성`, TASK citations, or contradictory version/history text.

Examples of the remaining arrays:

```json
{
  "relations": [
    {
      "relation_id": "REL-001",
      "kind": "FC_FRD_TRACE",
      "source_path": "Docs/App/App-FC.md",
      "target_path": "Docs/App/FRD/App-FRD-014.md",
      "feature_id": "F014",
      "authority_ids": [],
      "outcome": "CREATE_AND_TRACE",
      "requirement": "FC, FRD acceptance, and FRD tests agree",
      "verification": "MECHANICAL"
    }
  ],
  "risk_flags": [
    {
      "risk_id": "RISK-001",
      "description": "bounded residual risk",
      "evidence": ["path §section"]
    }
  ],
  "questions": [
    {
      "question_id": "Q-001",
      "question": "one authority decision required",
      "evidence": ["path §section"]
    }
  ],
  "unsupported_changes": [
    {
      "change_id": "UNSUPPORTED-001",
      "path": "Docs/App/App-FC.md",
      "reason": "why exact operations cannot safely express the change"
    }
  ]
}
```

Do not write `result_path`. The runner validates this artifact and derives the
completion envelope.
