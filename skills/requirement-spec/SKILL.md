---
name: requirement-spec
description: grill-me 인터뷰로 요구사항을 도출해 Intent Part 1(기능 명세)을 쓰고, Part 2(작업 지시: FR·엣지·오류·Acceptance·Verification·Handoff)를 파생한 뒤 사용자 승인 1회로 `docs/<App>/INTENT/<App>-INT-<NNN>.md`를 확정하는 스킬. "기능 명세 만들어줘", "Intent 작성", "요구사항 정리해서 명세까지", "requirement-spec" 요청 시 트리거.
argument-hint: "[--app <App>] [--type 기능개발|리팩토링]"
---

# Requirement Spec

요구사항을 인터뷰로 도출해 **Intent 문서 1개**를 확정하는 스킬이다. 인터뷰 결과는 Part 1(기능 명세)이 되고, Part 2(작업 지시)는 Part 1만 근거로 세션이 파생한다. 사용자 승인 1회로 문서를 확정하고 거기서 멈춘다. 다른 스킬을 쓸 때는 해당 `SKILL.md`를 읽어 **그 지침을 이 대화에서 그대로 수행**한다(인라인 실행 — 별도 프로세스·핸드오프 아님).

## 핵심 원칙

- **산출물은 Intent 1개** — `docs/<App>/INTENT/<App>-INT-<NNN>.md`.
- **인터뷰는 grill-me 1회** — 인터뷰를 두 번 돌리지 않는다.
- **Part 2는 질문 없이 파생** — Part 1에서 도출한다.
- **승인은 1회**, 승인 전 문서 상태는 `draft`.
- **클래스·파일·구현 방법은 어느 Part에도 쓰지 않는다** — 개발 세션 몫이다.
- **후속 단계(개발·리뷰)는 자동 실행하지 않는다** — 경로만 보고한다.
- 모든 대화·산출물은 **한국어**로 쓴다(섹션 헤딩은 템플릿의 영어 표기 유지).

---

## Phase 0 — Orient

1. **App·유형 확정**: `$ARGUMENTS` 에 `--app <App>`·`--type <유형>` 이 있으면 그 값을 쓰고, **없는 것만 사용자에게 한 턴에 묶어 1회** 묻는다. 유형은 `기능개발`·`리팩토링` 중 하나다. 답이 없으면 중단하고 사유를 보고한다.
2. **템플릿 경로 해석** — 순서대로 시도한다:
   1. repo 의 `docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md`
   2. 없으면 `${CLAUDE_PLUGIN_ROOT}/docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md`
   3. 둘 다 없으면 **중단**하고 그 사실을 보고한다.
3. **디렉터리 준비**: `docs/<App>/INTENT/` 가 없으면 생성한다.
4. **NNN 산정**: 그 디렉터리의 `<App>-INT-*.md` 중 최대 번호 + 1, 3자리 0패딩. 파일이 없으면 `001`.
5. **문서 생성**: 템플릿을 `docs/<App>/INTENT/<App>-INT-<NNN>.md` 로 복사한 뒤 TEMPLATE 경고 블록을 삭제하고, 메타 표의 `문서 ID`·`작성`을 채우고 `상태` = `draft`, `승인` = `pending` 으로 두고, `유형` 행에는 Phase 0에서 확정된 값 하나만 남긴다. 1행의 제목은 Phase 1 종료 시 확정해 기록한다.

**전이 조건**: App 확정 + Intent 파일 생성 완료.

---

## Phase 1 — grill-me 인터뷰 (인라인)

`skills/grill-me/SKILL.md` 를 읽어 그 Phase 0~4 를 **그대로** 수행한다. 아래 **오버라이드 3개 외에는 grill-me 절차를 바꾸지 않는다**(질문 1개/턴, `AskUserQuestion` 사용, pushback·escalation 규칙 모두 유지).

1. **탐색 영역 추가** — grill-me Phase 1(Map Exploration Areas)의 영역 목록에 3개를 더한다: `완료 조건·검증 방법`, `Out of scope`, `결정과 기각 대안`.
2. **출력 포맷 교체** — grill-me Phase 4 의 정리본 포맷(배경·전개·전환·결론) 대신 **Intent Part 1 의 6섹션**(Problem / Outcome / Affected / Constraints / Decisions / Open questions)으로 출력하고, 확정된 내용을 Phase 0에서 만든 Intent 파일의 Part 1 에 기록한다. **정리본 파일은 만들지 않는다** — 산출물은 Intent 파일 하나다.
3. **리뷰는 유지, 저장 단계만 제외** — grill-me Phase 4 리뷰 절차 중 **1~3단계**(정리본 초안 제시 · `AskUserQuestion` 으로 확정 확인 · 수정 반영 후 재제시)는 그대로 둔다. **4단계(정리본 파일 자동 저장)는 수행하지 않는다** — 확정 내용을 Intent 파일의 Part 1 에 기록하는 것으로 대체한다. 사용자가 Part 1 을 확인·확정한 뒤에 Phase 2 로 간다.

Part 1 은 세션에서 실제로 다룬 질의·응답으로만 채운다(grill-me 작성 규칙). 1행 제목은 확정된 Outcome 을 한 줄로 옮긴 것으로 쓴다.

**전이 조건**: Part 1 의 6섹션이 모두 채워짐(`Open questions` 는 `none` 허용) + 1행 제목 확정.

---

## Phase 2 — Part 2 파생

세션이 **Part 1만 근거로** Part 2 의 7섹션(Functional requirements / Edge cases / Error cases / Acceptance / Verification / Risks / Handoff)을 채운다.

- **사용자에게 질문하지 않는다** — 검토는 Phase 3에서 한 번에 한다.
- **FR 은 Outcome·Decisions·Constraints 에서 추적 가능해야 한다.** 근거 없는 FR 을 추가하지 않는다.
- **각 FR 마다 엣지·오류를 검토**하고, 해당 사항이 없으면 그 섹션에 `none` 을 명시한다.
- **Acceptance 는 유형별로** 쓴다: 기능개발 = `- [ ] <완료 조건>` 체크리스트, 리팩토링 = `- <보존해야 할 동작>` 목록.
- **Verification 은 확인 방법만** 쓴다. 실행 명령은 쓰지 않는다.
- **Handoff 는 알 수 있는 값**(repo · app 등)만 채우고, 모르는 값은 `pending` 으로 둔다.
- 클래스명·파일명·구현 방법은 쓰지 않는다.

**전이 조건**: 7섹션 모두 기록됨(해당 없는 섹션은 `none`, 미확인 Handoff 값은 `pending`).

---

## Phase 3 — 검토·승인 (1회)

1. Intent 경로와 **Part 1·2 섹션별 핵심 요약**을 사용자에게 제시한다.
2. 사용자가 수정을 요청하면 반영하고 다시 제시한다 — 승인 또는 중단까지 반복한다.
3. **승인 조건**: `Open questions` 가 `none` **이고**, Handoff 에 `pending` 이 없고, 메타 표의 `유형` 이 `기능개발`·`리팩토링` 중 하나로 확정되어 있어야 한다. 미충족이면 승인할 수 없다고 알리고, **해당 항목만** 사용자에게 물어 채운다.
4. **승인 시**: 메타 표의 `상태` = `approved`, `승인` = `<사용자> · <YYYY-MM-DD>` 로 갱신한다.
5. **거절·중단 시**: `상태` = `draft` 를 유지한다.
6. **종료 보고**: Intent 경로, 상태, Handoff 요약을 보고한다. 후속(개발 세션 위임)은 **사용자가** 진행한다 — 이 스킬은 실행하지 않는다.

---

## 산출물 경계

- **만드는 것**: Intent 문서 1개 (`docs/<App>/INTENT/<App>-INT-<NNN>.md`).
- **만들지 않는 것**: 인터뷰 정리본·별도 지시서·TASK·기타 부속 문서, 구현 코드, 브랜치·워크트리.
- 후속 스킬을 자동으로 호출하지 않는다. `ExitPlanMode` 를 호출하지 않는다.

## 실패 처리

| 상황 | 처리 |
|---|---|
| 템플릿을 두 경로 모두에서 못 찾음 | 중단, 찾은 경로 후보를 보고 (문서 생성 안 함) |
| App 이 1회 질문 후에도 미정 | 중단, 사유 보고 (디렉터리·문서 생성 안 함) |
| grill-me 인터뷰가 사용자 중단으로 종결 | Part 1 까지 기록된 상태로 `draft` 유지, Phase 2 진행 안 함 |
| 승인 조건 미충족 (Open questions 잔존 · Handoff `pending` · `유형` 미확정) | 승인 불가 사유를 알리고 해당 항목만 질문, 채워지면 재제시 |
| 사용자가 승인을 거절 | `draft` 유지, 경로만 보고하고 종료 |
