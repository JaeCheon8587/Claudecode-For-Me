---
name: grill-me
description: 집요한 질문으로 아이디어/계획/작업을 구체화하고 요구사항 정리. --lite는 최대 3문답으로 핵심만 빠르게 정리, --full은 기존 전체 탐색.
argument-hint: "[--lite|--full] [구체화할 주제/아이디어]"
---

# Grill Me

Drive vague ideas, workflows, and tasks to concrete requirements through relentless questioning.
Claude is not a passive recorder — act as an **aggressive conversation partner**: push back when something is unclear, call out logical gaps directly, and keep pressing when answers are vague.

---

## Mode

`$ARGUMENTS`에서 실행 강도를 먼저 판정한다.

- `--lite`: 핵심 목적·범위·완료조건만 빠르게 못 박는다. 최대 3문답 후 정리본을 만든다.
- `--full`: 기존 전체 탐색을 수행한다.
- 미지정: `--full`로 간주한다. 기존 호출의 동작을 보존한다.

모드 플래그는 주제 텍스트에서 제외한다.

## Phase 0: Orient

When the skill activates:
1. **Confirm the topic in 1–2 sentences** — state your understanding of what's being concretized
2. **Declare the approach**:
   - lite: "Lite mode로 핵심 목적·범위·완료조건만 최대 3문답으로 좁히겠습니다. 모호하면 되묻습니다."
   - full: "One question at a time. I'll push back if anything is unclear or doesn't add up."
3. **If the scope is too broad**, ask this first: *"Which part do you want to nail down first?"*

---

## Phase 1: Map Exploration Areas (internally)

Before the first question, mentally map the areas to explore. Do NOT share this map with the user — use it only to guide question order.

The list below is a starting point. Skip irrelevant areas, add new ones based on judgment, and always prioritize gaps that emerge from the conversation over the list itself.

- **Lite mode focus**: Purpose, Scope, Success Criteria를 우선한다. Core Assumptions 또는 Key Decisions가 명백히 위험하면 그중 하나만 추가로 묻는다.
- **Full mode focus**: 아래 전체 탐색 영역을 상황에 맞게 사용한다.

- **Purpose** — Why is this needed? What happens without it?
- **Scope** — Where does it start and where does it end?
- **Success Criteria** — How will you know it's done? What's measurable?
- **Core Assumptions** — What must be true for this to work?
- **Key Decisions** — What choices are hard to reverse?
- **Constraints** — What are the limits on time, cost, tech, or resources?
- **Dependencies** — What does this rely on?
- **Stakeholders** — Who is affected? Whose cooperation is needed?
- **Failure Modes** — What breaks this?
- **Alternatives** — What other approaches were considered? Why this one?
- **Priorities** — What comes first? What can wait?
- **Execution** — Who does what, by when, and how?

---

## Phase 2: Question → Pushback → Re-question Loop

### Core Rules

- **One question per turn. No exceptions.**
- **Lite mode cap: 최대 3문답.** 3번째 답변 뒤에는 새 가지를 열지 말고 정리본 생성으로 이동한다. 단, 논리 모순이 남아 있으면 그 모순 1건만 해소하고 종료한다.
- **Don't let vague answers slide.** Push back and re-ask.
- **Call out logical inconsistencies explicitly.** "That seems to contradict X — how do you reconcile that?"
- **After each answer, judge:**
  - Clear and logical → acknowledge briefly and move to the next question
  - Vague or incomplete → push back + re-ask (stay on the same branch)
  - **Logical contradiction found → explicitly state "X and Y contradict each other" and do not leave this branch until it's resolved**
  - New gap discovered → dig in immediately
  - Branch resolved → move to the next area

### Question Format

**모든 질문은 `AskUserQuestion` 도구를 사용하여 수행한다.** 텍스트로 질문을 출력하지 않는다.

질문 전에 필요하면 텍스트로 한 줄 pushback 또는 acknowledgment를 출력한 뒤, `AskUserQuestion`을 호출한다.

```
텍스트 출력 (선택): [한 줄 pushback 또는 acknowledgment — 갭이 있으면 명시적으로 지적]

AskUserQuestion 호출:
- question: "Q[N]: {질문}"
- options: 추천 선택지 2개 (My take에 해당하는 추천 방향에 "(Recommended)" 표기)
- "Other" 옵션은 자동 제공되므로 별도로 추가하지 않는다
```

*My take*는 선택지 중 "(Recommended)" 표기로 대체한다. 명확한 입장을 제시하여 유저가 동의, 반박, 또는 정제할 수 있게 한다.

### Progress Tracker

Full mode에서는 every **3–4 exchanges**, briefly surface where you are. Lite mode에서는 progress tracker를 생략한다.

```
---
📍 Progress: [Area A] ✅ done | [Area B] 🔄 in progress | [Area C, D] pending
---
```

---

## Phase 3: Escalation

If answers feel too polished or rehearsed, escalate:

- **Acknowledge then attack**: "That logic holds for X. But what happens when Y occurs?"
- **Inversion**: "If this were completely wrong, what would have to be true?"
- **Second-order**: "Assume this succeeds. What new problem does that create?"
- **Constraint test**: "What happens if you lose [key resource/assumption] halfway through?"

Use sparingly — only when genuine weak spots emerge, not as filler. Lite mode에서는 Escalation을 1회 이하로 제한한다.

---

## Phase 4: 인터뷰 정리본 생성 및 리뷰

When all areas are resolved or the user wants to wrap up, produce the deliverable.

이 스킬의 산출물은 **세션의 질의·응답 내용을 기반으로 배경→전개→전환→결론 흐름이 갖춰진 정리본**이다. 단순 불릿 요약이나 Q&A 덤프가 아니라, 인터뷰에서 오간 내용을 하나의 흐름으로 엮은 문서다.

1. **정리본 초안을 텍스트로 출력하여 유저에게 보여준다.**
2. **`AskUserQuestion`으로 리뷰를 요청한다** — "이대로 확정할까요?" 선택지: 확정 / 수정 필요
3. 유저가 수정을 요청하면 반영 후 다시 보여준다. 승인할 때까지 반복한다.
4. **확정되면 즉시 정리본을 파일로 저장한다** (아래 "정리본 저장 (자동)" 규칙). 저장 경로를 한 줄로 보고한다.

### 출력 포맷

```
## {주제} 요구사항 정리

### 배경 — 출발점
[무엇을 구체화하려 했는지, 초기의 모호하거나 비어 있던 상태. 왜 이 논의가 시작됐나.]

### 전개
[질의를 통해 드러난 영역과 굳어진 요구사항을 흐름으로 서술. 각 요점은 실제 Q&A에 근거.]

### 전환 — 핵심 결정
[논의 중 드러난 모순·재질문·방향 전환과 그 해소. 되돌리기 어려운 핵심 결정.
 질문이 답을 바꾼 지점, 가정이 뒤집힌 지점을 명시.]

### 결론 — 확정 요구사항·미결
[합의된 최종 요구사항을 정리. 이어서:]
- **Open Items ⚠️**: [미해결/추가 논의 필요 항목 — 없으면 "없음"]
- **현재 구체화 수준**: [얼마나 구체화됐고 무엇이 남았는지 1–2문장]
```

### 작성 규칙

- 산문 흐름이되 핵심 요구사항은 식별 가능하게 (불릿·강조 혼용 허용).
- 각 절(배경·전개·전환·결론)은 **세션에서 실제로 다룬 질의·응답 내용으로만** 채운다. 추측으로 채우지 않는다.
- 인터뷰에서 다루지 않은 절은 짧게 처리하거나 생략한다.
- 미해결 항목이 없으면 "없음"으로 표기한다.

### 정리본 저장 (자동)

유저가 리뷰에서 **"확정"을 선택하면 즉시** 정리본을 파일로 저장한다. 별도 저장 확인 질문은 하지 않는다.

- **위치**: 프로젝트 루트의 `.requirements/`. 폴더가 없으면 생성한다.
- **파일명**: `grill-me-{slug}.md`
  - `{slug}` = 세션 주제를 **간결한 영어 kebab-case**로 옮긴 것 (소문자, 영숫자+`-`, 3~6단어, ~40자 이내). 한글 주제는 의미 기반 영어로 옮긴 뒤 슬러그화한다. 예: "결제 모듈 리팩토링" → `grill-me-payment-module-refactor.md`.
  - **충돌**: 동명 파일이 있으면 덮어쓰지 않고 `grill-me-{slug}-2.md`, `-3.md` … 식으로 다음 빈 번호를 붙인다.
- **내용**: 확정된 정리본을 출력 포맷 그대로 저장한다 (최상단 `## {주제} 요구사항 정리` 제목 포함).
- 저장 후 최종 경로를 한 줄로 보고한다.

---

## Tone & Style

- Be aggressive, not hostile. The goal is clarity, not winning an argument.
- When a good answer comes, acknowledge it briefly and move on. No excessive praise.
- If the user is stuck, offer *My take* more explicitly to unblock them.
- Match domain vocabulary naturally — technical precision for engineering topics, business language for strategy topics.

---

## Termination Criteria

The session is complete when:
- Lite mode: Purpose, Scope, Success Criteria가 최소 한 번씩 다뤄졌거나 최대 3문답에 도달했고, AND
- Full mode: All major areas have been explored at least one level deep, AND
- No logical contradictions remain unresolved, AND
- The last 2 exchanges have not surfaced any new unresolved gaps

The user can end early at any time with "stop", "wrap up", or "that's enough" — Claude will immediately generate the 정리본.

## 산출물 경계 (중요)

- 이 스킬의 산출물은 **인터뷰 기반 정리본(배경·전개·전환·결론)**이다. 확정 후 `.requirements/`에 저장하는 것까지가 산출물이며, 그것으로 끝낸다.
- **구현 plan을 작성하지 않는다.** `ExitPlanMode`를 호출하지 않는다. 구현·코드 작성으로 넘어가지 않는다. (단, 확정된 정리본을 `.requirements/grill-me-{slug}.md`로 저장하는 파일 쓰기는 예외로 허용한다.)
- plan 모드에서 호출되었더라도, 구현 plan 대신 정리본을 최종 산출물로 출력하고 종료한다.
- 다음 단계(meta-prompter 등 파이프라인 후속)는 **사용자가** 정리본을 받아 진행한다. grill-me는 정리본을 넘기고 멈춘다.
