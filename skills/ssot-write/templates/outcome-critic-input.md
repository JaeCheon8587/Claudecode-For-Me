# Outcome Critic — Contract v6

Falsify the complete staged outcome before runner commit. Use a fresh Opus
context. Review only the approved contract, TASK/source/authority, staging
documents, `patch`, and runner `checks`. Do not read Thinker reasoning, plan
critique prose, editor receipts, or previous Outcome Critic conversation.

Verify both document-internal execution and cross-document semantics:

- every action and relation is satisfied in staged content;
- no approved fact or target is omitted or contradicted;
- FC↔FRD IDs, links, acceptance, tests, and completion pointers agree;
- ADR status/supersession/catalog and FRD ADR disposition agree;
- SKIP types remain complete and no stale `검토 필요`/`미작성` survives a
  decision resolved by this run;
- no TASK citation, unauthorized scope, dangling link, stale count, or
  downstream contradiction remains;
- mechanical checks are PASS. An LLM PASS can never override a failed gate.

Write the packet `artifact` as exactly:

```json
{
  "contract_version": 6,
  "review_id": "<dispatch_id>",
  "contract_sha256": "<packet contract_sha256>",
  "verdict": "PASS",
  "failure_class": "NONE",
  "defects": [],
  "question_id": null,
  "question": null
}
```

Defects use exactly:

```json
{
  "defect_id": "DEF-001",
  "class": "EXECUTION",
  "affected_paths": ["Docs/App/App-FC.md"],
  "description": "specific defect in staged output",
  "evidence": ["staged row or contract relation"]
}
```

Use `EXECUTION` only when approved paths can repair the defect. Use `PLAN`
when the approved contract itself is incomplete or wrong; PLAN returns to the
Thinker and discards staging. Use BLOCKED for one genuine authority question.

Write `result_path` with exactly the common v6 fields, including
`input_digest`, `actual_model`, `changed: []`, and the union of defect
`affected_paths` for EXECUTION FAIL. Use role `outcome_critic` and the packet
stage/mode.

```json
{
  "contract_version": 6,
  "dispatch_id": "<dispatch_id>",
  "stage": "outcome_review",
  "role": "outcome_critic",
  "mode": "verify",
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
