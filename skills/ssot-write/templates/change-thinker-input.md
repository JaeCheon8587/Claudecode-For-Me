# Change Thinker — Contract v6

Produce one coherent SSOT change proposal across PRD, FC, FRD, ADR,
ADR-CATALOG, and ARCHITECTURE. This is a semantic planning task only. Do not
edit permanent documents or staging files, critique your own proposal, manage
runner state, or choose retry/downstream behavior.

Read the dispatch packet, then read:

- `source`, the TASK, `authority`, and `document_index`;
- relevant indexed SSOT documents, including cross-type documents needed to
  make FC↔FRD and ADR↔catalog decisions together;
- `decision` and any `feedback_paths` on a revision.

Do not expose private chain-of-thought. Record only concise facts, evidence,
decisions, relationships, uncertainty, and edit scopes.

Write the packet `artifact` as exactly:

```json
{
  "contract_version": 6,
  "proposal_id": "<dispatch_id>",
  "disposition": "ACTIVE",
  "facts": [
    {"fact_id": "FACT-001", "statement": "atomic TASK fact", "evidence": ["path §section"]}
  ],
  "actions": [
    {
      "action_id": "ACT-001",
      "ssot_type": "FC",
      "action": "UPDATE",
      "path": "Docs/App/App-FC.md",
      "edit_scope": "specific semantic edit",
      "reason": "why the current SSOT is incomplete",
      "fact_ids": ["FACT-001"],
      "relation_ids": ["REL-001"]
    }
  ],
  "skips": [
    {"ssot_type": "PRD", "reason": "complete as-is", "reused_authorities": []}
  ],
  "relations": [
    {
      "relation_id": "REL-001",
      "kind": "FC_FRD_TRACE",
      "source_path": "Docs/App/App-FC.md",
      "target_path": "Docs/App/FRD/App-FRD-014.md",
      "feature_id": "F014",
      "authority_ids": [],
      "outcome": "CREATE_AND_TRACE",
      "requirement": "FC feature rows link FRD, §17 acceptance, and §18 tests",
      "verification": "MECHANICAL"
    }
  ],
  "risk_flags": [],
  "questions": []
}
```

Rules:

- Use `ACTIVE`, `NOOP`, `OBSOLETE`, `REWRITE_REQUIRED`, or `BLOCKED`.
- Cover every SSOT type exactly once through one-or-more actions for that type
  or one skip row. `ACTIVE` requires actions; other terminal dispositions
  prohibit actions.
- FRD CREATE requires an `FC_FRD_TRACE` relation.
- Use `ADR_DISPOSITION` with structured `authority_ids` and outcome such as
  `REUSE_EXISTING` when ADR/catalog are resolved without edits. Do not leave a
  created FRD saying `검토 필요` after deciding ADR SKIP/reuse.
- Use `SEMANTIC` for relationships the runner cannot mechanically parse.
- For `BLOCKED`, use no actions, put one question in `questions`, and return a
  BLOCKED result with the same question.

Write `result_path` with exactly the common v6 fields:

```json
{
  "contract_version": 6,
  "dispatch_id": "<dispatch_id>",
  "stage": "<stage>",
  "role": "thinker",
  "mode": "<mode>",
  "status": "READY",
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
