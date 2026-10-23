# 프로젝트: {프로젝트명} ({SOLUTION_CODE})

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다. 본 파일은 레포 루트(`/CLAUDE.md`)에 배치한다. 레포 세팅 절차는 [`docs/DOCUMENT_GUIDE.md` §0](docs/DOCUMENT_GUIDE.md#0-레포-세팅) 참조. 기존 레포의 문서 폴더가 `Docs/` 면 이 파일의 링크 · 경로의 `docs/` 를 모두 `Docs/` 로 쓴다 — 링크는 실제 폴더 표기와 같아야 Linux · WSL 에서도 열린다(대소문자 구분). `intent/` · `.task/` 는 늘 소문자다.

> {프로젝트 한 줄 요약 — 무엇을 하는 시스템인가}. **설계·규칙은 아래 상시 문서가, 기능의 동작·결정은 Intent 문서가 단일 진실 공급원(SSOT)**. 코드 작성 전 관련 문서를 직접 읽어 최신 정합성을 확보한다.

## 용어 정의

- **SOLUTION_CODE**: 솔루션(레포 전체) 식별자. 예: `XLAB`. 솔루션 공통 문서 (`ARCHITECTURE.md` 등) 에서 사용.
- **SYSTEM_CODE** ≡ **APP_CODE** ≡ **{App}**: App(S/W 단위) 식별자. 동일 개념의 3개 별칭. 본 파일의 § Backend Services Overview 표가 단일 출처(SSOT). 예: `LOADER`. App별 문서 ID 패턴 `{SYSTEM_CODE}-PRD`, `{SYSTEM_CODE}-ARCHITECTURE` 에 사용. Intent 는 SYSTEM_CODE 의 **소문자** `{app}` 을 쓴다 — 폴더 `intent/{app}/`, 문서 ID `{app}-int-{NNN}`(예: `loader-int-001`), 카탈로그 `{app}-intent-catalog`. 작업 문서 Task 는 App 에 묶이지 않는 레포 번호열 `tsk-{NNN}` 이다.

상세 식별자 규약은 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) §5 참조.

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

## 설계 문서 인덱스

| 영역 | 경로 | 역할 |
|---|---|---|
| **AI 진입점 (본 파일)** | `/CLAUDE.md` | SOLUTION_CODE / SYSTEM_CODE SSOT · Backend Services Overview · 라우터 |
| **문서 작성 룰** | [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) | 문서 작성 SSOT — 문서 종류/식별자/메타/인용 패턴/AI 작업 시나리오 |
| **솔루션 ARCHITECTURE** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 솔루션 공통 룰 (레이어 모델·참조 매트릭스·폴더→레이어 매핑·접미사) |
| **코드 룰** | [`docs/.rules/`](docs/.rules/) | 채택한 코드 룰 (DDD / OOP / 클래스 구조 / 로깅 / Behavioral). 채택하지 않은 룰 파일은 두지 않는다 |
| **(선택) 솔루션 PRD** | [`docs/PRD.md`](docs/PRD.md) | 솔루션 단일 PRD (다중 S/W 통합 시). per-app PRD 만 사용 시 미배치 — 해당 행 삭제 |
| **App: {SYSTEM_CODE}** | [`docs/{SYSTEM_CODE}/`](docs/{SYSTEM_CODE}/) | App PRD (기능 목록) · App ARCHITECTURE |
| **Intent** | [`intent/intent-app-catalog.md`](intent/intent-app-catalog.md) | 기능 문서 진입점 (생성물) — App 마다 `intent/{app}/intent-catalog.md` → `intent/{app}/{app}-int-{NNN}.md`. 로컬 설계 문서라 검색 도구가 건너뛴다 — 이 링크를 따라 찾는다 |
| **Task** | [`.task/task-catalog.md`](.task/task-catalog.md) | 작업 문서(`.task/tsk-{NNN}.md`) 목록 · 상태 (생성물). Task 는 `/task-split` 이 만든다 |
| {CI · 자동화 도구} | {경로 또는 "해당 없음"} | {도구 역할 한 줄} |

App 다수 시 `App: {SYSTEM_CODE}` 행 복제. 문서 종류 상세는 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) §1.

## Backend Services Overview

본 솔루션의 App 레지스트리. **SYSTEM_CODE 단일 출처(SSOT)**. 신규 App 도입 시 본 표 행 추가가 모든 다른 작업(App 문서·Intent 작성) 보다 선행. App 다수 시 행 복제.

| SYSTEM_CODE | 한 줄 설명 | 호스트 종류 | TFM/런타임 | 폴더 |
|---|---|---|---|---|
| {SYSTEM_CODE} | {App 역할 1줄} | {WPF / .NET Worker / ASP.NET Web API / etc.} | {예: net6.0} | [`docs/{SYSTEM_CODE}/`](docs/{SYSTEM_CODE}/) |

## 진입 순서

- 신규 작성자/AI 는 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) 를 먼저 읽는다 (문서 종류·식별자·인용 패턴).
- 코드 작성 전 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 절대 금지 매트릭스 확인.
- **설계 문서는 커밋하지 않는다** — `docs/` · `intent/` · `.task/` 는 이 clone 의 `.git/info/exclude` 에 올라 있어야 한다(`docs_helpers.py ensure-exclude`). `git add` 하지 않는다 ([DOCUMENT_GUIDE §0](docs/DOCUMENT_GUIDE.md#0-레포-세팅)).
- **기능개발 · 버그수정 · 리팩토링 흐름** ([DOCUMENT_GUIDE §2](docs/DOCUMENT_GUIDE.md#2-작성-순서) 준수):
  1. `/requirement-spec` — 인터뷰로 Intent(기능 문서)를 새로 쓰거나 고친다. 산출물 `intent/{app}/{app}-int-{NNN}.md`
  2. `/task-split` — 바뀐 항목을 Task(`.task/tsk-{NNN}.md`) n 개로 자르고 한 번에 승인한다. 개발 프롬프트를 낸다
  3. `/worktree-init <이름>` — 워크트리 · 브랜치 구성 (Task 를 읽지 않는다)
  4. 그 워크트리에서 개발 세션을 시작해 개발 프롬프트로 개발하고, Task 하나의 개발을 커밋할 때마다 워크트리 안에서 `worktree_setup.py finish tsk-{NNN}`(절대경로는 `/worktree-init` 보고에 있다 — 커밋 안 된 변경이 있으면 멈춘다)
  5. `/branch-review` → 머지 → `/worktree-delete` (머지 확인 · Task `done` · 진행 표시 정리)
  6. 기능 목록이 바뀌었으면 App PRD §7, 코드 규칙이 바뀌었으면 ARCHITECTURE · `.rules/` 갱신 (근거 Task ID 기록)
- **결정 기록**: 그 결정이 속한 기능 Intent 의 `Decisions` 에 남긴다. 별도 결정 문서를 만들지 않는다.
- **신규 App 추가**:
  1. 본 파일 § Backend Services Overview 표 행 추가 (SYSTEM_CODE 확정)
  2. 본 파일 § 설계 문서 인덱스 표에 `App: {SYSTEM_CODE}` 행 복제·추가
  3. `docs/{SYSTEM_CODE}/` 폴더 생성. `intent/{app}/` 는 미리 만들지 않는다 — 첫 `/requirement-spec` 이 만든다
  4. (권장) App PRD · App ARCHITECTURE 작성 — `.templates/App/APP-PRD-TEMPLATE.md` · `.templates/App/APP-ARCHITECTURE-TEMPLATE.md` 참고

## 레포 세팅 (최초 1회)

템플릿은 플러그인의 `docs/.templates/` 에 있는 **참고 명세**다. 대상 레포에 복사해 두지 않고, 구조를 참고해 각 문서를 작성한다. 만드는 것·만들지 않는 것의 전체 목록은 [`docs/DOCUMENT_GUIDE.md` §0](docs/DOCUMENT_GUIDE.md#0-레포-세팅).

세팅 완료 상태:

- [ ] `/CLAUDE.md` — 본 파일. SOLUTION_CODE · Backend Services Overview 확정
- [ ] `/README.md`
- [ ] `docs/DOCUMENT_GUIDE.md`
- [ ] `docs/ARCHITECTURE.md`
- [ ] `docs/.rules/` — 채택한 룰만
- [ ] (선택) `docs/PRD.md` — 여러 App 을 묶을 때
- [ ] App 마다 `docs/{SYSTEM_CODE}/` (+ 권장 App PRD · App ARCHITECTURE)

## 절대 변경 금지

- `docs/DOCUMENT_GUIDE.md`, `docs/ARCHITECTURE.md` — 가이드 SSOT. 사용자 승인 전 수정 금지.
- `intent/intent-app-catalog.md` · `intent/{app}/intent-catalog.md` — 생성물. 손으로 고치지 않는다 (Intent 를 고치고 재생성).
- `.task/task-catalog.md` — 생성물. 손으로 고치지 않는다 (Task 를 고치고 재생성).
- `/CLAUDE.md`(본 파일), `MEMORY.md` — 사용자 승인 전 수정 금지.
- {`README.md`, CI 설정, 자동화 도구 등 도메인별 보존 항목}.
