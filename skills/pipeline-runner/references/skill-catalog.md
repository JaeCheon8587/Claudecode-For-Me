# pipeline-runner Skill Catalog

이 문서는 pipeline-runner가 조합할 수 있는 스킬의 입출력과 게이트를 요약한다. 실제 실행 시에는 반드시 각 `skills/<skill>/SKILL.md`를 읽고 그 지침을 따른다.

| Skill | Input | Required Params | Expected Output | Gate | Next Input |
|---|---|---|---|---|---|
| task-write | requirement-spec 산출물 또는 자연어 요구 | `--from <requirement-path>`, optional `--app <APP>` | `docs/<App>/TASK/<App>-TASK-<NNN>.md` | TASK audit pass 또는 AUDIT_BLOCKED 기록 | TASK path |
| ssot-write | TASK path, Opus Main | optional `--app <APP>`, optional `--process <path>` | `build.md`, `progress.md`, `plan.json`, `review.json`, `handoff.json`; READY는 SSOT CREATE/UPDATE + `changes.json` 추가 | progress/handoff `SUCCESS` + Critic `SUCCESS`; `FAILED`·`MANUAL_REQUIRED`면 중단 | TASK path + ssot process dir |
| work-packet-write | TASK path + ssot process | optional `--app <APP>`, `--process <process-dir>` | `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md` | Work Packet `Ready`, Blocking none | Work Packet path |
| forge-scope | Work Packet path 또는 TASK path | optional `--name <slug>` | forge worktree branch, `.process/<docName>/forge-scope-build.md` | build/test pass | forge slug |
| ddr-loop | forge slug | optional `--docs <doc...>` | 문서 기준 conformance 수렴 결과 | conformance >= 99 또는 cap 결과 기록 | forge branch |
| branch-review | branch diff | optional ref, optional `--spec <path>`, optional `--resume` | `.review/branch-review-<short-sha>.md` | review report saved | final report |

## Linking Rules

- `task-write -> forge-scope` 경로에서는 TASK가 `forge-scope` legacy 입력이다.
- `ssot-write`의 `progress.md`와 `handoff.json`이 모두 `SUCCESS`로 끝난 경로에서만 `work-packet-write`를 실행한다.
- Opus Main은 Opus Planner, Sonnet Writer, Opus Critic을 실제 독립 서브에이전트로 호출한다. Writer만 SSOT를 수정하고 Critic은 Plan을 읽지 않은 채 TASK 핵심 의미와 실제 SSOT 투영을 네 의미 축으로 최대 3회 비교한다.
- `plan.json`은 Writer 실행 입력이며 Critic 기준이 아니다. `changes.json`은 실제 파일·섹션 변경을 cycle 간 누적한다. Critic FAIL은 Planner가 review를 읽어 실패 target만 포함한 REPAIR 계획을 작성한다. `handoff.json`은 후속 단계의 단일 machine input이다.
- pipeline-runner 메인은 ssot-write 역할을 대신하거나 agent artifact를 재작성하지 않는다. 신규 실행에서 legacy `scripts/ssot_runner.py`를 호출하지 않는다.
- `work-packet-write` 결과가 `Draft`이면 `forge-scope`를 실행하지 않는다.
- Work Packet 기반 `forge-scope` 이후 `ddr-loop`은 `--docs`를 생략할 수 있다. ddr-loop가 Work Packet + 연결 TASK + Required SSOT를 자동 구성한다.
- `branch-review`는 마지막 검증 단계이며 소스 파일을 수정하지 않는다.

## Status Values

pipeline-runner progress에서 단계 상태는 다음 값만 사용한다.

```text
pending / doing / done / blocked / skipped
```
