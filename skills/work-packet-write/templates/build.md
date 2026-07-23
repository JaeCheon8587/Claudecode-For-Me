# work-packet-write Build

## Objective

{{OBJECTIVE}}

## Paths

| Key | Absolute Path |
|---|---|
| Repository | `{{REPO_ROOT}}` |
| App | `{{APP}}` |
| WP Id | `{{WP_ID}}` |
| Work Packet | `{{WP_PATH}}` |
| TASK | `{{TASK_PATH}}` |
| Handoff Source (ssot-write) | `{{HANDOFF_PATH}}` |
| Template | `{{TEMPLATE_PATH}}` |
| Helper | `{{HELPER_PATH}}` |
| Process | `{{PROCESS_PATH}}` |
| Manifest | `{{MANIFEST_PATH}}` |
| Review | `{{REVIEW_PATH}}` |
| Handoff (out) | `{{HANDOFF_OUT_PATH}}` |

## Agent Definitions

| Role | AGENT_DEFINITION_PATH |
|---|---|
| Builder | `{{WP_BUILDER_DEF}}` |
| Critic | `{{WP_CRITIC_DEF}}` |

## Roles

| Role | Model | Output |
|---|---|---|
| Main | Opus | build.md, progress.md, handoff.json |
| Builder | Opus | Work Packet 파일, manifest.json |
| Critic | Opus | review.json |

## Fixed Flow

```text
Builder → Critic SUCCESS → Handoff
   ▲                │
   └──── FAIL ──────┘
```

- Maximum Critic cycles: 3
- Output scope: Work Packet 파일 1개(CREATE). Ready 또는 Draft.
- Critic 관심사: **링킹 정확성만**(ROUTER-DISCIPLINE·LINK-COVERAGE·LINK-VALIDITY·LINK-TRACEABILITY·GATE-LINKAGE). 내용 참/거짓 판정 금지.
- Critic: 5 check 중 하나라도 FAIL → 무조건 FAIL. Plan 없음 — expected는 handoff에서 재도출.
- Critic FAIL: Builder부터 REPAIR cycle(링킹 결함만).
- Third Critic FAIL: MANUAL_REQUIRED (handoff 없음).
- Main 완전 비대화형: 사용자 질문 없음. handoff 불량/부재 시 BLOCKED, 그 외 부족 시 FAILED.
- 경로 2원화: dispatch key=절대경로, JSON 기록 필드=REPO_ROOT 기준 상대경로.
- Main은 에이전트 출력 본문을 절대로 읽지 않는다. 라우팅은 반환 토큰으로만.
- 모든 Agent 호출: general-purpose 실제 독립 에이전트. prompt 첫 줄 고정 + KEY=절대경로만 전달.
