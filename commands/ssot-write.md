---
description: Contract v8 runner로 TASK 권위를 인증하고 ClaimSpec·deterministic preview/FRD·비판·검증 후 영구 SSOT를 commit한다.
argument-hint: "<TASK-path> [--app <APP>] [--process <path>]"
---

저장소의 `skills/ssot-write/SKILL.md`를 읽고 그대로 실행한다.

- 대상 repo runner를 먼저 사용하고 없으면 `${CLAUDE_PLUGIN_ROOT}/scripts/ssot_runner.py`를 사용한다.
- 메인은 Contract v8 `init -> next -> prompt_path role dispatch -> accept-artifact` 루프만 수행한다. v8에서 `accept-result`를 호출하지 않는다.
- 모든 진행 보고·판단·질문·산출물 자연어와 최종 보고는 한국어로 작성한다. protocol enum·ID·경로·코드 literal만 원문을 유지한다.
- 역할은 직접 `path/line/quote`를 작성하지 않고 runner evidence catalog의 `evidence_id`만 선택한다. Authority Critic은 runner가 추출한 모든 후보를 판정한다.
- dispatch의 `prompt_path`만 지정 role/model의 새 에이전트에 전달하고 prompt·role·model·path를 바꾸지 않는다.
- 새 Opus Authority Critic, ClaimSpec Thinker, Change Critic, Outcome Critic과 필요할 때만 호출하는 Sonnet FRD prose renderer 컨텍스트를 합치지 않는다.
- Authority Critic은 TASK·ADR·DDD·문서 governance에 대한 다섯 mandatory check와 exact path/line/quote 증거 certificate를 먼저 확정한다. 역할은 runner의 bounded packet 밖 파일을 탐색하지 않는다.
- runner가 certificate-bound ClaimSpec을 deterministic compiled preview와 claim 기반 신규 FRD로 검증하고, Change Critic 통과 뒤 별도 risk approval을 받은 계약만 staging에 재현한다.
- model-authored 전체 FRD, `CREATE_EXACT`, raw document body는 금지한다. Sonnet은 staging/live를 쓰지 않고 승인된 신규 FRD의 선택적 bounded prose block JSON만 작성하며 실패 시 runner deterministic claim bullet로 fallback한다.
- artifact 계약 오류는 `next`가 새 immutable retry packet과 `last_rejection`으로 다시 dispatch한다. 메인이 오류를 해석하거나 artifact/result를 수정하지 않는다.
- `ask_user` 질문은 가공하지 않는다. 비위험 답변은 기존 Authority Certificate와 파생 계약을 무효화한 뒤 새 Authority Critic부터 재인증한다. 고위험 승인은 runner가 준 nonce와 일회성 event ID를 `--actor-kind user --source interactive_user_prompt` provenance로 `resolve`에 기록한다.
- `retry`는 역할 호출 없이 지정된 짧은 대기 뒤 같은 `next`를 재실행한다.
- 메인은 TASK/SSOT/Authority Certificate/ClaimSpec/contract/preview/staging/artifact/diff/process state를 읽거나 수정하지 않는다.
- 기존 Contract v5/v6/v7 process는 wrapper가 각 구버전 runner로 재개하며 자동 변환하지 않는다.
- `done`의 `response_mode: verbatim`, `allow_additional_text: false`를 준수하고 runner-owned `final-report.txt`의 정확한 네 줄만 반환한다.
