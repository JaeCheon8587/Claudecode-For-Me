---
name: requirement-spec
description: grill-me 인터뷰로 기능 문서(Intent)를 새로 쓰거나 고치는 스킬 — App 마다 Intent 1개, 계약이 바뀌면 호출하는 App · 제공하는 App 둘 다. Part 1(왜 · 무엇 · 결정)을 쓰고 Part 2(테스트할 수 있는 동작 FR · E · X)를 파생한 뒤, 코드 생성 체크리스트 + opus 판정 루프(Intent 마다 최대 3회)로 검증하고 품질 지표를 남겨 사용자 확정 1회로 끝낸다. 고칠 때는 고치기 전 사본(기준선)을 남겨 /task-split 이 바뀐 항목을 Task 로 자르게 한다. "요구사항 정리해서 명세까지", "기능 명세 만들어줘", "Intent 작성", "Intent 수정", "requirement-spec" 요청 시 트리거
argument-hint: "[<Intent ID 또는 경로> ...] [--app <App> ...] [--no-gate]"
---

# Requirement Spec

요구사항을 인터뷰로 도출해 **기능 문서(Intent)** 를 새로 쓰거나 고치는 스킬이다. Intent 는 기능 하나가 어떻게 동작해야 하는지를 담는 상시 문서다(App 소속, 기능 1개 = Intent 1개). 인터뷰 결과는 Part 1(왜 · 무엇 · 결정)이 되고, Part 2(테스트할 수 있는 동작 FR · E · X)는 Part 1만 근거로 세션이 파생한다. 파생한 Intent 는 코드가 생성한 체크리스트와 opus 서브에이전트 판정으로 검증하고, 결과를 품질 지표로 남긴 뒤 사용자 확정 1회로 끝내고 거기서 멈춘다. 다른 스킬을 쓸 때는 해당 `SKILL.md`를 읽어 **그 지침을 이 대화에서 그대로 수행**한다(인라인 실행 — 별도 프로세스·핸드오프 아님).

흐름에서의 자리: **`requirement-spec`**(Intent 작성 · 수정) → `/task-split`(바뀐 항목을 Task 로) → `/worktree-init <이름>`(워크트리) → 개발 세션 → `finish TSK-<NNN>` → 머지 → `/worktree-delete`.

## 핵심 원칙

- **산출물은 대상 Intent** — `docs/<App>/INTENT/<App>-INT-<NNN>.md`, App 마다 1개. 계약(API · 요청/응답 필드 · 오류 코드)이 바뀌면 호출하는 App 과 제공하는 App 의 Intent 를 한 실행에서 함께 쓴다. 새로 쓰기(새 기능)와 고치기(있는 기능)를 한 실행에 섞을 수 있다.
- **인터뷰는 grill-me 1회** — 대상 Intent 가 여럿이어도 한 번이다.
- **Part 2는 질문 없이 파생** — Part 1에서 도출한다.
- **고치기 전에 기준선을 남긴다** — 문서는 커밋하지 않아 git 이력이 "고치기 전" 을 알려 주지 못한다. 고치기 전 사본(`.process/intent-base/<ID>.md`)이 `/task-split` 이 바뀐 항목을 뽑는 기준이다.
- **바꾸지 않는 항목은 글자 하나도 고치지 않는다** — `/task-split` 은 기준선과 문장이 다른 FR · E · X 를 전부 변경으로 자른다. 진행 표시(`[TSK-<NNN> 진행 중]` · `[TSK-<NNN> 삭제 예정]`)가 붙은 항목은 그 Task 가 끝나기 전에 고치지 않는다.
- **검증 기준은 인터뷰다** — 인터뷰 전사에서 1회 도출한 오라클(`expected.md`, 이후 불변)과 코드가 회차마다 만드는 사실표를 함께 쓴다. LLM 판정은 Intent 마다 최대 3회다.
- **확정은 1회** — Intent 에는 승인 행이 없다. 변경의 승인은 `/task-split` 이 Task 와 함께 받는다.
- **완료 조건 · 확인 방법 · 위험 · 착수 정보는 쓰지 않는다** — Task 몫이다(`/task-split`).
- **내부 코드 이름은 쓰지 않는다** — 클래스 · 인터페이스 · 메서드 · 함수 · 속성 · 필드 · 변수 · 네임스페이스 · 파일. 밖에서 보이는 이름(API 경로 · 요청/응답 필드 · 설정 키 · 오류/상태 코드 · 화면 문구)은 `종류어 + 백틱`으로 쓴다(응답 필드 `retryCount`). 상세는 Intent 템플릿 작성 규칙 1~3 · DOCUMENT_GUIDE §1.4.
- **문서는 커밋하지 않는다** — 문서 폴더(`docs` · `Docs`) · `.task/` · `.process/` 는 `.git/info/exclude` 에 올리고 `git add` 하지 않는다(팀 정책).
- **후속 단계(Task · 개발)는 자동 실행하지 않는다** — `/task-split` 을 안내만 한다.
- 모든 대화·산출물은 **한국어**로 쓴다(섹션 헤딩은 템플릿의 영어 표기 유지).

helper 경로:

```bash
DH="${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py"
```

---

## Phase 0 — Orient

1. **Python 3.10+ 확인**: `python --version`(없으면 `py -3 --version`). 없으면 중단하고 설치를 안내한다 — 기준선 · 검사 · 카탈로그가 모두 스크립트다.
2. **exclude 보장**: `python "$DH" ensure-exclude --repo .` — `ADDED` 면 한 줄 고지("`.git/info/exclude` 에 문서 폴더 · `.process/` 를 올렸다 — 커밋되지 않는다"). `WARN TRACKED` 가 있으면 그대로 전한다 — 이미 커밋된 문서는 숨지 않는다. 추적을 끊을지(`git rm --cached`)는 사용자가 정한다. **대신 하지 않는다.** `FAIL EXCLUDE`(git repo 아님)면 중단한다.
3. **`--no-gate` 해석**: `$ARGUMENTS` 에 `--no-gate` 가 있으면 2a(오라클) · Phase 3 을 건너뛰고, Phase 4 는 최소 quality.json 만 쓴다. Phase 5 는 그대로 수행하고 검증을 `SKIPPED — --no-gate` 로 보고한다.
4. **템플릿 경로 해석** — 순서대로 시도한다:
   1. repo 의 `docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md`
   2. 없으면 `${CLAUDE_PLUGIN_ROOT}/docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md`
   3. 둘 다 없으면 **중단**하고 그 사실을 보고한다.
5. **대상 정하기**:
   - `$ARGUMENTS` 의 Intent ID(`LOADER-INT-003`) 또는 경로 → **고치기** 대상. 파일이 없으면 중단하고 보고한다.
   - `--app <App>` → 그 App 의 **새로 쓰기** 대상 1개. 여러 번 줄 수 있다. 문서 ID 는 그 App 의 `INTENT/` 에 있는 `<App>-INT-*.md` 중 최대 번호 + 1(3자리 0패딩, 없으면 `001`)이다.
   - 둘 다 없으면 **한 번** 묻는다(산문) — 있는 Intent 목록(ID · 제목 · 상태 — `docs` · `Docs` 둘 다 본다)을 보여 주고 "새 기능이면 App, 있는 기능을 고치면 Intent ID, 계약을 주고받는 App 이 있으면 모두" 를 묻는다. 답이 없으면 중단하고 사유를 보고한다.
   - 문서 폴더는 레포에 이미 있는 표기를 쓴다 — `Docs/` 가 있으면 `Docs/<App>/INTENT/`. `docs` · `Docs` 는 같은 폴더로 보며(이 스킬의 `docs/` 는 둘 다를 뜻한다) 대소문자만 다른 폴더를 새로 만들거나 이름을 바꾸지 않는다.
6. **작업 폴더**: `<W>` = `.process/intent-check/<첫 대상 Intent ID>-<YYYYMMDD-HHMM>/` 를 만든다. 실행마다 새 폴더다 — 같은 Intent 를 다시 고쳐도 앞선 실행의 기록을 덮지 않는다. Intent 별 산출물은 하위 폴더 `<W>/<Intent ID>/` 에 쓴다.
7. **고치기 대상마다**:
   1. **v1 판별** — 메타에 `유형` · `승인` · `검증` 행이 있거나 Part 2 에 `Acceptance` · `Verification` · `Risks` · `Handoff` 섹션이 있으면 v1(3.74 이하) 문서다. v2 로 옮길지 **한 번** 묻는다 — 거절하면 그 대상을 빼고 보고한다(남은 대상이 없으면 중단). 이 스킬은 v1 문서를 쓰지 않는다.
   2. **고치기 전 사본**: Intent 를 `<W>/before/<Intent ID>.md` 로 복사한다 — 중단할 때 되돌리는 원본이다(v1 이면 옮기기 전 모습).
   3. **v1 옮기기**(v1 일 때만) — 동작은 바꾸지 않고 형식만 옮긴다:
      - 메타를 5행 `문서 ID · 기능 ID · 상태 · 작성 · 관련 Intent` 로 바꾼다 — `기능 ID` 는 App PRD §7 기능 목록에서 이 Intent 를 가리키는 행(없으면 사용자에게 묻는다), `상태` = `active`. `유형` · `승인` · `검증` 행은 지운다.
      - 헤딩을 `## Part 1 — 기능 정의` · `## Part 2 — 동작` 으로 바꾸고, `Acceptance` · `Verification` · `Risks` · `Handoff` 섹션을 지운다 — Task 몫이다. 섹션 주석 · 작성 규칙 주석은 v2 템플릿 것으로 바꾼다.
      - `python "$DH" check-intent --repo . --file <intent> --json` 의 FAIL 을 0 으로 만든다 — 이름 규칙(`INT_NAME_*`) 위반 문장은 뜻을 바꾸지 않고 표현만 고친다. 기준선보다 먼저 해야 이 고침이 변경으로 잘리지 않는다.
   4. **기준선**: `python "$DH" intent-base --repo . --intent <Intent ID> --save` — v1 에서 옮긴 문서이고 그 v1 `상태` 가 `in-dev` · `in-review` · `done`(옛 방식으로 개발함)이면 `--implemented` 를 붙인다(`draft` · `approved` 는 아직 코드가 없다). 결과를 대상마다 기록한다 — Phase 5 가 쓴다:
      - `SAVED` — 이번 실행이 기준선을 남겼다.
      - `KEPT` — 앞서 고치고 아직 자르지 않은 기준선이 있다. 그대로 둔다 — 그 고침과 이번 고침이 함께 잘린다.
      - `NEW` — 아직 한 번도 자르지 않은 Intent 라 기준선이 필요 없다(자를 때 항목 전부가 신규다).
   5. **지금 상태**: `python "$DH" intent-diff --repo . --intent <Intent ID> --json` —
      - `next_ids` — 새 항목에 쓸 번호(D · C · FR · E · X). 지운 번호까지 세므로 이 값을 쓴다.
      - `mode` 가 `base` 이고 `changes` 가 있으면(`KEPT`) 앞선 고침이 아직 잘리지 않았다 — 목록을 고지한다. `mode` 가 `new` 면(`NEW`) 한 번도 자르지 않은 Intent 라 자를 때 항목 전부가 신규다 — 한 줄로 고지한다.
      - 진행 표시가 붙은 항목을 모아 고지한다 — 그 Task 가 끝나기(`done`) 전에는 고치지 않는다. 표시의 Task 가 초안(`draft`)이면 앞서 중단한 자르기다 — 그 항목을 고쳐야 하면 `/task-split` 을 다시 실행해 그 초안을 지운 뒤 고친다.
8. **새로 쓰기 대상마다**: `docs/<App>/INTENT/` 가 없으면 만들고, 템플릿을 `docs/<App>/INTENT/<App>-INT-<NNN>.md` 로 복사한 뒤 TEMPLATE 경고 블록을 삭제한다. 메타 `문서 ID` · `작성`(`<작성자> · <YYYY-MM-DD>`)을 채우고 `상태` 는 `active` 로 둔다. 1행 제목 · `기능 ID` · `관련 Intent` 는 Phase 1 끝에 채운다.

**전이 조건**: 대상 1개 이상 확정 + 고치기 대상의 사본 · 기준선 결과 기록 + 새로 쓰기 대상 파일 생성.

---

## Phase 1 — grill-me 인터뷰 (인라인)

`skills/grill-me/SKILL.md` 를 읽어 그 Phase 0~4 를 **그대로** 수행한다. 아래 **오버라이드 5개 외에는 grill-me 절차를 바꾸지 않는다**(질문 1개/턴, `AskUserQuestion` 사용, pushback·escalation 규칙 모두 유지). 고치기 대상이 있으면 인터뷰 전에 그 Intent 를 읽는다 — 질문은 지금 동작에서 무엇이 바뀌는지에 맞춘다.

1. **탐색 영역 추가** — grill-me Phase 1(Map Exploration Areas)의 영역 목록에 4개를 더한다: `동작 기준(무엇이 되면 맞게 동작하는가)`, `Out of scope`, `결정과 기각 대안`, `계약을 주고받는 App`(다른 App 이 이 기능을 호출하는가, 이 기능이 다른 App 을 호출하는가). 고치기 대상이 있으면 `지금 동작에서 바뀌는 것 · 그대로 둘 것` 도 더한다.
2. **출력 포맷 교체** — grill-me Phase 4 의 정리본 포맷(배경·전개·전환·결론) 대신 **대상 Intent 마다 Part 1 의 6섹션**(Problem / Outcome / Affected / Constraints / Decisions / Open questions)으로 출력하고, 확정된 내용을 그 Intent 파일의 Part 1 에 기록한다. Constraints · Decisions 항목 번호는 새로 쓰기면 `C1.` · `D1.` 부터, 고치기면 `next_ids` 부터 붙인다 — 있는 번호는 바꾸지 않는다. 고치기 대상은 바뀐 줄을 제시한다. **정리본 파일은 만들지 않는다** — 산출물은 Intent 파일이다.
3. **리뷰는 유지, 저장 단계만 제외** — grill-me Phase 4 리뷰 절차 중 **1~3단계**(정리본 초안 제시 · `AskUserQuestion` 으로 확정 확인 · 수정 반영 후 재제시)는 그대로 둔다. **4단계(정리본 파일 자동 저장)는 수행하지 않는다** — 확정 내용을 Intent 파일의 Part 1 에 기록하는 것으로 대체한다. 사용자가 Part 1 을 확인·확정한 뒤에 Phase 2 로 간다.
4. **전사 기록 추가** — 인터뷰 원문을 `<W>/interview.md` 에 남긴다. 대상이 여럿이어도 한 파일이다. 이 파일이 Phase 2 오라클의 유일한 입력이다.
   - grill-me 가 질문을 던진 **매 턴 직후** append 한다: `Q<n>. <질문 원문>` / `A<n>. <답변 원문>`.
   - `AskUserQuestion` 선택 답은 `A<n>. [선택] <라벨>` 로 쓰고, 다중 선택은 `[선택] <라벨1> · <라벨2>` 로 잇는다. 자유 입력이 있으면 같은 줄에 `[입력] <원문>` 을 덧붙인다.
   - **인터뷰 시작 전 발화**(사용자가 준 주제·제약, Phase 0 질문에 대한 답)는 파일 맨 위 `Q1` 앞에 `Q0. (인터뷰 전 — 질문 없음)` / `A0. <원문>` 으로 적는다. 여러 건이면 `A0.` 아래 `- <원문>` 으로 잇는다. expector 는 여기서 나온 항목의 출처를 `Q0/A0` 으로 쓴다.
   - 질문 턴 밖의 사용자 발화(자발 발언·중간 정정)는 **직전 `A<n>` 에 원문 그대로 이어 쓴다** — 새 `Q` 를 만들지 않는다. 별도 줄(`(인터뷰 중 발화)` 등)로 떼어 쓰지 않는다 — 떼면 expector 가 인용할 번호가 없다.
   - `templates/intent-expector.md`·`templates/intent-critic.md` 는 **Phase 1 중에 읽지 않는다** — 오라클 추출 규칙을 아는 채로 전사를 쓰면 전사가 오라클에 맞춰진다. 2a·3d 에서 처음 읽는다.
   - **요약·합성 금지** — 원문만 쓴다. 세션이 해석한 문장은 쓰지 않는다.
   - grill-me Phase 4 리뷰에서 사용자가 고친 것은 `R<n>. <사용자 요청 원문>` 만 기록한다. 반영 결과·요약은 쓰지 않는다(Part 1 누출 방지).
   - 인터뷰 종료 시 `Q` 개수 == 질문 턴 수를 확인한다. 불일치면 누락 턴을 채운 뒤 진행한다.
   - **정리본(Part 1)은 여기 쓰지 않는다.**
   - 한계: 선택지 라벨은 세션이 쓴 문구다 — 독립성은 "사용자가 무엇을 골랐는가" 수준이다.
5. **대상 추가** — 인터뷰 중 계약을 주고받는 App 이 더 드러나면 사용자에게 확인하고 대상에 더한다 — Phase 0 의 7(고치기) 또는 8(새로 쓰기)을 그 대상에 수행한다. 전사는 같은 파일에 이어 쓴다.

Part 1 은 세션에서 실제로 다룬 질의·응답으로만 채운다(grill-me 작성 규칙). 인터뷰가 끝나면 대상마다 채운다:

- **1행 제목**(새로 쓰기) — `<문서 ID> — <기능 이름>`. 기능 이름은 App PRD §7 의 기능명을 쓴다(행이 없으면 인터뷰에서 확정한 이름).
- **`기능 ID`**(새로 쓰기) — App PRD(`docs/<App>/<App>-PRD.md`) §7 기능 목록에서 이 기능의 행. 행이 없으면 다음 번호를 제안해 사용자에게 확인하고, PRD §7 에 그 행을 더해야 한다고 종료 보고에 적는다 — 이 스킬은 PRD 를 고치지 않는다.
- **`관련 Intent`** — 이번 대상끼리 계약을 주고받으면 서로의 ID 를 ` · ` 로 적는다(양쪽 다). 대상 밖 Intent 와 맞물리면 이 문서에만 적고, 그 Intent 에는 없다는 것을 종료 보고에 적는다.

**전이 조건**: 대상마다 Part 1 의 6섹션이 채워짐(`Open questions` 는 `none` 허용) + 1행 제목 · `기능 ID` 확정.

---

## Phase 2 — 오라클 도출 + Part 2 파생

이 Phase 에서 두 가지를 함께 진행한다 — **expector 스폰**(인터뷰 오라클)과 **메인 세션의 Part 2 파생**. expector 는 Part 2 를 보지 않는다. `--no-gate` 면 2a 를 건너뛴다.

### 2a — expector 스폰 (오라클)

`templates/intent-expector.md` 를 Read 해 `{{INTERVIEW_PATH}}` `{{INTENTS}}` `{{INTENT_ID}}` `{{EXPECTED_PATH}}` 를 실제 값으로 치환하고, **치환된 전문을 프롬프트로 그대로** 전달한다 — `Agent(subagent_type: "general-purpose", model: "opus", prompt: <치환 전문>)`.

- `{{INTENTS}}` = 대상마다 한 줄 `<Intent ID> — <App> — <기능 이름>`, `{{INTENT_ID}}` = 그 첫 줄의 Intent ID, `{{EXPECTED_PATH}}` = `<W>/expected.md`.
- 대상이 여럿이면 expector 가 항목마다 `— 대상: <Intent ID>` 를 붙인다 — 3b 가 Intent 마다 그 Intent 를 대상으로 한 항목만 행으로 만든다.
- **expector 가 `expected.md` 를 직접 쓴다.** 세션은 반환을 옮겨 적지 않는다 — 파일이 생겼는지만 확인한다. **파일 미작성** — 세션이 `{{EXPECTED_PATH}}` 존재를 먼저 확인한다. 없으면 같은 에이전트에 `FAIL READ_TEXT cannot read: <경로>` 한 줄**만** 붙여 1회 재요청한다.
- **세션은 `expected.md` 를 편집하지 않는다** — 오라클은 불변이다. 형식이 어긋나도 고쳐 쓰지 말고 아래 재요청 규칙을 따른다.
- 형식 검증은 1회차 3b 에서 `--oracle` 로 실행할 때 이뤄진다. exit 2 는 세 갈래다:
  - stdout `ORACLE: <Intent ID> 를 대상으로 한 EXP 항목이 없다` → 그 Intent 만 **오라클 없음 폴백**이다. 재요청하지 않는다 — 다시 시키면 인터뷰에 없는 항목을 지어낸다.
  - 그 밖의 `ORACLE:` 줄 → **형식 오류**. 파일 하나의 문제라 대상마다 같은 줄이 나온다 — 아래 재요청 규칙대로 expector 에 **한 번** 재요청한다(대상이 여럿이어도 한 번).
  - `ORACLE:` 줄 없이 stderr `FAIL READ_TEXT cannot read: <expected.md 경로>` → **경로 읽기 실패** — 파일은 있는데 세션이 넘긴 경로가 틀린 경우다. 경로를 고쳐 1회 재실행한다. stderr 가 Intent 경로의 `FAIL READ_TEXT` 거나 `FAIL PARSE` 면 오라클이 아니라 Intent 문제다 — 3a 로 돌아가 고친다.
- **재요청 규칙** (2a·3e 공통):
  - **형식 오류** → 같은 에이전트에 파서가 낸 줄(`ORACLE:` / finding 줄)**만 그대로** 붙여 1회 재요청한다. 정답·예시·대체 문구·내용 지시를 덧붙이지 않는다 — 무엇을 써야 하는지 알려주면 그 산출물은 더 이상 독립 판정이 아니다.
  - **내용 문제**(항목이 틀렸다·빠졌다고 세션이 판단) → 재요청하지 않는다. 산출물은 그대로 쓰고 해당 항목은 3f 에서 **기각(CARRY)** 한다.
- **재요청 뒤에도 형식 오류**거나 경로를 못 읽거나 `general-purpose` 를 쓸 수 없으면 → 모든 대상이 **오라클 없음 폴백**이다. 폴백인 Intent 는 `--oracle` 없이 D/C 행 체크리스트로 진행하고, Phase 4 의 `verdict` 끝에 ` · oracle SKIPPED` 를 붙이고, Phase 5 에서 경고한다.

### 2b — Part 2 파생 (메인 세션)

세션이 대상마다 **Part 1만 근거로** Part 2 의 3섹션(Functional requirements / Edge cases / Error cases)을 쓴다.

- **사용자에게 질문하지 않는다** — 검토는 Phase 5에서 한 번에 한다.
- **Part 2 의 모든 항목은 Part 1(Outcome·Decisions·Constraints·Out of scope)에 근거가 있어야 한다.** 근거 없는 항목을 추가하지 않는다.
- **참조 표기**: FR 은 `(Dn)`·`(Cn)`, E/X 는 `(FR-n)`·`(Dn)`·`(Cn)`·`(OS)` 로 근거를 표기한다. 여러 개는 `, ` 로 잇는다. 섹션 값이 `none` 이면 예외.
- **항목 ID**: D/C/FR/E/X 항목은 1부터 오름차순 ID 를 갖는다. 항목을 지워도 번호를 재사용하지 않고, 있는 번호를 바꾸지 않는다 — Task 가 이 번호로 항목을 가리킨다.
- **각 FR 마다 엣지·오류를 검토**하고, 해당 사항이 없으면 그 섹션에 `none` 을 명시한다.
- **FR 은 테스트할 수 있는 문장**으로 쓴다 — Task 의 완료 조건이 이 문장에서 나온다. Edge cases 는 작업이 끝난 뒤에도 유지되는 동작만 쓴다 — 작업 · 배포 동안에만 생기는 상황은 Task 의 Risks 몫이다.
- **이름 규칙** — 내부 코드 이름은 쓰지 않는다. 밖에서 보이는 이름은 종류어를 앞에 두고 백틱으로 감싼다(API `POST /uploads` · 오류 코드 `UPLOAD_RETRY_EXHAUSTED`). 화면 문구는 큰따옴표.
- **계약** — 계약의 동작(API · 요청/응답 필드 · 오류 코드)은 **제공하는 App 의 Intent FR** 에 적는다. 호출하는 App 의 Intent 에는 그 계약을 쓰는 쪽의 동작(보내는 값 · 응답과 오류를 다루는 방법)을 적는다.
- **고치기 대상** — 바뀌는 항목만 고친다:
  - 신규 — `next_ids` 의 번호부터 종류마다 하나씩 늘려 붙인다.
  - 변경 — 번호를 그대로 두고 문장을 고친다.
  - 삭제 — 줄을 지운다(섹션에 남는 항목이 없으면 `none`). `/task-split` 이 기준선 문장으로 다시 넣고 `삭제 예정` 표시를 단다 — 코드에는 아직 그 동작이 있다.
  - 그대로 둘 항목은 표현 다듬기도 하지 않는다 — 문장이 다르면 변경으로 잘린다.
  - 진행 표시가 붙은 항목은 고치지 않는다(Phase 0 의 7.5).
  - 지운 D · C 를 가리키는 참조가 남지 않게 한다(`INT_REF_DANGLING`).
  - 기능을 없애면 `상태` 를 `retired` 로 바꾸고 Part 2 항목을 모두 지운다 — `/task-split` 이 삭제 Task 로 자른다.
- **근거를 댈 수 없는 항목은 쓰지 않는다** — 삭제하거나 Part 1 의 Decisions/Constraints 에 근거를 추가하고 Part 1 변경으로 기록한다. Open questions 는 진짜 미결만.

**전이 조건**: 대상마다 3섹션 기록됨(해당 없는 섹션은 `none`) + `expected.md` 저장 또는 폴백 확정(`--no-gate` 면 해당 없음).

---

## Phase 3 — 검증 루프

`--no-gate` 면 이 Phase 를 건너뛰고 Phase 4 의 최소 quality.json 을 쓴 뒤 Phase 5 로 간다. 시작할 때 1줄로 고지한다 — "검증 루프 — Intent 마다 회차당 코드 검사 + opus 서브에이전트 1회, 최대 3회. 임시 파일은 <W>/ (커밋 안 함)".

Intent 마다 따로 돈다 — 회차 카운터 `n`(**LLM 판정 횟수**, 최대 3) · CARRY · 무진전 가드가 Intent 마다 있다. 대상이 여럿이면 회차마다 3a~3c 를 대상마다 마친 뒤 3d 의 critic 을 한 메시지에서 함께 스폰한다(병렬). 루프가 끝난 Intent 는 다음 회차에서 빠진다. 아래 `<D>` 는 그 Intent 의 하위 폴더 `<W>/<Intent ID>/` 다.

### 3a — 형식 검사

`python "$DH" check-intent --repo . --file <intent> --json`

- JSON 은 `{"summary": {"pass": n, "warn": n, "fail": n}, "results": [...]}` 형태고, exit 0 = FAIL 없음 · 1 = FAIL 있음 · 2 = 인자 오류다.
- FAIL 이 있으면 세션이 인라인 수정 후 재실행한다(회차에 산입하지 않음, **최대 3번**). 3번을 넘으면 `code: FAIL` 로 그 Intent 의 루프를 끝내고 Phase 4 로 간다. 고치기 대상에서 이번 변경 밖 항목의 문장을 고쳐야 FAIL 이 풀리면, 그 항목도 이번 변경이 된다는 것을 Phase 5 에 적는다.
- FAIL 0 이면 3b 로 진행한다. WARN 은 진행을 막지 않는다.

### 3b — 기준표 생성

`python "$DH" intent-checklist --repo . --file <intent> --round <n> --oracle <W>/expected.md`

- 오라클 없음 폴백이면 `--oracle` 을 생략한다.
- stdout 을 `<D>/checklist-round-<n>.md` 로 저장한다. 표의 열은 `ID | 대상 | facts | 판정 기준 | 심각도 | N/A | 인용` 이고, 마지막 줄은 `rows: <행 수> · quote: <인용 표본 행 ID>` 다.
- `--oracle` 을 주면 `EXP-n` 행이 **표 맨 앞**에 온다 — `대상` 이 없거나 이 Intent 를 가리키는 항목만이다. EXP 행의 `N/A` 열은 `불가` 이고, 인용 표본에는 EXP 가 들어가지 않는다.
- `expected.md` 형식이 어긋나거나 이 Intent 를 대상으로 한 항목이 없으면 `ORACLE: ` 로 시작하는 줄이 stdout 에 나오고 exit 2 로 끝난다 — 2a 의 세 갈래대로 처리한다. **1회차는 모든 대상의 3b 를 먼저 돌린다** — 형식 오류 재요청으로 `expected.md` 가 바뀌면 모든 대상의 1회차 체크리스트를 다시 만든다. 재요청 · 폴백 판단은 1회차 3d 전에 끝낸다 — 그 뒤 `expected.md` 는 바뀌지 않는다.
- 같은 명령에 `--json` 을 붙여 한 번 더 받아 `<D>/checklist-round-<n>.json` 으로 저장한다 — Phase 4 의 quality.json 집계(행 수·인용 표본·traceability·`oracle`)에 쓴다.

### 3c — 스냅샷

Intent 파일을 `<D>/round-<n>.md` 로 복사한다.

### 3d — LLM 판정

`templates/intent-critic.md` 를 Read 해 `{{INTENT_PATH}}` `{{CHECKLIST_PATH}}` `{{ROUND}}` `{{CARRY}}` `{{RETURN_PATH}}` 를 실제 값으로 치환하고, **치환된 전문을 프롬프트로 그대로** 전달한다 — `Agent(subagent_type: "general-purpose", model: "opus", prompt: <치환 전문>)`. `{{RETURN_PATH}}` = `<D>/critic-round-<n>.txt`.

- **critic 이 `critic-round-<n>.txt` 를 직접 쓴다.** 세션은 반환을 옮겨 적지 않고, **이 파일을 편집하지 않는다**.
- 회차마다 **새 에이전트**를 스폰한다. 3e 의 형식 재요청만 같은 에이전트를 이어 쓴다.
- 넘기지 않는 것: 인터뷰 대화(전사 원문), 세션 추론, 수정 방향, 이전 회차 반환문. 인터뷰 내용은 **`expected.md` 를 거쳐 체크리스트의 EXP 행으로만** 전달된다. 판정 기준은 체크리스트 행에 다 있다.
- `general-purpose` 를 쓸 수 없으면 `llm: SKIPPED` 로 두고 Phase 5 에서 경고한다.

### 3e — 반환 검사

critic 이 쓴 `critic-round-<n>.txt` 가 있는지 확인한 뒤:

`python "$DH" intent-checklist --repo . --file <intent> --round <n> --oracle <W>/expected.md --check-return <D>/critic-round-<n>.txt`

- **`--oracle` 은 3b 와 똑같이 붙인다.** 빠뜨리면 재생성 행에 EXP 가 없어 반환의 EXP 행이 전부 `EXTRA` 로 뜬다. 오라클 없음 폴백인 Intent 에서만 생략한다.
- 출력이 `OK` 면 둘째 줄 `RETURN-SHA256: <해시>  <파일명>` 의 해시를 Phase 4 용으로 기록하고 3f 로 간다.
- 아니면 finding 줄(`MISSING` / `EXTRA` / `OVERLAP` / `BAD-KEY` / `NA-NOT-ALLOWED` / `NA-NO-LOCATION` / `QUOTE-MISSING` / `QUOTE-NOT-FOUND`)을 2a 의 **재요청 규칙**대로 그 줄만 붙여 같은 에이전트에 1회 재요청한다 — critic 이 같은 경로에 다시 쓴다. 세션이 파일을 고치지 않는다.
- 2회째도 불일치면 `llm: FAIL(protocol)` 로 기록하고 그 Intent 의 루프를 끝낸다(`stopped_early: return_mismatch`).

### 3f — 판정과 처분

- 반환의 FAIL 키 중 **심각도 MAJOR**(체크리스트 `심각도` 열 기준)가 0 이면 `llm: PASS`, 그 Intent 의 루프 종료.
- 아니면 finding 마다 세션이 ① 수정 ② 기각(사유 1줄) ③ N/A 수용 중 하나로 처분한다. 기각·N/A 수용은 CARRY 목록(`REJECTED <키> — 사유` / `ACCEPTED-N/A <키> — 사유`)에 누적해 다음 회차 critic 에 전달한다.
- **EXP 처분** — EXP 행에는 N/A 가 없다.
  - (b) 기준이 없는 행(종류 `제약`·`제외`·`프로세스`·`배경`)은 **(a) 만** 판정한다 — (b) 는 요구·완료조건·결정 행에만 있다. 배경 행의 (a) 는 MINOR 다. 프로세스 행(완료 보고 · 브랜치 · 커밋)은 Task 몫이다 — 그 (a) 는 진행 방식이 Intent 에 동작처럼 섞여 들어갔는지를 보는 MINOR 다.
  - `EXP-n:a` FAIL = 인터뷰에 있는데 Intent 에 없다 → Part 1 또는 Part 2 에 추가한다. Part 1 에 추가한 것은 `part1_edits` 에 기록하고, **추가·명확화만** 한다.
  - `EXP-n:b` FAIL = Part 1 에만 있고 Part 2 로 내려오지 않았다 → 대응하는 FR/E/X 를 추가한다.
  - 오라클이 틀렸다고 판단하면 기각해 CARRY 에 넣는다(`REJECTED EXP-3:a — 사유`).
- **고치기 대상의 변경 밖 항목** — 고치기 대상이면 3f 를 시작할 때 `python "$DH" intent-diff --repo . --intent <Intent ID> --json` 을 다시 돌린다(Phase 0 의 값은 고치기 전이라 비어 있다). finding 이 그 `changes` 에 없는 FR · E · X 를 가리키면 고치지 않고 기각한다(`REJECTED FR-2:b — 이번 변경 밖`) — 문장을 고치면 `/task-split` 이 변경으로 자른다. Phase 5 에 따로 보여 주고, 다룰지는 사용자가 정한다(다루면 그 항목도 이번 변경이 된다).
- **Part 1 은 추가·명확화만** 한다 — 이번 인터뷰에서 사용자가 확정한 문장은 삭제하지 않는다. 변경한 줄은 `part1_edits` 에 기록한다.
- 새 항목 번호는 고치기 대상이면 `intent-diff --json` 의 `next_ids` 를 다시 받아 쓰고, 새로 쓰기 대상이면 이어지는 번호를 쓴다. 항목을 지워도 번호는 재사용하지 않는다.
- 체크리스트 파일 끝에 `## 결과` 를 덧붙인다 — 장부 4줄(PASS/FAIL/N/A/QUOTE) + 세션 처분(수정·기각·N/A 수용).
- **무진전 가드**: CARRY 를 제외한 FAIL 키 집합이 직전 회차와 같으면 그 Intent 의 루프를 끝낸다(`stopped_early: no_progress`).
- `n < 3` 이면 3b 부터 다음 회차, 아니면 그 Intent 의 루프 종료.

**전이 조건**: 대상마다 `llm: PASS` · 3회 소진 · 조기 중단 · SKIPPED 중 하나로 루프가 끝남.

---

## Phase 4 — 품질 지표

Intent 마다 `<D>/quality.json` 을 세션이 **단일 작성**한다(expector·critic 은 자기 산출물 파일만 쓰고 quality.json 은 쓰지 않는다). 스키마:

```json
{ "intent": "<App>-INT-<NNN>", "run": "<W 폴더 이름>", "mode": "new|edit", "baseline": "SAVED|KEPT|NEW|DROPPED|none", "implemented": false, "v1_migrated": false,
  "max_rounds": 3, "rounds_used": 2, "final": "PASS|FAIL|OVERRIDE|SKIPPED", "verdict": "PASS — code PASS · llm PASS · 2/3",
  "code": {"status": "PASS|FAIL|SKIPPED", "inline_fixes": n, "last": {"pass": n, "warn": n, "fail": n, "fail_codes": []}},
  "llm":  {"status": "PASS|FAIL|FAIL(protocol)|SKIPPED", "judge": "subagent:general-purpose/opus|self|skipped", "per_round": [
            {"round": 1, "rows": 41, "pass": 36, "fail_rows": 4, "na": 1, "fail_major_keys": ["OS2:a"], "fail_minor_keys": ["E-2:c"],
             "quote_rows": ["D3","FR-7","E-2","X-1","G-2"], "return_retry": 0}]},
  "interview": {"questions": n, "review_edits": n},
  "oracle": {"status": "OK|SKIPPED", "expected": n,
             "kinds": {"요구": n, "완료조건": n, "결정": n, "제약": n, "제외": n, "프로세스": n, "배경": n},
             "per_round": [{"round": 1, "covered_a": n, "covered_b": n, "missing_keys": ["EXP-3:a", "EXP-7:b"], "rejected": n}]},
  "improve": ["…", "…"],
  "rows_per_round": [41, 43],
  "traceability": {"fr": n, "fr_with_ref": n, "ex": n, "ex_with_ref": n, "d_unreferenced": n, "c_unreferenced": n},
  "part1_edits": [{"round": n, "section": "Constraints", "diff": ["+ C6. …"]}],
  "carry": [{"round": n, "key": "FR-3:a", "kind": "REJECTED|ACCEPTED-N/A", "reason": "…"}],
  "stopped_early": "none|no_progress|format_cap|return_mismatch",
  "snapshots": ["round-1.md"], "checklists": ["checklist-round-1.md"],
  "artifacts": {"expected_sha256": "<hex>", "returns": [{"round": 1, "sha256": "<hex>"}]},
  "confirmed_by": "…", "confirmed_at": "YYYY-MM-DD" }
```

- **`mode` · `baseline`** — 새로 쓰기면 `new` · `none`, 고치기면 `edit` · Phase 0 의 7.4 결과(`SAVED` · `KEPT` · `NEW`). Phase 5 에서 기준선을 지우면 `DROPPED` 로 고친다. `implemented` 는 `--implemented` 로 남겼을 때, `v1_migrated` 는 v1 문서를 옮겼을 때 `true`.
- **`--no-gate`** — `intent` · `run` · `mode` · `baseline` · `implemented` · `v1_migrated` · `final`(`SKIPPED`) · `verdict`(`SKIPPED — --no-gate`)만 쓴다 — Phase 5 의 확정 기록 · 기준선 정리가 이 값을 읽는다.
- `oracle.expected` 와 `oracle.kinds` 는 3b 의 `--json` 출력에 있는 `oracle` 필드를 그대로 옮긴다 — 그 Intent 를 대상으로 한 항목만 센 값이다.
- **`llm.judge`** — 실제 판정 주체. 서브에이전트가 판정했으면 `subagent:general-purpose/opus`, 서브에이전트를 못 써 세션이 대신했으면 `self`, 건너뛰었으면 `skipped`. `self`·`skipped` 면 Phase 5 본문에 경고 1줄.
- **`artifacts`** — 산출물 해시. `expected_sha256` 는 1회차 3d 직전(재요청 · 폴백 판단이 끝난 뒤)의 `expected.md` 해시(`sha256sum` 등으로 구한다), `returns[].sha256` 은 3e 가 `OK` 와 함께 출력한 `RETURN-SHA256` 값 그대로. 나중에 파일 해시가 이 값과 다르면 **수용 뒤 누군가 고친 것**이다.
- **`verdict`** — `<총평> — code <상태> · llm <상태> · <회차>/3`. 총평은 code FAIL 0 이고 llm PASS 면 `PASS`, 둘 중 하나라도 FAIL 이면 `FAIL`, 서브에이전트 불가로 llm 이 SKIPPED 면 `SKIPPED — <사유>` 다. 예: `PASS — code PASS · llm PASS · 2/3`. 오라클 없음 폴백이면 끝에 ` · oracle SKIPPED` 를 붙인다 — 예 `PASS — code PASS · llm PASS · 1/3 · oracle SKIPPED`. `final` 은 총평 단어다.

---

## Phase 5 — 사용자 확정 (1회)

대상 전부를 한 번에 확정한다 — 계약을 주고받는 Intent 는 함께 맞아야 한다. 확정 · 중단은 대상 전부에 함께 적용한다.

1. **보여 줄 것** — 대상마다:
   - Intent 경로 · 새로 쓰기/고치기(v1 을 옮겼으면 그 사실) · 기준선 결과(`SAVED` · `KEPT` · `NEW`)
   - 검증 값(`verdict`, `--no-gate` 면 `SKIPPED — --no-gate`) · 최종 체크리스트 경로 + `<PASS 행>/<전체 행> PASS`
   - `인터뷰 반영 <covered>/<expected> · 누락 <EXP 키>`(오라클 없음 폴백이면 없다)
   - 잔존 MAJOR·MINOR 키와 각 1줄 요약 · 변경 밖이라 기각한 키
   - `IMPROVE` 목록(있으면, 차단 아님)
   - **자를 변경 목록** — `python "$DH" intent-diff --repo . --intent <Intent ID>` 의 출력(신규 · 변경 · 삭제 줄). `/task-split` 이 이 목록을 Task 로 자른다. 새로 쓰기 · `NEW` 면 "항목 전부 신규(FR n · E n · X n)" 한 줄로 쓴다.
   - Part 1 변경 줄 diff(≤10줄, 초과하면 비교할 사본 경로 `<W>/before/<ID>.md` 만)
   - `Open questions` 가 남아 있으면 경고 — 확정은 되지만 `/task-split` 이 Task 를 승인할 수 없다(`TSK_APPROVED_GATE`). 지금 답할지 함께 묻는다.
   - SKIPPED 경고(있으면), `llm.judge` 가 `self`·`skipped` 면 "판정이 독립 서브에이전트가 아니다" 경고

   `--no-gate` 면 판정을 하지 않았다 — 검증 값(`SKIPPED — --no-gate`) · 기준선 결과 · 자를 변경 목록 · Part 1 diff · `Open questions` 경고만 보여 준다. 체크리스트 · 인터뷰 반영 · 잔존 키 · `IMPROVE` · `llm.judge` 경고는 없다(quality.json 최소 필드에 없다).

   그리고 산문으로 묻는다 — 모든 대상의 총평이 `PASS`·`SKIPPED` 면 **확정 / 고칠 곳 / 중단**, 하나라도 `FAIL` 이면 **고친 뒤 재검증 1회 / OVERRIDE 확정 / 중단**.
2. **고칠 곳** — 2b 의 규칙대로 반영하고 3a 형식 검사를 다시 돌린 뒤 다시 제시한다 — 확정 또는 중단까지 반복한다. **고친 뒤 재검증 1회** 는 고친 Intent 에 3b~3f 를 한 회차 더 돈다 — 최대 3회를 넘는 이 1회만 허용한다.
3. **확정** — Intent 파일은 더 고치지 않는다(승인 행이 없다). 대상마다 quality.json 의 `confirmed_by` · `confirmed_at` 을 쓴다. OVERRIDE 면 `final` 을 `OVERRIDE` 로, `verdict` 의 총평을 `OVERRIDE` 로 바꾼다.
4. **중단** — 남길지 되돌릴지 묻는다.
   - **남기면** 그대로 둔다 — 기준선이 남아 다음 `requirement-spec` · `/task-split` 이 이어 간다.
   - **되돌리면** 고치기 대상은 `<W>/before/<ID>.md` 로 덮어 되돌리고, 기준선이 `SAVED`(이번 실행이 남김)면 `python "$DH" intent-base --repo . --intent <ID> --drop` 으로 지우고 quality.json 이 있으면 `baseline` 을 `DROPPED` 로 고친다(Phase 4 전에 중단했으면 quality.json 이 없다 — 만들지 않는다) — `KEPT` 는 앞선 고침의 기준선이라 남긴다. 새로 쓰기 대상은 파일을 지운다.
5. **기준선 정리** — 확정했거나 남긴 고치기 대상의 기준선이 `SAVED` 이고 `--implemented` 로 남긴 것이 아닌데 `intent-diff` 의 `changes` 가 0 이면(Part 1 만 고쳤다 — 자를 변경이 없다) `intent-base --drop` 으로 지우고 quality.json 이 있으면 `baseline` 을 `DROPPED` 로 고친다. **`--implemented` 기준선은 변경이 없어도 남긴다** — 그 Intent 를 가리키는 Task 가 아직 없어 기준선이 "이미 구현됨" 의 유일한 기록이다. 지우면 다음 실행이 `NEW` 로 보고 `/task-split` 이 구현된 항목을 전부 신규로 자른다.
6. **카탈로그 재생성** — 3~5 가 끝난 뒤 대상 App 마다 `python "$DH" intent-catalog --repo . --app <App> --write` 를 한 번 실행한다. **카탈로그를 손으로 쓰지 않는다** — 모든 열이 Intent 문서에서 파생된다.
7. **종료 보고** — 대상마다 Intent 경로 · 기준선 결과 · 검증 값, 카탈로그 경로(`docs/<App>/<App>-INT-CATALOG.md`), PRD §7 에 더할 행(있으면), 대상 밖 `관련 Intent`(있으면). 확정했으면 다음 단계를 **한 줄로 안내만** 한다 — `/task-split <Intent ID> …`(이번 대상 전부, 자를 변경이 있는 것만). 후속은 **사용자가** 진행한다 — 이 스킬은 실행하지 않는다.

---

## 산출물 경계

- **만드는 것** — 전부 커밋하지 않는다(`.git/info/exclude`):
  - 대상 Intent — 새로 쓰거나 고친다(`docs/<App>/INTENT/<App>-INT-<NNN>.md`).
  - 기준선 `.process/intent-base/<ID>.md` — 고치기 대상, `intent-base --save` 가 쓴다.
  - 생성물 `docs/<App>/<App>-INT-CATALOG.md` — `intent-catalog --write` 가 쓴다(Phase 5 의 6에서 1회). 세션이 쓰지 않는다.
  - 검증 작업 폴더 `<W>/` — `interview.md` · `expected.md` · `before/<ID>.md` · `<ID>/{checklist-round-<n>.md, checklist-round-<n>.json, round-<n>.md, critic-round-<n>.txt, quality.json}`. 쓰는 주체: `expected.md` = expector, `critic-round-<n>.txt` = critic, 나머지 = 세션.
- **만들지 않는 것**: Task(`.task/`) · 진행 표시 — `/task-split` 몫. PRD 수정, 인터뷰 정리본 · 별도 지시서, 구현 코드, 브랜치 · 워크트리 · 커밋.
- 후속 스킬을 자동으로 호출하지 않는다. `ExitPlanMode` 를 호출하지 않는다.

## 실패 처리

| 상황 | 처리 |
|---|---|
| Python 3.10+ 없음 | 중단, 설치 안내 (문서 생성 안 함) |
| `ensure-exclude` 가 `FAIL EXCLUDE` (git repo 아님) | 중단, 사유 보고 |
| 템플릿을 두 경로 모두에서 못 찾음 | 중단, 찾은 경로 후보를 보고 (문서 생성 안 함) |
| 대상이 1회 질문 후에도 미정 · 고칠 Intent 파일이 없음 | 중단, 사유 보고 (디렉터리·문서 생성 안 함) |
| v1 문서를 옮기는 것을 거절 | 그 대상을 빼고 보고, 남은 대상이 없으면 중단 |
| `intent-base` · `intent-diff` 가 FAIL | 그 줄을 그대로 보고하고 중단 |
| 고칠 항목에 진행 표시가 붙어 있음 | 고치지 않고 알린다 — 그 Task 가 `done` 된 뒤 고친다. 초안(`draft`) Task 의 표시면 `/task-split` 에서 그 초안을 지운 뒤 고친다 |
| grill-me 인터뷰가 사용자 중단으로 종결 | Phase 5 의 4(중단) — 남길지 되돌릴지 묻고, 5 · 6 을 수행한다. quality.json 은 아직 없다 — 만들지 않는다 |
| expector 사용 불가 (`general-purpose` 불가) | 오라클 없음 폴백 — `--oracle` 없이 진행, `verdict` 에 `· oracle SKIPPED` 접미, Phase 5 본문에 경고 |
| `expected.md` 형식 2회 실패 (stdout `ORACLE:`) · 경로 읽기 2회 실패 (stderr `FAIL READ_TEXT <expected.md>`) | 모든 대상이 오라클 없음 폴백 — `--oracle` 없이 진행, `verdict` 에 `· oracle SKIPPED` 접미, Phase 5 본문에 경고 |
| `ORACLE: <Intent ID> 를 대상으로 한 EXP 항목이 없다` | 재요청 없이 그 Intent 만 오라클 없음 폴백 — 다른 대상은 오라클로 진행 |
| 형식 FAIL 이 인라인 수정 3번으로 안 잡힘 | 그 Intent 의 루프 종료, `verdict` = `FAIL — code FAIL · llm <상태> · <회차>/3`, `stopped_early: format_cap`, Phase 5 에서 잔존 FAIL 코드 제시 |
| 3회 소진 후 MAJOR 잔존 | 그 Intent 의 루프 종료, `verdict` = `FAIL — code PASS · llm FAIL · 3/3`, Phase 5 에서 잔존 MAJOR 키 제시(옵션 = 고친 뒤 재검증 1회 / OVERRIDE 확정 / 중단) |
| 무진전으로 중단 (CARRY 제외 FAIL 키 집합 동일) | 그 Intent 의 루프 종료, `stopped_early: no_progress`, 총평은 잔존 MAJOR 유무로 결정, Phase 5 에서 중단 사유 고지 |
| expector 가 `expected.md` 를 쓰지 않음 | `FAIL READ_TEXT cannot read: <경로>` 한 줄만 붙여 1회 재요청 → 그래도 없으면 오라클 없음 폴백 |
| critic 이 `critic-round-<n>.txt` 를 쓰지 않음 | `--check-return` 의 stderr `FAIL READ_TEXT cannot read: <경로>` 한 줄만 붙여 1회 재요청 → 그래도 없으면 `llm: FAIL(protocol)`, `stopped_early: return_mismatch` |
| 반환 불일치 2회 | `llm: FAIL(protocol)`, `verdict` = `FAIL — code <상태> · llm FAIL · <회차>/3`, `stopped_early: return_mismatch`, Phase 5 에서 finding 줄 제시 |
| `general-purpose` 서브에이전트 사용 불가 | `llm: SKIPPED`, `verdict` = `SKIPPED — general-purpose 불가`, Phase 5 본문에 미검증 경고 |
| 사용자가 OVERRIDE 확정 | quality.json `final: OVERRIDE`, `verdict` 총평 `OVERRIDE`, 보고에 OVERRIDE 명시 |
| 사용자가 중단 | Phase 5 의 4 — 남길지 되돌릴지 묻는다 |
