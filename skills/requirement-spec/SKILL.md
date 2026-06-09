---
name: requirement-spec
description: 요구사항을 대화로 도출하고 완료조건·검증을 설계한 뒤 개발 지시서로 정제하고 codex로 자기검증하는 메타 스킬. grill-me로 요구사항 도출 → acceptance-design으로 완료조건·엣지·오류·검증 4축 설계 → meta-prompter로 개발 지시서 정제 → .requirements/requirement-{slug}.md 저장 → codex로 정리본+설계본 대비 반영도(%) 검증 → 보완점 1회 반영. "요구사항 지시서 만들어줘", "요구사항부터 같이 정리해서 작업지시서까지", "요구사항 도출하고 검증까지", "requirement-spec" 요청 시 트리거.
argument-hint: "[요구사항 도출할 주제]"
---

# Requirement Spec

요구사항 도출부터 개발 지시서 산출·자기검증까지를 **한 번의 호출로 자동 진행**하는 메타 스킬.
기존 스킬(`grill-me`, `acceptance-design`, `meta-prompter`)을 인라인 실행으로 엮고, codex 위임 검증을 붙인 오케스트레이터다.

**최종 산출물**: `.requirements/requirement-{slug}.md` — 다른 AI 에이전트가 그대로 수행할 수 있는 개발 지시서.
`{slug}`는 grill-me 결과물(`.requirements/grill-me-{slug}.md`)과 **동일**하다.

---

## 동작 원칙

- **자동 인라인 체인**: Phase 1~6을 자동으로 이어 간다. **사용자 상호작용은 grill-me 인터뷰(Phase 1)·acceptance-design 인터뷰(Phase 1.5)·최종 리뷰(Phase 5)에서만** 발생한다.
- **인라인 실행**: 다른 스킬을 호출할 때는 해당 `SKILL.md`를 읽어 **그 지침을 이 대화에서 그대로 수행**한다(별도 프로세스·핸드오프 아님).
- **산출물 경계**: 지시서 저장/갱신까지가 이 스킬의 끝이다. **구현 코드를 작성하지 않고, `ExitPlanMode`를 호출하지 않는다.** (단, 정리본·지시서를 `.requirements/`에 저장하는 파일 쓰기는 허용.)
- **Phase 게이트(전역)**: 각 Phase는 게이트다. 해당 Phase의 **전이 조건(완료 조건)을 충족하기 전에는 절대로 다음 Phase로 넘어가지 않는다.** 건너뛰기·앞당기기 금지. 각 Phase 머리의 ⛔ 게이트 문구를 매번 확인한다.

---

## Phase 0 — Orient

> ⛔ **게이트**: 주제 확인 + 파이프라인 선언을 **마치기 전에는 절대** Phase 1로 넘어가지 않는다.

스킬 활성화 시:
1. 주제를 1~2문장으로 확인한다.
2. 파이프라인을 1줄로 선언한다: *"요구사항 도출(grill-me) → 완료조건·검증 4축 설계(acceptance-design) → 개발 지시서 정제(meta-prompter) → 저장 → codex 검증 → 보완. grill-me·acceptance-design 인터뷰 외에는 자동 진행한다."*
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
- 산출 = 코드블록 1개(메타헤더 + 본문 + `[에이전트 행동 규칙]` 가드레일 4문구, **개조식** 종결).
- **주의**: meta-prompter는 파일을 저장하지 않는다. 저장은 Phase 3에서 이 스킬이 직접 한다.

---

## Phase 3 — 지시서 저장

> ⛔ **게이트**: `.requirements/requirement-{slug}.md` 저장이 완료되기 **전에는 절대** Phase 4로 넘어가지 않는다.

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

## Phase 4 — codex 자기검증

> ⛔ **게이트**: codex 결과 회수(Coverage 추출 또는 raw 확보)가 끝나기 **전에는 절대** Phase 5로 넘어가지 않는다. codex 미설치/오류 분기일 때는 Phase 5~6을 건너뛰고 즉시 종료한다(그 외 경로로 진행 금지).

grill-me 정리본 + acceptance 4축 설계본을 기준(GROUND TRUTH), requirement 지시서를 검증 대상(ARTIFACT)으로 두고 codex에 위임한다.

### 가용성 체크
- `codex --version`을 시도한다. 실패하면:
  ```
  codex CLI 미설치. `/codex:setup`을 먼저 실행하세요. (검증 생략 — 지시서는 저장됨)
  ```
  를 안내하고 **Phase 5~6을 건너뛰고 종료**한다(지시서 산출물은 그대로 보존).

### 호출
- **cwd = 프로젝트 루트** (codex가 `.requirements/*.md`를 직접 읽도록).
- 아래 프롬프트를 **stdin**으로 전달한다 (모델 `gpt-5.5`, reasoning effort 레벨 `high` 고정):
  ```bash
  codex exec --skip-git-repo-check -m gpt-5.5 -c model_reasoning_effort="high" -
  ```
  - reasoning effort는 CLI 플래그가 아니라 **config 키 `model_reasoning_effort`**로 전달한다(`-c`). 값(레벨)은 `minimal`/`low`/`medium`/`high`. (`--effort` 플래그는 존재하지 않음.)
  - Windows에서 `codex` 실행 파일이 `.cmd`/`.bat`이면 `cmd /c codex exec --skip-git-repo-check -m gpt-5.5 -c model_reasoning_effort="high" -` 로 래핑한다.
  - 장시간(최대 ~30분) 걸릴 수 있다.

### codex 프롬프트 템플릿
`{grill_me_path}`, `{acceptance_path}`, `{requirement_path}`를 실제 경로로 치환해 전달한다:

```
# ROLE
You are a requirements auditor. The grill-me 정리본 + acceptance 4축 설계본 together are the GROUND TRUTH (확정 요구사항·완료조건·검증 설계).
The requirement 지시서 is the ARTIFACT to audit. Judge how completely the 지시서 reflects the GROUND TRUTH.
Do not invent requirements not present in the GROUND TRUTH.

# GROUND TRUTH — 요구사항 정리본 (read this file directly)
{grill_me_path}

# GROUND TRUTH — 완료조건·엣지·오류·검증 4축 설계본 (read this file directly)
{acceptance_path}

# ARTIFACT (read this file directly)
{requirement_path}

# TASK
1. GROUND TRUTH(정리본+설계본)에서 확정 요구사항·핵심 결정·완료조건·엣지케이스·오류케이스·검증방법·Open Items를 빠짐없이 추출해 체크리스트로 만든다.
2. 각 항목이 ARTIFACT(지시서)에 반영됐는지 판정한다: ✓ 반영 / ⚠ 부분 / ✗ 누락.
3. Coverage %를 아래 RUBRIC으로 계산한다.
4. 보완 필요 항목과 "지시서의 어디를 어떻게 고쳐야 하는지"를 구체적으로 제시한다.

# OUTPUT FORMAT — STRICT
No preamble before `## Checklist`. No epilogue after the `Coverage: N%` line.

## Checklist (from GROUND TRUTH)
| # | 요구사항 (정리본 근거) | 상태 | 지시서 반영 위치/항목 | 비고 (누락·약한 부분) |
|---|---|---|---|---|
| 1 | <정리본 요구사항 한 줄> | ✓/⚠/✗ | <지시서 항목/섹션 or MISSING> | <≤120자, ✗·⚠는 누락 내용 명시> |
| 2 | ... | ... | ... | ... |

(GROUND TRUTH의 모든 요구사항을 열거. 같은 주제 요구는 한 행으로 통합하고 상태는 가장 나쁜 것 우선 ✗ > ⚠ > ✓.)

## Gaps to Fix
1. [<상태>] <항목> — 지시서의 <항목/섹션>을 <어떻게> 보완. (정리본 근거 "...")
2. ...

(보완 필요 항목만. 최대 10개. 없으면 `- (none)`.)

## Coverage
Counts: ✓ <a>, ⚠ <b>, ✗ <c>
<가중 산식을 명시: 각 행 weight = 핵심 요구 2, 부수 요구 1. ✓는 weight 전액, ⚠는 0.5×weight, ✗는 0.
 pct = round(100 × passed_weight / total_weight). 예: "✓2개(2,2), ⚠1개(2→1), ✗1개(1→0) → passed=5 / total=7 → 71%">

Coverage: <integer 0-100>%

# FIELD RULES
- 상태 기호: 정확히 ✓, ⚠, ✗ 중 하나.
- ⚠ Partial: 항목은 언급됐으나 정리본의 결정·제약·수치가 일부 누락. 핵심 literal(수치·식별자·결정값)이 빠지면 ⚠가 아니라 ✗.
- ✗ Missing: 지시서에 해당 요구가 전혀 없거나 정반대.
- Open Items(미결)는 "지시서에 미결로 명시됐는가"로 판정한다.
- 의심스러우면 더 엄격한 쪽(✗ over ⚠, ⚠ over ✓)을 택한다.
- 100%는 모든 행이 ✓일 때만.
```

### 출력 회수
- stdout을 캡처한다.
- 마지막 `Coverage: <N>%` 라인에서 정수를 추출한다(정규식 `Coverage:\s*(\d{1,3})%`, 마지막 매칭).
- 파싱 실패 시 codex raw 출력을 그대로 사용자에게 노출하고 Phase 5로 진행한다.

---

## Phase 5 — 사용자 리뷰

> ⛔ **게이트**: 사용자의 답(반영/미반영)을 받기 **전에는 절대** Phase 6으로 넘어가지 않는다. 임의로 반영 여부를 가정하지 않는다.

- codex 결과를 텍스트로 요약·노출한다: **Coverage %**, ✗/⚠ 항목, **Gaps to Fix** 목록.
- 리뷰 시 **반드시** `AskUserQuestion`을 사용.
- `AskUserQuestion` 1회:
  - question: "codex가 찾은 보완점을 지시서에 반영할까요? (Coverage {N}%)"
  - options: **반영 (Recommended)** / **미반영 — 현 지시서 확정**

---

## Phase 6 — 반영 후 종료

> ⛔ **게이트**: Phase 5의 사용자 선택에 따라서만 동작한다. 이 Phase로 스킬이 **종료**되며, 구현·코드 작성 단계로 넘어가지 않는다.

- **반영 선택**: codex의 `Gaps to Fix`를 지시서에 반영해 `.requirements/requirement-{slug}.md`를 **덮어쓴다**.
  - meta-prompter 출력 규약(개조식 종결, 항목 형식, 가드레일 4문구, 코드블록 본문 구조)을 유지한다.
  - 갱신 후 최종 경로를 한 줄로 보고한다.
- **미반영 선택**: 현 지시서를 그대로 확정하고 경로를 보고한다.
- 종료. 구현 단계로 넘어가지 않는다.

---

## 엣지 케이스

| 상황 | 처리 |
|---|---|
| grill-me 미확정/사용자 중단 | 파이프라인 중단, 지시서 생성 안 함 |
| acceptance-design 미확정/사용자 중단 | 파이프라인 중단, 지시서 생성 안 함 (정리본은 보존) |
| meta-prompter 필수 항목 누락 | meta-prompter 규칙대로 ≤3개 묶음 질문 |
| codex 미설치 | `/codex:setup` 안내, Phase 5~6 스킵, 지시서 보존하고 종료 |
| codex timeout/실행 오류 | 에러 노출, 지시서 보존, 검증 생략 종료 |
| `Coverage:` 파싱 실패 | codex raw 출력 노출 후 Phase 5 진행 |
| 같은 slug 재실행 | grill-me가 suffix(`-2`)로 slug를 분기하면 충돌 없음. 동일 slug면 Phase 6 갱신 흐름으로 흡수 |

## slug 일관성 규칙

- `{slug}`는 grill-me가 실제로 저장한 파일명(`.requirements/grill-me-{slug}.md`)에서 파생한다 — 별도로 다시 만들지 않는다.
- 세 산출물은 항상 같은 `{slug}`를 공유한다: `grill-me-{slug}.md`(정리본) ↔ `{slug}-acceptance.md`(4축 설계본) ↔ `requirement-{slug}.md`(지시서).
- Phase 1.5는 acceptance-design 기본 slug(doc stem)을 무시하고 이 `{slug}`를 강제 적용한다.
