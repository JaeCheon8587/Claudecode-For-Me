# DOCUMENT_GUIDE — 문서 작성 가이드

> AI 코딩 에이전트가 레포를 세팅하거나 문서를 작성할 때 따라야 할 단일 SSOT. 작성 룰 충돌 시 본 가이드 우선. 코드 룰은 [DDD_ARCHITECTURE_RULES](.rules/DDD_ARCHITECTURE_RULES.md) / [OBJECT_ORIENTED_DESIGN_RULES](.rules/OBJECT_ORIENTED_DESIGN_RULES.md) / [BEHAVIORAL_GUIDELINES_RULES](.rules/BEHAVIORAL_GUIDELINES_RULES.md) 참조.
> **본 파일은 세팅 후 `docs/DOCUMENT_GUIDE.md` 위치 기준**. 상대 경로는 `../CLAUDE.md`, 코드 룰 파일은 `.rules/` 하위.
> **템플릿은 참고 명세다.** 플러그인의 `docs/.templates/` 는 각 문서의 구조를 보여 주는 견본이다. 대상 레포에 복사해 두는 원본이 아니다 — 문서를 만들 때 해당 템플릿을 참고해 대상 레포 맥락으로 작성한다.

| 항목 | 값 |
|---|---|
| 문서 ID | DOCUMENT_GUIDE (단일 파일) |
| 버전 | 1.0 |
| 작성 가정 | 문서는 두 종류다 — 상시 문서(CLAUDE · ARCHITECTURE · 코드 룰 · PRD)와 작업 단위 문서(Intent). 작업 단위 문서는 Intent 1종뿐이다 |
| 관련 문서 | [CLAUDE](../CLAUDE.md) · [ARCHITECTURE](ARCHITECTURE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 1.0 | 2026-10-07 | Intent 1문서 체계로 재작성. 0.x 의 작업 단위·인덱스 문서 폐지(§1.3). §0 레포 세팅 신설 — 템플릿은 복사 원본이 아니라 참고 명세 | {이름} |

## 0. 레포 세팅

새 레포를 세팅하거나 기존 레포를 이 체계에 맞출 때 이 절부터 읽는다.

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
| `docs/{App}/INTENT/{App}-INT-{NNN}.md` | `/requirement-spec` 이 인터뷰로 작성한다. 손으로 만들지 않는다 |
| `docs/{App}/{App}-INT-CATALOG.md` | 생성물 — `docs_helpers.py intent-catalog --write` 가 `INTENT/` 에서 파생한다. requirement-spec · `/forge-init` · forge-scope 가 상태 전이 때 다시 쓴다 |
| `docs/.templates/` | 플러그인 쪽 참고 명세다. 대상 레포에 둘 필요 없다. 단 `docs/.templates/App/INTENT/APP-INT-001-TEMPLATE.md` 를 두면 requirement-spec 이 플러그인 템플릿 대신 그것을 쓴다 (레포별 커스터마이즈) |

<!-- retired-doc-types:begin -->
**폐지 문서 — 만들지 않는다**: `FRD/` · `ADR/` · `TASK/` · `WORK_PACKET/` · `RFD/` 폴더와 `{App}-FC.md` · `{App}-ADR-CATALOG.md`. 0.x 체계의 문서이며 역할은 Intent 가 대체한다 (§1.3).
<!-- retired-doc-types:end -->

### 0.3 세팅 순서

1. `/CLAUDE.md` — SOLUTION_CODE 확정, Backend Services Overview 에 App 행 등록.
2. `docs/DOCUMENT_GUIDE.md` · `docs/ARCHITECTURE.md` · 채택한 `docs/.rules/`.
3. App 마다 `docs/{App}/` + (권장) App PRD · App ARCHITECTURE. 여러 App 이면 (선택) `docs/PRD.md`.
4. `/README.md`.
5. 첫 작업은 `/requirement-spec` 으로 시작한다 — §2.

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

### 1.2 App별 (per-{App})

| 종류 | 위치 | 역할 | 성격 | 참고 템플릿 |
|---|---|---|---|---|
| App PRD | `docs/{App}/{App}-PRD.md` | App 시점 — 배경/목표/범위 + **기능 목록 SSOT (§7)**. 기술 시야(호스트/런타임)는 App ARCHITECTURE 위임. cross-cutting 부록은 솔루션 PRD 인용 | 상시 | `.templates/App/APP-PRD-TEMPLATE.md` |
| App ARCHITECTURE | `docs/{App}/{App}-ARCHITECTURE.md` | App 호스트 아키텍처 (런타임/진입점/책임/구성요소) | 상시 | `.templates/App/APP-ARCHITECTURE-TEMPLATE.md` |
| Intent | `docs/{App}/INTENT/{App}-INT-{NNN}.md` | 작업 단위 계약 — Part 1 기능 명세(무엇을·왜·결정) + Part 2 작업 지시(FR · 엣지 · 오류 · Acceptance · Verification · Handoff) | 작업 단위 | `.templates/App/INTENT/APP-INT-001-TEMPLATE.md` |
| Intent 카탈로그 | `docs/{App}/{App}-INT-CATALOG.md` | Intent 목록·상태 인덱스. 모든 열이 Intent 에서 파생 | 생성물 | `.templates/App/APP-INT-CATALOG-TEMPLATE.md` (예시) |

**Intent 생애주기**: `draft` → `approved` (requirement-spec 승인) → `in-dev` (`/forge-init`) → `in-review` (forge-scope 마감) → `done` (사람이 전이). 전이마다 카탈로그를 다시 쓴다.

**코드 상세 위치**: Intent 는 생성·수정 대상의 클래스명·메서드명·파일 경로·라이브러리 API 를 Handoff 표 밖에 쓰지 않는다 — 개발 세션 몫이다. PRD 는 product 시야라 코드 상세를 쓰지 않는다. 코드 구조 규칙은 ARCHITECTURE · `.rules/` 에 둔다.

### 1.3 폐지 문서 대응 (0.x → 1.0)

<!-- retired-doc-types:begin -->
| 0.x 문서 | 1.0 에서 맡는 곳 |
|---|---|
| FRD (기능 요구) | Intent Part 1 + Part 2 `Functional requirements` |
| TASK (작업 범위 계약) | Intent Part 2 (`Edge cases` · `Error cases` · `Acceptance` · `Verification` · `Handoff`) |
| RFD (리팩토링 계획) | Intent `유형 = 리팩토링` |
| Work Packet (실행 manifest) | `/forge-init` 매니페스트 (`.process/forge/handoff.json`, 생성물) |
| ADR (결정 기록) | Intent Part 1 `Decisions` (`D1.` …) |
| ADR-CATALOG (결정 인덱스) | `{App}-INT-CATALOG.md` (생성물) |
| FC (기능 레지스트리) | App PRD §7 기능 목록 |

기존 레포에 0.x 문서가 있으면 지우지 않는다 — 과거 요구·결정의 기록이다. 새 작업은 Intent 로만 하고, 필요하면 Intent 의 Constraints · Decisions 에서 인용한다. 0.x 문서를 갱신하거나 새로 만들지 않는다.
<!-- retired-doc-types:end -->

## 2. 작성 순서

**신규 기능 · 리팩토링**:
1. `/requirement-spec` — 인터뷰로 Intent 를 작성하고 검증·승인한다. 산출물 `docs/{App}/INTENT/{App}-INT-{NNN}.md` (+ 카탈로그).
2. `/forge-init` — 승인된 Intent 로 워크트리·브랜치를 만들고 `in-dev` 로 전이한다.
3. 워크트리에서 개발 세션을 시작해 `/forge-scope` — 슬라이스마다 RED → GREEN → 리뷰 → 커밋, Acceptance 증거로 마감한다.
4. `/branch-review` — 워크트리 브랜치를 리뷰한다.
5. Intent 가 끝나면 상시 문서를 맞춘다 — 기능 목록이 바뀌었으면 App PRD §7 (여러 App 이면 솔루션 PRD §8 도), 코드 규칙이 바뀌었으면 ARCHITECTURE · `.rules/`. 근거로 Intent ID 를 남긴다.

**결정 기록**: 되돌리기 어려운 결정은 그 결정을 실행하는 Intent 의 `Decisions` 에 남긴다 (근거 · 기각 대안 포함). 실행할 작업이 없는 규칙 변경이면 ARCHITECTURE · `.rules/` 본문을 직접 고치고 변경 이력에 근거를 남긴다.

**신규 App 추가**: `/CLAUDE.md` Backend Services Overview 행 추가 (SYSTEM_CODE 확정) → `/CLAUDE.md` 설계 문서 인덱스 App 행 복제 → `docs/{App}/` 생성 → (권장) App PRD · App ARCHITECTURE 작성. 하위 폴더는 미리 만들지 않는다 — `INTENT/` 는 첫 `/requirement-spec` 이 만든다.

## 3. 메타 표 공통 패턴

상시 콘텐츠 문서 상단 보유 (라우터 CLAUDE 제외). Intent 는 자체 메타 표(7행)를 쓴다 — Intent 템플릿 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | (§5 식별자 규약 참조) |
| 버전 | 0.1 (Draft) 등 |
| 작성 가정 | 작성 시 깔린 가정 한 줄 |
| 관련 문서 | 상위 SSOT 인용 (PRD / ARCHITECTURE 등) |

## 4. 변경 이력 표 공통 패턴

메타 표 직후 신설. 상시 콘텐츠 문서에 적용한다. Intent 와 카탈로그는 제외 — Intent 는 상태 전이가 커밋으로 남고, 카탈로그는 생성물이다.

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
| SYSTEM_CODE ≡ APP_CODE ≡ {App} | 영문 대문자 (App 이름) | `LOADER` |
| 솔루션 PRD ID | `{SOLUTION_CODE}-PRD` (NNN 없음 — 단일) | `XLAB-PRD` |
| App PRD ID | `{App}-PRD` | `LOADER-PRD` |
| ARCHITECTURE ID | `{App}-ARCHITECTURE` | `LOADER-ARCHITECTURE` |
| Intent ID | `{App}-INT-{NNN}` (NNN 3자리 0패딩) | `LOADER-INT-001` |
| Intent 카탈로그 ID | `{App}-INT-CATALOG` | `LOADER-INT-CATALOG` |
| Intent 항목 | `D{n}` 결정 · `C{n}` 제약 · `FR-{n}` · `E-{n}` · `X-{n}` · `A-{n}` (Intent 내부 로컬, 1부터) | `FR-3`, `A-2` |
| 기능 ID | `F{NNN}` (App PRD §7 행, App 내부 로컬) | `F001` |
| 기능 ID (cross-app) | `{App}:F{NNN}` | `LOADER:F001` |
| errorCode | SCREAMING_SNAKE | `INVALID_TOKEN` |

SYSTEM_CODE 후보는 [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md) 표를 단일 출처. 신규 App 도입 시 해당 표 행 추가 선행. SOLUTION_CODE 는 `/CLAUDE.md` 제목 line + `docs/ARCHITECTURE.md` 메타 표가 단일 출처.

## 6. placeholder / 빈칸 룰

- placeholder 형식: `{설명}` 중괄호. 실제 값 채우거나 줄 삭제.
- 솔루션 레벨 placeholder: `{SOLUTION_CODE}`, `{프로젝트명}`.
- App 레벨 placeholder: `{App}` (또는 `{SYSTEM_CODE}` / `{APP_CODE}` — 동의어), `{NNN}` (Intent 번호 3자리).
- 빈칸 / "N/A" **금지**. 해당 없으면 **"없음" 명기** (Intent 는 템플릿 규칙대로 `none`).
- 미완성 항목은 "미작성/추후" 명기.
- `_` 또는 `.` 시작 폴더는 기본적으로 SSOT 아님. 단 `docs/.rules/` 는 예외 — 코드 룰 (DDD/OOP/클래스 구조/로깅/Behavioral) SSOT.

## 7. 인용 패턴

상호 참조 시 마크다운 링크 + anchor.

### 7.1 App 폴더 내부 상대 경로 (기준: `docs/{App}/` 내부 파일)

- PRD 절: `[PRD §3]({App}-PRD.md#3-목표)`
- Intent: `[{App}-INT-001](INTENT/{App}-INT-001.md)`
- Intent 결정: `[{App}-INT-001 D2](INTENT/{App}-INT-001.md#decisions)`
- Intent 카탈로그: `[INT-CATALOG]({App}-INT-CATALOG.md)`

### 7.2 솔루션 공통 문서 참조 (기준: `docs/{App}/` 내부 파일 → 상위)

- 솔루션 ARCHITECTURE: `[ARCHITECTURE](../ARCHITECTURE.md)`
- DDD 룰: `[DDD](../.rules/DDD_ARCHITECTURE_RULES.md)`
- DOCUMENT_GUIDE: `[DOCUMENT_GUIDE](../DOCUMENT_GUIDE.md)`
- CLAUDE: `[CLAUDE](../../CLAUDE.md)` (레포 루트)

### 7.3 인용 방향

- Intent → 상시 문서: 허용. Constraints · Decisions 의 근거로 인용한다.
- 상시 문서 → Intent: 근거 표기로만 — App PRD §7 `근거 Intent` 열, 규칙 변경의 근거. Intent 본문을 상시 문서에 복제하지 않는다.
- "관련 문서" 메타 행에는 상위 SSOT 를 인용하고, 하위(디테일)는 본문에서 인용한다.

## 8. 동기화 부담 위치

| 변경 | 갱신 위치 |
|---|---|
| 신규 Intent | `/requirement-spec` 이 `INTENT/` 에 작성 + 카탈로그 재생성 (자동) |
| Intent 상태 전이 | 카탈로그 재생성 — requirement-spec · `/forge-init` · forge-scope 가 자동 수행. 빠뜨리면 `docs_helpers.py check` 가 `INT_CATALOG stale` 로 잡는다 |
| Intent 완료로 기능 목록 변경 | App PRD §7 (+ 여러 App 이면 솔루션 PRD §8) |
| Intent 완료로 cross-cutting 영향 | 위 + 솔루션 PRD §3.1 · 부록 B/D/E (영향 시) |
| 결정으로 코드 규칙 변경 | ARCHITECTURE / `.rules/` 본문 + 변경 이력에 근거 Intent ID |
| 솔루션 PRD ↔ App PRD 동기화 | App PRD §3.1 · §7 변경 시 솔루션 PRD §3.1 · §8 동기화. 신규 errorCode/도메인 entity/Contract DTO 발생 시 솔루션 PRD 부록 B/D/E 등재 선행 |
| 신규 App | `/CLAUDE.md` Backend Services Overview + `/CLAUDE.md` 인덱스 표 + `docs/{App}/` (+ 권장 App PRD · App ARCHITECTURE) + 솔루션 PRD 가 있으면 §7 App 레지스트리 · §11 진입점 행 |
| 새 룰 파일 추가 | `/CLAUDE.md` 인덱스 행 추가 |
| 신규 솔루션 (레포 초기화) | §0 레포 세팅 |

## 9. AI 작업 시나리오 요약

- **레포 세팅 요청** → §0. §0.2 의 만들지 않는 것은 만들지 않는다.
- **신규 기능 · 리팩토링 요청** → §2 흐름. 문서를 손으로 먼저 만들지 않는다 — `/requirement-spec` 이 Intent 를 만든다.
- **결정 기록 요청** → §2 결정 기록.
- **신규 App 추가 요청** → §2 신규 App 추가. Backend Services Overview 행 추가가 모든 다른 작업보다 선행.
- **코드 작성 요청** → 승인된 Intent (개발 세션에서는 `/forge-init` 매니페스트) 를 먼저 읽는다. Part 2 가 범위, Constraints · Decisions · ARCHITECTURE · `.rules/` 가 제약이다. 충돌하면 구현하지 않고 보고한다. Intent 에 없는 요구는 구현하지 않는다. 공통 룰 파일의 4단계 마커 (반드시/허용/금지/절대 금지) 를 준수한다.
- **0.x 문서가 남은 레포에서 작업 요청** → §1.3.
