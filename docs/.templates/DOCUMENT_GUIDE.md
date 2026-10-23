# DOCUMENT_GUIDE — 문서 작성 가이드

> AI 코딩 에이전트가 레포를 세팅하거나 문서를 작성할 때 따라야 할 단일 SSOT. 작성 룰 충돌 시 본 가이드 우선. 코드 룰은 [DDD_ARCHITECTURE_RULES](.rules/DDD_ARCHITECTURE_RULES.md) / [OBJECT_ORIENTED_DESIGN_RULES](.rules/OBJECT_ORIENTED_DESIGN_RULES.md) / [BEHAVIORAL_GUIDELINES_RULES](.rules/BEHAVIORAL_GUIDELINES_RULES.md) 참조.
> **본 파일은 세팅 후 `docs/DOCUMENT_GUIDE.md` 위치 기준**. 상대 경로는 `../CLAUDE.md`, 코드 룰 파일은 `.rules/` 하위, Intent 폴더는 `../intent/`, 작업 폴더는 `../.task/`.
> **템플릿은 참고 명세다.** 플러그인의 `docs/.templates/` 는 각 문서의 구조를 보여 주는 견본이다. 대상 레포에 복사해 두는 원본이 아니다 — 문서를 만들 때 해당 템플릿을 참고해 대상 레포 맥락으로 작성한다.

| 항목 | 값 |
|---|---|
| 문서 ID | DOCUMENT_GUIDE (단일 파일) |
| 버전 | 2.1 |
| 작성 가정 | 문서는 세 종류다 — 상시 문서(CLAUDE · ARCHITECTURE · 코드 룰 · PRD · Intent), 작업 문서(Task), 생성물(카탈로그). 기능은 App 에 속하고(Intent), 작업은 레포에 속한다(Task). 설계 문서(문서 폴더 · `intent/` · `.task/`)는 커밋하지 않는다 |
| 관련 문서 | [CLAUDE](../CLAUDE.md) · [ARCHITECTURE](ARCHITECTURE.md) · [Intent 카탈로그](../intent/intent-app-catalog.md) · [Task 카탈로그](../.task/task-catalog.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 2.1 | 2026-10-23 | Intent 를 레포 루트 `intent/` 로 — `intent/{app}/{app}-int-{NNN}.md`, App 카탈로그 `intent/{app}/intent-catalog.md`, 상위 카탈로그 `intent/intent-app-catalog.md`(CLAUDE 가 링크하는 진입점). Intent · Task 의 폴더 · 파일명 · 문서 ID 는 모두 소문자(`tsk-{NNN}`, 진행 표시 `[tsk-{NNN} 진행 중]`). `docs/` 에는 PRD · ARCHITECTURE · 코드 룰이 남는다 | {이름} |
| 2.0 | 2026-10-22 | Intent 를 기능 문서(상시)로, 작업 계약을 Task(레포 루트 `.task/`)로 분리 — Task 는 `/task-split` 이 Intent 변경에서 자른다. 문서 폴더 · `.task/` 는 커밋하지 않는다(`.git/info/exclude`). Task 카탈로그 신설. 이름 규칙(§1.4) — 내부 코드 이름 금지, 밖에서 보이는 이름 허용. 1.x Intent 대응(§1.5) | {이름} |
| 1.0 | 2026-10-07 | Intent 1문서 체계로 재작성. 0.x 의 작업 단위·인덱스 문서 폐지(§1.5). §0 레포 세팅 신설 — 템플릿은 복사 원본이 아니라 참고 명세 | {이름} |

## 0. 레포 세팅

새 레포를 세팅하거나 기존 레포를 이 체계에 맞출 때 이 절부터 읽는다.

**문서 폴더 표기**: 새 레포는 `docs/` 로 만든다. 기존 레포가 `Docs/` 를 쓰면 그대로 둔다 — 플러그인 도구(`/requirement-spec` · `/task-split` · `/worktree-init` · `worktree_setup.py` · `docs_helpers.py`)는 `docs`·`Docs` 를 같은 폴더로 보고, 이 가이드의 `docs/` 도 둘 다를 뜻한다. 표기를 맞추려고 이름만 바꾸지 않는다 — Windows·macOS 에서 탐색기로 바꾸면 git 은 옛 표기를 계속 쓴다. 링크 · 경로도 실제 표기로 쓴다 — `Docs` 레포에서는 템플릿의 `docs/…` 링크가 `Docs/…` 가 된다(Linux · WSL 은 대소문자를 구분해 소문자 링크가 깨진다). 이 표기 규칙은 문서 폴더에만 있다 — `intent/` · `.task/` 는 늘 소문자다.

**설계 문서는 커밋하지 않는다**: 문서 폴더(`docs/` · `Docs/`)와 `intent/` · `.task/` 는 팀 밖으로 나가지 않는 설계 문서다 — 커밋 · 푸시하지 않는다. 공유 `.gitignore` 를 고치면 그 고침이 커밋 대상이 되므로 이 clone 의 `.git/info/exclude` 에 올린다 — `docs_helpers.py ensure-exclude` 가 하고, `/requirement-spec` · `/task-split` · `/worktree-init` 이 먼저 실행한다. 레포를 세팅할 때는 문서를 만들기 전에 직접 실행한다(§0.3 의 1). 메인 작업트리의 문서가 정본이다 — 워크트리에는 `/worktree-init` 이 정본을 복사해 넣고(링크 아님), Task 상태 전이 · 진행 표시 정리는 정본에 쓴다. 이미 커밋된 문서는 exclude 로 숨지 않는다 — 추적을 끊을지(`git rm --cached`)는 사람이 정한다.

**Intent 폴더 `intent/`**: Intent 와 Intent 카탈로그는 레포 루트 `intent/` 에 둔다 — `docs/` 와 같은 레벨이다. 문서 폴더처럼 커밋하지 않는다.

```
intent/
├── intent-app-catalog.md        상위 카탈로그 (생성물) — /CLAUDE.md 가 링크하는 진입점
└── {app}/
    ├── intent-catalog.md        App 카탈로그 (생성물)
    └── {app}-int-{NNN}.md       Intent
.task/
├── task-catalog.md              Task 카탈로그 (생성물)
└── tsk-{NNN}.md                 Task
```

**소문자 규칙**: `intent/` · `.task/` 아래의 폴더 · 파일명 · 문서 ID 는 모두 소문자다 — `{app}` 은 SYSTEM_CODE 의 소문자(`LOADER` → `loader`), Intent `loader-int-001`, Task `tsk-012`. 파일명은 문서 ID 와 같다. 대문자가 섞인 파일(`Loader-INT-001.md` · `TSK-001.md`)은 도구가 읽지 않는다 — 대소문자를 무시하는 Windows · macOS 에서도 다른 파일로 본다. 항목 ID(`D1` · `C1` · `FR-1` · `E-1` · `X-1` · `A-1` · `R-1`)는 대문자 그대로다.

**작업 폴더 `.task/`**: Task 와 Task 카탈로그는 레포 루트 `.task/` 에 둔다 — `docs/` · `intent/` 와 같은 레벨이다. 문서 폴더처럼 커밋하지 않는다.

### 0.1 만드는 것

| 경로 | 역할 | 참고 템플릿 | 필요성 |
|---|---|---|---|
| `/CLAUDE.md` | AI 진입점 · App 레지스트리(Backend Services Overview) · 문서 인덱스 | `.templates/CLAUDE-TEMPLATE.md` | 필수 |
| `/README.md` | 사람용 개요 · 빌드·실행 | `.templates/README-TEMPLATE.md` | 필수 |
| `docs/DOCUMENT_GUIDE.md` | 본 가이드 | `.templates/DOCUMENT_GUIDE.md` | 필수 |
| `docs/ARCHITECTURE.md` | 솔루션 공통 코드 레이어 규칙 | `.templates/ARCHITECTURE-TEMPLATE.md` | 필수 |
| `docs/.rules/*.md` | 코드 룰 (§1.1) | `.templates/.rules/` | 채택한 것만 |
| `docs/PRD.md` | 솔루션 PRD — 여러 App 을 묶을 때 | `.templates/PRD-TEMPLATE.md` | 선택 |
| `docs/{App}/` | App 폴더 — App 마다 1개 | — | 필수 |
| `docs/{App}/{App}-PRD.md` | App PRD · 기능 목록(§7) | `.templates/App/APP-PRD-TEMPLATE.md` | 권장 |
| `docs/{App}/{App}-ARCHITECTURE.md` | App 호스트 아키텍처 | `.templates/App/APP-ARCHITECTURE-TEMPLATE.md` | 권장 |

### 0.2 만들지 않는 것

| 대상 | 이유 |
|---|---|
| `intent/{app}/{app}-int-{NNN}.md` | `/requirement-spec` 이 인터뷰로 만들고 고친다. 손으로 만들지 않는다 |
| `intent/{app}/intent-catalog.md` · `intent/intent-app-catalog.md` | 생성물 — `docs_helpers.py intent-catalog --app {app} --write` 가 `intent/{app}/` 에서 App 카탈로그를, `intent/` 에서 상위 카탈로그를 함께 파생한다. requirement-spec · `/task-split` · `/worktree-delete` 가 다시 쓴다 |
| `.task/tsk-{NNN}.md` | `/task-split` 이 Intent 변경에서 자른다. 손으로 만들지 않는다 |
| `.task/task-catalog.md` | 생성물 — `docs_helpers.py task-catalog --write` 가 `.task/` 에서 파생한다. `/task-split` · `worktree_setup.py finish` · `/worktree-delete` 가 Task 상태 전이 때 다시 쓴다 |
| `.process/` | 도구의 작업 폴더 — Intent 기준선(`intent-base/`) · 검증 기록(`intent-check/`) · 워크트리 매니페스트(`worktree/`). 손대지 않는다 |
| `docs/.templates/` | 플러그인 쪽 참고 명세다. 대상 레포에 둘 필요 없다. 단 `docs/.templates/intent/app/app-int-001-template.md` 를 두면 requirement-spec 이, `docs/.templates/.task/tsk-001-template.md` 를 두면 `/task-split` 이 플러그인 템플릿 대신 그것을 쓴다 (레포별 커스터마이즈) |

<!-- retired-doc-types:begin -->
**폐지 문서 — 만들지 않는다**: `FRD/` · `ADR/` · `TASK/` · `WORK_PACKET/` · `RFD/` 폴더와 `{App}-FC.md` · `{App}-ADR-CATALOG.md`. 0.x 체계의 문서다 (§1.5). `docs/{App}/TASK/` 의 0.x TASK 는 레포 루트 `.task/` 의 Task 와 다른 문서다 — 새로 만들지 않고, Task 로 옮겨 쓰지도 않는다.
<!-- retired-doc-types:end -->

### 0.3 세팅 순서

1. 설계 문서를 커밋 대상에서 뺀다 — `python ~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<버전>/scripts/docs_helpers.py ensure-exclude --repo .` 가 문서 폴더 · `intent/` · `.task/` 를 이 clone 의 `.git/info/exclude` 에 올린다. 문서를 만들기 전에 한다 — 먼저 만든 문서는 `git add .` 한 번에 커밋된다. clone 마다 한다(exclude 는 공유되지 않는다).
2. `/CLAUDE.md` — SOLUTION_CODE 확정, Backend Services Overview 에 App 행 등록. 문서 인덱스에 `intent/intent-app-catalog.md` · `.task/task-catalog.md` 행을 둔다(첫 Intent · Task 전에는 링크만).
3. `docs/DOCUMENT_GUIDE.md` · `docs/ARCHITECTURE.md` · 채택한 `docs/.rules/`.
4. App 마다 `docs/{App}/` + (권장) App PRD · App ARCHITECTURE. 여러 App 이면 (선택) `docs/PRD.md`.
5. `/README.md`.
6. 첫 작업은 `/requirement-spec` 으로 시작한다 — §2. `intent/` 는 `/requirement-spec` 이, `.task/` 는 `/task-split` 이 만든다. 미리 만들지 않는다.

## 1. 문서 종류와 역할

### 1.1 솔루션 공통 (상시 문서)

| 종류 | 위치 | 역할 | 참고 템플릿 |
|---|---|---|---|
| CLAUDE | `/CLAUDE.md` | AI 진입점 / 라우터 / SOLUTION_CODE·SYSTEM_CODE SSOT / Backend Services Overview | `.templates/CLAUDE-TEMPLATE.md` |
| ARCHITECTURE | `docs/ARCHITECTURE.md` | 솔루션 공통 레이어 모델 / 참조 매트릭스 / 폴더→레이어 매핑 / 접미사 | `.templates/ARCHITECTURE-TEMPLATE.md` |
| (선택) 솔루션 PRD | `docs/PRD.md` | 솔루션 시점 — 시스템 전체 배경/목표/범위 + cross-cutting SSOT 부록 (errorCode/도메인/DTO). 미채택 시 App PRD 가 cross-cutting 부록 겸유 | `.templates/PRD-TEMPLATE.md` |
| 룰: DDD | `docs/.rules/DDD_ARCHITECTURE_RULES.md` | 레이어 위반 방지 단일 룰 | `.templates/.rules/DDD_ARCHITECTURE_RULES.md` |
| 룰: OOP | `docs/.rules/OBJECT_ORIENTED_DESIGN_RULES.md` | SOLID 책임 분해 룰 | `.templates/.rules/OBJECT_ORIENTED_DESIGN_RULES.md` |
| 룰: 클래스 구조 | `docs/.rules/CLASS_STRUCTURE_RULES.md` | 클래스 작성 규약 | `.templates/.rules/CLASS_STRUCTURE_RULES.md` |
| 룰: 로깅 | `docs/.rules/LOGGING_RULES.md` | 서비스 로깅 규약 | `.templates/.rules/LOGGING_RULES.md` |
| 룰: Behavioral | `docs/.rules/BEHAVIORAL_GUIDELINES_RULES.md` | LLM coding 행동 가이드 | `.templates/.rules/BEHAVIORAL_GUIDELINES_RULES.md` |
| 본 가이드 | `docs/DOCUMENT_GUIDE.md` | 문서 작성 SSOT (본 파일) | `.templates/DOCUMENT_GUIDE.md` |

### 1.2 App별 (per-App) — `docs/{App}/` · `intent/{app}/`

| 종류 | 위치 | 역할 | 성격 | 참고 템플릿 |
|---|---|---|---|---|
| App PRD | `docs/{App}/{App}-PRD.md` | App 시점 — 배경/목표/범위 + **기능 목록 SSOT (§7)**. 기술 시야(호스트/런타임)는 App ARCHITECTURE 위임. cross-cutting 부록은 솔루션 PRD 인용 | 상시 | `.templates/App/APP-PRD-TEMPLATE.md` |
| App ARCHITECTURE | `docs/{App}/{App}-ARCHITECTURE.md` | App 호스트 아키텍처 (런타임/진입점/책임/구성요소) | 상시 | `.templates/App/APP-ARCHITECTURE-TEMPLATE.md` |
| Intent | `intent/{app}/{app}-int-{NNN}.md` | **기능 문서** — 기능 하나의 왜 · 무엇 · 결정(Part 1)과 테스트할 수 있는 동작 FR · Edge · Error(Part 2). App PRD §7 기능 1개 = Intent 1개 | 상시 | `.templates/intent/app/app-int-001-template.md` |
| App Intent 카탈로그 | `intent/{app}/intent-catalog.md` | App 의 Intent 목록 · 진행 중 Task. 모든 열이 Intent 에서 파생 | 생성물 | `.templates/intent/app/intent-catalog-template.md` (예시) |
| 상위 Intent 카탈로그 | `intent/intent-app-catalog.md` | App 마다 App 카탈로그 링크 · Intent 수. `/CLAUDE.md` 가 링크하는 Intent 진입점 | 생성물 | `.templates/intent/intent-app-catalog-template.md` (예시) |

**Intent 는 기능이 바뀔 때 먼저 고친다** (`/requirement-spec` — 고치기 전 사본을 기준선 `.process/intent-base/` 로 남긴다). 바뀐 항목은 `/task-split` 이 Task 로 자르고 그 항목에 진행 표시(`[tsk-{NNN} 진행 중]` · `[tsk-{NNN} 삭제 예정]`)를 붙인다 (§1.3). `진행 중` 항목은 아직 base 브랜치 코드에 없는 동작이다 — 변경 항목의 지금 동작은 그 Task Scope 의 `이전` 문장이다. `삭제 예정` 항목은 그 Task 가 끝날 때까지 코드에 남아 있는 동작이다. 두 표시는 그 Task 가 끝날 때(`done`) 지운다 — `삭제 예정` 은 줄째. Intent 에는 작업 상태 전이가 없다 — 상태는 `active` · `retired` 뿐이다.

### 1.3 레포 단위 (작업 문서)

| 종류 | 위치 | 역할 | 성격 | 참고 템플릿 |
|---|---|---|---|---|
| Task | `.task/tsk-{NNN}.md` | **작업 계약** — 이번 작업이 바꾸는 Intent 항목의 사본(Scope) · 완료 조건(Acceptance) · 확인 방법 · 위험 · 착수 정보(Handoff). 여러 App 의 Intent 를 함께 바꿀 수 있다 | 작업 단위 | `.templates/.task/tsk-001-template.md` |
| Task 카탈로그 | `.task/task-catalog.md` | 모든 Task 목록 — 설명 · 유형 · 상태 · 선행 · 대상 Intent 링크. 모든 열이 Task 에서 파생 | 생성물 | `.templates/.task/task-catalog-template.md` (예시) |

**원칙 — 기능은 App 에, 작업은 레포에.** Intent : Task 는 1:1 · 1:N · N:N 이 모두 된다 — 계약 변경처럼 여러 App 이 함께 바뀌는 작업도 Task 하나로 묶을 수 있다. App 사이의 완료 조건(한쪽이 준 값을 다른 쪽이 쓰는 것)은 그 Task 의 Acceptance 에 둔다. 브랜치는 Task 가 아니라 워크트리(`/worktree-init <이름>`)가 정한다 — 한 워크트리에서 Task 여러 개를 개발하고, 순서는 Task 메타 `선행 Task` 로 고정한다.

**Task 는 새 동작을 만들지 않는다.** Scope 는 Intent 항목의 사본이고 문장이 Intent 와 글자까지 같다. 동작이 바뀌면 Intent 를 먼저 고친다. 바뀐 항목의 예전 문장은 Intent 에 남지 않으므로 Scope 의 `이전` 줄에 남긴다 — 취소할 때 되돌리는 근거도 이 줄이다.

**Task 생애주기**: `draft` → `approved` (`/task-split` 일괄 승인) → `in-review` (개발 세션이 워크트리 안에서 `worktree_setup.py finish tsk-{NNN}`) → `done` (`/worktree-delete` 가 브랜치 머지를 확인한 뒤 — 진행 표시를 지운다). 어느 단계에서든 작업을 접으면 `dropped` — Task 의 Scope 로 Intent 를 되돌린다. 전이마다 Task 카탈로그를 다시 쓴다.

**Task 유형**:
- `기능개발` — Intent 를 바꾼다. Scope 항목은 신규 · 변경 · 삭제.
- `버그수정` — Intent 는 그대로다. 코드가 어긴 항목을 '위반'으로 담는다. 스펙에 없던 경계에서 난 버그는 Intent 에 E/X 를 신규로 더하고 Scope 에 '신규'로 담는다.
- `리팩토링` — Intent 는 그대로다. 바뀌면 안 되는 항목을 '보존'으로 담는다.

**Edge · Error 가 놓이는 곳**:

| 종류 | 담는 곳 |
|---|---|
| 작업이 끝난 뒤에도 유지되는 경계 · 오류 동작 | Intent `Edge cases` · `Error cases` → Task Scope 사본 → Acceptance |
| 작업 · 배포 동안에만 생기는 상황 (이미 저장된 데이터, 배포 중 요청, 옛 클라이언트와의 공존, App 별 배포 순서) | Task `Risks` (`R-n`). 확인이 필요하면 A 의 근거로 `(R-n)` |
| 코드 내부의 경계 (널 처리 · 동시성 · 자원 해제) | 문서에 쓰지 않는다 — 개발 세션이 테스트로 다룬다 |

**구현 결정 위치**: 파일 · 인터페이스 · 스키마 · 라이브러리 선택은 Intent · Task 어디에도 쓰지 않는다 — 개발 세션이 정한다. 코드 구조 규칙은 ARCHITECTURE · `.rules/` 에 둔다. PRD 는 product 시야라 코드 상세를 쓰지 않는다.

**찾는 길**: 기능은 `/CLAUDE.md` 문서 인덱스 → `intent/intent-app-catalog.md` → `intent/{app}/intent-catalog.md` → 각 Intent. 작업은 `/CLAUDE.md` → `.task/task-catalog.md` → 각 Task. 설계 문서는 `.git/info/exclude` 에 올라 있어 ripgrep 기반 검색(Grep · Glob)이 건너뛰고, 점으로 시작하는 폴더도 일부 검색 도구가 건너뛴다 — 카탈로그 링크를 입구로 쓴다.

### 1.4 이름 규칙 (Intent · Task)

**판별 기준 — 사용자 · 외부 시스템 · 운영자가 코드를 열지 않고 볼 수 있는 이름이면 쓴다. 코드를 열어야 보이는 이름이면 쓰지 않는다.**

| 쓴다 (밖에서 보이는 이름) | 쓰지 않는다 (내부 코드 이름) |
|---|---|
| API 경로 · HTTP 메서드 — API `POST /uploads` | 클래스 · 구조체 · 레코드 · enum 이름 |
| 요청 · 응답 필드명 — 응답 필드 `retryCount` | 인터페이스 이름 |
| 설정 키 — 설정 키 `upload.retry.max` | 메서드 · 함수 · 생성자 이름, 시그니처, 호출 구문 |
| 오류 코드 · 상태 코드 — 오류 코드 `UPLOAD_RETRY_EXHAUSTED`, 상태 코드 `503` | 속성 · 필드 · 변수 · 상수 · enum 멤버 이름 |
| 화면 문구 — 문구 "업로드를 다시 시도하는 중" | 네임스페이스 · 패키지 · import 경로 |
| 기능 영역 · 계층 · 패턴 용어 — "업로드 저장 단계", "인프라 계층의 저장소 어댑터" | 파일명 · 파일 경로 |
| App 코드 · 스택 · 외부 시스템 이름 — LOADER, PostgreSQL, Docker | 라이브러리 API, 테스트 이름, 실행 명령 |

- **표기 규약**: 밖에서 보이는 이름은 백틱으로 감싸고 바로 앞에 종류어를 붙인다 — `API` · `요청 필드` · `응답 필드` · `설정 키` · `오류 코드` · `상태 코드`. 화면 문구는 큰따옴표로 감싼다. 검사기(`check-intent` · `check-task`)가 이 표기로 허용 이름을 구분한다.
- **응답 필드명은 쓴다.** 코드의 속성처럼 보이지만 밖과 맞춘 계약 이름이다. 코드 쪽 이름이 다르더라도 문서에는 밖에서 보이는 이름을 쓴다.
- **유일한 경로 예외**: Task Handoff 의 `손대지 말 영역` 에는 폴더 · 프로젝트 단위 경로를 쓴다. 파일 경로는 쓰지 않는다 — 파일명이 곧 클래스명인 언어가 있다.

| 쓰지 않는다 | 이렇게 쓴다 |
|---|---|
| `UploadService.RetryAsync()` 에 재시도 추가 | 업로드 처리 단계에서 일시 오류를 다시 시도한다 |
| `IRetryPolicy` 구현체 추가 | 재시도 규칙을 인프라 계층의 정책으로 둔다 |
| `UploadResult.RetryCount` 속성 추가 | 응답 필드 `retryCount` 로 재시도 횟수를 담는다 |
| `appsettings.json` 에 값 추가 | 설정 키 `upload.retry.max` 를 둔다 |
| `UploadTests.Retry_Twice_Succeeds` 통과 | 일시 오류 두 번 뒤 성공하는 업로드가 성공 응답을 받는다 |

### 1.5 폐지 · 이전 문서 대응

<!-- retired-doc-types:begin -->
| 0.x 문서 | 2.0 에서 맡는 곳 |
|---|---|
| FRD (기능 요구) | Intent (Part 1 + Part 2) |
| TASK (작업 범위 계약, `docs/{App}/TASK/`) | Task (`.task/`) — 형식을 새로 정했다. 0.x TASK 를 옮겨 쓰지 않는다 |
| RFD (리팩토링 계획) | Task `유형 = 리팩토링` |
| Work Packet (실행 manifest) | `/worktree-init` 매니페스트 (`.process/worktree/handoff.json`, 생성물) |
| ADR (결정 기록) | Intent Part 1 `Decisions` (`D1.` …) |
| ADR-CATALOG (결정 인덱스) | `intent/{app}/intent-catalog.md` (생성물) |
| FC (기능 레지스트리) | App PRD §7 기능 목록 |

기존 레포에 0.x 문서가 있으면 지우지 않는다 — 과거 요구·결정의 기록이다. 새 작업은 Intent · Task 로만 하고, 필요하면 Intent 의 Constraints · Decisions 에서 인용한다. 0.x 문서를 갱신하거나 새로 만들지 않는다.
<!-- retired-doc-types:end -->

| 1.x Intent (작업 단위) 의 부분 | 2.0 에서 맡는 곳 |
|---|---|
| Part 1 (Problem · Outcome · Affected · Constraints · Decisions · Open questions) | Intent Part 1 |
| Part 2 `Functional requirements` · `Edge cases` · `Error cases` | Intent Part 2 |
| Part 2 `Acceptance` · `Verification` · `Risks` · `Handoff` | Task |
| 메타 `유형` · `상태`(작업 전이) · `승인` · `검증` | Task 메타 |
| App Intent 카탈로그의 상태 · 검증 열 | `.task/task-catalog.md` |

1.x · 2.0 Intent 의 옛 위치(`docs/{App}/INTENT/`) · 대문자 이름은 도구가 읽지 않는다 — 옮기는 일은 이 가이드 밖에서 한다. 1.x Intent 는 `/requirement-spec` 이 고칠 때 2.0 형식으로 옮긴다 — 동작은 바꾸지 않고 형식만. 옛 방식으로 이미 개발한 Intent 는 옮긴 모습을 기준선으로 남겨(`intent-base --save --implemented`) 다음 고침부터 바뀐 항목만 Task 로 잘리게 한다.

## 2. 작성 순서

**기능개발 · 버그수정 · 리팩토링** (한 흐름):
1. `/requirement-spec` — 인터뷰로 무엇을 바꿀지 정하고 대상 Intent 를 고친다(새 기능이면 만든다). 계약이 바뀌면 호출하는 App · 제공하는 App 의 Intent 를 함께 고친다. 고치기 전 사본을 기준선으로 남기고, 검증한 뒤 사용자가 한 번 확정한다. Intent 카탈로그(App · 상위)를 다시 만든다. 버그수정 · 리팩토링으로 Intent 가 바뀌지 않으면 건너뛴다.
2. `/task-split` — 바뀐 항목을 자르기 기준으로 Task n 개(`.task/tsk-{NNN}.md`)로 자르고, 그 항목에 진행 표시를 붙이고, 한 번에 승인받는다(`approved`). Intent · Task 카탈로그를 다시 만들고, 개발 세션에 넣을 개발 프롬프트를 낸다.
3. `/worktree-init <이름>` — 워크트리 · 브랜치(`work/<이름>`)를 만들고 문서 폴더 · `intent/` · `.task/` 를 복사해 넣는다. Task 를 읽지 않는다.
4. 워크트리에서 개발 세션을 시작해 개발 프롬프트로 Task 들을 개발한다. Task 하나의 개발을 커밋할 때마다 워크트리 안에서 `python "<worktree_setup.py 절대경로>" finish tsk-{NNN}` — 경로는 `/worktree-init` 보고와 개발 프롬프트에 있다. 커밋 안 된 변경이 있거나 base 이후 개발 커밋이 없으면 멈춘다. 정본 Task 를 `in-review` 로 바꾸고 Task 카탈로그를 다시 만든다.
5. `/branch-review` — 워크트리 브랜치를 리뷰한다. 사람이 브랜치를 base 에 머지한다.
6. `/worktree-delete` — 머지를 확인하고, 그 워크트리에서 마감한 Task 를 `done` 으로 바꾸고, 대상 Intent 의 진행 표시와 `삭제 예정` 줄을 지우고, Intent · Task 카탈로그를 다시 만든 뒤 워크트리 · 브랜치를 지운다.
7. 기능 목록이 바뀌었으면 App PRD §7 (여러 App 이면 솔루션 PRD §8 도), 코드 규칙이 바뀌었으면 ARCHITECTURE · `.rules/` 를 맞춘다. 근거로 Task ID 를 남긴다.

**취소**: 승인 뒤 작업을 접으면 사용자 확인을 받아 Task 를 `dropped` 로 바꾸고 Task 의 Scope 로 Intent 를 되돌린다 — 신규 항목은 지우고, 변경 항목은 `이전` 문장으로 복원하고, 진행 표시를 지운다. Intent · Task 카탈로그를 다시 만든다. 워크트리가 있으면 `/worktree-delete` 로 정리한다.

**결정 기록**: 기능에 대한 되돌리기 어려운 결정은 그 기능 Intent 의 `Decisions` 에 남긴다 (근거 · 기각 대안 포함) — `/requirement-spec` 으로 고치고, 동작이 바뀌면 그 변경은 `/task-split` 이 Task 와 함께 승인받는다. 구현 결정은 개발 세션 ledger 에 남는다. 실행할 작업이 없는 규칙 변경이면 ARCHITECTURE · `.rules/` 본문을 직접 고치고 변경 이력에 근거를 남긴다.

**신규 App 추가**: `/CLAUDE.md` Backend Services Overview 행 추가 (SYSTEM_CODE 확정) → `/CLAUDE.md` 설계 문서 인덱스 App 행 복제 → `docs/{App}/` 생성 → (권장) App PRD · App ARCHITECTURE 작성. `intent/{app}/` 는 미리 만들지 않는다 — 그 App 의 첫 Intent 를 만드는 `/requirement-spec` 이 만든다.

## 3. 메타 표 공통 패턴

상시 콘텐츠 문서 상단 보유 (라우터 CLAUDE 제외). Intent 는 자체 메타 표(5행), Task 는 자체 메타 표(8행)를 쓴다 — 각 템플릿 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | (§5 식별자 규약 참조) |
| 버전 | 0.1 (Draft) 등 |
| 작성 가정 | 작성 시 깔린 가정 한 줄 |
| 관련 문서 | 상위 SSOT 인용 (PRD / ARCHITECTURE 등) |

## 4. 변경 이력 표 공통 패턴

메타 표 직후 신설. 상시 콘텐츠 문서에 적용한다. Intent · Task · 카탈로그는 제외 — Intent 의 변경은 그 변경을 자른 Task 의 Scope 가 기록하고(바뀌기 전 문장은 `이전` 줄, Task 카탈로그의 대상 Intent 열로 역으로 찾는다), Task 는 메타 `상태` 가 전이를 담고, 카탈로그는 생성물이다.

```
## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |
```

## 5. 식별자 규약

| 식별자 | 형식 | 예시 |
|---|---|---|
| SOLUTION_CODE | 영문 대문자 (솔루션 이름) | `XLAB` |
| SYSTEM_CODE ≡ APP_CODE ≡ {App} | 영문 대문자 (App 이름) — `docs/{App}/` 문서 | `LOADER` |
| {app} | SYSTEM_CODE 의 소문자 — `intent/{app}/` 폴더 · Intent ID | `loader` |
| 솔루션 PRD ID | `{SOLUTION_CODE}-PRD` (NNN 없음 — 단일) | `XLAB-PRD` |
| App PRD ID | `{App}-PRD` | `LOADER-PRD` |
| ARCHITECTURE ID | `{App}-ARCHITECTURE` | `LOADER-ARCHITECTURE` |
| Intent ID | `{app}-int-{NNN}` (NNN 3자리 0패딩, 파일명과 같다) | `loader-int-001` |
| App Intent 카탈로그 ID | `{app}-intent-catalog` (파일 `intent/{app}/intent-catalog.md`) | `loader-intent-catalog` |
| 상위 Intent 카탈로그 ID | `intent-app-catalog` (파일 `intent/intent-app-catalog.md`) | `intent-app-catalog` |
| Intent 항목 | `D{n}` 결정 · `C{n}` 제약 · `FR-{n}` · `E-{n}` · `X-{n}` (Intent 내부 로컬, 1부터) | `FR-3`, `E-2` |
| Intent 항목 (문서 밖에서) | `{app}-int-{NNN} {항목}` — Task 등 다른 문서에서 가리킬 때는 App 접두까지 쓴다 | `loader-int-003 FR-4` |
| Task ID | `tsk-{NNN}` (레포 전체에서 하나의 번호열, NNN 3자리 0패딩, 파일명과 같다) | `tsk-012` |
| Task 카탈로그 ID | `task-catalog` | `task-catalog` |
| Task 항목 | `A-{n}` 완료 조건 · `R-{n}` 위험 (Task 내부 로컬, 1부터) | `A-2`, `R-1` |
| 진행 표시 | `[tsk-{NNN} 진행 중]` · `[tsk-{NNN} 삭제 예정]` (Intent 항목 줄 끝) | `[tsk-012 진행 중]` |
| 워크트리 브랜치 | `work/{이름}` (`/worktree-init <이름>`, `--branch` 로 바꾼다) | `work/upload-retry` |
| 기능 ID | `F{NNN}` (App PRD §7 행, App 내부 로컬) | `F001` |
| 기능 ID (cross-app) | `{App}:F{NNN}` | `LOADER:F001` |
| errorCode | SCREAMING_SNAKE | `INVALID_TOKEN` |

Intent · Task 의 폴더 · 파일명 · 문서 ID 는 소문자, 항목 ID 는 대문자다 (§0 소문자 규칙). SYSTEM_CODE 후보는 [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md) 표를 단일 출처. 신규 App 도입 시 해당 표 행 추가 선행. SOLUTION_CODE 는 `/CLAUDE.md` 제목 line + `docs/ARCHITECTURE.md` 메타 표가 단일 출처.

## 6. placeholder / 빈칸 룰

- placeholder 형식: `{설명}` 중괄호. 실제 값 채우거나 줄 삭제.
- 솔루션 레벨 placeholder: `{SOLUTION_CODE}`, `{프로젝트명}`.
- App 레벨 placeholder: `{App}` (또는 `{SYSTEM_CODE}` / `{APP_CODE}` — 동의어), `{app}` (그 소문자 — `intent/` 아래), `{NNN}` (Intent · Task 번호 3자리).
- 빈칸 / "N/A" **금지**. 해당 없으면 **"없음" 명기** (Intent · Task 는 템플릿 규칙대로 `none`).
- 미완성 항목은 "미작성/추후" 명기.
- `_` 또는 `.` 시작 폴더는 기본적으로 SSOT 아님. 단 `docs/.rules/` 는 예외 — 코드 룰 (DDD/OOP/클래스 구조/로깅/Behavioral) SSOT. `.task/` 도 SSOT 가 아니다 — 기능의 기준은 Intent 다.

## 7. 인용 패턴

상호 참조 시 마크다운 링크 + anchor.

### 7.1 App 폴더 내부 상대 경로 (기준: `docs/{App}/` 내부 파일)

- PRD 절: `[PRD §3]({App}-PRD.md#3-목표)`
- Intent: `[{app}-int-001](../../intent/{app}/{app}-int-001.md)`
- Intent 결정: `[{app}-int-001 D2](../../intent/{app}/{app}-int-001.md#decisions)`
- Intent 카탈로그: `[{app}-intent-catalog](../../intent/{app}/intent-catalog.md)`

### 7.2 솔루션 공통 문서 참조 (기준: `docs/{App}/` 내부 파일 → 상위)

- 솔루션 ARCHITECTURE: `[ARCHITECTURE](../ARCHITECTURE.md)`
- DDD 룰: `[DDD](../.rules/DDD_ARCHITECTURE_RULES.md)`
- DOCUMENT_GUIDE: `[DOCUMENT_GUIDE](../DOCUMENT_GUIDE.md)`
- CLAUDE: `[CLAUDE](../../CLAUDE.md)` (레포 루트)
- Task 카탈로그: `[task-catalog](../../.task/task-catalog.md)`

### 7.3 Intent 폴더 내부 상대 경로 (기준: `intent/{app}/` 내부 파일)

- 같은 App 의 Intent: `[{app}-int-002]({app}-int-002.md)`
- 다른 App 의 Intent: `[viewer-int-001](../viewer/viewer-int-001.md)`
- App 카탈로그: `[{app}-intent-catalog](intent-catalog.md)` · 상위 카탈로그: `[intent-app-catalog](../intent-app-catalog.md)`
- App PRD: `[{App}-PRD §7](../../docs/{App}/{App}-PRD.md#7-기능-목록-본-app-ssot)`
- 솔루션 ARCHITECTURE · DOCUMENT_GUIDE: `[ARCHITECTURE](../../docs/ARCHITECTURE.md)` · `[DOCUMENT_GUIDE](../../docs/DOCUMENT_GUIDE.md)`
- CLAUDE: `[CLAUDE](../../CLAUDE.md)` (레포 루트)

### 7.4 Task 와 Intent 사이

- Task → Intent 문서 (기준: `.task/`): `[loader-int-003](../intent/loader/loader-int-003.md)`.
- Task 안의 Intent 항목: `loader-int-003 FR-4` — 링크 없이 ID 로 쓴다. Scope 에 문장 사본이 있다.
- Intent → Task: 진행 표시 `[tsk-012 진행 중]` 로만 가리킨다. 링크가 필요하면 `[tsk-012](../../.task/tsk-012.md)` (기준: `intent/{app}/`).

### 7.5 인용 방향

- Intent → 상시 문서: 허용. Constraints · Decisions 의 근거로 인용한다.
- Task → Intent: 허용 — Scope · Acceptance 의 근거. Task 는 Intent 에 없는 동작을 만들지 않는다.
- Intent → Task: 진행 표시로만. Task 본문을 Intent 에 복제하지 않는다.
- 상시 문서 → Intent: App PRD §7 `Intent` 열, 결정의 근거. Intent 본문을 상시 문서에 복제하지 않는다.
- 상시 문서 → Task: 근거 표기로만 — 기능 목록 · 규칙 변경의 근거 Task ID.
- "관련 문서" 메타 행에는 상위 SSOT 를 인용하고, 하위(디테일)는 본문에서 인용한다.

## 8. 동기화 부담 위치

| 변경 | 갱신 위치 |
|---|---|
| 기능을 새로 만들거나 바꿈 | `/requirement-spec` 이 Intent 작성 · 수정 + 기준선 + Intent 카탈로그(App · 상위) 재생성 (자동) |
| Task 자르기 (`approved`) | `/task-split` 이 Task 작성 + 진행 표시 + 기준선 소비 + Intent · Task 카탈로그 재생성 (자동) |
| Task 마감 (`in-review`) | Task 카탈로그 재생성 — `worktree_setup.py finish` 가 수행 |
| Task 완료 (`done`) | 진행 표시 · 삭제 예정 줄 제거 + Intent · Task 카탈로그 재생성 — `/worktree-delete` 가 머지를 확인한 뒤 수행 |
| Task 취소 (`dropped`) | Task Scope 로 Intent 되돌리기 + Intent · Task 카탈로그 재생성 |
| 카탈로그 재생성 누락 | `docs_helpers.py check` 가 `INT_CATALOG stale` · `INT_APP_CATALOG stale` · `TSK_CATALOG stale` 로 잡는다 |
| Task 완료로 기능 목록 변경 | App PRD §7 (+ 여러 App 이면 솔루션 PRD §8) — 근거 Task ID |
| Task 완료로 cross-cutting 영향 | 위 + 솔루션 PRD §3.1 · 부록 B/D/E (영향 시) |
| 결정으로 코드 규칙 변경 | ARCHITECTURE / `.rules/` 본문 + 변경 이력에 근거 Task ID |
| 솔루션 PRD ↔ App PRD 동기화 | App PRD §3.1 · §7 변경 시 솔루션 PRD §3.1 · §8 동기화. 신규 errorCode/도메인 entity/Contract DTO 발생 시 솔루션 PRD 부록 B/D/E 등재 선행 — Task 승인 전에 둔다 |
| 신규 App | `/CLAUDE.md` Backend Services Overview + `/CLAUDE.md` 인덱스 표 + `docs/{App}/` (+ 권장 App PRD · App ARCHITECTURE) — `intent/{app}/` 와 상위 카탈로그 행은 첫 `/requirement-spec` 이 만든다 + 솔루션 PRD 가 있으면 §7 App 레지스트리 · §11 진입점 행 |
| 새 룰 파일 추가 | `/CLAUDE.md` 인덱스 행 추가 |
| 신규 솔루션 (레포 초기화) | §0 레포 세팅 |

## 9. AI 작업 시나리오 요약

- **레포 세팅 요청** → §0. §0.2 의 만들지 않는 것은 만들지 않는다.
- **기능 변경 · 버그 수정 · 리팩토링 요청** → §2 흐름. Intent · Task 를 손으로 먼저 만들지 않는다 — `/requirement-spec` 이 Intent 를, `/task-split` 이 Task 를 만든다.
- **결정 기록 요청** → §2 결정 기록.
- **신규 App 추가 요청** → §2 신규 App 추가. Backend Services Overview 행 추가가 모든 다른 작업보다 선행.
- **코드 작성 요청** → 승인된 Task 를 먼저 읽는다(개발 세션에서는 `/task-split` 이 준 개발 프롬프트가 가리키는 Task). Scope 가 범위, Acceptance 가 완료 조건, 대상 Intent 의 Constraints · Decisions 와 ARCHITECTURE · `.rules/` 가 제약이다. 충돌하면 구현하지 않고 보고한다. Task 에 없는 요구는 구현하지 않는다. 공통 룰 파일의 4단계 마커 (반드시/허용/금지/절대 금지) 를 준수한다.
- **기능이 지금 어떻게 동작하는지 묻는 요청** → `intent/intent-app-catalog.md` 에서 링크를 따라 그 기능의 Intent 를 읽는다. `진행 중` 항목은 아직 base 브랜치 코드에 없는 동작이다 — 변경 항목의 지금 동작은 그 Task Scope 의 `이전` 문장이다. `삭제 예정` 항목은 그 Task 가 끝날 때까지 코드에 남아 있는 동작이다.
- **진행 중인 작업을 묻는 요청** → `.task/task-catalog.md` 의 상태 열.
- **0.x 문서나 1.x Intent 가 남은 레포에서 작업 요청** → §1.5. 옛 위치(`docs/{App}/INTENT/`)에만 Intent 가 있으면 도구가 찾지 못한다 — 사람에게 알린다.
- **문서를 커밋하려는 요청** → §0 — 문서 폴더 · `intent/` · `.task/` 는 커밋하지 않는다. `git add` 하지 않고, 이미 커밋된 문서는 추적을 끊을지 사람에게 묻는다.
