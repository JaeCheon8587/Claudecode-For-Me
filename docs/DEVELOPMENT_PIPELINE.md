# DEVELOPMENT_PIPELINE — 개발 파이프라인 설계

> 이 레포의 기존 스킬을 조합해 **요구사항 → 설계 문서 → 개발 → 검증 → 반영** 닫힌 루프를 정의하는 프로세스 설계 문서. SSOT 분류(PRD/FRD/TASK/ADR) 아닌 프로세스 문서. 문서 작성 룰은 [DOCUMENT_GUIDE](.templates/DOCUMENT_GUIDE.md) 준수.

| 항목 | 값 |
|---|---|
| 문서 ID | DEVELOPMENT_PIPELINE (단일 파일) |
| 버전 | 1.7 (Draft) |
| 작성 가정 | 기존 스킬(grill-me/acceptance-design/meta-prompter/task-write/ssot-write/work-packet-write/forge-scope/doc-driven-review) 실존. v0.7 per-App SSOT 체계 전제 |
| 관련 문서 | [DOCUMENT_GUIDE](.templates/DOCUMENT_GUIDE.md) · [CLAUDE](../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-31 | 초안 — 6단계 파이프라인 정의, step3 분기, 향후 보완 backlog | jaecheon.jeong |
| 0.2 | 2026-06-09 | step 1.5 acceptance-design(완료조건·엣지·오류·검증 4축 설계) 삽입 | jaecheon.jeong |
| 0.3 | 2026-07-03 | docs-add-task 폐지 — step3 을 task-write→ssot-write→work-packet-write 트리오로 분할 | jaecheon.jeong |
| 0.4 | 2026-07-10 | ssot-write를 Opus 오케스트레이터·planner·auditor와 Sonnet actor의 컨텍스트 격리 멀티 에이전트 흐름으로 전환 | jaecheon.jeong |
| 0.5 | 2026-07-10 | ssot-write 메인의 TASK·역할 템플릿 사전 열람을 금지하고 감사 실패를 execution repair와 plan replan으로 분리 | jaecheon.jeong |
| 0.6 | 2026-07-10 | ssot-write all-SKIP fast path, summary 없는 구조 envelope, artifact registry reducer, TASK↔최신 ADR precedence/downstream constraint 추가 | jaecheon.jeong |
| 0.7 | 2026-07-11 | ssot-write 상태·전이·권한·baseline diff를 deterministic runner Contract v4로 강제 | jaecheon.jeong |
| 0.8 | 2026-07-11 | ssot-write Contract v5에서 문서유형별 판단·파일별 편집/검토·교차 감사를 분리하고 runner가 plan을 컴파일 | jaecheon.jeong |
| 0.8 | 2026-07-11 | ssot-write helper 검사를 runner gate로 이동하고 no-op/finalize 이벤트 및 verbatim final-report 추가 | jaecheon.jeong |
| 0.9 | 2026-07-11 | ssot-write 동일 타입 다중 artifact action과 dispatch/누적 승인 권한 분리 추가 | jaecheon.jeong |
| 1.0 | 2026-07-11 | ssot-write task outcome/downstream, precedence 조합, ADR 상태와 rejected result를 runner gate로 이동 | jaecheon.jeong |
| 1.1 | 2026-07-11 | ssot-write Contract v6 — 전체 변경 Opus 제안·fresh Opus 계획/결과 비판, Sonnet staging, runner 관계 gate·journaled commit/rollback으로 전환 | jaecheon.jeong |
| 1.2 | 2026-07-11 | ssot-write Contract v7 — exact ChangeSpec/compiled preview/structured apply와 선택적 신규 FRD prose JSON 렌더링으로 Sonnet 자유 편집 제거 | jaecheon.jeong |
| 1.3 | 2026-07-11 | ssot-write Contract v8 — mandatory Opus Authority Certificate, certificate-bound ClaimSpec, runner deterministic preview/FRD assembly, fresh Change/Outcome Critic, 별도 risk approval, bounded optional Sonnet prose로 권위·작성 책임 분리 | jaecheon.jeong |
| 1.4 | 2026-07-12 | ssot-write v8 — runner-owned evidence ID→exact quote 정규화, Authority 후보별 coverage, 실행 구현 SHA 동결, 전 과정·결과 한국어 계약 추가 | jaecheon.jeong |
| 1.5 | 2026-07-13 | ssot-write slim — Opus Main + Opus Planner + Sonnet Writer + Opus Critic, 6개 파일 계약, Critic 최대 3회로 단순화 | jaecheon.jeong |
| 1.6 | 2026-07-13 | ssot-write 실전 보강 — 실제 docs_root 대소문자, Writer 이전 baseline diff, 중단 attempt, bounded range, 단계 완료 게이트를 강제하고 내부 승인·commit 제거 | jaecheon.jeong |
| 1.7 | 2026-07-16 | task-write를 ssot-write와 동일한 Opus Main + Opus Planner + Sonnet Writer + Opus Critic 멀티 에이전트 3-agent 순환으로 전환. read-only auditor를 Critic 통합 구조 검증으로 대체, 완전 비대화형 Main, TASK 파일 1개 계약 유지 | jaecheon.jeong |

## 0. 목적

흩어진 스킬을 하나의 개발 흐름으로 묶는다. 목표:

- **단일 진실원천**: 설계 문서(FRD/TASK)를 1급 산출물로 두고 개발·검증이 같은 문서를 참조
- **책임 분리**: 단계마다 단일 책임 (캐묻기 / 완료조건·검증설계 / 정제 / 문서산출 / 개발 / 검증 / 반영)
- **검증 가능**: 개발 결과를 문서 기준으로 기계 검증 (Conformance%)

## 1. 파이프라인 개요

```mermaid
flowchart TD
    A["1. grill-me<br/>요구사항 구체화"] --> A2["1.5 acceptance-design<br/>완료조건·검증 4축 설계"]
    A2 --> B["2. meta-prompter<br/>설계 프롬프트 정제"]
    B --> C1["3a. task-write<br/>TASK 작성 (Scope Authority)"]
    C1 --> C2["3b. ssot-write<br/>Opus Main + Planner/Writer/Critic"]
    C2 --> C3["3c. work-packet-write<br/>TASK+SSOT → Work Packet"]
    C3 --> F["4. forge-scope<br/>Work Packet 기반 개발"]
    F --> G["5. doc-driven-review<br/>Codex 문서 기준 검증"]
    G --> H["6. 반영<br/>리뷰 결과 코드/문서 반영"]
    H -.->|향후: 재검토 루프| G
```

## 2. 단계별 명세

| 단계 | 스킬/커맨드 | 입력 | 출력 | 책임 |
|---|---|---|---|---|
| 1 | `grill-me` | 거친 아이디어/계획 | 합의된 요구사항 (대화형) | 모호함을 집요한 질문으로 구체화. 논리 공백 지적 |
| 1.5 | `acceptance-design` | grill-me 정리본 (doc) | 완료조건·엣지케이스·오류케이스·검증방법 4축 설계본 (대화형) | doc 기준 "끝의 정의"와 검증을 같이 설계 |
| 2 | `meta-prompter` | grill-me 결과 + 4축 설계본 | 한국어 개조식 메타프롬프트 (마크다운 코드블록) | 요구사항을 다음 단계가 안정 수행할 구조화 프롬프트로 정제 |
| 3a | `task-write` | 요구사항 문서 또는 자연어 요청 | `docs/<App>/TASK/<App>-TASK-<NNN>.md` (Scope Authority — 목적·범위·비목표·완료기준·엣지·오류·테스트만) + process `build.md`, `progress.md`, `plan.json`, `changes.json`, `review.json`, `handoff.json`. 영구 SSOT 는 생성·수정·분석하지 않음 | Opus Main이 두 진행 문서를 기준으로 Opus Planner, Sonnet Writer, Opus Critic을 순환 호출. Critic이 요구사항 원문↔실제 TASK를 네 의미 축으로 비교하고 check-task 구조 검증까지 수행. Critic FAIL은 Planner 재계획으로 최대 3회. 완전 비대화형 |
| 3b | `ssot-write` | task-write 산출 TASK | 영향 SSOT upsert + `build.md`, `progress.md`, `plan.json`, `changes.json`, `review.json`, `handoff.json` | Opus Main이 두 진행 문서를 기준으로 Opus Planner, Sonnet Writer, Opus Critic을 순환 호출한다. Critic FAIL은 Planner 재계획으로 돌아가며 최대 3회. 승인·commit은 범위 밖 |
| 3c | `work-packet-write` | task-write TASK + ssot-write `handoff.json` | `App-WORK_PACKET/App-WP-<NNN>.md` — Ready gate, 연결 TASK, Required SSOT Execution Matrix, Implementation Output Contract | TASK와 handoff Action/authority를 연결해 forge 실행용 Work Packet만 생성 (TASK/SSOT/코드 수정 안 함) |
| 4 | `forge-scope` | work-packet-write 산출 Work Packet | `phases/scoped/<phase-dir>/index.json` + `step{N}.md` + 코드 | Work Packet 기반 경량 scoped 개발 실행 |
| 5 | `doc-driven-review` | doc-path (1개 이상) | Missing / Improve / Overengineered / Conformance(%) | Codex 위임 — 문서가 코드 변경점에 반영됐는지 검증 |
| 6 | (수동) | 리뷰 결과 | 반영된 코드/문서 | Missing 보강, Overengineered 제거, Improve 판단 반영 |

## 3. 분기 규칙 (step 3)

step3 는 **task-write → ssot-write → work-packet-write** 3단 체인. 옛 `docs-add-task` monolith(단일 진입점 + 내부 자산별 upsert)가 책임별로 분해됐다:

- **task-write (3a)** — 요구사항을 TASK 로만 좁힌다. 신규/기존 판단·영구 SSOT 분석을 하지 않는다 (그 판단은 3b 책임). App 결정 + TASK 번호 할당 + 본문 작성 + read-only 서브에이전트 자체 검증.
- **ssot-write (3b)** — TASK 를 입력으로 받아 영향 SSOT 를 upsert. 신규/기존 판단은 여기서 수행:
  - **신규 기능** → 해당 App `{App}-FC.md` 에 대응 기능 행 **없음**. 새 FRD 20절 신설, App-PRD §3.1/§7 갱신, FC 5표 행 추가.
  - **기존 수정/개선/refactor** → FC 에 이미 기능 행 **존재** (또는 운영성 work_type). 영향 FRD 다수 자동 식별 후 영향 FRD 갱신, FC 행 상태 갱신.
  - **혼합 허용** — 한 TASK 에서 신규 FRD 신설 + 기존 FRD 갱신 동시 가능.
  - **ADR 은 필요 시** — 새 결정이면 신설, 기존 결정 변경이면 기존 ADR 수정(supersede/in-place), 결정 없으면 생략. op 따라 ADR-CATALOG 동기화.
  - **실제 역할 분리** — Main Orchestrator는 Opus다. Opus Planner가 `plan.json`, Sonnet Writer가 실제 SSOT와 `changes.json`, Opus Critic이 `review.json`을 각각 소유한다.
  - **Agent dispatch** — registry를 조회하지 않고 세 역할 모두 `general-purpose` 독립 agent가 같은 `agents/ssot-*.md` 정의를 먼저 읽는 bootstrap-only mode를 사용한다. `ssot-*` availability probe와 named 호출은 금지한다.
  - **파일 전달** — 역할끼리 직접 대화하지 않고 Main이 파일 경로만 전달한다. Main은 역할의 의미 판단이나 SSOT 작성을 대신하지 않는다.
  - **진행 기준** — Main은 모든 Agent 호출 직전에 `build.md`와 `progress.md`를 다시 읽고 cycle·현재 역할·다음 역할을 결정한다.
  - **Writer 변경 보고** — Writer는 계획된 `target_path`만 수정하고 파일·섹션·anchor·summary·criterion을 `changes.json`에 cycle 간 누적 기록한다.
  - **좁은 Critic** — Critic은 Plan을 읽지 않는다. TASK 핵심 의미와 Writer 결과 경로의 실제 SSOT 투영을 모순·핵심 누락·금지 범위 포함·근거 없는 추가 결정 네 축으로만 비교하며, 하나라도 실패하면 무조건 FAIL이다. 코드·테스트·빌드 세부의 문구 복제 여부와 문체·취향은 범위 밖이다.
  - **보정 루프** — Critic `FAIL`은 `PLAN_PATH + REVIEW_PATH`를 Planner에게 전달해 FAIL finding 관련 target만 포함한 REPAIR 계획을 만들고 Writer·Critic을 다시 호출한다. Critic은 최대 3회이며 세 번째 FAIL은 `MANUAL_REQUIRED`다.
  - **NOOP 검토** — NOOP도 Critic을 호출하며 Writer만 생략한다. Planner 단독 NOOP 완료는 금지한다.
  - **상태와 진행** — `build.md`가 고정 실행 설계, `progress.md`가 현재 cycle과 결과다. 중단 후 재개는 지원하지 않는다.
  - **handoff** — Critic SUCCESS 직후 승인 질문이나 commit 없이 `handoff.json`을 작성한다. Action, source/target/authority, instruction, acceptance, section modifications를 담는 후속 단계 단일 입력이다.
  - **legacy** — 신규 실행은 Runner를 사용하지 않는다. `ssot_runner.py`와 v5-v8 구현은 기존 process 재개 전용이다.
- **work-packet-write (3c)** — TASK + 반영된 SSOT를 연결해 forge 실행용 Work Packet만 생성한다. `handoff.json.actions`와 `authority_paths`를 Required 입력과 실행 규칙으로 변환한다. TASK/SSOT/코드는 수정하지 않는다.

TASK 는 휘발성 + 외부 SSOT 인용 금지 ([DOCUMENT_GUIDE §1.2](.templates/DOCUMENT_GUIDE.md) 룰).

요구사항 정합 검증은 단계별로 분산됐다. task-write는 TASK 파일 1개를 `docs_conformance.py`로 채점하고, ssot-write Critic은 Plan을 무시하고 TASK 핵심 의미가 실제 SSOT에 올바르게 투영됐는지를 네 의미 축으로 최대 3회 직접 비교한다. **step5 `doc-driven-review`(문서↔코드)와는 검증 축이 다르다**: step3 검증 = TASK 의미↔SSOT 투영, step5 = 문서↔코드.

## 4. 데이터 흐름 / SSOT

- 설계 문서(FRD/TASK)가 **단일 진실원천**. step4 forge-scope 와 step5 doc-driven-review 가 **같은 문서**를 참조 → 개발 의도와 검증 기준 일치.
- forge-scope 산출물(`phases/scoped/<dir>/`)은 개발 추적용. 영구 추적은 docs/ SSOT + 코드.
- doc-driven-review 는 working-tree + untracked 변경점을 문서 기준으로 대조 → Conformance% 산출.
- ssot-write Main은 `build.md`의 고정 실행 설계와 `progress.md`의 현재 cycle을 함께 읽는다. `plan.json`, `changes.json`, `review.json`은 역할 전달 계약이고 `handoff.json`은 성공한 후속 단계 계약이다.

## 5. 향후 보완 (Backlog)

현행 파이프라인은 골격만 갖춘 단방향(폭포수) 흐름. 합의된 약점 — **진행하며 보완**:

| # | 보완 항목 | 위치 | 문제 |
|---|---|---|---|
| 1 | **verify-gate** | step4 ↔ step5 사이 | 빌드/테스트 통과 확인 단계 없음. 깨진 코드가 리뷰로 흘러감 |
| 2 | **branch-review (Standards 축)** | step5 보강 | doc-driven-review 는 Spec(문서 일치)만 검증. 코딩 컨벤션/Standards 축 누락 → `branch-review` 스킬로 보완 |
| 3 | **재검토 루프** | step6 → step5 | 반영이 1-shot. 반영이 새 결함 넣어도 모름 → Conformance 임계치까지 반복 |
| 4 | **commit 마무리** | step6 이후 | 파이프라인 끝이 working-tree 더미. `commit-analysis` 스킬로 커밋 마감 |
| 5 | **피드백 문서 역류 경로** | step5 → step3 | 리뷰가 "문서 자체 결함/오버엔지니어링" 잡아도 문서로 되돌아갈 경로 없음 (단방향 한계) |

위 항목은 별도 후속 작업. 본 문서는 현행 흐름 + backlog 기록까지를 범위로 한다.
