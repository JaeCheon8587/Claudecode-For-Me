# Intent · Task 분리 개정안

> **상태:** 1단계(개발 단계 입력을 Task 로)는 v3.72.0 에서 이행했습니다. forge-scope 는 v3.73.0 에서 제거했고, forge-init · forge-cancel 은 v3.74.0 에서 `/worktree-init` · `/worktree-delete` 로 이름을 바꿨습니다.
> **개정 2(§0)가 그 뒤의 결정을 바꿉니다** — 문서는 커밋하지 않고, Task 는 `/task-split` 이 자르고, `/worktree-init` 은 Task 를 읽지 않습니다. §1 이하와 §0 이 다르면 §0 이 우선합니다. §6 은 1단계 이행 때의 영향 목록(기록)입니다.
> **개정 2 는 v3.75.0 에서 이행했습니다** (§0.3 의 1~3). 이 폴더의 초안 파일(§2)은 이행 전 기록입니다 — 현행은 `docs/.templates/` 의 Intent v2.0 · Task 템플릿과 DOCUMENT_GUIDE 2.0 입니다.

## 0. 개정 2 — 문서는 로컬에만, Task 는 잘라서, 워크트리는 환경만

### 0.1 흐름

```
requirement-spec   Intent 를 쓰거나 고친다 — App 마다 1개. 계약이 바뀌면 호출하는 App · 제공하는 App 둘 다
      ↓
/task-split        고친 Intent 들의 바뀐 항목을 개발 단위 Task n 개로 자른다 (Intent : Task = 1:1 · 1:N · N:N)
      ↓
/worktree-init     <이름> 으로 워크트리만 만든다 — Task 를 읽지 않는다. 문서 폴더 · .task/ 를 복사해 넣는다
      ↓
개발 세션           /task-split 이 준 개발 프롬프트로 Task 들을 개발한다. Task 하나를 마칠 때마다 finish
      ↓
머지               사용자가 워크트리 브랜치를 base 에 머지한다
      ↓
/worktree-delete   머지를 확인하고, 마감한 Task 를 done 으로 바꾸고 진행 표시를 지운 뒤, 워크트리 · 브랜치를 지운다
```

### 0.2 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 문서 공유 | 문서 폴더(`docs/` · `Docs/`)와 `.task/` 는 **커밋 · 푸시하지 않습니다.** `.git/info/exclude` 에 올려 `git add -A` 에도 잡히지 않게 합니다 | 팀 정책 — 설계 문서를 공유하지 않습니다. `info/exclude` 는 공유 `.gitignore` 를 고치지 않고, linked worktree 가 함께 씁니다 |
| 정본 | 메인 작업트리의 문서가 정본입니다. 상태 전이 · 진행 표시 정리는 모두 정본에 씁니다(커밋 없음) | git 이력이 없습니다 |
| 워크트리의 문서 | `/worktree-init` 이 정본을 **복사**합니다(워크트리에 없는 파일만). 개발 세션이 읽는 스냅샷입니다. 링크(junction)는 쓰지 않습니다 | 실측: junction 이 남은 채 `git worktree remove --force` 를 하면 링크 대상(정본)의 내용이 지워집니다 |
| 스냅샷 갱신 | 하지 않습니다. 워크트리를 만든 뒤 생긴 Task 파일은 `/worktree-init` 을 같은 이름으로 다시 실행하면 복사됩니다(있는 파일은 덮지 않습니다) | 재복사 옵션은 나중에 검토합니다 |
| `/worktree-init` 입력 | `<이름>` 하나. 브랜치는 `work/<이름>`(또는 `--branch`). Task 를 읽지 않습니다 — 승인 커밋 게이트 · 상태 전이가 없습니다 | 워크트리 하나에서 Task 여러 개를 개발합니다 |
| Task 만들기 | `/task-split` — 바뀐 Intent 항목을 자르기 기준(task-split SKILL)으로 나눠 Task n 개를 쓰고, 진행 표시를 붙이고, 한 번에 승인받습니다 | requirement-spec 다음 단계가 비어 있었습니다 |
| Intent 변경 기준선 | requirement-spec 이 기존 Intent 를 고치기 전 사본을 `.process/intent-base/<ID>.md` 에 남깁니다. `/task-split` 이 그 사본과 비교해 신규 · 변경(이전 문장) · 삭제를 뽑습니다. 사본이 없고 초안(`draft`)이 아닌 Task 가 가리킨 적 없는 Intent 는 새 Intent 라 전부 신규입니다(초안은 지금 자르는 중인 Task 라 세지 않습니다) | git 이력이 없어 비교 기준이 따로 있어야 합니다 |
| 선행 Task | Task 메타에 `선행 Task`(`none` 또는 ` · ` 로 나열한 TSK ID)를 둡니다. 형식 · 자기 자신 · 없는 Task · 순환은 FAIL, 취소된 선행은 WARN(`TSK_DEPENDS`). E · X 가 기대는 FR 을 끝나지 않은 다른 Task 가 바꾸면 그 Task 가 선행(거쳐서도)이어야 합니다(`TSK_DEPENDS_ORDER`). 카탈로그에 `선행` 열을 둡니다 | 한 워크트리에서 Task 여러 개를 개발하므로 순서를 문서로 고정합니다 |
| Task Handoff | `repo · app` · `손대지 말 영역` · `완료 보고 방식` 3행. `base branch` · `브랜치명` 은 뺍니다 | 브랜치는 `/worktree-init` 이 정하고, Task 하나가 브랜치 하나가 아닙니다 |
| Task 상태 | `draft → approved → in-review → done`, 언제든 `dropped`. **`in-dev` 는 없앱니다** | Task 를 읽지 않는 init 은 in-dev 로 바꿀 수 없고, 달리 쓰는 곳이 없습니다 |
| 마감(in-review) | 개발 세션이 워크트리 안에서 `worktree_setup.py finish TSK-<NNN> …` — 정본 Task 를 `approved → in-review` 로 바꾸고, Task 카탈로그를 다시 만들고, 메인 매니페스트에 Task ID 를 남깁니다. 커밋 안 된 변경이 있거나 개발 커밋이 없으면 멈춥니다 | |
| 완료(done) · 진행 표시 정리 | `/worktree-delete` 가 브랜치가 base 에 머지됐는지 봅니다. 머지됐으면 그 워크트리에서 마감한 Task 를 `done` 으로 바꾸고, 대상 Intent 의 진행 표시와 `삭제 예정` 줄을 지우고, 카탈로그를 다시 만든 뒤 워크트리 · 브랜치를 지웁니다 | 머지 = 코드가 base 에 들어간 시점입니다. in-review 동안 표시가 남아 있어야 리뷰에서 돌려보낼 때 Intent 가 맞습니다 |
| 머지 안 됨 | `/worktree-delete` 가 멈추고 사용자에게 묻습니다 — squash · rebase 머지라 조상 검사에 안 잡히면 `--merged`, 버리려면 `--force`(문서는 그대로) | 안전 게이트를 겸합니다 |

### 0.3 이행 (v3.75.0)

1. `worktree_setup.py` · `/worktree-init` · `/worktree-delete` — 위 결정대로. `docs_helpers.py ensure-exclude` 신설, Task 상태에서 `in-dev` 제거.
2. `/task-split` 신설 — 자르기 기준 · 개발 프롬프트. Task · Task 카탈로그 템플릿을 `docs/.templates/.task/` 로 옮깁니다.
3. `requirement-spec` 개편 — 기존 Intent 수정 모드(기준선 사본), 여러 App, Intent v2.0 템플릿, `check-intent` v2, DOCUMENT_GUIDE v2.0.

## 1. 무엇이 바뀌나

- **Intent = 기능 문서 (상시, App 소속).** 기능 하나의 왜 · 무엇 · 결정(Part 1)과 테스트할 수 있는 동작 FR · Edge · Error(Part 2)를 담습니다. 기능이 바뀌면 Intent부터 고치고, 바뀐 항목에 진행 표시 `[TSK-012 진행 중]`을 붙입니다.
- **Task = 작업 계약서 (작업 단위, 레포 소속).** 레포 루트 `.task/TSK-{NNN}.md`에 둡니다.
  - Intent에서 바뀐 항목의 사본(Scope)과 Acceptance · Verification · Risks · Handoff를 담습니다.
  - 여러 App에 걸친 계약 변경도 Task 하나, 브랜치 하나로 묶습니다.
  - `/worktree-init`의 입력이 Intent에서 Task로 바뀝니다.
- **Task 카탈로그 `.task/task-catalog.md` (생성물).** Task 링크 · 설명 · 유형 · 상태 · 대상 Intent 링크를 담습니다.
- **이름 규칙.** 내부 코드 이름(클래스 · 인터페이스 · 함수 · 속성 등)은 쓰지 않습니다. 밖에서 보이는 이름(API 경로 · 응답 필드 · 설정 키 · 오류 코드 등)은 `종류어 + 백틱`으로 씁니다.

## 2. 초안 파일

| 초안 | 이행 시 위치 | 바뀌는 것 |
|---|---|---|
| [DOCUMENT_GUIDE.md](DOCUMENT_GUIDE.md) | `docs/.templates/DOCUMENT_GUIDE.md` | v1.0 → v2.0. §0에 `.task/` 추가, §1.2 Intent를 기능 문서로, §1.3 Task 신설, §1.4 이름 규칙 신설, §1.5 1.x 대응표, §2 · §5 · §7 · §8 · §9 개편. 외부에서 링크하는 §0 · §1 · §2 · §5 · §8 번호는 유지 |
| [APP-INT-001-TEMPLATE.md](APP-INT-001-TEMPLATE.md) | `docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md` | 작업 지시(Acceptance · Verification · Risks · Handoff)와 메타 `유형 · 승인 · 검증`을 빼고 `기능 ID`를 넣음. 진행 표시 규칙 추가 |
| [TSK-001-TEMPLATE.md](TSK-001-TEMPLATE.md) | `docs/.templates/.task/TSK-001-TEMPLATE.md` | 신설 |
| [task-catalog-TEMPLATE.md](task-catalog-TEMPLATE.md) | `docs/.templates/.task/task-catalog-TEMPLATE.md` | 신설 |
| [EXAMPLE.md](EXAMPLE.md) | 이행하지 않음 (검토용) | 초안 템플릿으로 쓴 예시 — 여러 App에 걸친 기능개발 Task 1건, 버그수정 Task 1건 |

## 3. 설계에서 확정한 것

| 항목 | 결정 | 반영 위치 |
|---|---|---|
| 문서 역할 | 기능은 App에(Intent), 작업은 레포에(Task) | DOCUMENT_GUIDE §1.2 · §1.3 |
| 흐름 | Intent를 먼저 고치고, 바뀐 부분을 Task로 파생하고, Task로 워크트리를 만든다 | DOCUMENT_GUIDE §2 |
| 이름 규칙 | 내부 코드 이름 금지, 밖에서 보이는 이름 허용 (Intent · Task 공통) | DOCUMENT_GUIDE §1.4, 두 템플릿 작성 규칙 1~3 |
| Scope 형식 | 사본을 기본으로, '변경' 항목에만 `이전` 문장 | Task 템플릿 Scope · 규칙 6 |
| Edge · Error | Intent에 두고, Task는 Scope 사본과 A로 판정. 작업·배포 동안에만 생기는 상황은 Task Risks `R-n` | DOCUMENT_GUIDE §1.3, Task 템플릿 Risks |
| 위치 · ID | `.task/TSK-{NNN}.md`, App 접두 없음, 레포 전체 번호열. 0.x `{App}-TASK-{NNN}`와 섞이지 않게 `TSK` | DOCUMENT_GUIDE §0 · §5 |
| `.task/` 커밋 | ~~점 폴더지만 커밋한다~~ → **개정 2: 커밋하지 않는다**(§0.2 문서 공유) | DOCUMENT_GUIDE §0 |
| Task 유형 | 기능개발 · 버그수정('위반') · 리팩토링('보존') | DOCUMENT_GUIDE §1.3 |
| 손대지 말 영역 | 폴더 · 프로젝트 단위 경로만 | DOCUMENT_GUIDE §1.4, Task 템플릿 Handoff |
| 카탈로그 | 생성물. 열 = Task · 설명 · 유형 · 상태 · 대상 Intent | task-catalog 템플릿 |

## 4. 초안에 기본값으로 넣은 결정 — 검토 필요

설계 단계에서 "개정안에서 정한다"로 남겼던 항목입니다. 초안에는 아래 기본값으로 썼습니다. 바꾸면 반영 위치의 문장을 함께 고칩니다.

| # | 결정 | 초안의 기본값 | 반영 위치 | 다른 선택지 |
|---|---|---|---|---|
| 1 | Intent 메타의 `상태` | `active` · `retired`만 둡니다. `유형 · 승인 · 검증` 행은 Task로 옮깁니다. Intent 변경은 Task와 함께 승인되므로 Intent 자체 승인 행이 필요 없습니다 | Intent 템플릿 메타 · 규칙 11 | 상태 행을 아예 없앰 (retired 기능은 문서 삭제) |
| 2 | 진행 표시를 지우는 시점 | ~~개발 마감(`finish`)에서 워크트리의 Intent 표시를 지우고 커밋~~ → **개정 2: `done` 때(`/worktree-delete` 가 머지를 확인한 뒤) 메인 정본에서 지웁니다.** 문서가 git 에 없어 머지로 옮길 수 없습니다 | DOCUMENT_GUIDE §2 3번, Intent 템플릿 규칙 9 | — |
| 3 | Task 취소 | `dropped` 상태를 추가합니다. Scope로 Intent를 되돌립니다(신규 삭제, 변경은 `이전` 문장으로 복원, 표시 삭제). Intent를 먼저 고치는 흐름에서는 작업을 접으면 Intent가 거짓이 되므로 되돌리는 길이 필요합니다 | Task 템플릿 메타 · 규칙 6, DOCUMENT_GUIDE §1.3 · §2 · §8 | 취소된 Task를 파일째 지우고 Intent는 git revert |
| 4 | done Task 보관 | `.task/`에 그대로 둡니다. 카탈로그가 전체 목록이자 Intent 역방향 찾기 수단입니다 | task-catalog 템플릿 | 일정 기간 뒤 `.task/archive/`로 옮김 |
| 5 | 계약을 적는 곳 | 계약의 동작(API · 필드 · 오류 코드)은 **제공하는 App의 Intent FR**에 적습니다. errorCode · DTO 등재는 지금처럼 솔루션 PRD 부록에 두고 Task 승인과 같은 커밋에 넣습니다. Task Scope는 Intent 항목만 가리킵니다 | DOCUMENT_GUIDE §8 | 계약 전용 문서를 솔루션 레벨에 두고 Scope가 그 항목도 가리킴 |
| 6 | PRD §7 ↔ Intent | 기능 1개 = Intent 1개. Intent 메타에 `기능 ID`를 두고, PRD §7의 `근거 Intent` 열은 `Intent` 열이 됩니다 | Intent 템플릿 메타, DOCUMENT_GUIDE §1.2 · §7.4 | 큰 기능은 Intent 여러 개 허용 (`관련 Intent`로 묶음) |
| 7 | Task 승인 조건 | 대상 Intent의 Open questions가 모두 none이어야 승인할 수 있습니다 | Task 템플릿 규칙 10, Intent 템플릿 Open questions | 이번 Task Scope와 무관한 질문은 허용 |
| 8 | INT 카탈로그 열 | (초안 템플릿 없음) `Intent · 제목 · 기능 ID · 상태 · 진행 중 Task · 요약 · 규모(FR · E · X 수)`를 제안합니다. `진행 중 Task`는 진행 표시에서 뽑습니다. `검증` 열은 Task 카탈로그로 갑니다 | 이행 계획에서 `APP-INT-CATALOG-TEMPLATE.md` 개정 | — |

## 5. 다루지 않기로 한 것

- App이 서브모듈로 나뉜 레포
- 1.x 형식으로 쓴 Intent를 새 형식으로 옮기는 방법
- Taskfile(go-task)의 `.task/` 캐시 폴더와 겹치는 문제 — 그런 레포가 없습니다

## 6. 영향 목록 (이행 계획의 입력)

줄 번호는 이 초안을 쓴 시점(HEAD `590dd3a`) 기준입니다.

### 6.1 스크립트

**`scripts/docs_helpers.py`**
- `_parse_intent` (`:283`): Part 2 섹션이 3개(FR · Edge · Error)로 줄어듭니다.
- `_split_intent_refs` (`:274`): 근거 괄호가 줄 끝에 있다고 가정합니다. 진행 표시가 그 뒤에 붙으므로 표시를 먼저 떼어 내야 합니다.
- 상수:
  - `INTENT_META_EXPECTED` (`:411`): 5행 `문서 ID · 기능 ID · 상태 · 작성 · 관련 Intent`로
  - `INTENT_HANDOFF_EXPECTED` (`:412`): Task 쪽으로 이동
  - `INTENT_PART2_SECTIONS` (`:414`): 3개로
- `INTENT_RULES` (`:786`): Acceptance · Verification · Handoff · 승인 게이트 규칙을 Task 규칙으로 옮깁니다.
- 체크리스트:
  - `CHECKLIST_CRITERIA`의 A 행 (`:961`): Task 체크리스트로
  - G-3 (`:1000`): DOCUMENT_GUIDE §1.4의 판별 기준으로 바꾸고 MINOR → MAJOR
- `intent-catalog` (`:1331~`): 열을 바꿉니다 (§4 #8).
- 신설:
  - `_parse_task`, `check-task`, `task-catalog`
  - `check`의 `TSK_CATALOG stale`
  - Scope ↔ Intent 정합 검사 (문장 일치, App 접두, `이전` 줄, 진행 표시 1:1, A 근거)
  - Task 간 충돌 검사 (done · dropped가 아닌 Task의 Scope 항목 중복)
  - 이름 검사 (종류어 없는 백틱 · 호출 구문 · 소스 확장자 FAIL, 식별자 모양 토큰 WARN)

**`scripts/worktree_setup.py`**
- `_detect_input_kind` (`:208`): `.task/TSK-{NNN}.md`를 Task 입력으로 인식해야 합니다. 0.x `docs/{App}/TASK/{App}-TASK-{NNN}.md`는 계속 LEGACY로 막습니다 (`tests/test_worktree_setup.py:220`).
- `_gate_intent` (`:216`) → Task 게이트: 상태가 `approved`/`in-dev`인지, `check-task`를 통과하는지, 대상 Intent와 카탈로그가 base 커밋에 있는지 봅니다.
- 상태 전이 커밋 (`:420-443`): Task 메타 + `task-catalog.md`
- 매니페스트 (`:641-650`):
  - `intent` · `intent_worktree` → `task` · `task_worktree` + `intents`(대상 Intent 경로 목록)
  - `acceptance` · `handoff`는 Task에서 읽습니다.
- `_intent_branch` (`:135`): 기본 브랜치 `task/TSK-{NNN}`
- 폐지 안내 문구 (`:586`, "Work Packet·TASK 입력은 v3.58 에서 폐지"): 0.x TASK와 새 Task를 구분하는 문구로 고칩니다. `tests/test_intent_only.py` ALLOWED도 함께 고칩니다.
- 가드레일 복사 (`:368`): `.task/`는 넣지 않습니다 (의도한 동작).

### 6.2 스킬 · 커맨드

**`skills/requirement-spec/SKILL.md`** (+ `commands/requirement-spec.md` 설명)
- Phase 0: 대상 Intent를 찾거나 새로 만들고, TSK 번호를 매기고, `.task/`가 `git check-ignore`에 걸리는지 확인합니다.
- Phase 1: 인터뷰 결과로 Intent Part 1을 고칩니다.
- Phase 2: Intent Part 2를 고치고, 그 diff에서 Task Scope를 만들고, Acceptance 등을 파생합니다.
- Phase 3: 검증 대상이 Intent 변경분 + Task가 됩니다.
- Phase 5: Task와 Intent 변경을 1회 승인하고, 카탈로그 2개를 다시 만듭니다.

**`skills/requirement-spec/templates/intent-critic.md` · `intent-expector.md`**: 판정 대상이 Intent + Task 두 문서가 됩니다. EXP (b) 기준("Part 2로 내려왔나")은 "Task Scope · A로 내려왔나"로 바뀝니다.

**`commands/worktree-init.md`**
- 인자가 `.task/TSK-{NNN}.md`가 됩니다.
- 승인 커밋 대상: Task · `task-catalog.md` · 진행 표시가 붙은 Intent들 · 해당 INT 카탈로그들
- `:(icase)` 스테이징 경로를 바꿉니다.

**forge-scope**: 1단계에서 Task 입력으로 바꿨다가 v3.73.0 에서 제거했습니다. 마감 전이(Task 상태 · 진행 표시 제거 · 카탈로그 재생성 · 커밋)는 `worktree_setup.py finish` 가 단독으로 맡습니다 (1단계에서 구현).

**`commands/worktree-delete.md` (`:47`)**: 브랜치 기본값 문구(`intent/<문서 ID>`)를 바꾸고, 작업을 접으려고 워크트리를 지울 때 Task `dropped`와 Intent 되돌리기를 안내합니다.

**`skills/branch-review/SKILL.md` 3-1 Spec 위치 탐색**: `docs/**/*.md` glob에는 `.task/`가 잡히지 않습니다. `.task/*.md`를 추가하거나, worktree-init 매니페스트가 있으면 그 Task를 spec으로 씁니다. finder 템플릿의 "Intent 블록"은 커밋 의도를 뜻하는 다른 개념이므로 바꾸지 않습니다.

### 6.3 템플릿

- **`docs/.templates/CLAUDE-TEMPLATE.md`**:
  - `:10` ID 패턴
  - `:28` 문서 인덱스 App 행 (`INTENT/`를 기능 문서로)
  - `.task/task-catalog.md` 인덱스 행 신설
  - `:45-55` 흐름 문구
  - `:75` 생성물 목록에 `task-catalog.md`
- **`docs/.templates/README-TEMPLATE.md`**: `:52-53` 문서 표, `:60` 기여 정책 문구
- **`docs/.templates/App/APP-PRD-TEMPLATE.md`**: `:62` · `:65` · `:67` (§7 `근거 Intent` → `Intent`), `:84-87` (§10 Intent 진입점에 Task 카탈로그 추가)
- **`docs/.templates/PRD-TEMPLATE.md`**: `:99` 결정 SSOT 문구 ("그 결정을 실행한 Intent" → "그 결정이 속한 기능의 Intent")
- **`docs/.templates/App/APP-INT-CATALOG-TEMPLATE.md`**: 열 변경 (§4 #8), 재생성 시점 표

### 6.4 에이전트 · 테스트 · 기타

- **에이전트 문서 종류 열거에 Task 추가**: `agents/coder.md:105`, `agents/{opus,fable}-orchestrator.md:48` · `:113`, `agents/reviewer-lite.md:31`, `agents/scribe.md:3`
- **테스트**:
  - `tests/test_intent_only.py`: RETIRED 정규식은 `-TASK-` · `TASK/`만 잡으므로 `TSK-` · `.task/`는 걸리지 않습니다. ALLOWED 문구만 6.1에 맞춰 고칩니다.
  - `tests/test_templates.py`: 새 템플릿 경로의 참조 무결성
  - `tests/test_docs_helpers.py` · `test_worktree_setup.py` · `test_worktree_init_command.py`: 입력이 Intent에서 Task로 바뀝니다.
- **플러그인 `README.md`**: 문서 체계 설명과 변경로그. `plugin.json` · `marketplace.json` 버전
