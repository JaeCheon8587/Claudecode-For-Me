# ssot-write Build

## Objective

{{OBJECTIVE}}

## Paths

| Key | Absolute Path |
|---|---|
| Repository | `{{REPO_ROOT}}` |
| TASK | `{{TASK_PATH}}` |
| Process | `{{PROCESS_PATH}}` |
| Plan | `{{PLAN_PATH}}` |
| Changes | `{{CHANGES_PATH}}` |
| Review | `{{REVIEW_PATH}}` |
| Handoff | `{{HANDOFF_PATH}}` |

## Roles

| Role | Model | Output |
|---|---|---|
| Main | Opus | build.md, progress.md, handoff.json |
| Planner | Opus | plan.json |
| Writer | Sonnet | SSOT, changes.json |
| Critic | Opus | review.json |

## Fixed Flow

```text
Planner → Writer → Critic SUCCESS → Handoff
   ▲                  │
   └──── FAIL ────────┘
```

- Maximum Critic cycles: 3
- Critic comparison: TASK core meaning ↔ actual SSOT projection; exactly four semantic checks; Plan ignored
- NOOP: Planner → Critic; Writer skipped
- Critic FAIL: Planner부터 REPAIR cycle; failed targets only
- Third Critic FAIL: MANUAL_REQUIRED
- Resume, audit, commit: unsupported
