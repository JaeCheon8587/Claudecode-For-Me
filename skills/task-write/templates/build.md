# task-write Build

## Objective

{{OBJECTIVE}}

## Paths

| Key | Absolute Path |
|---|---|
| Repository | `{{REPO_ROOT}}` |
| App | `{{APP}}` |
| Task Id | `{{TASK_ID}}` |
| TASK | `{{TASK_PATH}}` |
| Requirement | `{{REQUIREMENT_PATH}}` |
| Template | `{{TEMPLATE_PATH}}` |
| Helper | `{{HELPER_PATH}}` |
| Process | `{{PROCESS_PATH}}` |
| Plan | `{{PLAN_PATH}}` |
| Changes | `{{CHANGES_PATH}}` |
| Review | `{{REVIEW_PATH}}` |
| Handoff | `{{HANDOFF_PATH}}` |

## Roles

| Role | Model | Output |
|---|---|---|
| Main | Opus | build.md, progress.md, requirement.md, handoff.json |
| Planner | Opus | plan.json |
| Writer | Sonnet | TASK 파일, changes.json |
| Critic | Opus | review.json |

## Fixed Flow

```text
Planner → Writer → Critic SUCCESS → Handoff
   ▲                  │
   └──── FAIL ────────┘
```

- Maximum Critic cycles: 3
- Output scope: TASK 파일 1개만 생성. NOOP 없음(항상 CREATE). REPAIR target도 동일 TASK 파일 1개.
- Critic comparison: 요구사항 원문 ↔ 실제 TASK 파일; 정확히 네 의미 check + check-task 구조 검증; Plan 무시
- Critic FAIL: Planner부터 REPAIR cycle; FAIL finding 관련만
- Third Critic FAIL: MANUAL_REQUIRED
- Main 완전 비대화형: 사용자 질문 없음. App·요구사항 부족 시 FAILED
- Resume, audit, commit, SSOT 접촉: unsupported
