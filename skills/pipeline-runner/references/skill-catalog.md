# pipeline-runner Skill Catalog

이 문서는 pipeline-runner가 조합할 수 있는 스킬의 입출력과 게이트를 요약한다. 실제 실행 시에는 반드시 각 `skills/<skill>/SKILL.md`를 읽고 그 지침을 따른다.

| Skill | Input | Required Params | Expected Output | Gate | Next Input |
|---|---|---|---|---|---|
| task-write | requirement-spec 산출물 또는 자연어 요구 | `--from <requirement-path>`, optional `--app <APP>` | `docs/<App>/TASK/<App>-TASK-<NNN>.md` | TASK audit pass 또는 AUDIT_BLOCKED 기록 | TASK path |
| ssot-write | TASK path | optional `--app <APP>`, optional `--name <slug>` | SSOT CREATE/UPDATE, `.process/<TASK-stem>/ssot-write-build.md` | consistency audit pass 또는 blocked 없음 | TASK path + ssot process dir |
| work-packet-write | TASK path + ssot process | optional `--app <APP>`, `--process <process-dir>` | `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md` | Work Packet `Ready`, Blocking none | Work Packet path |
| forge-scope | Work Packet path 또는 TASK path | optional `--name <slug>` | forge worktree branch, `.process/<docName>/forge-scope-build.md` | build/test pass | forge slug |
| ddr-loop | forge slug | optional `--docs <doc...>` | 문서 기준 conformance 수렴 결과 | conformance >= 99 또는 cap 결과 기록 | forge branch |
| branch-review | branch diff | optional ref, optional `--spec <path>`, optional `--resume` | `.review/branch-review-<short-sha>.md` | review report saved | final report |

## Linking Rules

- `task-write -> forge-scope` 경로에서는 TASK가 `forge-scope` legacy 입력이다.
- `ssot-write`를 실행한 경로에서는 반드시 `work-packet-write`를 실행해 Work Packet을 만든다.
- `work-packet-write` 결과가 `Draft`이면 `forge-scope`를 실행하지 않는다.
- Work Packet 기반 `forge-scope` 이후 `ddr-loop`은 `--docs`를 생략할 수 있다. ddr-loop가 Work Packet + 연결 TASK + Required SSOT를 자동 구성한다.
- `branch-review`는 마지막 검증 단계이며 소스 파일을 수정하지 않는다.

## Status Values

pipeline-runner progress에서 단계 상태는 다음 값만 사용한다.

```text
pending / doing / done / blocked / skipped
```
