# pipeline-runner Skill Catalog

이 문서는 pipeline-runner가 조합할 수 있는 스킬의 입출력과 게이트를 요약한다. 실제 실행 시에는 반드시 각 `skills/<skill>/SKILL.md`를 읽고 그 지침을 따른다.

| Skill | Input | Required Params | Expected Output | Gate | Next Input |
|---|---|---|---|---|---|
| task-write | requirement-spec 산출물 또는 자연어 요구 | `--from <requirement-path>`, optional `--app <APP>` | `docs/<App>/TASK/<App>-TASK-<NNN>.md` | TASK audit pass 또는 AUDIT_BLOCKED 기록 | TASK path |
| ssot-write | TASK path, thin main session | optional `--app <APP>`, optional `--process <path>` | SSOT CREATE/UPDATE, Contract v8 source/index/authority/governance, runner-owned evidence catalog·Authority 후보 coverage receipt·정규화 인증서, certificate-bound ClaimSpec, deterministic compiled preview/FRD, Change/Outcome certificates, approved contract, structured staging, optional bounded prose JSON, checks, commit receipt, 한국어 `final-report.txt` | `run_status: terminal` + `terminal_result: DONE|NOOP` + `downstream: WORK_PACKET`; 다른 terminal 결과·BLOCKED·revision cap이면 중단 | TASK path + ssot process dir |
| work-packet-write | TASK path + ssot process | optional `--app <APP>`, `--process <process-dir>` | `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md` | Work Packet `Ready`, Blocking none | Work Packet path |
| forge-scope | Work Packet path 또는 TASK path | optional `--name <slug>` | forge worktree branch, `.process/<docName>/forge-scope-build.md` | build/test pass | forge slug |
| ddr-loop | forge slug | optional `--docs <doc...>` | 문서 기준 conformance 수렴 결과 | conformance >= 99 또는 cap 결과 기록 | forge branch |
| branch-review | branch diff | optional ref, optional `--spec <path>`, optional `--resume` | `.review/branch-review-<short-sha>.md` | review report saved | final report |

## Linking Rules

- `task-write -> forge-scope` 경로에서는 TASK가 `forge-scope` legacy 입력이다.
- `ssot-write`가 `terminal_result: DONE|NOOP`, `downstream: WORK_PACKET`으로 끝난 경로에서만 `work-packet-write`를 실행한다. OBSOLETE/REWRITE_REQUIRED/실패 terminal은 해당 분기에서 중단하거나 task-write로 되돌린다.
- runner가 검증한 mandatory Authority Certificate와 동결한 `approved-contract.json`의 6종 coverage + atomic claims + exact action paths/mutations + relations가 structured staging과 commit 원본이다. 신규 FRD는 runner가 hash-bound canonical 20절 template contract와 claims로 조립하며 model-authored 전체 FRD/`CREATE_EXACT`를 허용하지 않는다. 선택적 Sonnet renderer는 certificate/ClaimSpec에 결속된 bounded prose artifact JSON만 만들며 경로 쓰기 권한이 없다. `ssot-write-build.md`는 target별 matrix와 관계/authority constraint를 펼친 work-packet-write 호환 view다. pipeline-runner가 certificate·계약 본문을 메인 컨텍스트로 복사하지 않는다.
- Authority/ClaimSpec/Change/Outcome 역할은 runner가 만든 hash-bound file/byte budget packet만 읽고 exact path/line/quote evidence를 제출한다. Change Critic 통과와 별도 interactive risk approval은 서로 대체하지 않으며, wrapper는 v5/v6/v7 process를 각 구버전 runner로 재개하고 신규 실행만 v8로 시작한다.
- 같은 build의 `Input Precedence and Downstream Constraints`는 work-packet-write가 직접 읽는다. `CURRENT_SSOT_WINS` authority는 matrix가 SKIP이어도 Work Packet Required 입력이 된다.
- pipeline-runner 메인은 `ssot-write` TASK/SSOT/역할 템플릿/subagent artifact를 사전 열람하지 않고 runner action/result만 중계한다.
- `work-packet-write` 결과가 `Draft`이면 `forge-scope`를 실행하지 않는다.
- Work Packet 기반 `forge-scope` 이후 `ddr-loop`은 `--docs`를 생략할 수 있다. ddr-loop가 Work Packet + 연결 TASK + Required SSOT를 자동 구성한다.
- `branch-review`는 마지막 검증 단계이며 소스 파일을 수정하지 않는다.

## Status Values

pipeline-runner progress에서 단계 상태는 다음 값만 사용한다.

```text
pending / doing / done / blocked / skipped
```
