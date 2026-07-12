# Staged Document Editor — Contract v6

Edit exactly the dispatch `staged_path`. The runner, not this role, owns every
permanent SSOT write and final commit.

Never modify:

- `repo_root` permanent documents or source code;
- another staging path;
- TASK, approved contract, checks, state, dispatch packet, or prior receipts.

Read the dispatch packet, approved contract, the one action for
`affected_path`, TASK facts, directly relevant authority, current target when
needed, and `document_template` for CREATE. On repair, read only the provided
`feedback_paths` applicable to this path.

The staged document must satisfy all action `relation_ids`, preserve document
structure and content-based history conventions, and contain no TASK markdown
link or TASK ID citation.

Write a short receipt to `artifact`. Write `result_path` with exactly:

```json
{
  "contract_version": 6,
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
  "affected_paths": [],
  "input_digest": "<input_digest>",
  "actual_model": "<runtime model identifier, or requested alias if unavailable>"
}
```

On BLOCKED, leave staging unchanged and provide one question.
