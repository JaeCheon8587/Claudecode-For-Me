# 프로젝트: {프로젝트명} ({SOLUTION_CODE})

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다. 본 파일은 레포 루트(`/CLAUDE.md`)에 배치한다. 부트스트랩 절차는 § 최초 부트스트랩 참조.

> {프로젝트 한 줄 요약 — 무엇을 하는 시스템인가}. **모든 설계·결정·기능 명세는 아래 문서들이 단일 진실 공급원(SSOT)**. 코드 작성 전 관련 문서를 직접 읽어 최신 정합성을 확보한다.

## 용어 정의

- **SOLUTION_CODE**: 솔루션(레포 전체) 식별자. 예: `XLAB`. 솔루션 공통 문서 (`ARCHITECTURE.md` 등) 에서 사용.
- **SYSTEM_CODE** ≡ **APP_CODE** ≡ **{App}**: App(S/W 단위) 식별자. 동일 개념의 3개 별칭. 본 파일의 § Backend Services Overview 표가 단일 출처(SSOT). 예: `LOADER`. App별 문서 ID 패턴 `{SYSTEM_CODE}-PRD`, `{SYSTEM_CODE}-FC`, `{SYSTEM_CODE}-FRD-{NNN}`, `{SYSTEM_CODE}-TASK-{NNN}`, `{SYSTEM_CODE}-ADR-{NNN}` 등에 사용. (RFD 양식은 DOCUMENT_GUIDE v0.7 폐기 — 리팩토링은 TASK 작업 유형 = `refactor`.)

상세 식별자 규약은 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) §5 참조.

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

## 설계 문서 인덱스

| 영역 | 경로 | 역할 |
|---|---|---|
| **AI 진입점 (본 파일)** | `/CLAUDE.md` | SOLUTION_CODE / SYSTEM_CODE SSOT · Backend Services Overview · 라우터 |
| **문서 작성 룰** | [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) | 문서 작성 SSOT — 식별자/메타/변경 이력/SSOT 인용 패턴/AI 작업 시나리오 |
| **솔루션 ARCHITECTURE** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 솔루션 공통 룰 (레이어 모델·참조 매트릭스·폴더→레이어 매핑·접미사) |
| **(선택) 솔루션 PRD** | [`docs/PRD.md`](docs/PRD.md) | 솔루션 단일 PRD (다중 S/W 통합 시). per-app PRD 만 사용 시 미배치 — 해당 행 삭제 |
| **App: {SYSTEM_CODE}** | [`docs/{SYSTEM_CODE}/`](docs/{SYSTEM_CODE}/) | App별 PRD/FC/ARCHITECTURE/FRD/TASK/ADR/ADR-CATALOG SSOT 폴더 |
| **빈 템플릿 (보존)** | [`docs/.templates/`](docs/.templates/) | Active 11 종 양식 + 가이드 원본. Legacy 양식은 호환 확인용으로만 보존 |
| {Forge/CI 자동화} | {경로 또는 "해당 없음"} | {도구 역할 한 줄} |

App 다수 시 `App: {SYSTEM_CODE}` 행 복제. 폴더 구조 상세는 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) §1.

### `docs/.templates/` 구성 (Active 양식 11 + 가이드)

| 위치 | 양식 | 용도 |
|---|---|---|
| `.templates/CLAUDE-TEMPLATE.md` | 본 파일 | `/CLAUDE.md` 부트스트랩 |
| `.templates/ARCHITECTURE-TEMPLATE.md` | 솔루션 ARCHITECTURE | `docs/ARCHITECTURE.md` 부트스트랩 |
| `.templates/PRD-TEMPLATE.md` | 솔루션 단일 PRD (선택) | `docs/PRD.md` 부트스트랩 (per-app PRD 만 쓰면 미사용) |
| `.templates/App/APP-PRD-TEMPLATE.md` | App PRD | `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-PRD.md` |
| `.templates/App/APP-FC-TEMPLATE.md` | App Feature Catalog | `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-FC.md` |
| `.templates/App/APP-ARCHITECTURE-TEMPLATE.md` | App ARCHITECTURE | `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ARCHITECTURE.md` |
| `.templates/App/APP-ADR-CATALOG-TEMPLATE.md` | App ADR Catalog | `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ADR-CATALOG.md` |
| `.templates/App/ADR/APP-ADR-001-TEMPLATE.md` | App ADR 본문 (단일 ADR 1건 base) | `docs/{SYSTEM_CODE}/ADR/{SYSTEM_CODE}-ADR-{NNN}.md` |
| `.templates/App/FRD/APP-FRD-001-TEMPLATE.md` | App FRD 본문 (기능 요구 문서 1건 base, 코드 상세 금지) | `docs/{SYSTEM_CODE}/FRD/{SYSTEM_CODE}-FRD-{NNN}.md` |
| `.templates/App/TASK/APP-TASK-001-TEMPLATE.md` | App TASK 본문 (AI 실행용 휘발성 작업 지시서 base. 작업 유형 = feature / refactor / maintenance / migration / setup / investigation. RFD 흡수) | `docs/{SYSTEM_CODE}/TASK/{SYSTEM_CODE}-TASK-{NNN}.md` |
| `.templates/DOCUMENT_GUIDE.md` | 문서 작성 가이드 | `docs/` 루트로 그대로 복사 (가이드 SSOT) |

Redirect/Legacy 양식 (`ADR-TEMPLATE.md`, `FC-TEMPLATE.md`, `FRD-TEMPLATE.md`, `README-TEMPLATE.md`, `UI_GUIDE-TEMPLATE.md`) 은 0.2 이전 전역 문서 구조 이식 확인용이다. 신규 문서 작성에는 위 Active 양식만 사용한다.

ADR 명칭은 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) 0.3 기준이다. 부트스트랩/신규 작성 시 템플릿 파일명, 결과 파일명, 문서 ID 모두 `ADR` 를 사용한다.

## Backend Services Overview

본 솔루션의 App 레지스트리. **SYSTEM_CODE 단일 출처(SSOT)**. 신규 App 도입 시 본 표 행 추가가 모든 다른 작업(PRD/FC/FRD/TASK/ADR 작성) 보다 선행. App 다수 시 행 복제.

| SYSTEM_CODE | 한 줄 설명 | 호스트 종류 | TFM/런타임 | 폴더 |
|---|---|---|---|---|
| {SYSTEM_CODE} | {App 역할 1줄} | {WPF / .NET Worker / ASP.NET Web API / etc.} | {예: net6.0} | [`docs/{SYSTEM_CODE}/`](docs/{SYSTEM_CODE}/) |

## 진입 순서

- 신규 작성자/AI 는 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) 를 먼저 읽는다 (작성 룰·식별자·SSOT 인용 패턴).
- 코드 작성 전 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 절대 금지 매트릭스 확인.
- **신규 기능 작성 흐름** ([DOCUMENT_GUIDE §2](docs/DOCUMENT_GUIDE.md#2-작성-순서) 준수):
  1. `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-PRD.md` §3.1·§7 갱신
  2. `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-FC.md` 5축 표 행 추가
  3. `docs/{SYSTEM_CODE}/FRD/{SYSTEM_CODE}-FRD-{NNN}.md` 신규 (`.templates/App/FRD/APP-FRD-001-TEMPLATE.md` 복사·placeholder 채움. 코드 상세 금지)
  4. 필요 시 `docs/{SYSTEM_CODE}/ADR/{SYSTEM_CODE}-ADR-{NNN}.md` 등재 (`.templates/App/ADR/APP-ADR-001-TEMPLATE.md` 복사) + `{SYSTEM_CODE}-ADR-CATALOG.md` 동기화
  5. 구현 착수 전 최신 코드 기준으로 세부 설계 판단
- **AI 실행용 작업 지시서 (TASK) 작성 흐름** — 모든 코드 작업 (feature / refactor / maintenance / migration / setup / investigation) 통합:
  1. (사전) 영향 영구 SSOT (PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE) 를 작성자가 직접 갱신
  2. `docs/{SYSTEM_CODE}/TASK/{SYSTEM_CODE}-TASK-{NNN}.md` 신규 (`.templates/App/TASK/APP-TASK-001-TEMPLATE.md` 복사) — 휘발성 + self-contained. 외부 SSOT 마크다운 링크 인용 금지 (양방향)
  3. TASK §6 영향 SSOT 표에 갱신 상태 = "완료" 텍스트로 선언
  4. TASK §12 컨텍스트 임베드 — AI 코드 실행에 필요한 외부 계약·데이터 구조·정책·코드 경로를 본문에 임베드
  5. AI 에게 TASK 던져 §8 실행. AI 는 코드만 변경
  6. 완료 후 TASK 파일 삭제 가능
- ~~리팩토링 계획 작성 흐름~~ — **DEPRECATED (v0.7)**. RFD 폐기. 리팩토링도 위 TASK 흐름 (작업 유형 = `refactor`).
- **신규 App 추가**:
  1. 본 파일 § Backend Services Overview 표 행 추가 (SYSTEM_CODE 확정)
  2. 본 파일 § 설계 문서 인덱스 표에 `App: {SYSTEM_CODE}` 행 복제·추가
  3. `docs/{SYSTEM_CODE}/` 폴더 생성 + 하위 `FRD/`, `ADR/`, `TASK/` 서브폴더 생성 (RFD 폐기 — v0.7)
  4. `.templates/App/` 의 4 종 직접 양식 복사·rename:
     - `APP-PRD-TEMPLATE.md` → `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-PRD.md`
     - `APP-FC-TEMPLATE.md` → `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-FC.md`
     - `APP-ARCHITECTURE-TEMPLATE.md` → `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ARCHITECTURE.md`
     - `APP-ADR-CATALOG-TEMPLATE.md` → `docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ADR-CATALOG.md`
  5. 첫 ADR/FRD/TASK 작성 시 `.templates/App/ADR/`, `.templates/App/FRD/`, `.templates/App/TASK/` 서브폴더 양식 사용 (RFD 폐기).
  6. 솔루션 공통 양식 (`.templates/PRD-TEMPLATE.md`, `.templates/ARCHITECTURE-TEMPLATE.md`) 은 신규 App 시 사용 안 함.
- **신규 ADR 등재**: `.templates/App/ADR/APP-ADR-001-TEMPLATE.md` 복사 → `docs/{SYSTEM_CODE}/ADR/{SYSTEM_CODE}-ADR-{NNN}.md` → `{SYSTEM_CODE}-ADR-CATALOG.md` Proposed/Accepted 행 추가 → 영향 PRD/FC/FRD 본문에 ADR 인용 (TASK 인용 X — v0.7 룰).

## 최초 부트스트랩 (template repo 도입 1회만)

`docs/.templates/` 양식을 deploy 위치로 promotion 하는 1회성 절차. 본 절차 완료 후 위 인덱스 표 경로가 모두 유효해진다.

1. `docs/.templates/CLAUDE-TEMPLATE.md` → `/CLAUDE.md` 로 복사 (본 파일). placeholder 채움. SOLUTION_CODE 확정.
2. `docs/.templates/DOCUMENT_GUIDE.md` → `docs/` 루트로 복사 (그대로 SSOT).
3. `docs/.templates/ARCHITECTURE-TEMPLATE.md` → `docs/ARCHITECTURE.md` 로 복사·rename. SOLUTION_CODE 등 placeholder 채움.
4. (선택) `docs/.templates/PRD-TEMPLATE.md` 는 솔루션 단일 PRD 가 필요한 경우에만 `docs/PRD.md` 로 복사. per-app PRD 만 사용 시 미복사.
5. 첫 App 도입은 위 § 진입 순서 "신규 App 추가" 절차 수행.
6. `docs/.templates/` 폴더는 **원본 보존** — 추후 신규 App/ADR/FRD/TASK 추가 시 재참조.

## 절대 변경 금지

- `docs/.templates/**` — 원본 양식. 사용자 승인 전 수정 금지 (신규 App/ADR/FRD/TASK 부트스트랩 시 재참조).
- `docs/DOCUMENT_GUIDE.md`, `docs/ARCHITECTURE.md` — 가이드 SSOT. 사용자 승인 전 수정 금지.
- `/CLAUDE.md`(본 파일), `MEMORY.md` — 사용자 승인 전 수정 금지.
- {`README.md`, CI 설정, Forge 도구 등 도메인별 보존 항목}.
