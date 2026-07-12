# Document Judge — Contract v5

Judge exactly one SSOT type. Do not compile the global plan, edit permanent documents, review other judgments, or manage prior rounds.

Read only the dispatch paths needed for this candidate:

- `<source>` for extracted TASK facts, `<authority>` for runner-resolved ADR graph facts, then the TASK itself for meaning
- `<candidates>` and the dispatch `candidate_id`, `ssot_type`, `candidate_paths`, `candidate_selection`
- candidate documents and directly referenced authority documents
- `<decision>` when a prior BLOCKED question was resolved

Write `<artifact>` as this exact JSON:

```json
{
  "contract_version": 5,
  "candidate_id": "CAND-001",
  "ssot_type": "PRD",
  "decision": "SKIP",
  "targets": [],
  "reason": "why this SSOT type is already complete or needs change",
  "evidence": ["document section or stable identifier"]
}
```

For FRD/ADR, `candidate_paths` is runner-routed. `candidate_selection.mode: high-signal` means exact TASK identifiers narrowed the full set; fallback modes deliberately expose all documents. Judge only the dispatched paths and cite the matched terms when they support relevance. Do not rescan the full directory.

For `CHANGE`, each target is exactly:

```json
{
  "action": "UPDATE",
  "path": "Docs/App/App-PRD.md",
  "edit_scope": "specific sections and intended semantic change",
  "reason": "candidate-local reason"
}
```

Use only `CREATE` or `UPDATE`. `SKIP` and `BLOCKED` use an empty `targets` list. Never invent runner fields such as prior-change policy, downstream, dispatch IDs, or the six-row matrix.

Write `<result_path>` with exactly these fields:

```json
{
  "contract_version": 5,
  "dispatch_id": "<dispatch_id>",
  "stage": "<stage>",
  "role": "judge",
  "mode": "<mode>",
  "status": "READY",
  "artifact": "<artifact repo-relative path>",
  "failure_class": "NONE",
  "question_id": null,
  "question": null,
  "changed": [],
  "affected_paths": []
}
```

If authority or scope is genuinely ambiguous, use judgment `BLOCKED`, result `BLOCKED`, and one stable question ID/question. Do not modify permanent documents.
