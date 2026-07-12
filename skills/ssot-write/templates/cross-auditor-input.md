# Cross-document Auditor — Contract v5

Audit relationships only after every changed document passed its isolated review. Do not redo document editing or create the plan.

Read `<plan>`, `<patch>`, reviewer artifacts, current changed documents, and runner mechanical checks. Verify:

- the six isolated judgments collectively cover PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE;
- changed SSOT meanings agree across document boundaries;
- identifiers, ADR status/catalog relationships, and downstream outcome are coherent;
- no missing candidate requires a different isolated judgment.
- FRD/ADR candidate routing used high-signal matches or an explicit full-set fallback; do not silently assume unselected paths were semantically reviewed.

Do not modify permanent documents. Write `<artifact>` and the common v5 result JSON to `<result_path>`.

- PASS: `failure_class: NONE`, `affected_paths: []`
- FAIL/EXECUTION: list only changed paths needing another edit
- FAIL/PLAN: `affected_paths: []`; runner will re-run isolated judges
- BLOCKED: provide one question

Always include exactly the common fields: `contract_version`, `dispatch_id`, `stage`, `role`, `mode`, `status`, `artifact`, `failure_class`, `question_id`, `question`, `changed`, `affected_paths`.
