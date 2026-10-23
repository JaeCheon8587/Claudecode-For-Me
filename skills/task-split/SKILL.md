---
name: task-split
description: requirement-spec 으로 쓰거나 고친 Intent 들의 바뀐 항목을 애자일 자르기 기준으로 개발 단위 Task n 개로 나누는 스킬 — 변경 목록 추출(스크립트) → 자르기 제안 → Task 작성 · 진행 표시 · 검사 → 일괄 승인 1회 → 개발 프롬프트. Intent : Task 는 1:1 · 1:N · N:N 모두 된다. "Task 로 잘라줘", "작업 나눠줘", "task-split" 요청 시 트리거
argument-hint: "[<Intent ID 또는 경로> ...] [--type 기능개발|버그수정|리팩토링]"
---

# Task Split

고친 Intent(기능 문서)의 바뀐 항목을 **개발 단위 Task**(작업 계약서, `.task/tsk-<NNN>.md`) 여러 개로 자르는 스킬이다. 무엇이 바뀌었는지는 스크립트가 뽑고, 어떻게 자를지는 아래 **자르기 기준**으로 세션이 제안하고 사용자가 정한다. Task 를 쓰고 진행 표시를 붙이고 검사를 통과시킨 뒤 **한 번에 승인**받고, 개발 세션에 넣을 **개발 프롬프트**를 내고 멈춘다.

흐름에서의 자리: `requirement-spec`(Intent 작성 · 수정) → **`/task-split`** → `/worktree-init <이름>`(워크트리) → 개발 세션(개발 프롬프트) → `finish tsk-<NNN>` → 머지 → `/worktree-delete`.

## 핵심 원칙

- **Task 는 새 동작을 만들지 않는다** — Scope 는 Intent 에서 바뀐 항목의 사본이다. 동작이 더 바뀌어야 하면 `requirement-spec` 으로 Intent 를 먼저 고친다.
- **바뀐 항목은 정확히 한 Task 에** 들어간다 — 빠뜨리지도, 두 Task 에 넣지도 않는다. 한 번 실행에 바뀐 항목을 전부 나눈다.
- **결정적인 일은 스크립트가 한다** — 변경 목록 · Scope 문장 · 진행 표시 · 검사 · 카탈로그. 세션은 자르기 제안과 Goal · Acceptance · Verification · Risks 문장을 쓴다. 자르기와 승인은 사용자가 정한다.
- **문서는 커밋하지 않는다** — 문서 폴더(`docs` · `Docs`)와 `intent/` · `.task/` 는 설계 문서다(팀 정책). `.git/info/exclude` 에 올리고 `git add` 하지 않는다.
- **내부 코드 이름은 쓰지 않는다** — 밖에서 보이는 이름만 `종류어 + 백틱`(응답 필드 `retryCount`). 상세는 Task 템플릿 작성 규칙 1~3.
- **후속 단계(워크트리 · 개발)는 실행하지 않는다** — 개발 프롬프트를 내고 끝낸다.
- 모든 대화 · 산출물은 **한국어**로 쓴다(섹션 헤딩은 템플릿의 영어 표기 유지).

helper 경로:

```bash
DH="${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py"
WT_SETUP="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

---

## 자르기 기준

### 단위

Task 하나 = **밖에서 관찰할 수 있는 동작 한 조각**(세로 조각)이다. 그 동작에 필요한 모든 층(화면 · API · 저장소)을 한 Task 가 관통한다. 각 Task 는:

- **혼자 머지해도** 빌드와 기존 테스트가 깨지지 않는다 — 다음 Task 를 기다리지 않고 머지할 수 있어야 한다.
- **Acceptance 로 확인할 수 있는** 결과를 낸다 — Scope 항목마다 A 가 하나 이상 있다.
- **작다** — 기본 상한은 Scope 7항목 · FR 3개. 넘으면 나눌 수 있는지 먼저 보고, 못 나누면 이유를 자르기 표에 적는다.
- **선행이 적다** — 꼭 앞선 Task 의 동작이 있어야 할 때만 `선행 Task` 에 적는다.

작은 변경(바뀐 항목 7개 이하, 한 흐름)은 **Task 1개**가 기본이다. 자르기 위해 자르지 않는다.

### 자르는 순서 (패턴)

큰 변경은 위에서부터 적용해 본다.

| 패턴 | 언제 | 어떻게 |
|---|---|---|
| 1. 뼈대 먼저 | 새 기능 · 큰 흐름 | 가장 단순한 정상 경로가 끝에서 끝까지 동작하는 Task 를 먼저 만들고, 나머지를 그 위에 얹는다(뒤 Task 의 `선행` = 뼈대) |
| 2. 흐름 단계 | 여러 단계를 거치는 흐름(접수 → 검토 → 승인) | 단계마다 Task — 앞 단계가 선행 |
| 3. 경로 | 정상 경로와 경계 · 오류 경로가 많을 때 | E · X 를 FR 과 떼어 뒤 Task 로 — **단 그 FR 보다 앞서지 않는다**(같은 Task 이거나, FR 이 든 Task 를 선행으로) |
| 4. 규칙 변형 | 같은 동작에 업무 규칙 변형이 여럿 | 기본 규칙 Task 다음에 변형마다 Task |
| 5. 데이터 변형 | 형식 · 종류별 처리 | 가장 흔한 형식 먼저, 나머지는 뒤 Task |
| 6. 연산 | 조회 · 생성 · 수정 · 삭제 | 조회(또는 생성) 먼저, 연산마다 Task |
| 7. 인터페이스(App) | 계약 변경으로 여러 App 의 Intent 가 바뀜 | 아래 "App 을 넘는 계약 변경" |
| 8. 비기능 미루기 | 성능 · 견고성 항목이 기본 동작과 따로 가치가 있을 때 | 기본 동작 Task 뒤로 |

### 하지 않는 자르기

| 안티패턴 | 왜 | 대신 |
|---|---|---|
| 계층 자르기(저장소 Task · API Task · 화면 Task) | 어느 Task 도 혼자서는 관찰할 동작이 없다 | 동작 한 조각이 모든 층을 관통하게 |
| 준비 전용 Task("기반 작업", "먼저 정리") | 확인할 결과가 없다 | 첫 동작 Task 에 넣는다. 구조만 바꾸는 일이면 `리팩토링` Task 로 바뀌면 안 되는 항목을 `보존` 으로 담는다 |
| 너무 잘게(FR 하나씩) | 같은 흐름이라 따로 확인할 수 없는 FR 을 갈라 놓으면 Task 마다 반쪽이다 | 함께 확인되는 FR 은 한 Task |
| 같은 항목을 두 Task 에 | 한 항목은 한 Task 만 바꾼다(`TSK_CONFLICT`) | 항목을 한쪽에만 |
| E · X 를 그 FR 보다 앞 Task 에 | 기댈 동작이 아직 없다(`TSK_DEPENDS_ORDER`) | 같은 Task, 또는 FR 의 Task 를 선행으로 |
| 대체를 둘로 가름(옛 동작 삭제 Task · 새 동작 신규 Task) | 사이에 아무 동작도 없는 상태가 생긴다 | 바꾸는 항목(`삭제` + 그 자리의 `신규`)은 한 Task |

### App 을 넘는 계약 변경

API · 필드 · 오류 코드처럼 App 사이의 계약이 바뀌면 **제공하는 App 의 Intent** 와 **호출하는 App 의 Intent** 가 함께 바뀐다.

- **하위 호환이 되면**(새 필드 추가 · 새 API 추가) — 제공 App Task 를 먼저, 호출 App Task 는 그것을 선행으로. 제공 쪽을 먼저 배포해도 호출 쪽이 깨지지 않는다.
- **하위 호환이 안 되면**(필드 이름 변경 · 삭제 · 의미 변경) — ① 한 Task 로 묶어 함께 배포하거나 ② 세 단계로 나눈다: 제공 App 이 새 계약을 **추가**(옛 것 유지) → 호출 App 이 새 계약으로 **전환** → 제공 App 이 옛 계약을 **삭제**. ② 는 Intent 에 중간 상태가 있어야 하므로 Intent 를 그렇게 썼을 때만 쓴다. 고르지 못하면 사용자에게 묻는다.
- App 사이의 동작(한쪽이 준 값을 다른 쪽이 쓰는 것)을 확인하는 A 는 **호출 App 쪽 Task** 에 둔다.

### 유형

| 유형 | 언제 | Scope 변경 |
|---|---|---|
| 기능개발 | Intent 가 바뀌었다 | 신규 · 변경 · 삭제 |
| 버그수정 | Intent 는 그대로인데 코드가 어긴다 | 위반(어긴 항목) · 신규(스펙에 없던 경계라 Intent 에 E · X 를 더했을 때) |
| 리팩토링 | 동작은 그대로 두고 구조를 바꾼다 | 보존(바뀌면 안 되는 항목) |

위반 · 보존 항목은 Intent 를 바꾸지 않아 진행 표시가 없고, 변경 목록에도 나오지 않는다 — 사용자가 고른 항목을 쓴다.

---

## Phase 0 — Orient

1. Python 3.10+ 확인: `python --version`(없으면 `py -3 --version`). 없으면 중단하고 설치를 안내한다.
2. **exclude 보장**: `python "$DH" ensure-exclude --repo .` — `ADDED` 면 한 줄 고지("`.git/info/exclude` 에 문서 폴더 · `intent/` · `.task/` 를 올렸다 — 커밋되지 않는다"). `WARN TRACKED` 가 있으면 그대로 전한다 — 이미 커밋된 문서는 숨지 않는다. 추적을 끊을지(`git rm --cached`)는 사용자가 정한다. **대신 하지 않는다.**
3. **템플릿 경로** — 순서대로: repo 의 `docs/.templates/.task/tsk-001-template.md` → `${CLAUDE_PLUGIN_ROOT}/docs/.templates/.task/tsk-001-template.md`. 둘 다 없으면 **중단**한다.
4. **대상 Intent** — `$ARGUMENTS` 의 Intent ID(`loader-int-003`) 또는 경로를 쓴다. 없으면 후보를 보여 주고 고르게 한다 — `.process/intent-base/` 에 기준선이 있는 Intent(고쳤는데 아직 자르지 않음)와, 초안(`draft`)이 아닌 Task 의 `대상 Intent` 에 없는 Intent(새로 써서 아직 자르지 않음 — 초안만 가리키면 앞서 중단하고 남긴 자르기다). 후보가 없고 유형이 `기능개발` 이면 "자를 변경이 없다" 를 보고하고 끝낸다.
5. **유형** — `--type` 이 있으면 그 값. 없으면 변경 목록이 있으면 `기능개발`, 없으면 `버그수정` · `리팩토링` 중 무엇인지 한 번 묻는다.

## Phase 1 — 변경 목록 (스크립트)

대상 Intent 마다:

```bash
python "$DH" intent-diff --repo . --intent <Intent ID> --json
```

- `mode` — `base`(기준선 `.process/intent-base/<ID>.md` 와 비교) · `new`(초안이 아닌 Task 가 가리킨 적 없는 Intent — 항목 전부 신규. 초안은 지금 자르는 중인 Task 라 세지 않는다) · `none`(기준선도 없고 초안이 아닌 Task 가 가리킨 적 있음 — 바뀐 것 없음).
- `changes` 의 각 항목은 `kind`(신규 · 변경 · 삭제) · `id` · `scope_line`(Task Scope 에 그대로 쓸 줄) · `prev_line`(변경일 때 `이전` 줄)을 갖는다. **Scope 는 이 줄을 글자 그대로 옮긴다** — 다시 쓰지 않는다.
- `locked_by` 가 있는 항목 — 끝나지 않은 다른 Task 가 바꾸는 중이다. **중단**하고 알린다: 그 Task 가 끝난(done) 뒤 다시 고치거나, 그 Task 를 고친다. 단 `locked_by` 가 초안(`draft`) Task 면 앞서 중단하고 남긴 자르기다 — 그 초안으로 이어 갈지(Phase 3 의 3 검사부터) 지우고 새로 자를지(Phase 4 의 5 방식으로 지운 뒤 다시 실행) 묻는다.
- `open_questions` 가 `false`(Open questions 가 none 이 아님) — 승인할 수 없다(`TSK_APPROVED_GATE`). **중단**하고 `requirement-spec` 으로 질문을 먼저 닫게 한다.
- `mode: new` 인데 이미 구현된 기능의 Intent 면(옛 방식으로 쓰고 개발한 Intent) 전부 신규로 잘리면 안 된다 — 사용자에게 확인하고, 그런 Intent 면 지금 문서를 기준선으로 남기고(`python "$DH" intent-base --repo . --intent <ID> --save --implemented`) 그 Intent 는 자르지 않는다. 다음 고침부터 바뀐 항목만 잘린다.
- `locked_by` · 변경 판정은 Task 상태를 본다 — 끝난(done · dropped) Task 의 표시는 잠그지 않고, 그 Task 가 끝나며 생긴 차이(done 이 지운 `삭제 예정` 줄, dropped 가 되돌린 신규 · 변경)는 변경 목록에 나오지 않는다.

버그수정 · 리팩토링이면 변경 목록 대신 사용자가 고른 항목(위반 · 보존)을 쓴다 — 항목 ID 를 묻고 그 문장을 Intent 에서 그대로 옮긴다.

## Phase 2 — 자르기 제안

자르기 기준으로 Task 를 제안하고 **표로** 보여 준다:

| Task | 제목 | 유형 | Scope 항목 | 선행 | 자른 이유(패턴) |
|---|---|---|---|---|---|
| tsk-012 | 업로드 재시도 뼈대 | 기능개발 | loader-int-003 FR-4, FR-5, X-3 | none | 1. 뼈대 먼저 |
| tsk-013 | 재시도 횟수 응답 | 기능개발 | loader-int-003 FR-6, E-2 · viewer-int-001 FR-2 | tsk-012 | 7. 인터페이스 |

- 번호는 `.task/` 의 최대 번호 + 1 부터 차례로 매긴다(`tsk-<NNN>`, 3자리, 레포 전체 번호열).
- 모든 변경 항목이 정확히 한 행에 들어갔는지 표 아래에 한 줄로 적는다(`변경 9 · 배정 9`).
- 표 다음에 **추천과 그 이유**를 쓰고 산문으로 묻는다 — 이대로 갈지, 어디를 바꿀지. 사용자가 고치면 반영해 다시 보여 준다. 합의될 때까지 Phase 3 으로 가지 않는다.

## Phase 3 — Task 작성 · 진행 표시 · 검사

1. **Task 작성** — 합의한 행마다 템플릿을 `.task/tsk-<NNN>.md` 로 복사해 TEMPLATE 경고 블록을 지우고 채운다:
   - 메타 — `문서 ID`, `유형`(한 값), `상태` = `draft`, `대상 Intent`(이 Task 의 Scope 가 속한 Intent, ` · ` 로), `선행 Task`(없으면 `none`), `작성` = `<git config user.name> · <오늘>`, `승인` = `pending`, `검증` = `pending`.
   - Goal — 계기 · 완료 상태. Intent 의 Problem · Outcome 에서 이 조각에 해당하는 것만.
   - Scope — Phase 1 의 `scope_line` · `prev_line` 을 **그대로** 옮긴다. `- Out of scope:` 에는 이 Task 가 하지 않는 것(다른 Task 가 맡는 항목 포함)을 쓴다.
   - Acceptance — Scope 항목마다 하나 이상(`TSK_SCOPE_COVERAGE`). 근거는 `(<Intent ID> FR-n)` 처럼 App 접두까지.
   - Verification · Risks · Handoff — 템플릿 주석대로. Handoff 에 모르는 값은 묻는다(승인 조건에 `pending` 이 없어야 한다).
2. **진행 표시** — Task 마다:
   ```bash
   python "$DH" mark-intent --repo . --task .task/tsk-<NNN>.md
   ```
   이 Task 의 표시를 Scope 와 같게 맞춘다 — 신규 · 변경 항목에 `[tsk-<NNN> 진행 중]`, 삭제 항목에 `[tsk-<NNN> 삭제 예정]` 을 붙이고, Scope 에서 빠진 항목의 이 Task 표시는 걷어 낸다. 고칠 때 지운 삭제 항목은 기준선의 문장으로 제자리에 다시 넣고 표시를 단다 — 코드에는 아직 그 동작이 있다. 하나라도 막히면 아무 Intent 도 고치지 않는다. **진행 표시를 손으로 붙이지 않는다.**

   **자르기를 고쳐 다시 표시할 때**(Phase 2 로 돌아갔거나 Phase 4 에서 Scope 를 고쳤을 때) — 먼저 이번 실행의 초안 Task **전부**를 `mark-intent --remove` 로 걷어 낸 뒤 Task 를 고치고 전부 다시 `mark-intent` 한다. 옛 초안의 표시가 남아 있으면 항목을 넘겨받은 Task 의 `mark-intent` 가 "다른 Task 의 표시" 로 막힌다.
3. **Task 검사** — Task 마다 `python "$DH" check-task --repo . --file .task/tsk-<NNN>.md`. FAIL 은 세션이 고치고 다시 돌린다(Task 마다 최대 3번). 고쳐도 남으면 Phase 4 에서 그대로 보여 준다.
4. **자르기 검사** — 이번에 만든 Task 전부를 한 번에:
   ```bash
   python "$DH" split-check --repo . --task .task/tsk-<NNN>.md [--task …]
   ```
   바뀐 항목이 정확히 한 Task 에 들어갔는지(`SPLIT_UNASSIGNED` · `SPLIT_DUP`), Scope 가 변경 목록과 같은지(`SPLIT_EXTRA` · `SPLIT_KIND` · `SPLIT_TEXT` · `SPLIT_PREV`), 크기(`SPLIT_SIZE` WARN)를 본다. FAIL 이면 Phase 2 로 돌아가 자르기를 고친다.

## Phase 4 — 일괄 승인 (1회)

1. **보여 줄 것** — Task 표(번호 · 제목 · 유형 · Scope 수 · A 수 · 선행), 개발 순서(선행을 따른 순서), `check-task` · `split-check` 결과(남은 FAIL · WARN), Intent 에 붙은 진행 표시 수. 그리고 산문으로 묻는다 — **승인 / 고칠 곳 / 중단**.
2. **승인 조건** — Task 마다 FAIL 0, Handoff 에 `pending` 없음, 대상 Intent 의 Open questions 가 none. `split-check` FAIL 0. 미충족이면 승인할 수 없다고 알리고 그 부분만 고친다.
3. **승인 시** — Task 마다 메타 `상태` = `approved`, `승인` = `<사용자> · <오늘>`, `검증` = `PASS — check-task PASS · split-check PASS`(WARN 을 알고 승인했으면 `PASS — … · WARN <코드>`). 그다음:
   ```bash
   python "$DH" check-task --repo . --file .task/tsk-<NNN>.md      # Task 마다 — TSK_APPROVED_GATE 확인
   python "$DH" task-catalog --repo . --write
   python "$DH" intent-catalog --repo . --app <app> --write          # 대상 Intent 의 App 마다 — 상위 카탈로그도 함께
   python "$DH" intent-base --repo . --intent <Intent ID> --drop     # 대상 Intent 마다 — 기준선 소비
   ```
4. **고칠 곳** — 반영해 다시 묻는다. Scope 가 바뀌었으면 Phase 3 의 2(표시 — 초안 전부를 걷어 낸 뒤 다시)부터, 문장만 바뀌었으면 3(검사)부터 다시 한다.
5. **중단** — 만든 Task 를 남길지(초안 `draft`) 지울지 묻는다. 지우면 Task 마다 먼저 `python "$DH" mark-intent --repo . --task .task/tsk-<NNN>.md --remove` 로 진행 표시를 걷어 내고(다시 넣은 삭제 항목 줄도 빠진다) Task 파일을 지운다. 기준선은 남긴다 — 다음 실행이 같은 변경 목록을 본다. 남기든 지우든 카탈로그를 다시 쓴다 — 진행 표시와 Task 목록이 바뀌었다:
   ```bash
   python "$DH" task-catalog --repo . --write
   python "$DH" intent-catalog --repo . --app <app> --write          # 대상 Intent 의 App 마다 — 상위 카탈로그도 함께
   ```

## Phase 5 — 개발 프롬프트

승인했으면 개발 세션에 그대로 넣을 프롬프트를 코드 블록으로 낸다. `<WT_SETUP 절대경로>` 는 helper 경로를 펼친 값으로 쓴다.

````markdown
이 워크트리에서 아래 Task 를 순서대로 개발한다. Task 문서는 워크트리의 `.task/` 사본이다 — 문서(Task · Intent)는 고치지 않는다.

1. tsk-012 — 업로드 재시도 뼈대 (선행 없음)
2. tsk-013 — 재시도 횟수 응답 (선행 tsk-012)

Task 마다:
- `.task/tsk-<NNN>.md` 의 Scope(바꿀 Intent 항목)와 Acceptance(완료 조건)를 읽는다. Intent 원문은 `intent/<app>/<ID>.md`.
- 구현하고, Acceptance 를 테스트로 확인하고, 커밋한다.
- 마치면 워크트리 안에서 `python "<WT_SETUP 절대경로>" finish tsk-<NNN>` 을 실행한다.

선행 Task 를 먼저 한다. Task 파일이 워크트리에 없으면 멈추고 알린다 — 메인에서 `/worktree-init <이름>` 을 같은 이름으로 다시 실행하면 복사된다.
````

프롬프트 다음에 **다음 단계 안내**를 두 줄로 쓴다 — ① `/worktree-init <이름>` 으로 워크트리를 만들고 그 워크트리의 세션에 위 프롬프트를 넣는다 ② 선행으로 이어지지 않은 Task 묶음은 워크트리를 따로 만들어 나란히 개발할 수 있다(묶음마다 프롬프트를 나눠 준다). **실행하지 않는다.**

---

## 산출물 경계

- **만드는 것**: `.task/tsk-<NNN>.md` n 개, 대상 Intent 의 진행 표시(`mark-intent`), 생성물 `.task/task-catalog.md` · `intent/<app>/intent-catalog.md` · `intent/intent-app-catalog.md`(`--write` 가 쓴다), 기준선 소비(`intent-base --drop`). 전부 커밋하지 않는다.
- **만들지 않는 것**: Intent 의 동작 문장 변경(진행 표시 · 다시 넣은 삭제 항목 줄 외), 코드, 브랜치 · 워크트리, 커밋.
- 후속 스킬을 자동으로 호출하지 않는다.

## 실패 처리

| 상황 | 처리 |
|---|---|
| 템플릿을 두 경로 모두에서 못 찾음 | 중단, 찾은 경로 후보를 보고 |
| `intent-diff` 의 `locked_by` | 중단 — 그 Task 가 끝난 뒤 다시 고치거나 그 Task 를 고친다. 초안(`draft`) Task 면 남긴 자르기를 이어 갈지 지울지 묻는다 |
| 대상 Intent 의 Open questions 가 none 이 아님 | 중단 — `requirement-spec` 으로 먼저 닫는다 |
| `mark-intent` FAIL — 다른 Task 의 표시 | 그 Task 가 이번 실행의 초안이면 초안 전부를 `--remove` 한 뒤 전부 다시 표시한다(Phase 3 의 2). 아니면 그 줄을 그대로 보고하고 중단한다 — 끝나지 않은 다른 Task 가 바꾸는 항목이다 |
| `mark-intent` FAIL — Intent 에 없는 신규 · 변경 항목 | 그 줄을 그대로 보고하고 Phase 2 로 — Scope 가 변경 목록과 어긋났다(다시 쓰기 전에 초안 전부를 `--remove`) |
| `check-task` FAIL 이 3번 고쳐도 남음 | Phase 4 에서 그 FAIL 을 보여 준다 — 승인 불가 |
| `split-check` FAIL | Phase 2 로 돌아가 자르기를 고친다 — 다시 쓰기 전에 이번 실행의 초안 전부를 `mark-intent --remove` |
| python 실행 불가 | 중단 — 변경 목록 · 진행 표시 · 검사를 손으로 대신하지 않는다 |
| 사용자가 중단 | Phase 4 의 5 — 초안을 남길지 지울지 묻는다 |
