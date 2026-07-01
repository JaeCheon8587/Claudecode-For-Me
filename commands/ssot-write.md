---
description: TASK 문서를 기준으로 영구 SSOT 문서를 갱신하고 `.process/<TASK-stem>/`에 실행계획과 진행로그를 남긴다.
argument-hint: "<TASK-path> [--app <APP>] [--name <slug>] [--resume]"
---

$ARGUMENTS 인자로 ssot-write 스킬을 실행하라.

`skills/ssot-write/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

인자 규칙:
- `<TASK-path>`는 필수다.
- TASK 경로는 `docs/<App>/TASK/<App>-TASK-<NNN>.md` 형식이어야 한다.
- `--app <APP>`가 있으면 TASK 경로의 App 과 일치해야 한다.
- `--name <slug>`가 없으면 TASK 파일 stem 을 `.process/<slug>/` 이름으로 사용한다.
- `--resume`이면 기존 `.process/<slug>/ssot-write-progress.md`를 읽고 미완 단계부터 재개한다.

필수 절차:
- `.process/<slug>/ssot-write-build.md`와 `.process/<slug>/ssot-write-progress.md`를 생성 또는 재사용한다.
- 영향 분석은 `skills/ssot-write/templates/impact-auditor-input.md`와 `skills/ssot-write/templates/impact-auditor-output.md`를 사용해 read-only 서브에이전트에 위임한다.
- 수정 후 일관성 감사는 `skills/ssot-write/templates/consistency-auditor-input.md`와 `skills/ssot-write/templates/consistency-auditor-output.md`를 사용해 read-only 서브에이전트에 위임한다.
- 서브에이전트가 사용할 수 없으면 결과의 Audit 에 `AUDIT_BLOCKED - read-only subagent unavailable`을 명시한다.

절대 금지:
- 서브에이전트가 파일을 수정하지 않는다.
- 영구 SSOT 본문에 TASK markdown link 또는 TASK ID 직접 인용을 남기지 않는다.
- 모호한 영향 범위나 신규/기존 기능 판단을 임의로 확정하지 않는다.

결과 보고 형식:

```text
UPDATE/CREATE <SSOT paths>
Process: .process/<TASK-stem>/
Audit: PASS | FAIL | AUDIT_BLOCKED - read-only subagent unavailable
Next: work-packet-write
```
