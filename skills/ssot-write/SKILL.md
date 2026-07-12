---
name: ssot-write
description: TASK를 기준으로 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 영구 SSOT를 갱신한다. Contract v8 runner가 mandatory Opus Authority Certificate, Opus ClaimSpec, deterministic preview·FRD assembly, fresh Opus Change/Outcome Critic, 선택적 bounded Sonnet prose, journaled commit/rollback을 강제한다. ssot-write, TASK 기반 SSOT 갱신, 안전한 SSOT 반영, 권위·governance 검증이 필요한 요청에 사용한다.
---

# ssot-write

`Docs/<App>/TASK/<App>-TASK-<NNN>.md`를 Scope Authority로 삼아 영구
SSOT를 좁게 갱신한다.

## 한국어 강제 계약

**모든 과정과 결과의 자연어는 반드시 한국어로 작성한다.** 메인 진행 보고,
서브에이전트 판단, `finding`·`statement`·`reason`·`description`·`question`,
선택적 설명문, process 빌드/진행 문서, 사용자 질문, 최종 네 줄 보고 모두
한국어를 사용한다. JSON key, protocol enum, ID, SHA, 파일 경로, 코드·설정
literal처럼 기계 일치가 필요한 토큰만 원문을 유지한다. runner는 역할 artifact의
자연어 필드에 한글이 없으면 `KOREAN_LANGUAGE_REQUIRED`로 거절한다. 메인은
영문 recap이나 별도 설명을 최종 보고에 덧붙이지 않는다.

## Contract v8

`scripts/ssot_runner.py`를 유일한 control plane으로 사용한다. 메인은
`init → next → dispatch → accept-artifact`만 반복한다. TASK/SSOT,
Authority Certificate, ClaimSpec, preview, staging, patch, critic artifact를
읽고 판단하지 않는다.

| 단계 | 소유자 | 단일 책임 | 영구 SSOT 쓰기 |
|---|---|---|---|
| Source/Index/Authority/Governance | runner | TASK 사실·문서 색인·ADR 그래프·governance hash와 bounded evidence packet 생성 | 없음 |
| Authority Critic | fresh Opus | TASK·ADR·DDD·문서 governance를 대조해 mandatory evidence certificate 생성 | 없음 |
| ClaimSpec Thinker | fresh Opus | certificate 안에서 atomic claim·관계·exact mutation을 제안 | 없음 |
| Compiled Preview / FRD Assembly | runner | exact precondition 검증, 변경 미리보기, claim 기반 FRD 골격 생성 | 없음 |
| Change Critic | fresh Opus | certificate·ClaimSpec·실제 preview를 반증 | 없음 |
| Risk Gate | runner + 사용자 | 동결된 compiled contract SHA를 대화형 사용자 승인에 결속 | 없음 |
| Structured Apply | runner | 승인 preview를 staging에 결정적으로 재현 | 없음 |
| Prose Renderer | Sonnet, 필요할 때만 | 신규 FRD의 승인된 prose block을 JSON으로 렌더링 | 없음 |
| Mechanical Gates | runner | 관계·governance·helper·ADR·hash·scope 검증 | 없음 |
| Outcome Critic | fresh Opus | 전체 staging 결과를 반증 | 없음 |
| Commit/Finalizer | runner | journaled commit·rollback·보고 | runner만 |

Authority Critic, ClaimSpec Thinker, Change Critic, Outcome Critic은 모두 새
Opus 컨텍스트로 호출한다. 이전 역할 대화나 사적 추론을 다음 역할에
전달하지 않는다. 각 역할은 서로 독립된 새 컨텍스트를 사용한다. runner는
요청 model family와 artifact 결속만 검증할 수 있으므로, 실제 새 컨텍스트
생성은 host adapter가 보장해야 하는 실행 전제다. host가 이를 보장할 수 없으면
메인이 같은 대화를 재사용하지 말고 실행을 중단한다.

## Runner 찾기와 버전

다음 순서로 첫 번째 존재 runner를 사용한다.

1. `<repo-root>/scripts/ssot_runner.py`
2. `${CLAUDE_PLUGIN_ROOT}/scripts/ssot_runner.py`

새 process는 Contract v8로 생성한다. wrapper는 기존 `state.json`의
`contract_version`을 읽어 v5, v6, v7 process를 각각 해당 구버전 runner로만
재개한다. 실행 중 process를 v8로 자동 변환하지 않는다. 같은 TASK를 v8로
다시 실행하려면 새 `--process` 경로를 사용한다.

init은 v8 runner, v8 contract module, 이 SKILL.md의 경로·SHA-256을
`implementation_fingerprint`로 동결한다. 이후 `next`, `accept-artifact`,
`resolve`에서 하나라도 달라지면 `RUNNER_CHANGED_RESTART_REQUIRED`로 거절하고
새 process 실행을 요구한다. 이전 코드 revision에서 만든 파생 산출물을 현재
runner가 암묵적으로 재사용하지 않는다.

모든 명령은 대상 repo root에서 실행한다. 기본 process는
`.process/<TASK-stem>`이다.

```text
python <runner> init --repo <repo-root> --task <TASK-path> --app <APP> [--process <process>]
python <runner> next --process <process>
```

## 메인 오케스트레이션 계약

`next` action별로 처리한다.

- `dispatch`: `prompt_path`만 runner가 지정한 role/model의 새 에이전트에
  전달한다. 역할 에이전트는 prompt를 읽고 지정된 artifact만 작성한다.
  메인은 prompt를 재작성하거나 artifact/result JSON을 고치지 않는다.
- 역할 완료 후 dispatch의 정확한 artifact와 실제 모델을 전달한다.

  ```text
  python <runner> accept-artifact --process <process> --artifact <artifact_path> --actual-model <actual_model>
  ```

  v8 메인은 `accept-result`를 호출하지 않는다. artifact가 역할 판정의 단일
  원본이며 runner가 내부 completion envelope를 파생한다. runner는
  `actual_model` 문자열이 요청한 Opus/Sonnet 계열과 일치하는지 검사하지만,
  모델 실행의 진위 증명은 호스트 adapter의 실행 metadata를 신뢰한다.
- artifact 계약 오류가 나면 `next`를 다시 실행한다. runner가 새 dispatch
  ID·새 immutable prompt packet·`last_rejection`을 발행한다. 메인이 오류를
  해석한 교정 prompt를 만들지 않는다.
- `ask_user`: 질문을 그대로 사용자에게 전달하고 답을 `resolve`로 기록한다.
  권위 질문은 사용자 답변을 `--answer`로 그대로 전달한다.
  risk approval이 아닌 답변은 기존 Authority Certificate와 모든 파생
  proposal/preview/critique를 무효화하고, 갱신된 `decision.json`을 입력으로 한
  새 Authority Critic부터 재인증한다. 새 certificate는 답변을
  `AUTH-SCOPE`와 authority fact/prohibition에 직접 결속해야 한다. 사용자
  답변을 이전 certificate에 암묵적으로 덧붙이지 않는다.
- 고위험 승인은 UI에서 실제 사용자가 승인한 이벤트만 허용한다. `next`가
  준 conflict ID와 nonce를 사용하고 새 event ID를 한 번만 쓴다.

  ```text
  python <runner> resolve --process <process> --conflict <conflict_id> --choice APPROVE \
    --actor-kind user --source interactive_user_prompt --event-id <event_id> --nonce <nonce>
  ```

  거부는 같은 provenance와 `--choice REJECT`로 기록한다. 승인 event 재사용,
  nonce 불일치, 계약 SHA 변경은 runner가 거부한다.
- `retry`: 다른 run이 App commit lock을 보유한 일시 상태다. 역할을 호출하지
  말고 `retry_after_seconds` 뒤 같은 `next`를 다시 실행한다.
- `done`: `response_mode: verbatim`, `allow_additional_text: false`를 확인하고
  `report_path`의 네 줄만 반환한다.

역할 에이전트를 사용할 수 없으면 메인이 대신 분석·편집하지 않는다.

## Authority Certificate와 ClaimSpec

Authority Critic은 `templates/v8-authority-critic-input.md`를 사용한다.
계획 전에 `AUTH-TASK-GOVERNANCE`, `AUTH-ADR-STATUS`, `AUTH-DDD-LAYER`,
`AUTH-DOC-GOVERNANCE`, `AUTH-SCOPE` 다섯 check를 모두 판정한다. 모든
authority fact·prohibition·question에는 runner가 발행한 `evidence_id`가
필요하다. 역할은 `path`·`line`·`quote`를 직접 작성하지 않는다. runner가
ID를 packet-bound 원본 byte의 실제 path·1-based line·exact quote로 확장하고
정규화된 인증서를 별도 생성한다. certificate
FAIL은 ClaimSpec으로 진행하지 않고, 증거가 부족하면 하나의 권위 질문으로
BLOCKED한다.

runner는 Authority dispatch마다 TASK의 component, Port, Client, persistence,
scheduling, composition registration 후보를 `authority-candidates`로 추출한다.
Authority Critic은 모든 `required_candidate_ids`를 정확히 한 번씩
`PASS`·`FAIL`·`BLOCKED`로 판정한다. runner는 후보 coverage, 후보 TASK 근거,
DDD/architecture/governance 규칙 근거와 `AUTH-DDD-LAYER` 합성 verdict를
검증한다. 하나라도 누락하면 `AUTHORITY_CANDIDATE_COVERAGE`로 거절한다.
러너가 추출하지 못한 의미 후보는 Critic이 `supplemental_candidates`로
추가하고 같은 artifact에서 판정한다. runner는 추가 후보도 TASK+규칙 증거와
DDD 합성 verdict에 포함한다. coverage는 추출된 유한 후보 집합과 Critic이
추가한 후보의 완전성을 보장하며, 저장소의
모든 잠재 의미 문제를 수학적으로 보장한다고 주장하지 않는다.

각 mandatory check는 역할별로 지정된 TASK/governance/contract/preview/
staging/checks source 조합을 모두 인용해야 한다. `{`, `---`, 표 구분선처럼
의미 문자가 없는 quote나 필수 source class를 충족하지 않는 인용 재사용은
runner가 거부한다. 올바른 source의 인용이 결론을 의미상 뒷받침하는지는
Critic의 책임이며 뒤의 독립 Change/Outcome Critic이 다시 반증한다. exact
citation만으로 의미적 타당성이 수학적으로 증명된다고 간주하지 않는다.

ClaimSpec Thinker는 `templates/v8-claim-thinker-input.md`를 사용한다.
통과한 certificate에 결속된 atomic claim, 여섯 SSOT coverage,
actions/skips, relations, risk flags, questions와 exact mutation만 구조화한다.
숫자·상태·레이어 배치·scope·acceptance·test 같은 의미는 renderer가 추론하지
않도록 각각 claim으로 확정한다. 각 claim/action/mutation/relation은 certificate
check와 검증 가능한 증거에 결속한다.

runner가 지원하는 mutation은 다음뿐이다.

- `REPLACE_EXACT`
- `INSERT_BEFORE_EXACT`
- `INSERT_AFTER_EXACT`

UPDATE는 `RUNNER_PATCH`만 사용한다. runner는 anchor/old text가 정확히 한 번
일치하는지 확인한 뒤
`compiled-preview.patch`와 operation receipt를 만든다. 0회·복수 일치,
지원하지 않는 변환, 사실/governance 미결속은 LLM 재량 편집으로 넘기지 않고
계약을 거부하거나 `MANUAL_REQUIRED`/`REWRITE_REQUIRED`로 종료한다.

신규 FRD는 `RUNNER_CREATE_FROM_CLAIMS`만 허용한다. model-authored 전체 문서,
`CREATE_EXACT`, raw Markdown body, multi-section 자유서술 mutation은 금지한다.
runner가 hash로 동결한 canonical FRD 20절 template contract, identity, metadata, 링크, version/history,
acceptance/test 표와 deterministic claim bullet을 조립한다. 자동 CREATE는
FRD에만 허용하며 그 밖의 문서 CREATE는 `MANUAL_REQUIRED`다.

Change Critic은 `templates/v8-change-critic-input.md`를 사용해 Authority
Certificate, ClaimSpec, 실제 compiled preview와 operation receipt를 새
컨텍스트에서 반증한다. mandatory check가 하나라도 빠지거나 evidence가
불충분하면 승인할 수 없다. runner는 모든 action ID·target path·operation
receipt가 비판 증거에 개별 포함됐는지 대조하므로 일부 action만 표본 검사해
전체 PASS할 수 없다. 승인 뒤 runner가
certificate/proposal/preview/critique/governance SHA를
`approved-contract.json`으로 동결한다.

필수 관계:

- FRD CREATE에는 `FC_FRD_TRACE`를 두고 FC 링크, §17 수용 기준, §18 테스트
  추적을 함께 검증한다.
- ADR SKIP/재사용이 신규·수정 FRD에 영향을 주면 `ADR_DISPOSITION`을 둔다.
- 코드로 확정할 수 없는 관계는 `SEMANTIC`으로 Outcome Critic에 남긴다.
- TASK 링크/ID는 영구 SSOT 본문과 변경 이력에 남기지 않는다.

disposition은 `ACTIVE`, `NOOP`, `OBSOLETE`, `REWRITE_REQUIRED`,
`MANUAL_REQUIRED`, `BLOCKED` 중 하나다.

## 별도 Risk Gate와 선택적 Sonnet prose

Change Critic 승인과 compiled contract 생성 뒤에만 별도 risk approval을
수행한다. CREATE, ADR 변경, authority conflict, 다수 target, risk flag 등은
runner가 계산하며 승인은 정확한 compiled contract SHA·nonce·일회성 interactive
user event provenance에 결속한다. Critic 승인을 사용자 승인으로 대체하거나
메인이 self-approve할 수 없다.

Sonnet은 범용 문서 편집자가 아니다. `RUNNER_CREATE_FROM_CLAIMS`로 승인된
신규 FRD에 의미가 이미 claim으로 완결된 선택적 설명 block이 있을 때만
`templates/v8-prose-renderer-input.md`로 호출한다.

- Sonnet은 staging/live 문서를 쓰지 않고 지정 artifact JSON만 쓴다.
- 승인된 render ID·claim IDs·required/forbidden literal과
  글자 제한 안에서 Markdown block만 만든다.
- 신규 사실, 정책, 수치, 문서 대상, ADR 판단, 구조 변경을 만들지 않는다.
- runner가 block coverage와 literal을 검증하고 승인 placeholder에 삽입한다.
- UPDATE와 FRD 구조·표·링크·버전·변경 이력·acceptance/test는 Sonnet 없이
  runner가 수행한다.
- 렌더링 실패는 decision을 Sonnet에게 확대하지 않는다. 결정적 fallback이
  가능할 때만 runner가 사용하며 아니면 안전한 terminal로 끝낸다.

## Governance, 검증과 commit

runner는 init에서 `CLAUDE.md`, `Docs/DOCUMENT_GUIDE.md`, 관련 rules,
guidelines, 문서 template을 `governance.json`에 경로+hash로 동결한다.
모든 의미 역할 입력에 governance를 포함하고 preview·검증·commit 전에
freshness를 다시 확인한다.

각 역할은 runner가 만든 bounded packet manifest에 열거된 파일만 읽는다. packet은
경로·hash·file/byte budget에 결속되며 역할이 directory를 탐색하거나 unbound
파일을 읽는 것은 계약 위반이다. mandatory certificate와 모든 critic check는
runner evidence ID 없이는 PASS할 수 없다. runner가 ID를 exact citation으로
정규화한다.

runner는 evidence가 packet-bound 원본과 일치하는지는 검증하지만 프로세스의
모든 read syscall을 관찰하지는 못한다. 따라서 실제 읽기 격리는 host의
filesystem sandbox/ACL이 제공해야 한다. 격리가 없는 host에서는 packet 밖
읽기 금지가 adapter 정책 경계로 남으며, runner-owned evidence와 독립 critic이 그
영향을 줄이지만 완전한 기술적 증명은 아니다.

staging overlay의 기계 검사는 다음을 포함한다.

- 승인 action 경로와 exact mutation receipt
- 미해결 render placeholder 및 TASK 링크/ID 부재
- FC↔FRD 관계, ADR disposition, version↔history 정합
- 격리 validation root의 docs helper와 ADR file/catalog status
- staging/live/read-set/governance hash와 역할 범위 밖 write

write guard는 runner의 hash 기반 사후 탐지 경계다. 호스트가 filesystem
sandbox/ACL을 제공하면 역할 artifact 경로만 writable로 실행한다. 그런 격리가
없을 때 역할이 live 파일을 직접 쓰면 runner는 `VERIFY_FAILED`로 중단하지만,
동시 사용자 변경과 구분할 수 없으므로 그 live mutation을 임의 rollback하지
않는다. 이 경우 사용자가 변경 내용을 확인해 복구해야 한다.

기계 FAIL은 Opus PASS로 덮어쓸 수 없다. deterministic action의 결함은
Sonnet repair로 보내지 않고 PLAN revision 또는 안전한 terminal로 라우팅한다.

Outcome Critic은 `templates/v8-outcome-critic-input.md`를 사용해 Authority
Certificate, approved ClaimSpec, staging, patch, renderer artifact, checks만
읽고 mandatory evidence certificate로 전체 결과를 반증한다. runner 생성
내용이나 claim/authority 결함은 PLAN으로 되돌리고, EXECUTION은 선택적 render
block에 한정한다. `OUTCOME-CROSS-DOC`은 모든 staged changed path를 개별
인용해야 한다. Sonnet repair로 승인 범위를 확대하지 않는다.

모든 검증을 통과하면 runner가 App advisory lock을 잡고 write-ahead
journal·backup/temp를 durable 상태로 만든 뒤 영구 SSOT에 반영한다.
중간 종료는 다음 `next`가 hash 기반 rollback 또는 COMMITTED roll-forward로
복구한다. 제3자 변경을 덮지 않으며 git reset/checkout을 사용하지 않는다.

## Terminal과 금지사항

정상 실패를 PASS로 수렴시키지 않는다. terminal에는 `DONE`, `NOOP`,
`OBSOLETE`, `REWRITE_REQUIRED`, `MANUAL_REQUIRED`, `USER_REJECTED`,
`PLAN_REJECTED`, `VERIFY_FAILED`, `CONTRACT_BLOCKED`,
`COMMIT_FAILED_ROLLED_BACK`, `RECOVERY_REQUIRED`가 있다.

메인은 다음을 하지 않는다.

- TASK/SSOT/Authority Certificate/ClaimSpec/contract/preview/staging/diff/artifact를 읽고 재판단
- dispatch prompt, 역할, 모델, stage 변경
- agent artifact, runner result/state/generated view 직접 수정
- Sonnet에게 영구 SSOT 또는 staging 파일 편집 지시
- Critic에 이전 역할 대화 전달
- 계약 오류 해석·교정 prompt 생성
- final report에 recap, 표, 설명, 질문 추가

완료 후 stdout과 `final-report.txt`가 일치하는지 확인한다. 보고 형식은
`갱신/생성`, `프로세스`, `감사`, `다음` 네 줄의 한국어 label만 사용한다.

```text
python <runner> report --process <process>
```
