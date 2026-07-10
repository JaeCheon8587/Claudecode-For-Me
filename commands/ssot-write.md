---
description: TASK를 기준으로 Opus thinker/auditor와 Sonnet actor를 오케스트레이션해 영구 SSOT를 갱신한다.
argument-hint: "<TASK-path> [--app <APP>] [--name <slug>] [--resume]"
---

$ARGUMENTS 인자로 ssot-write 스킬을 실행하라.

`skills/ssot-write/SKILL.md`를 읽고 멀티 에이전트 역할·모델·컨텍스트 보존 계약을 그대로 따른다.

인자 규칙:

- `<TASK-path>`는 필수다.
- TASK 경로는 `docs/<App>/TASK/<App>-TASK-<NNN>.md` 형식이어야 한다.
- `--app <APP>`가 있으면 TASK 경로의 App과 일치해야 한다.
- `--name <slug>`가 없으면 TASK 파일 stem을 `.process/<slug>/` 이름으로 사용한다.
- `--resume`이면 Sonnet bootstrap actor가 `.process/<slug>/ssot-write-progress.md`를 읽고 미완 단계부터 재개한다.

오케스트레이션 계약:

- 이 명령은 Opus 메인 세션에서 실행한다. 메인은 오케스트레이션만 수행한다.
- 메인은 TASK/SSOT 본문, 전체 diff, process artifact 전문을 읽거나 파일을 직접 수정하지 않는다.
- Opus planning thinker가 TASK 검증, 영향 분석, `Confirmed SSOT Action Matrix` 확정을 수행한다.
- Sonnet actor가 bootstrap, 확정 SSOT 수정, 감사 지시 기반 repair와 process finalize를 수행한다.
- Opus consistency auditor가 수정 후 독립 감사를 수행한다.
- 상세 인계는 `.process/<slug>/ssot-write-impact.md`, `ssot-write-action.md`, `ssot-write-audit.md`로 전달한다.
- 메인은 각 에이전트의 짧은 status envelope만 받아 gate와 사용자 질문을 처리한다.
- 서브에이전트를 사용할 수 없으면 메인이 fallback하지 않고 `AUDIT_BLOCKED - required subagent unavailable`로 중단한다.

역할 템플릿:

- Planning thinker: `skills/ssot-write/templates/impact-planner-input.md` (`model: "opus"`)
- SSOT actor: `skills/ssot-write/templates/ssot-actor-input.md` (`model: "sonnet"`)
- Consistency auditor: `skills/ssot-write/templates/consistency-auditor-input.md` (`model: "opus"`)

절대 금지:

- 메인 orchestrator의 원문 탐색과 직접 파일 수정
- thinker/auditor의 TASK 또는 영구 SSOT 수정
- actor의 TASK 수정과 confirmed matrix 밖 범위 확장
- 영구 SSOT의 TASK markdown link 또는 TASK ID 직접 인용
- 모호한 영향 범위나 신규/기존 기능 판단의 임의 확정

결과 보고 형식:

```text
UPDATE/CREATE <SSOT paths>
Process: .process/<TASK-stem>/
Audit: PASS | FAIL | AUDIT_BLOCKED - required subagent unavailable
Next: work-packet-write
```
