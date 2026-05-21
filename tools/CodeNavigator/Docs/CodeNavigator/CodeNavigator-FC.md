# CodeNavigator-FC — CodeNavigator Feature Catalog

> 식별자 규약은 [DOCUMENT_GUIDE §5](../DOCUMENT_GUIDE.md#5-식별자-규약) 참조.
> 본 FC 는 단일 App (`CodeNavigator`) 의 기능 레지스트리. SYSTEM_CODE SSOT 는 [`/CLAUDE.md` Backend Services Overview](../../CLAUDE.md).

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-FC |
| 버전 | 0.3 (Draft) |
| 작성 가정 | AI 코딩 에이전트용 검색 CLI + 개발자용 로컬 관리 UI. MVP 5개 + delete(F006) + 관리 UI(F007) + 수동 메타데이터(F008) 8개 기능 정의. |
| 관련 문서 | [CodeNavigator-PRD](CodeNavigator-PRD.md) · [CodeNavigator-ARCHITECTURE](CodeNavigator-ARCHITECTURE.md) · [CodeNavigator-ADR-CATALOG](CodeNavigator-ADR-CATALOG.md) · [FRD 폴더](FRD/) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.3 | 2026-05-21 | F007 관리 UI·F008 수동 메타데이터 관리 추가 | 정재천 |
| 0.2 | 2026-05-21 | F006 delete 추가 | 정재천 |
| 0.1 | 2026-05-21 | 초안 — MVP 5개 기능 등재 | 정재천 |

> **기능 ID 규약**: `F{NNN}` 은 본 App 내에서 unique. 정식 기능 F001~F099, Backlog F101~.

## App 개요

| 항목 | 요약 |
|---|---|
| App명 | CodeNavigator |
| 역할 | AI 코딩 에이전트용 C# 클래스 시맨틱 인덱서 + 개발자용 로컬 관리 UI |
| 목적 | 자연어 키워드로 C# 클래스 후보를 좁혀 에이전트의 Grep 시간·토큰 절감 |
| 주요 기능 범위 | 클래스 검색(F001) · reindex(F002) · hook 갱신(F003) · status(F004) · AI description(F005) · 파일 단위 삭제(F006) · 로컬 관리 UI(F007) · 수동 메타데이터 관리(F008) |
| 범위 밖 | 외부 공개용 UI, 사용자 계정/권한, C# 외 언어, 실시간 파일 감시 데몬, embedding 벡터 검색 |

## 기능 레지스트리

### 기본 식별·설명
| 기능 ID | 기능명 | 기능 설명 | 기능 상태 | 구현 상태 | 테스트 상태 | 우선순위 |
|---|---|---|---|---|---|---|
| F001 | FTS5 기반 클래스 검색 | 자연어 키워드 → BM25 + tag-hit 점수 기반 클래스 후보 JSON 반환. PascalCase 분해·한국어 bigram 지원. | Done | Implemented | 미작성 | P0 |
| F002 | 전체/변경 파일 reindex | `--full` (전체) / `--changed` (staged .cs) / `--files` (지정) 모드로 클래스 인덱스 갱신. 삭제 파일·고아 클래스 정리 포함. | Done | Implemented | 미작성 | P0 |
| F003 | pre-commit hook 인덱스 갱신 | git pre-commit hook 이 스테이징된 `.cs` 감지 후 `reindex --changed` 실행. AI 실패 시 stale 마킹 + exit 0. | Done | Implemented | 미작성 | P0 |
| F004 | 인덱스 상태 조회 | DB 경로·총 클래스 수·stale 수·최종 인덱싱 시각·stale 파일 목록 출력. | Done | Implemented | 미작성 | P0 |
| F005 | AI description 생성 | Claude CLI subprocess 로 클래스+메서드 description/tags 일괄 생성. 실패 시 stale=1 upsert. | Done | Implemented | 미작성 | P0 |
| F006 | 파일 단위 인덱스 삭제 | `codenav delete --file <path>` 로 특정 파일의 인덱스 row 제거. dry-run 기본 + `--yes` 확인. `--json` 출력 지원. | Done | Implemented | 통과 | P1 |
| F007 | 로컬 관리 UI | `localhost` 웹 UI 에서 대시보드·목록·상세·재인덱싱·stale 필터를 제공. | Ready | Not Started | 미작성 | P1 |
| F008 | 수동 메타데이터 관리 | UI 에서 description/tags 수정, 수동 항목 추가/삭제를 수행. | Ready | Not Started | 미작성 | P1 |

> **우선순위 정의**: P0 = MVP 필수 / 출시 차단. P1 = 이번 릴리즈 권장. P2 = Backlog.

| 기능 상태 | 허용 구현 상태 | 허용 테스트 상태 |
|---|---|---|
| Draft | Not Started | 미작성 |
| Ready | Not Started | 미작성 |
| In Progress | Implementing / Blocked | 미작성 / 작성중 |
| Done | Implemented | 통과 |

### 문서 연결
| 기능 ID | 관련 App PRD | 관련 FRD | 관련 API Spec | 관련 UI Spec | 관련 Data Spec |
|---|---|---|---|---|---|
| F001 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-001](FRD/CodeNavigator-FRD-001.md) | 미작성/추후 | 없음 (AI전용) | 미작성/추후 |
| F002 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-001](FRD/CodeNavigator-FRD-001.md) | 미작성/추후 | 없음 (AI전용) | 미작성/추후 |
| F003 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-002](FRD/CodeNavigator-FRD-002.md) | 없음 | 없음 | 없음 |
| F004 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-001](FRD/CodeNavigator-FRD-001.md) | 미작성/추후 | 없음 | 없음 |
| F005 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-001](FRD/CodeNavigator-FRD-001.md) | 없음 | 없음 | 없음 |
| F006 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-003](FRD/CodeNavigator-FRD-003.md) | 없음 | 없음 | 없음 |
| F007 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-004](FRD/CodeNavigator-FRD-004.md) | 미작성/추후 | 없음 (로컬 관리 UI) | 미작성/추후 |
| F008 | [App PRD §7](CodeNavigator-PRD.md#7-주요-기능-요약) | [CodeNavigator-FRD-004](FRD/CodeNavigator-FRD-004.md) | 미작성/추후 | 없음 (로컬 관리 UI) | 미작성/추후 |

### 검증·근거·확인
| 기능 ID | 관련 Test Case | 수용 기준 | 요구 근거 | 확인 필요 여부 |
|---|---|---|---|---|
| F001 | [FRD-001 §18](FRD/CodeNavigator-FRD-001.md#18-테스트-관점) | [FRD-001 §17](FRD/CodeNavigator-FRD-001.md#17-수용-기준) | 에이전트 Grep 시간 절감 요구 | 없음 |
| F002 | 미작성 | 미작성 | 인덱스 최신성 유지 요구 | 없음 |
| F003 | [FRD-002 §18](FRD/CodeNavigator-FRD-002.md#18-테스트-관점) | [FRD-002 §17](FRD/CodeNavigator-FRD-002.md#17-수용-기준) | commit 시 자동 갱신 요구 | 없음 |
| F004 | 미작성 | 미작성 | 운영 가시성 요구 | 없음 |
| F005 | 미작성 | 미작성 | AI description 자동 생성 요구 | 없음 |
| F007 | [FRD-004 §18](FRD/CodeNavigator-FRD-004.md#18-테스트-관점) | [FRD-004 §17](FRD/CodeNavigator-FRD-004.md#17-수용-기준) | 로컬에서 인덱스를 확인/운영할 수단 필요 | 없음 |
| F008 | [FRD-004 §18](FRD/CodeNavigator-FRD-004.md#18-테스트-관점) | [FRD-004 §17](FRD/CodeNavigator-FRD-004.md#17-수용-기준) | description/tags 수동 보정 및 수동 항목 관리 요구 | 없음 |

### 기능 요구 추적

| 기능 ID | 작업 유형 | 사용자 영향 | 문서 영향 | 완료 기준 |
|---|---|---|---|---|
| F001 | 신규 | `codenav search` JSON 반환 정확성 | FC / FRD-001 / ADR-001 / ADR-002 | FRD-001 §17 충족 |
| F002 | 신규 | `codenav reindex` 후 stale=0 정상 클래스 검색 가능 | FC / FRD-001 | FRD-001 §17 충족 |
| F003 | 신규 | commit 시 hook 자동 실행, AI 실패해도 commit 차단 없음 | FC / FRD-002 | FRD-002 §17 충족 |
| F004 | 신규 | `codenav status` 로 stale 파일 확인 가능 | FC | stale 파일 목록 정상 노출 |
| F005 | 신규 | description/tags 자동 채워짐 | FC / FRD-001 | Claude CLI 호출 성공 시 stale=0 |
| F006 | 신규 | `codenav delete --file` 로 파일 row 명시 삭제 가능 | FC / FRD-003 | dry-run 기본 동작 + `--yes` 실제 삭제 확인 |
| F007 | 신규 | 브라우저로 인덱스 상태/목록/상세/재인덱싱 확인 가능 | FC / FRD-004 | `localhost` UI 에서 핵심 운영 동선 수행 가능 |
| F008 | 신규 | description/tags 수동 수정 및 수동 항목 추가/삭제 가능 | FC / FRD-004 | 저장 후 검색/상세 결과 즉시 반영 |

### 타 App 협력 흐름

본 App 은 외부 App 과의 직접 협력이 없다. Claude Code CLI 는 description 생성 목적의 subprocess 호출이며, 구조적 협력 흐름이 아니다.

---

## 별도 문서 미작성 항목 안내

- **API Spec**: Python CLI stdin/stdout 인터페이스. 별도 OpenAPI 없음.
- **UI Spec**: 별도 문서 없음. 요구는 `CodeNavigator-FRD-004` 가 SSOT.
- **Data Spec**: SQLite 스키마는 코드(`src/codenav/store.py`)가 SSOT. 별도 문서 없음.
- **Test Case**: 미작성 (Step 4 예정).

---

## 확장 후보 기능 (Backlog)

| 기능 ID | 기능명 | 설명 | 상태 | 우선순위 | 근거 |
|---|---|---|---|---|---|
| F101 | embedding rerank | BM25 1차 후보를 embedding 유사도로 재정렬 | Backlog | P2 | [App PRD §4](CodeNavigator-PRD.md#4-비목표) |
| F102 | Roslyn 파서 | regex 파서 대체 — 정확한 C# AST 기반 파싱 | Backlog | P1 | 파서 오탐 개선 |
| F103 | 다국어 지원 | C# 외 Python/TypeScript 등 추가 | Backlog | P2 | [App PRD §4](CodeNavigator-PRD.md#4-비목표) |
| F104 | API 직접 호출 | Claude CLI subprocess 대신 Anthropic API 직접 호출 | Backlog | P1 | subprocess 의존 제거 |
