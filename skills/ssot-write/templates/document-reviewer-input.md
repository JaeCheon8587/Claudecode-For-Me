# Document Reviewer — Contract v5

Review exactly the dispatch `affected_path`. Check the compiled target scope, TASK meaning, authority, and the current content of that one document. Do not perform global plan coverage or cross-document consistency review. Do not modify permanent documents.

Write findings to `<artifact>`. Write `<result_path>` using the common v5 result fields. Use:

- PASS: `failure_class: NONE`, `affected_paths: []`
- FAIL: `failure_class: EXECUTION`, `affected_paths: ["<affected_path>"]`
- BLOCKED: one question, no affected paths

The result must also include `changed: []` and all common fields: `contract_version`, `dispatch_id`, `stage`, `role`, `mode`, `status`, `artifact`, `failure_class`, `question_id`, `question`, `changed`, `affected_paths`.
