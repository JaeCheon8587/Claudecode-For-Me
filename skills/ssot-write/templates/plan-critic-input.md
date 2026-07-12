# Plan Critic — Contract v6

Falsify one proposed SSOT contract before any permanent or staged edit. Use a
fresh Opus context. Do not edit files, rewrite the proposal, manage state, or
defer a detectable contradiction to the outcome review.

Read the dispatch packet, proposal, TASK, source, authority, document index,
and relevant current SSOT documents. Do not read Thinker conversation or
private reasoning. Challenge at least these surfaces:

- six-type coverage and wrong `SKIP`/missing target;
- contradictions between actions, skips, and relations;
- FC↔FRD trace obligations, including §17 acceptance and §18 tests;
- ADR authority, supersession, catalog synchronization, and resolved outcomes;
- `NOOP`, `OBSOLETE`, and `REWRITE_REQUIRED` disposition correctness;
- stale placeholders that the approved actions would make false;
- scope expansion, unsupported identifiers, and missing user authority.

Write the packet `artifact` as exactly:

```json
{
  "contract_version": 6,
  "critique_id": "<dispatch_id>",
  "proposal_sha256": "<packet proposal_sha256>",
  "verdict": "APPROVE",
  "defects": [],
  "risk_level": "LOW",
  "question_id": null,
  "question": null
}
```

A defect is exactly:

```json
{
  "defect_id": "DEF-001",
  "class": "PLAN",
  "affected_paths": ["Docs/App/App-FC.md"],
  "description": "specific falsifiable defect",
  "evidence": ["TASK §x", "current document row"]
}
```

Use `APPROVE`, `REJECT`, or `BLOCKED`. `REJECT` returns result `FAIL` with
`failure_class: PLAN`; `BLOCKED` supplies one authority question. `APPROVE`
must have no defects.

Write `result_path` with exactly the common v6 fields, including
`input_digest`, `actual_model`, `changed: []`, and `affected_paths: []`.
Use role `plan_critic`, the packet stage/mode, and status matching the verdict.

```json
{
  "contract_version": 6,
  "dispatch_id": "<dispatch_id>",
  "stage": "plan_critique",
  "role": "plan_critic",
  "mode": "challenge",
  "status": "PASS",
  "artifact": "<artifact repo-relative path>",
  "failure_class": "NONE",
  "question_id": null,
  "question": null,
  "changed": [],
  "affected_paths": [],
  "input_digest": "<input_digest>",
  "actual_model": "<runtime model identifier, or requested alias if unavailable>"
}
```
