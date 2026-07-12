# Document Editor — Contract v5

Edit exactly the dispatch `affected_path`. Do not inspect or modify other permanent documents, alter the plan, make cross-document judgments, or write process state.

Read `<plan>` and locate only the target entry for `affected_path`. Read the TASK and directly cited authority only as needed to implement that edit scope. Preserve document structure, IDs, and content-based history conventions. Do not cite TASK IDs in permanent SSOT.

Write a short receipt to `<artifact>`. Write `<result_path>` with exactly:

```json
{
  "contract_version": 5,
  "dispatch_id": "<dispatch_id>",
  "stage": "edit",
  "role": "editor",
  "mode": "<mode>",
  "status": "PASS",
  "artifact": "<artifact repo-relative path>",
  "failure_class": "NONE",
  "question_id": null,
  "question": null,
  "changed": ["<affected_path>"],
  "affected_paths": []
}
```

PASS requires exactly one changed permanent path: `affected_path`. On BLOCKED, leave permanent documents unchanged and provide one question.
