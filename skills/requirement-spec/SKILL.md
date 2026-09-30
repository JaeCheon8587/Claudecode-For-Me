---
name: requirement-spec
description: grill-me 인터뷰로 요구사항을 도출해 Intent Part 1(기능 명세)을 쓰고 Part 2(작업 지시)를 파생한 뒤, 코드 생성 체크리스트 + opus 판정 루프(최대 3회)로 검증하고 품질 지표를 남겨 사용자 승인 1회로 확정하는 스킬. "요구사항 정리해서 명세까지", "기능 명세 만들어줘", "Intent 작성", "requirement-spec" 요청 시 트리거
argument-hint: "[--app <App>] [--type 기능개발|리팩토링] [--no-gate]"
---

# Requirement Spec

요구사항을 인터뷰로 도출해 **Intent 문서 1개**를 확정하는 스킬이다. 인터뷰 결과는 Part 1(기능 명세)이 되고, Part 2(작업 지시)는 Part 1만 근거로 세션이 파생한다. 파생한 Part 2 는 코드가 생성한 체크리스트와 opus 서브에이전트 판정으로 검증하고, 결과를 품질 지표로 남긴 뒤 사용자 승인 1회로 문서를 확정하고 거기서 멈춘다. 다른 스킬을 쓸 때는 해당 `SKILL.md`를 읽어 **그 지침을 이 대화에서 그대로 수행**한다(인라인 실행 — 별도 프로세스·핸드오프 아님).

## 핵심 원칙

- **산출물은 Intent 1개** — `docs/<App>/INTENT/<App>-INT-<NNN>.md`.
- **인터뷰는 grill-me 1회** — 인터뷰를 두 번 돌리지 않는다.
- **Part 2는 질문 없이 파생** — Part 1에서 도출한다.
- **검증 기준은 인터뷰다** — 인터뷰 전사에서 1회 도출한 오라클(`expected.md`, 이후 불변)과 코드가 회차마다 만드는 사실표를 함께 쓴다. LLM 판정은 최대 3회다.
- **승인은 1회**, 승인 전 문서 상태는 `draft`.
- **클래스·파일·구현 방법은 어느 Part에도 쓰지 않는다** — 개발 세션 몫이다.
- **후속 단계(개발·리뷰)는 자동 실행하지 않는다** — 경로만 보고한다.
- 모든 대화·산출물은 **한국어**로 쓴다(섹션 헤딩은 템플릿의 영어 표기 유지).

---

## Phase 0 — Orient

1. **App·유형 확정**: `$ARGUMENTS` 에 `--app <App>`·`--type <유형>` 이 있으면 그 값을 쓰고, **없는 것만 사용자에게 한 턴에 묶어 1회** 묻는다. 유형은 `기능개발`·`리팩토링` 중 하나다. 답이 없으면 중단하고 사유를 보고한다.
2. **`--no-gate` 해석**: `$ARGUMENTS` 에 `--no-gate` 가 있으면 Phase 3·4 를 건너뛰고 메타 표의 `검증` 행을 `SKIPPED — --no-gate` 로 적는다(Phase 5 는 그대로 수행).
3. **템플릿 경로 해석** — 순서대로 시도한다:
   1. repo 의 `docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md`
   2. 없으면 `${CLAUDE_PLUGIN_ROOT}/docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md`
   3. 둘 다 없으면 **중단**하고 그 사실을 보고한다.
4. **디렉터리 준비**: `docs/<App>/INTENT/` 가 없으면 생성한다.
5. **NNN 산정**: 그 디렉터리의 `<App>-INT-*.md` 중 최대 번호 + 1, 3자리 0패딩. 파일이 없으면 `001`.
6. **문서 생성**: 템플릿을 `docs/<App>/INTENT/<App>-INT-<NNN>.md` 로 복사한 뒤 TEMPLATE 경고 블록을 삭제하고, 메타 표 7행을 채운다 — `문서 ID`·`작성` 을 채우고, `상태` = `draft`, `승인` = `pending`, `검증` = `pending`, `관련 Intent` 는 해당 없으면 `none` 으로 두고, `유형` 행에는 Phase 0에서 확정된 값 하나만 남긴다. 1행의 제목은 Phase 1 종료 시 확정해 기록한다.
7. **작업 폴더 생성**: `.process/intent-check/<문서 ID>/` 를 만든다. Phase 1 의 전사부터 여기에 쓴다.
8. **`.gitignore` 보장**: 대상 repo 루트 `.gitignore` 에 `.process/` 줄이 없으면 추가한다(파일이 없으면 생성). 추가했으면 1줄로 고지한다 — "`.process/` 를 .gitignore 에 추가했다 — 검증 임시 파일용".

**전이 조건**: App 확정 + Intent 파일 생성 완료.

---

## Phase 1 — grill-me 인터뷰 (인라인)

`skills/grill-me/SKILL.md` 를 읽어 그 Phase 0~4 를 **그대로** 수행한다. 아래 **오버라이드 4개 외에는 grill-me 절차를 바꾸지 않는다**(질문 1개/턴, `AskUserQuestion` 사용, pushback·escalation 규칙 모두 유지).

1. **탐색 영역 추가** — grill-me Phase 1(Map Exploration Areas)의 영역 목록에 3개를 더한다: `완료 조건·검증 방법`, `Out of scope`, `결정과 기각 대안`.
2. **출력 포맷 교체** — grill-me Phase 4 의 정리본 포맷(배경·전개·전환·결론) 대신 **Intent Part 1 의 6섹션**(Problem / Outcome / Affected / Constraints / Decisions / Open questions)으로 출력하고, 확정된 내용을 Phase 0에서 만든 Intent 파일의 Part 1 에 기록한다. Constraints 항목은 `C1.` 부터 번호를 붙인다. **정리본 파일은 만들지 않는다** — 산출물은 Intent 파일 하나다.
3. **리뷰는 유지, 저장 단계만 제외** — grill-me Phase 4 리뷰 절차 중 **1~3단계**(정리본 초안 제시 · `AskUserQuestion` 으로 확정 확인 · 수정 반영 후 재제시)는 그대로 둔다. **4단계(정리본 파일 자동 저장)는 수행하지 않는다** — 확정 내용을 Intent 파일의 Part 1 에 기록하는 것으로 대체한다. 사용자가 Part 1 을 확인·확정한 뒤에 Phase 2 로 간다.
4. **전사 기록 추가** — 인터뷰 원문을 `.process/intent-check/<문서 ID>/interview.md` 에 남긴다. 이 파일이 Phase 2 오라클의 유일한 입력이다.
   - grill-me 가 질문을 던진 **매 턴 직후** append 한다: `Q<n>. <질문 원문>` / `A<n>. <답변 원문>`.
   - `AskUserQuestion` 선택 답은 `A<n>. [선택] <라벨>` 로 쓰고, 다중 선택은 `[선택] <라벨1> · <라벨2>` 로 잇는다. 자유 입력이 있으면 같은 줄에 `[입력] <원문>` 을 덧붙인다.
   - **인터뷰 시작 전 발화**(사용자가 준 주제·제약, 사전 질문에 대한 답)는 파일 맨 위 `Q1` 앞에 `Q0. (인터뷰 전 — 질문 없음)` / `A0. <원문>` 으로 적는다. 여러 건이면 `A0.` 아래 `- <원문>` 으로 잇는다. expector 는 여기서 나온 항목의 출처를 `Q0/A0` 으로 쓴다.
   - 질문 턴 밖의 사용자 발화(자발 발언·중간 정정)는 **직전 `A<n>` 에 원문 그대로 이어 쓴다** — 새 `Q` 를 만들지 않는다. 별도 줄(`(인터뷰 중 발화)` 등)로 떼어 쓰지 않는다 — 떼면 expector 가 인용할 번호가 없다.
   - `templates/intent-expector.md`·`templates/intent-critic.md` 는 **Phase 1 중에 읽지 않는다** — 오라클 추출 규칙을 아는 채로 전사를 쓰면 전사가 오라클에 맞춰진다. 2a·3d 에서 처음 읽는다.
   - **요약·합성 금지** — 원문만 쓴다. 세션이 해석한 문장은 쓰지 않는다.
   - grill-me Phase 4 리뷰에서 사용자가 고친 것은 `R<n>. <사용자 요청 원문>` 만 기록한다. 반영 결과·요약은 쓰지 않는다(Part 1 누출 방지).
   - 인터뷰 종료 시 `Q` 개수 == 질문 턴 수를 확인한다. 불일치면 누락 턴을 채운 뒤 진행한다.
   - **정리본(Part 1)은 여기 쓰지 않는다.**
   - 한계: 선택지 라벨은 세션이 쓴 문구다 — 독립성은 "사용자가 무엇을 골랐는가" 수준이다.

Part 1 은 세션에서 실제로 다룬 질의·응답으로만 채운다(grill-me 작성 규칙). 1행 제목은 확정된 Outcome 을 한 줄로 옮긴 것으로 쓴다.

**전이 조건**: Part 1 의 6섹션이 모두 채워짐(`Open questions` 는 `none` 허용) + 1행 제목 확정.

---

## Phase 2 — 오라클 도출 + Part 2 파생

이 Phase 에서 두 가지를 함께 진행한다 — **expector 스폰**(인터뷰 오라클)과 **메인 세션의 Part 2 파생**. expector 는 Part 2 를 보지 않는다.

### 2a — expector 스폰 (오라클)

`templates/intent-expector.md` 를 Read 해 `{{INTERVIEW_PATH}}` `{{INTENT_ID}}` `{{EXPECTED_PATH}}` 를 실제 값으로 치환하고, **치환된 전문을 프롬프트로 그대로** 전달한다 — `Agent(subagent_type: "general-purpose", model: "opus", prompt: <치환 전문>)`. `{{EXPECTED_PATH}}` = `.process/intent-check/<ID>/expected.md`.

- **expector 가 `expected.md` 를 직접 쓴다.** 세션은 반환을 옮겨 적지 않는다 — 파일이 생겼는지만 확인한다. **파일 미작성** — 세션이 `{{EXPECTED_PATH}}` 존재를 먼저 확인한다. 없으면 같은 에이전트에 `FAIL READ_TEXT cannot read: <경로>` 한 줄**만** 붙여 1회 재요청한다.
- **세션은 `expected.md` 를 편집하지 않는다** — 오라클은 불변이다. 형식이 어긋나도 고쳐 쓰지 말고 아래 재요청 규칙을 따른다.
- 형식 검증은 3b 에서 `--oracle` 로 실행할 때 이뤄진다. exit 2 는 두 갈래다 — stdout 에 `ORACLE:` 줄이 있으면 **형식 오류**, `ORACLE:` 줄 없이 exit 2 면 **경로 읽기 실패**(stderr `FAIL READ_TEXT cannot read: <경로>`)이므로 — 파일은 있는데 세션이 넘긴 경로가 틀린 경우다 — 경로를 고쳐 1회 재실행한다.
- **재요청 규칙** (2a·3e 공통):
  - **형식 오류** → 같은 에이전트에 파서가 낸 줄(`ORACLE:` / finding 줄)**만 그대로** 붙여 1회 재요청한다. 정답·예시·대체 문구·내용 지시를 덧붙이지 않는다 — 무엇을 써야 하는지 알려주면 그 산출물은 더 이상 독립 판정이 아니다.
  - **내용 문제**(항목이 틀렸다·빠졌다고 세션이 판단) → 재요청하지 않는다. 산출물은 그대로 쓰고 해당 항목은 3f 에서 **기각(CARRY)** 한다.
- **재시도 후에도 실패**(형식·경로 어느 쪽이든)하거나 `general-purpose` 를 쓸 수 없으면 → **오라클 없음 폴백**: `--oracle` 없이 D/C 행 체크리스트로 진행하고, Phase 4 의 `검증` 행에 `· oracle SKIPPED` 를 붙이고, Phase 5 에서 경고한다.

### 2b — Part 2 파생 (메인 세션)

세션이 **Part 1만 근거로** Part 2 의 7섹션(Functional requirements / Edge cases / Error cases / Acceptance / Verification / Risks / Handoff)을 채운다.

- **사용자에게 질문하지 않는다** — 검토는 Phase 5에서 한 번에 한다.
- **Part 2 의 모든 항목은 Part 1(Outcome·Decisions·Constraints·Out of scope)에 근거가 있어야 한다.** 근거 없는 항목을 추가하지 않는다.
- **참조 표기**: FR 은 `(Dn)`·`(Cn)`, E/X/A 는 `(FR-n)`·`(Dn)`·`(Cn)`·`(OS)` 로 근거를 표기한다. 여러 개는 `, ` 로 잇는다. 섹션 값이 `none` 이면 예외.
- **항목 ID**: D/C/FR/E/X/A 항목은 1부터 오름차순 ID 를 갖는다. 항목을 지워도 번호를 재사용하지 않는다(빈 번호 허용).
- **각 FR 마다 엣지·오류를 검토**하고, 해당 사항이 없으면 그 섹션에 `none` 을 명시한다.
- **Acceptance 는 유형별로** 쓴다: 기능개발 = `- [ ] <완료 조건>` 체크리스트, 리팩토링 = `- <보존해야 할 동작>` 목록. Acceptance 항목은 `A-n.` ID 를 갖는다(기능개발 `- [ ] A-n.`, 리팩토링 `- A-n.`).
- **Verification 은 확인 방법만** 쓴다. 실행 명령은 쓰지 않는다.
- **Handoff 는 알 수 있는 값**(repo · app 등)만 채우고, 모르는 값은 `pending` 으로 둔다.
- 클래스명·파일명·구현 방법은 쓰지 않는다.
- **근거를 댈 수 없는 항목은 쓰지 않는다** — 삭제하거나 Part 1 의 Decisions/Constraints 에 근거를 추가하고 Part 1 변경으로 기록한다. Open questions 는 진짜 미결만.

**전이 조건**: 7섹션 모두 기록됨(해당 없는 섹션은 `none`, 미확인 Handoff 값은 `pending`) + `expected.md` 저장 또는 폴백 확정.

---

## Phase 3 — 검증 루프

`--no-gate` 면 이 Phase 와 Phase 4 를 건너뛰고 `검증` 행을 `SKIPPED — --no-gate` 로 둔 채 Phase 5 로 간다. 시작할 때 1줄로 고지한다 — "검증 루프 — 회차당 코드 검사 + opus 서브에이전트 1회, 최대 3회. 임시 파일은 .process/intent-check/<ID>/ (gitignore)".

작업 폴더는 `.process/intent-check/<문서 ID>/` 다. 회차 카운터 `n` 은 **LLM 판정 횟수**이고 최대 3이다.

### 3a — 형식 검사

`python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" check-intent --repo . --file <intent> --json`

- JSON 은 `{"summary": {"pass": n, "warn": n, "fail": n}, "results": [...]}` 형태고, exit 0 = FAIL 없음 · 1 = FAIL 있음 · 2 = 인자 오류다.
- FAIL 이 있으면 세션이 인라인 수정 후 재실행한다(회차에 산입하지 않음, **최대 3번**). 3번을 넘으면 `code: FAIL` 로 Phase 4 로 간다.
- FAIL 0 이면 3b 로 진행한다. WARN 은 진행을 막지 않는다.
- python 실행 불가 → `code: SKIPPED`. 체크리스트를 만들 수 없으므로 **LLM 도 SKIPPED** 이고, Phase 5 에서 경고한다.

### 3b — 기준표 생성

`python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" intent-checklist --repo . --file <intent> --round <n> --oracle .process/intent-check/<ID>/expected.md`

- 오라클 없음 폴백이면 `--oracle` 을 생략한다.
- stdout 을 `.process/intent-check/<ID>/checklist-round-<n>.md` 로 저장한다. 표의 열은 `ID | 대상 | facts | 판정 기준 | 심각도 | N/A | 인용` 이고, 마지막 줄은 `rows: <행 수> · quote: <인용 표본 행 ID>` 다.
- `--oracle` 을 주면 `EXP-n` 행이 **표 맨 앞**에 온다. EXP 행의 `N/A` 열은 `불가` 이고, 인용 표본에는 EXP 가 들어가지 않는다.
- `expected.md` 형식이 어긋나면 `ORACLE: ` 로 시작하는 줄이 stdout 에 나오고 exit 2 로 끝나며, 경로 읽기 실패도 exit 2 이지만 `ORACLE:` 줄이 없다(stderr `FAIL READ_TEXT`) — 둘 다 2a 의 처리(재요청·재실행·폴백)로 돌아간다.
- 같은 명령에 `--json` 을 붙여 한 번 더 받아 Phase 4 의 quality.json 집계(행 수·인용 표본·traceability·`oracle`)에 쓴다.

### 3c — 스냅샷

Intent 파일을 `.process/intent-check/<ID>/round-<n>.md` 로 복사한다.

### 3d — LLM 판정

`templates/intent-critic.md` 를 Read 해 `{{INTENT_PATH}}` `{{CHECKLIST_PATH}}` `{{ROUND}}` `{{CARRY}}` `{{RETURN_PATH}}` 를 실제 값으로 치환하고, **치환된 전문을 프롬프트로 그대로** 전달한다 — `Agent(subagent_type: "general-purpose", model: "opus", prompt: <치환 전문>)`. `{{RETURN_PATH}}` = `.process/intent-check/<ID>/critic-round-<n>.txt`.

- **critic 이 `critic-round-<n>.txt` 를 직접 쓴다.** 세션은 반환을 옮겨 적지 않고, **이 파일을 편집하지 않는다**.
- 회차마다 **새 에이전트**를 스폰한다. 3e 의 형식 재요청만 같은 에이전트를 이어 쓴다.

- 넘기지 않는 것: 인터뷰 대화(전사 원문), 세션 추론, 수정 방향, 이전 회차 반환문. 인터뷰 내용은 **`expected.md` 를 거쳐 체크리스트의 EXP 행으로만** 전달된다. 판정 기준은 체크리스트 행에 다 있다.
- `general-purpose` 를 쓸 수 없으면 `llm: SKIPPED` 로 두고 Phase 5 에서 경고한다.

### 3e — 반환 검사

critic 이 쓴 `critic-round-<n>.txt` 가 있는지 확인한 뒤:

`python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" intent-checklist --repo . --file <intent> --round <n> --oracle .process/intent-check/<ID>/expected.md --check-return .process/intent-check/<ID>/critic-round-<n>.txt`

- **`--oracle` 은 3b 와 똑같이 붙인다.** 빠뜨리면 재생성 행에 EXP 가 없어 반환의 EXP 행이 전부 `EXTRA` 로 뜬다. 오라클 없음 폴백 회차에서만 생략한다.
- 출력이 `OK` 면 둘째 줄 `RETURN-SHA256: <해시>  <파일명>` 의 해시를 Phase 4 용으로 기록하고 3f 로 간다.
- 아니면 finding 줄(`MISSING` / `EXTRA` / `OVERLAP` / `BAD-KEY` / `NA-NOT-ALLOWED` / `NA-NO-LOCATION` / `QUOTE-MISSING` / `QUOTE-NOT-FOUND`)을 2a 의 **재요청 규칙**대로 그 줄만 붙여 같은 에이전트에 1회 재요청한다 — critic 이 같은 경로에 다시 쓴다. 세션이 파일을 고치지 않는다.
- 2회째도 불일치면 `llm: FAIL(protocol)` 로 기록하고 루프를 끝낸다(`stopped_early: return_mismatch`).

### 3f — 판정과 처분

- 반환의 FAIL 키 중 **심각도 MAJOR**(체크리스트 `심각도` 열 기준)가 0 이면 `llm: PASS`, 루프 종료.
- 아니면 finding 마다 세션이 ① 수정 ② 기각(사유 1줄) ③ N/A 수용 중 하나로 처분한다. 기각·N/A 수용은 CARRY 목록(`REJECTED <키> — 사유` / `ACCEPTED-N/A <키> — 사유`)에 누적해 다음 회차 critic 에 전달한다.
- **EXP 처분** — EXP 행에는 N/A 가 없다.
  - (b) 기준이 없는 행(종류 `제약`·`제외`·`프로세스`·`배경`)은 **(a) 만** 판정한다 — (b) 는 요구·완료조건·결정 행에만 있고, 배경 행의 (a) 는 MINOR 다.
  - `EXP-n:a` FAIL = 인터뷰에 있는데 Intent 에 없다 → Part 1 또는 Part 2 에 추가한다. Part 1 에 추가한 것은 `part1_edits` 에 기록하고, **추가·명확화만** 한다.
  - `EXP-n:b` FAIL = Part 1 에만 있고 Part 2 로 내려오지 않았다 → 대응하는 FR/E/X/A 를 추가한다.
  - 오라클이 틀렸다고 판단하면 기각해 CARRY 에 넣는다(`REJECTED EXP-3:a — 사유`).
- **Part 1 은 추가·명확화만** 한다 — 사용자가 확정한 문장은 삭제하지 않는다. 변경한 줄은 `part1_edits` 에 기록한다.
- 항목을 지워도 번호는 재사용하지 않는다.
- 체크리스트 파일 끝에 `## 결과` 를 덧붙인다 — 장부 4줄(PASS/FAIL/N/A/QUOTE) + 세션 처분(수정·기각·N/A 수용).
- **무진전 가드**: CARRY 를 제외한 FAIL 키 집합이 직전 회차와 같으면 중단한다(`stopped_early: no_progress`).
- `n < 3` 이면 3b 부터 다음 회차, 아니면 루프 종료.

**전이 조건**: `llm: PASS` · 3회 소진 · 조기 중단 · SKIPPED 중 하나로 루프가 끝남.

---

## Phase 4 — 품질 지표

`.process/intent-check/<ID>/quality.json` 을 세션이 **단일 작성**한다(expector·critic 은 자기 산출물 파일만 쓰고 quality.json 은 쓰지 않는다). 스키마:

```json
{ "intent": "<App>-INT-<NNN>", "max_rounds": 3, "rounds_used": 2, "final": "PASS|FAIL|OVERRIDE|SKIPPED",
  "code": {"status": "PASS|FAIL|SKIPPED", "inline_fixes": n, "last": {"pass": n, "warn": n, "fail": n, "fail_codes": []}},
  "llm":  {"status": "PASS|FAIL|FAIL(protocol)|SKIPPED", "judge": "subagent:general-purpose/opus|self|skipped", "per_round": [
            {"round": 1, "rows": 61, "pass": 55, "fail_rows": 5, "na": 1, "fail_major_keys": ["OS2:a"], "fail_minor_keys": ["FR-2:b"],
             "quote_rows": ["D3","FR-7","A-4","E-2","G-2"], "return_retry": 0}]},
  "interview": {"questions": n, "review_edits": n},
  "oracle": {"status": "OK|SKIPPED", "expected": n,
             "kinds": {"요구": n, "완료조건": n, "결정": n, "제약": n, "제외": n, "프로세스": n, "배경": n},
             "per_round": [{"round": 1, "covered_a": n, "covered_b": n, "missing_keys": ["EXP-3:a", "EXP-7:b"], "rejected": n}]},
  "improve": ["…", "…"],
  "rows_per_round": [61, 62],
  "traceability": {"fr": n, "fr_with_ref": n, "a": n, "a_with_ref": n, "ex": n, "ex_with_ref": n, "d_unreferenced": n, "c_unreferenced": n},
  "part1_edits": [{"round": n, "section": "Constraints", "diff": ["+ C6. …"]}],
  "carry": [{"round": n, "key": "FR-3:a", "kind": "REJECTED|ACCEPTED-N/A", "reason": "…"}],
  "stopped_early": "none|no_progress|format_cap|return_mismatch",
  "snapshots": ["round-1.md"], "checklists": ["checklist-round-1.md"],
  "artifacts": {"expected_sha256": "<hex>", "returns": [{"round": 1, "sha256": "<hex>"}]},
  "approved_by": "…", "approved_at": "YYYY-MM-DD" }
```

`oracle.expected` 와 `oracle.kinds` 는 3b 의 `--json` 출력에 있는 `oracle` 필드를 그대로 옮긴다.

- **`llm.judge`** — 실제 판정 주체. 서브에이전트가 판정했으면 `subagent:general-purpose/opus`, 서브에이전트를 못 써 세션이 대신했으면 `self`, 건너뛰었으면 `skipped`. `self`·`skipped` 면 Phase 5 본문에 경고 1줄.
- **`artifacts`** — 산출물 해시. `expected_sha256` 는 3b 의 `--oracle` 파싱이 처음 성공한 시점의 `expected.md` 해시(`sha256sum` 등으로 구한다), `returns[].sha256` 은 3e 가 `OK` 와 함께 출력한 `RETURN-SHA256` 값 그대로. 나중에 파일 해시가 이 값과 다르면 **수용 뒤 누군가 고친 것**이다.

메타 표의 `검증` 행은 `<총평> — code <상태> · llm <상태> · <회차>/3` 로 쓴다. 총평은 code FAIL 0 이고 llm PASS 면 `PASS`, 둘 중 하나라도 FAIL 이면 `FAIL`, `--no-gate` 면 `SKIPPED — --no-gate`, python·서브에이전트 불가로 둘 다 SKIPPED 면 `SKIPPED — <사유>` 다. 예: `PASS — code PASS · llm PASS · 2/3`. 오라클 없음 폴백이면 행 끝에 ` · oracle SKIPPED` 를 붙인다 — 예 `PASS — code PASS · llm PASS · 1/3 · oracle SKIPPED`.

---

## Phase 5 — 사용자 승인 (1회)

<!-- 대응표: 이 승인 조건 문장은 템플릿 작성 규칙 4 · docs_helpers.py INT_APPROVED_GATE 와 동일해야 한다 -->

1. **카탈로그 재생성**: `python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" intent-catalog --repo . --app <App> --write` 를 실행한다. 승인 여부와 무관하게 **Phase 5 에 들어오면 무조건 한 번** 실행한다 — 카탈로그 열의 원천인 1행 제목(Phase 1 확정)·`검증` 행(Phase 3·4 확정)·FR/A 항목 수(Phase 2 확정)가 이 시점에 모두 확정돼 있다. **카탈로그를 손으로 쓰지 않는다** — 모든 열이 Intent 문서에서 파생되므로 직접 고치면 상태 전이에서 어긋난다. python 실행 불가면 건너뛰고 종료 보고에서 1줄 고지한다.
2. **`AskUserQuestion` 1회**로 확정을 묻는다. 본문에 반드시 넣는다:
   - Intent 경로
   - 메타 `검증` 행 값
   - 최종 체크리스트 경로 + `<PASS 행>/<전체 행> PASS`
   - `인터뷰 반영 <covered>/<expected> · 누락 <EXP 키>`
   - 잔존 MAJOR·MINOR 키와 각 1줄 요약
   - `IMPROVE` 목록(있으면, 차단 아님)
   - Part 1 변경 줄 diff(≤10줄, 초과하면 스냅샷 경로만)
   - SKIPPED 경고(있으면)
   - `llm.judge` 가 `self`·`skipped` 면 "판정이 독립 서브에이전트가 아니다" 경고
3. **옵션**: 총평이 `PASS`·`SKIPPED` 면 `승인 / 수정 요청 / 중단`, `FAIL` 이면 `수동 수정 후 재검증 1회 / OVERRIDE 승인 / 중단`.
4. 사용자가 수정을 요청하면 반영하고 다시 제시한다 — 승인 또는 중단까지 반복한다.
5. **승인 조건**: `상태: approved` 는 Open questions 가 `none` 이고, Handoff 에 `pending` 이 없고, `유형` 이 한 값이고, `검증` 이 `PASS`·`OVERRIDE`·`SKIPPED` 중 하나로 시작할 때만 가능하다. 미충족이면 승인할 수 없다고 알리고, **해당 항목만** 사용자에게 물어 채운다.
6. **승인 시**: 메타 표의 `상태` = `approved`, `승인` = `<사용자> · <YYYY-MM-DD>` 로 갱신한다. OVERRIDE 승인이면 `검증` 행의 총평을 `OVERRIDE` 로 바꾸고 quality.json 의 `final` 을 `OVERRIDE` 로 쓴다. 메타 표를 고친 **직후** `intent-catalog --repo . --app <App> --write` 를 **한 번 더** 실행한다 — 1번에서 쓴 뒤 `상태`·`승인` 행이 또 바뀌었고, 둘 다 카탈로그 열이다.
7. **거절·중단 시**: `상태` = `draft` 를 유지한다. 카탈로그는 **1번에서 이미 최신 상태**이므로 여기서 다시 쓰지 않는다 — 바뀐 메타 행이 없다.
8. **종료 보고**: Intent 경로, 카탈로그 경로(`docs/<App>/<App>-INT-CATALOG.md`), 상태, `검증` 행, Handoff 요약을 보고한다. 승인했으면 다음 단계를 **한 줄로 안내만** 한다 — `/forge-init <Intent 경로>`(개발 환경 구성: 승인 커밋 · base 선택 · 워크트리). 후속은 **사용자가** 진행한다 — 이 스킬은 실행하지 않는다.

---

## 산출물 경계

- **만드는 것**: Intent 문서 1개 (`docs/<App>/INTENT/<App>-INT-<NNN>.md`) + 파생 카탈로그 `docs/<App>/<App>-INT-CATALOG.md`(생성물 — 세션이 쓰지 않고 `intent-catalog --write` 가 쓴다. Phase 5 진입 시 1회, 승인하면 1회 더 — 그 전에는 쓰지 않는다) + 검증 임시 파일 `.process/intent-check/<ID>/{interview.md, expected.md, checklist-round-<n>.md, checklist-round-<n>.json, round-<n>.md, critic-round-<n>.txt, quality.json}` (gitignore 대상). 쓰는 주체: `expected.md` = expector, `critic-round-<n>.txt` = critic, 나머지 = 세션.
- **만들지 않는 것**: 인터뷰 정리본·별도 지시서·TASK·기타 부속 문서, 구현 코드, 브랜치·워크트리.
- 후속 스킬을 자동으로 호출하지 않는다. `ExitPlanMode` 를 호출하지 않는다.

## 실패 처리

| 상황 | 처리 |
|---|---|
| 템플릿을 두 경로 모두에서 못 찾음 | 중단, 찾은 경로 후보를 보고 (문서 생성 안 함) |
| App 이 1회 질문 후에도 미정 | 중단, 사유 보고 (디렉터리·문서 생성 안 함) |
| grill-me 인터뷰가 사용자 중단으로 종결 | Part 1 까지 기록된 상태로 `draft` 유지, Phase 2 진행 안 함. Phase 5 에 닿지 않았으므로 카탈로그는 재생성하지 않는다 — 다음 실행 때 반영된다 |
| expector 사용 불가 (`general-purpose` 불가) | 오라클 없음 폴백 — `--oracle` 없이 진행, `검증` 행에 `· oracle SKIPPED` 접미, Phase 5 본문에 경고 |
| `expected.md` 형식 2회 실패 (stdout `ORACLE:`) · 경로 읽기 2회 실패 (stderr `FAIL READ_TEXT`) | 오라클 없음 폴백 — `--oracle` 없이 진행, `검증` 행에 `· oracle SKIPPED` 접미, Phase 5 본문에 경고 |
| 형식 FAIL 이 인라인 수정 3번으로 안 잡힘 | 루프 종료, `검증` = `FAIL — code FAIL · llm <상태> · <회차>/3`, `stopped_early: format_cap`, Phase 5 에서 잔존 FAIL 코드 제시 |
| 3회 소진 후 MAJOR 잔존 | 루프 종료, `검증` = `FAIL — code PASS · llm FAIL · 3/3`, Phase 5 에서 잔존 MAJOR 키 제시(옵션 = 수동 수정 후 재검증 1회 / OVERRIDE / 중단) |
| 무진전으로 중단 (CARRY 제외 FAIL 키 집합 동일) | 루프 종료, `stopped_early: no_progress`, `검증` 총평은 잔존 MAJOR 유무로 결정, Phase 5 에서 중단 사유 고지 |
| expector 가 `expected.md` 를 쓰지 않음 | `FAIL READ_TEXT cannot read: <경로>` 한 줄만 붙여 1회 재요청 → 그래도 없으면 오라클 없음 폴백 |
| critic 이 `critic-round-<n>.txt` 를 쓰지 않음 | `--check-return` 의 stderr `FAIL READ_TEXT cannot read: <경로>` 한 줄만 붙여 1회 재요청 → 그래도 없으면 `llm: FAIL(protocol)`, `stopped_early: return_mismatch` |
| 반환 불일치 2회 | `llm: FAIL(protocol)`, `검증` = `FAIL — code <상태> · llm FAIL · <회차>/3`, `stopped_early: return_mismatch`, Phase 5 에서 finding 줄 제시 |
| `general-purpose` 서브에이전트 사용 불가 | `llm: SKIPPED`, `검증` = `SKIPPED — general-purpose 불가`, Phase 5 본문에 미검증 경고 |
| python 실행 불가 | `code: SKIPPED` + `llm: SKIPPED`, `검증` = `SKIPPED — python 불가`, Phase 5 본문에 미검증 경고. Phase 5 의 카탈로그 재생성(1번·6번)도 실행되지 않으므로 그 사실을 함께 고지한다 |
| 승인 조건 미충족 (Open questions 잔존 · Handoff `pending` · `유형` 미확정 · `검증` 미충족) | 승인 불가 사유를 알리고 해당 항목만 질문, 채워지면 재제시 |
| 사용자가 OVERRIDE 승인 | `상태` = `approved`, `검증` 총평 `OVERRIDE`, quality.json `final: OVERRIDE`, 보고에 OVERRIDE 명시 |
| 사용자가 승인을 거절 | `draft` 유지, 경로만 보고하고 종료 |
