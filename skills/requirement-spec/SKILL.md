---
name: requirement-spec
description: 요구사항을 대화로 도출하고 완료조건·검증을 설계한 뒤 개발 지시서로 정제하고 지시서 검증 게이트(Code+LLM 건전성)로 자기검증하는 메타 스킬. grill-me로 요구사항 도출 → acceptance-design으로 완료조건·엣지·오류·검증 4축 설계 → meta-prompter로 개발 지시서 정제 → .requirements/requirement-{slug}.md 저장 → 지시서 검증 게이트(모순·누락·완료조건↔검증방법·엣지↔기대동작) → 확정 후 pipeline-runner 실행 여부를 물어 인라인 핸드오프. "요구사항 지시서 만들어줘", "요구사항부터 같이 정리해서 작업지시서까지", "요구사항 도출하고 검증까지", "requirement-spec" 요청 시 트리거.
argument-hint: "[요구사항 도출할 주제]"
---

# Requirement Spec

요구사항 도출부터 개발 지시서 산출·자기검증까지를 **한 번의 호출로 자동 진행**하는 메타 스킬.
기존 스킬(`grill-me`, `acceptance-design`, `meta-prompter`)을 인라인 실행으로 엮고, 지시서 검증 게이트(Code+LLM)를 붙인 오케스트레이터다.

**최종 산출물**: `.requirements/requirement-{slug}.md` — 다른 AI 에이전트가 그대로 수행할 수 있는 개발 지시서.
`{slug}`는 grill-me 결과물(`.requirements/grill-me-{slug}.md`)과 **동일**하다.

---

## 동작 원칙

- **자동 인라인 체인**: Phase 1~5를 자동으로 이어 간다. **사용자 상호작용은 grill-me 인터뷰(Phase 1)·acceptance-design 인터뷰(Phase 1.5)·게이트 FAIL 분기(Phase 3.5)·후속 핸드오프(Phase 5)에서만** 발생한다.
- **인라인 실행**: 다른 스킬을 호출할 때는 해당 `SKILL.md`를 읽어 **그 지침을 이 대화에서 그대로 수행**한다(별도 프로세스·핸드오프 아님).
- **산출물 경계**: 지시서 저장/갱신까지가 이 스킬 **자체의** 산출물이다. **구현 코드를 직접 작성하지 않고, `ExitPlanMode`를 호출하지 않는다.** (단, 정리본·지시서를 `.requirements/`에 저장하는 파일 쓰기는 허용. 또한 Phase 5에서 **사용자가 명시적으로 선택하면** pipeline-runner로 인라인 핸드오프하며, pipeline-runner 자체 승인 게이트가 다시 막으므로 이 스킬이 구현으로 직행하지 않는다.)
- **Phase 게이트(전역)**: 각 Phase는 게이트다. 해당 Phase의 **전이 조건(완료 조건)을 충족하기 전에는 절대로 다음 Phase로 넘어가지 않는다.** 건너뛰기·앞당기기 금지. 각 Phase 머리의 ⛔ 게이트 문구를 매번 확인한다.

---

## Phase 0 — Orient

> ⛔ **게이트**: 주제 확인 + 파이프라인 선언을 **마치기 전에는 절대** Phase 1로 넘어가지 않는다.

스킬 활성화 시:
1. 주제를 1~2문장으로 확인한다.
2. 파이프라인을 1줄로 선언한다: *"요구사항 도출(grill-me) → 완료조건·검증 4축 설계(acceptance-design) → 개발 지시서 정제(meta-prompter) → 저장 → 지시서 검증 게이트(Code+LLM 건전성). grill-me·acceptance-design 인터뷰 외에는 자동 진행한다."*
3. `$ARGUMENTS`를 Phase 1의 grill-me 주제로 넘긴다.

---

## Phase 1 — 요구사항 도출 (grill-me 인라인)

> ⛔ **게이트**: grill-me 인터뷰가 끝나고 `.requirements/grill-me-{slug}.md`가 저장되기 **전에는 절대** Phase 2로 넘어가지 않는다. 정리본 미확정 시 파이프라인 중단.

- `skills/grill-me/SKILL.md`를 읽어 **그 지침을 그대로** 수행한다(인터뷰 Phase 0~4 전부).
- grill-me 종결 시 정리본이 `.requirements/grill-me-{slug}.md`로 자동 저장된다(grill-me의 "정리본 저장 (자동)" 규칙이 처리).
- **slug 확보**: 저장된 실제 파일명에서 `grill-me-` 접두어와 `.md`를 떼어 `{slug}`로 둔다. (충돌 suffix `-2` 등이 붙었으면 그대로 포함해 두 산출물 파일명을 일관 유지.)

**전이 조건**: `.requirements/grill-me-{slug}.md`가 존재해야 다음으로 간다.
grill-me가 사용자 중단으로 정리본을 확정하지 못하면 **파이프라인을 중단**한다(지시서 생성 안 함).

---

## Phase 1.5 — 완료조건·검증 4축 설계 (acceptance-design 인라인)

> ⛔ **게이트**: acceptance-design 인터뷰가 끝나고 `.requirements/{slug}-acceptance.md`가 저장되기 **전에는 절대** Phase 2로 넘어가지 않는다.

- `skills/acceptance-design/SKILL.md`를 읽어 **그 지침을 그대로** 수행한다(인터뷰 Phase 0~4 전부, 4축 질문 + 확정 리뷰 포함).
- **타겟 doc = Phase 1 정리본**(`.requirements/grill-me-{slug}.md`). acceptance-design의 Phase 0 doc 읽기 단계에 이 경로를 그대로 입력으로 넘긴다(별도 doc 경로를 사용자에게 묻지 않는다).
- **slug 고정**: acceptance-design 기본 slug(doc stem)을 쓰지 않고, **Phase 1에서 확보한 `{slug}`를 재사용**해 `.requirements/{slug}-acceptance.md`로 저장한다. (세 산출물이 동일 `{slug}` 공유.)
- 산출 = `.requirements/{slug}-acceptance.md` (완료조건·엣지케이스·오류케이스·검증방법 4축 설계본).

**전이 조건**: `.requirements/{slug}-acceptance.md`가 존재해야 다음으로 간다.
acceptance-design이 사용자 중단으로 설계본을 확정하지 못하면 **파이프라인을 중단**한다(지시서 생성 안 함).

---

## Phase 2 — 개발 지시서 정제 (meta-prompter 인라인)

> ⛔ **게이트**: meta-prompter 메타프롬프트 코드블록이 산출되기 **전에는 절대** Phase 3으로 넘어가지 않는다. 필수 항목 질문이 남아 있으면 답을 받은 뒤에만 진행.

- `skills/meta-prompter/SKILL.md`를 읽어 수행한다. **입력 = Phase 1 정리본 전문 + Phase 1.5 4축 설계본 전문**(`.requirements/grill-me-{slug}.md` + `.requirements/{slug}-acceptance.md` 내용). 정리본은 무엇을·왜, 설계본은 완료조건·엣지·오류·검증을 공급한다.
- meta-prompter가 작업 유형 분류 → 템플릿 선정 → 메타프롬프트 생성을 수행한다.
- meta-prompter의 필수 항목이 정리본에서 채워지지 않으면 그 규칙대로 ≤3개를 묶어 한 번에 질문한다(정리본이 대부분 커버하므로 질문 0건을 기대).
- 산출 = 코드블록 1개(메타헤더 + 본문 + `[에이전트 행동 규칙]` 가드레일 문구, **개조식** 종결).
- **주의**: meta-prompter는 파일을 저장하지 않는다. 저장은 Phase 3에서 이 스킬이 직접 한다.

---

## Phase 3 — 지시서 저장

> ⛔ **게이트**: `.requirements/requirement-{slug}.md` 저장이 완료되기 **전에는 절대** Phase 3.5로 넘어가지 않는다.

- Phase 2 코드블록의 **내부 내용**을 추출해 `.requirements/requirement-{slug}.md`에 저장한다(`Write`).
- `.requirements/` 폴더가 없으면 생성한다.
- 파일 구성:
  ```
  # 요구사항 개발 지시서: {주제}

  > 출처(GROUND TRUTH): .requirements/grill-me-{slug}.md + .requirements/{slug}-acceptance.md
  > 생성: requirement-spec 파이프라인

  ---

  {meta-prompter 코드블록 본문 그대로}
  ```
- meta-prompter 출력의 개조식·항목 형식을 보존한다(재서술 금지).

---

## Phase 3.5 — 지시서 검증 게이트 (Code + LLM 건전성 감사)

> ⛔ **게이트**: 게이트가 **PASS**로 판정되기 **전에는 절대** Phase 5(후속 핸드오프)로 넘어가지 않는다. **FAIL이면 하류(task-write 등)로 진행하지 않는다.**

Phase 3에서 저장한 `.requirements/requirement-{slug}.md`(지시서)를 **감사 대상**으로, 지시서 **내부 건전성**을 1회 비대화로 검증한다.
(이 게이트는 지시서 **내부 논리**만 본다. 정본↔지시서 반영률(coverage)은 이 파이프라인에서 검증하지 않는다 — 필요하면 LLM 노드에 커버리지 축을 추가할 수 있다.)

### 3.5-1. Code 노드 (결정론적, best-effort)

- python 실행이 가능하면 실행한다. 불가하면 이 층을 건너뛰고 LLM 노드로만 판정한다(그 사실을 1줄 로그로 남김):
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" check-instruction --repo <REPO_ROOT> --file .requirements/requirement-{slug}.md
  ```
  - Windows에서 `python`이 안 되면 `py -3 ...` 또는 `cmd /c python ...` 순으로 시도한다.
- 출력의 각 `FAIL <CODE> <경로> <사유>` 줄과 **종료 코드**를 수집한다. 종료 코드 ≠ 0 → Code 위반 있음.
- 검사 항목: 메타 헤더(`유형:`)·유형 무관 필수(`[작업 목표]`·`[작업 내용]`)·유형별 필수·고정문구(유형 조건부).

### 3.5-2. LLM 노드 (지시서 내부 4축 건전성) — best-effort: codex 우선, 서브에이전트 폴백

지시서를 **감사 대상**으로 4축(모순·누락/미결·완료조건↔검증방법·엣지↔기대동작) **내부 건전성**을 판정한다. **codex가 있으면 codex(다른 모델)로 위임**해 모델 다양성을 얻고, 없거나 실패하면 **`requirement-critic` 서브에이전트로 폴백**한다. 두 경로의 판정 기준·출력 의미는 동일하다. (커버리지는 어느 쪽도 판정하지 않는다.)

#### (a) codex 우선
- `codex --version`을 시도한다(Windows에서 실행 파일이 `.cmd`/`.bat`이면 `cmd /c`로 래핑). 성공하면 아래로 위임한다.
- cwd = 프로젝트 루트. 프롬프트를 **stdin**으로 전달한다(모델 `zai/glm-5.2`, `-c model_reasoning_effort="high"` — 필요시 상향):
  ```bash
  codex exec --skip-git-repo-check -m zai/glm-5.2 -c model_reasoning_effort="high" -
  ```
- 프롬프트 템플릿(`{requirement_path}`를 실제 경로로 치환):
  ```
  # ROLE
  You are an instruction auditor. Judge ONLY the INTERNAL soundness of the 지시서 itself.
  Do NOT judge coverage against any source. Read the file directly.

  # ARTIFACT (read this file directly)
  {requirement_path}

  # TASK — 4축 내부 건전성
  A 모순: 항목 간 상충 / 완료조건↔작업목표·작업내용 상충 / 동일 대상 수치·식별자·결정값 불일치.
  B 누락·미결: 완료조건 최소 1개 / 언급된 입력·기능의 처리 정의 / 미결이 "미결로 명시".
  C 완료조건↔검증방법: 모든 완료조건에 대응 검증방법 / 떠도는 검증방법 없음 / 판정 가능.
  D 엣지↔기대동작: 명시된 엣지·오류마다 기대동작 / 정상경로와 양립.

  # RULES
  - 각 위반은 지시서 원문 인용을 근거로 한다. 인용으로 못 밝히면 위반 아님(오탐 억제).
  - 근거 없는 선택 항목의 정당한 생략은 누락이 아니다. 커버리지는 판정하지 않는다.

  # OUTPUT — STRICT
  축별 한 줄: A/B/C/D 각 `PASS|FAIL — 근거`.
  위반이 있으면 `[축] 위치 — 원문 인용 — 문제`로 나열.
  맨 마지막 줄 정확히: `RESULT: SUCCESS` 또는 `RESULT: FAIL`
  ```
- stdout에서 마지막 `RESULT:\s*(SUCCESS|FAIL)`를 파싱해 LLM 판정으로 삼고, 위반 줄을 수집한다. **파싱 실패·실행 오류 시 (b)로 폴백**한다.

#### (b) 서브에이전트 폴백
- codex가 없거나 실패하면 `requirement-critic` 서브에이전트를 **실제 독립 에이전트로** 호출한다. 파일 내용·수정 힌트 없이 **경로만 전달**한다:
  - `INSTRUCTION_PATH` = `.requirements/requirement-{slug}.md`
  - `REVIEW_PATH` = `.requirements/requirement-{slug}.gate.json`
- Critic은 4축을 판정하고 `SUCCESS|FAIL REVIEW_PATH=<path>`만 반환한다. `REVIEW_PATH`의 `findings`를 읽는다.

어느 경로든 결과 = **LLM 판정(SUCCESS/FAIL) + 위반 리스트**.

### 3.5-3. 판정 + 라우팅

- **게이트 FAIL** = (Code 종료코드 ≠ 0) **또는** (Critic FAIL). 그 외 **PASS**.
- 결과를 아래 형식으로 출력한다 — Code FAIL 줄과 Critic findings를 **하나의 위반 리스트**로 병합한다:
  ```
  [게이트] PASS | FAIL
  위반: (있을 때만, 축/항목 — 위치 — 근거)
    - Code / INSTR_TYPE_REQUIRED — requirement-{slug}.md — [완료 조건] 없음 (유형 기능개발 필수)
    - LLM C / AC-VERIFY-LINK — [완료 조건] 3항 — "응답 200ms 이내"에 대응 검증방법 없음
  ```
- **PASS** → 지시서 확정. Phase 5(후속 핸드오프)로 진행한다.
- **FAIL** → 위반 리스트를 노출하고, **반드시 `AskUserQuestion` 1회**로 분기한다. 임의로 진행하지 않는다.
  - question: "지시서 검증 게이트 FAIL — 위반 {N}건. 어떻게 할까요?"
  - options:
    - **자가수정 (Recommended)** — 위반 항목만 지시서에 반영해 `.requirements/requirement-{slug}.md`를 덮어쓴 뒤(meta-prompter 출력 규약 유지) **Phase 3.5를 재실행**. 자가수정 재실행은 **최대 2회**.
    - **재인터뷰** — 정본 자체의 결함이면 Phase 1/1.5로 돌아가 정본을 다시 다듬는다.
    - **무시하고 진행** — 위반을 남긴 채 Phase 5로 진행(권장하지 않음).
  - **게이트가 PASS 되거나 사용자가 "무시하고 진행"을 명시적으로 고르기 전에는 하류(task-write)로 넘어가지 않는다.**

---

## Phase 5 — 종료 및 후속 핸드오프

> ⛔ **게이트**: 지시서를 먼저 마감 보고한 뒤, 후속 핸드오프 질문을 **반드시 AskUserQuestion으로** 묻는다. 이 스킬은 구현 코드를 직접 작성하지 않는다 — 후속 진행 여부는 오직 사용자 선택으로만 결정된다.

### 5-1. 지시서 마감
- Phase 3.5 게이트를 PASS한 `.requirements/requirement-{slug}.md`를 확정하고, 최종 경로를 한 줄로 보고한다.

### 5-2. 후속 파이프라인 핸드오프 (AskUserQuestion, 1회)
- 5-1 직후, **반드시** `AskUserQuestion`으로 후속 실행 여부를 묻는다. 텍스트로만 묻고 넘어가지 않는다.
- question: "지시서 확정 완료 (`{최종 경로}`). 후속 파이프라인(pipeline-runner)을 실행할까요?"
- options (2개):
  - **지금 바로 실행 (Recommended)** — 이 세션에서 pipeline-runner를 인라인 실행
  - **여기서 종료** — 파이프라인 실행 안 함
- **지금 바로 실행** 선택 시: `skills/pipeline-runner/SKILL.md`를 읽어 **그 지침을 이 대화에서 그대로 수행**한다(인라인 실행 — 별도 프로세스·핸드오프 아님). 입력은 방금 확정한 `.requirements/requirement-{slug}.md`(= pipeline-runner Phase 0의 `<requirement-path>`), slug는 동일 값을 사용한다. pipeline-runner는 자체 승인 게이트(`Approval: pending`)에서 다시 멈추므로 즉시 구현으로 진입하지 않는다.
- **여기서 종료** 선택 시: 종료. 아무 후속 동작도 하지 않는다.

---

## 엣지 케이스

| 상황 | 처리 |
|---|---|
| grill-me 미확정/사용자 중단 | 파이프라인 중단, 지시서 생성 안 함 |
| acceptance-design 미확정/사용자 중단 | 파이프라인 중단, 지시서 생성 안 함 (정리본은 보존) |
| meta-prompter 필수 항목 누락 | meta-prompter 규칙대로 ≤3개 묶음 질문 |
| 지시서 검증 게이트 FAIL | 위반 리스트 노출 → 자가수정/재인터뷰/무시 분기, PASS 전 하류 차단 (Phase 3.5) |
| python 미설치 | Code 노드 스킵, LLM 노드로만 게이트 판정 (Phase 3.5) |
| codex 미설치/실행·파싱 오류 | LLM 노드는 `requirement-critic` 서브에이전트로 폴백 (Phase 3.5) |
| 같은 slug 재실행 | grill-me가 suffix(`-2`)로 slug를 분기하면 충돌 없음. 동일 slug면 기존 파일을 덮어쓴다 |

## slug 일관성 규칙

- `{slug}`는 grill-me가 실제로 저장한 파일명(`.requirements/grill-me-{slug}.md`)에서 파생한다 — 별도로 다시 만들지 않는다.
- 세 산출물은 항상 같은 `{slug}`를 공유한다: `grill-me-{slug}.md`(정리본) ↔ `{slug}-acceptance.md`(4축 설계본) ↔ `requirement-{slug}.md`(지시서).
- Phase 1.5는 acceptance-design 기본 slug(doc stem)을 무시하고 이 `{slug}`를 강제 적용한다.
