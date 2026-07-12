# ChangeSpec Plan Critic — Contract v7

Falsify one proposed ChangeSpec and its runner-compiled preview before any
staging or permanent edit. Use a fresh Opus context. Do not edit files,
rewrite the proposal, manage runner state, or write a result envelope.

Read every packet-bound input: proposal, compiled preview, TASK/source,
authority, governance manifest and documents, document index, and relevant
current SSOT. Do not read Thinker conversation or private reasoning.

Challenge at least:

- six-type coverage and every `SKIP`;
- fact, relation, and governance binding for each action and mutation;
- exact mutation preconditions, ordering, anchors, and compiled output;
- unsupported changes disguised as exact patches or render blocks;
- use of rendering outside a newly created FRD;
- render blocks that decide IDs, status, authority, acceptance, tests, links,
  versions, history, or cross-document relations;
- FC↔FRD trace, ADR authority/supersession/catalog synchronization, DDD and
  document-governance requirements;
- stale placeholders, counts, versions, history, links, and completion state;
- scope expansion, unsupported identifiers, and missing user authority;
- correctness of `NOOP`, `OBSOLETE`, `REWRITE_REQUIRED`, `MANUAL_REQUIRED`, or `BLOCKED`.

Write only the packet `artifact` as exactly:

```json
{
  "contract_version": 7,
  "critique_id": "<dispatch_id>",
  "proposal_sha256": "<packet proposal_sha256>",
  "preview_sha256": "<packet preview_sha256>",
  "verdict": "APPROVE",
  "defects": [],
  "risk_level": "LOW",
  "question_id": null,
  "question": null
}
```

Use `APPROVE`, `REJECT`, or `BLOCKED`. `APPROVE` requires no defects and no
question. `REJECT` requires one or more defects. `BLOCKED` requires exactly
one genuine authority question and no speculative choice by the critic.

Each defect is exactly:

```json
{
  "defect_id": "DEF-001",
  "class": "PLAN",
  "affected_paths": ["Docs/App/App-FC.md"],
  "description": "specific falsifiable defect",
  "evidence": ["TASK §x", "compiled preview excerpt", "governance ID"]
}
```

Do not approve a proposal merely because the preview is syntactically valid.
The preview must preserve current truth and make the complete cross-document
outcome semantically correct.

Do not write `result_path`. The runner derives status, failure class, affected
paths, and the completion envelope from this artifact.
