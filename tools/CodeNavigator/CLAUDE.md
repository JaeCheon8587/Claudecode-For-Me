# 프로젝트: CodeNavigator (CodeNavigator)

> AI 코딩 에이전트가 C# 코드베이스에서 클래스를 자연어 키워드로 빠르게 찾을 수 있도록 SQLite FTS5 기반 시맨틱 인덱스를 제공하는 Python CLI 도구. **모든 설계·결정·기능 명세는 아래 문서들이 단일 진실 공급원(SSOT)**. 코드 작성 전 관련 문서를 직접 읽어 최신 정합성을 확보한다.

## 용어 정의

- **SOLUTION_CODE**: 솔루션(레포 전체) 식별자. `CodeNavigator`.
- **SYSTEM_CODE** ≡ **APP_CODE** ≡ **App**: App(S/W 단위) 식별자. `CodeNavigator`. App별 문서 ID 패턴 `CodeNavigator-PRD`, `CodeNavigator-FC`, `CodeNavigator-FRD-{NNN}`, `CodeNavigator-TASK-{NNN}`, `CodeNavigator-ADR-{NNN}` 에 사용.

상세 식별자 규약은 [`Docs/DOCUMENT_GUIDE.md`](Docs/DOCUMENT_GUIDE.md) §5 참조.

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

## 설계 문서 인덱스

| 영역 | 경로 | 역할 |
|---|---|---|
| **AI 진입점 (본 파일)** | `/CLAUDE.md` | SOLUTION_CODE / SYSTEM_CODE SSOT · Backend Services Overview · 라우터 |
| **문서 작성 룰** | [`Docs/DOCUMENT_GUIDE.md`](Docs/DOCUMENT_GUIDE.md) | 문서 작성 SSOT — 식별자/메타/변경 이력/SSOT 인용 패턴/AI 작업 시나리오 |
| **행동 지침** | [`Docs/BEHAVIORAL_GUIDELINES_RULES.md`](Docs/BEHAVIORAL_GUIDELINES_RULES.md) | LLM coding 행동 가이드 |
| **App: CodeNavigator** | [`Docs/CodeNavigator/`](Docs/CodeNavigator/) | App PRD/FC/ARCHITECTURE/FRD/TASK/ADR/ADR-CATALOG SSOT 폴더 |
| **빈 템플릿 (보존)** | [`Docs/_templates/`](Docs/_templates/) | Active 11 종 양식 + 4 종 룰/가이드 원본. Legacy 양식은 호환 확인용으로만 보존 |

단일 App 레포이므로 솔루션 PRD / 솔루션 ARCHITECTURE 는 미사용. App PRD([`Docs/CodeNavigator/CodeNavigator-PRD.md`](Docs/CodeNavigator/CodeNavigator-PRD.md)) 가 전체 PRD 역할 겸유.

### `Docs/_templates/` 구성 (Active 양식 11 + 룰/가이드 4)

| 위치 | 양식 | 용도 |
|---|---|---|
| `_templates/CLAUDE-TEMPLATE.md` | 본 파일 | `/CLAUDE.md` 부트스트랩 |
| `_templates/ARCHITECTURE-TEMPLATE.md` | 솔루션 ARCHITECTURE | `Docs/ARCHITECTURE.md` 부트스트랩 |
| `_templates/PRD-TEMPLATE.md` | 솔루션 단일 PRD (선택) | `Docs/PRD.md` 부트스트랩 (per-app PRD 만 쓰면 미사용) |
| `_templates/App/APP-PRD-TEMPLATE.md` | App PRD | `Docs/{SYSTEM_CODE}/{SYSTEM_CODE}-PRD.md` |
| `_templates/App/APP-FC-TEMPLATE.md` | App Feature Catalog | `Docs/{SYSTEM_CODE}/{SYSTEM_CODE}-FC.md` |
| `_templates/App/APP-ARCHITECTURE-TEMPLATE.md` | App ARCHITECTURE | `Docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ARCHITECTURE.md` |
| `_templates/App/APP-ADR-CATALOG-TEMPLATE.md` | App ADR Catalog | `Docs/{SYSTEM_CODE}/{SYSTEM_CODE}-ADR-CATALOG.md` |
| `_templates/App/ADR/APP-ADR-001-TEMPLATE.md` | App ADR 본문 | `Docs/{SYSTEM_CODE}/ADR/{SYSTEM_CODE}-ADR-{NNN}.md` |
| `_templates/App/FRD/APP-FRD-001-TEMPLATE.md` | App FRD 본문 | `Docs/{SYSTEM_CODE}/FRD/{SYSTEM_CODE}-FRD-{NNN}.md` |
| `_templates/App/TASK/APP-TASK-001-TEMPLATE.md` | App TASK 본문 | `Docs/{SYSTEM_CODE}/TASK/{SYSTEM_CODE}-TASK-{NNN}.md` |
| `_templates/{DOCUMENT_GUIDE,DDD_ARCHITECTURE_RULES,OBJECT_ORIENTED_DESIGN_RULES,BEHAVIORAL_GUIDELINES_RULES}.md` | 룰/가이드 4 종 | `Docs/` 루트로 그대로 복사 (룰 SSOT) |

ADR 명칭은 [`Docs/DOCUMENT_GUIDE.md`](Docs/DOCUMENT_GUIDE.md) 0.3 기준이다.

## Backend Services Overview

본 솔루션의 App 레지스트리. **SYSTEM_CODE 단일 출처(SSOT)**.

| SYSTEM_CODE | 한 줄 설명 | 호스트 종류 | TFM/런타임 | 폴더 |
|---|---|---|---|---|
| CodeNavigator | C# 클래스 시맨틱 인덱스 검색·갱신 Python CLI | Python CLI | Python 3.11+ | [`Docs/CodeNavigator/`](Docs/CodeNavigator/) |

## 진입 순서

- 신규 작성자/AI 는 [`Docs/DOCUMENT_GUIDE.md`](Docs/DOCUMENT_GUIDE.md) 를 먼저 읽는다.
- **신규 기능 작성 흐름** ([DOCUMENT_GUIDE §2](Docs/DOCUMENT_GUIDE.md#2-작성-순서) 준수):
  1. `Docs/CodeNavigator/CodeNavigator-PRD.md` §3.1·§7 갱신
  2. `Docs/CodeNavigator/CodeNavigator-FC.md` 5축 표 행 추가
  3. `Docs/CodeNavigator/FRD/CodeNavigator-FRD-{NNN}.md` 신규 (`_templates/App/FRD/APP-FRD-001-TEMPLATE.md` 복사·placeholder 채움. 코드 상세 금지)
  4. 필요 시 `Docs/CodeNavigator/ADR/CodeNavigator-ADR-{NNN}.md` 등재 + `CodeNavigator-ADR-CATALOG.md` 동기화
  5. 구현 착수 전 최신 코드 기준으로 세부 설계 판단
- **AI 실행용 작업 지시서 (TASK) 작성 흐름** — 모든 코드 작업 (feature / refactor / maintenance / migration / setup / investigation) 통합:
  1. (사전) 영향 영구 SSOT (PRD/FC/FRD/ADR) 를 작성자가 직접 갱신
  2. `Docs/CodeNavigator/TASK/CodeNavigator-TASK-{NNN}.md` 신규 — 휘발성 + self-contained
  3. AI 에게 TASK 던져 구현. AI 는 코드만 변경
  4. 완료 후 TASK 파일 삭제 가능
- **신규 ADR 등재**: `_templates/App/ADR/APP-ADR-001-TEMPLATE.md` 복사 → `Docs/CodeNavigator/ADR/CodeNavigator-ADR-{NNN}.md` → `CodeNavigator-ADR-CATALOG.md` Proposed/Accepted 행 추가 → 영향 PRD/FC/FRD 본문에 ADR 인용

## 행동 지침

@Docs/BEHAVIORAL_GUIDELINES_RULES.md

## 절대 변경 금지

- `Docs/_templates/**` — 원본 양식. 사용자 승인 전 수정 금지.
- `Docs/DOCUMENT_GUIDE.md`, `Docs/DDD_ARCHITECTURE_RULES.md`, `Docs/OBJECT_ORIENTED_DESIGN_RULES.md`, `Docs/BEHAVIORAL_GUIDELINES_RULES.md` — 룰/가이드 SSOT. 사용자 승인 전 수정 금지.
- `/CLAUDE.md`(본 파일) — 사용자 승인 전 수정 금지.
- `pyproject.toml`, `.githooks/`, `install-hook.*` — 패키지 진입점·훅 설치 스크립트. 사용자 승인 전 수정 금지.
