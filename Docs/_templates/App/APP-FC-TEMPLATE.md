# {App}-FC — {App명} Feature Catalog

> ⚠ **TEMPLATE** — `{...}` placeholder를 채우거나 해당 줄을 삭제한다.
> 식별자 규약은 [DOCUMENT_GUIDE §5](../DOCUMENT_GUIDE.md#5-식별자-규약) 참조.
> 본 FC 는 단일 App (`{App}`) 의 기능 레지스트리. SYSTEM_CODE SSOT 는 [`/CLAUDE.md` Backend Services Overview](../../CLAUDE.md). 솔루션 전체 시야는 [솔루션 PRD](../PRD.md) (있을 시) 또는 [`/CLAUDE.md`](../../CLAUDE.md).

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-FC |
| 버전 | {예: 0.1 (Draft)} |
| 작성 가정 | {본 카탈로그 작성 시 깔린 가정} |
| 관련 문서 | [{App}-PRD]({App}-PRD.md) · [{App}-ARCHITECTURE]({App}-ARCHITECTURE.md) · [{App}-ADR-CATALOG]({App}-ADR-CATALOG.md) · [FRD 폴더](FRD/) · [솔루션 PRD](../PRD.md) (있을 시) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

> **본 문서는 단일 App (`{App}`) 의 기능 레지스트리이다.** 솔루션 전체 시야는 [솔루션 PRD §11](../PRD.md#11-app-별-prdfcfrd-진입점) (있을 시) 또는 [`/CLAUDE.md` Backend Services Overview](../../CLAUDE.md) 참조. 미작성 컬럼은 빈칸이 아닌 "미작성/추후"로 명기.
> **기능 ID 규약**: `F{NNN}`은 본 App 내에서 unique. 다른 App 의 동일 번호와 별개. 정식 기능은 F001~F099, Backlog는 F101~.

## App 개요
> 본 절은 빠른 이해를 위한 요약이다. 정식 역할·범위 정의는 [{App}-PRD §1·§3]({App}-PRD.md) 와 [{App}-ARCHITECTURE]({App}-ARCHITECTURE.md) 를 기준으로 한다.

| 항목 | 요약 |
|---|---|
| App명 | {App명} |
| 역할 | {본 App 이 솔루션 안에서 담당하는 역할 한 줄} |
| 목적 | {이 App 이 제공해야 하는 핵심 가치 한 줄} |
| 주요 기능 범위 | {본 FC에 등재되는 기능 범위 요약} |
| 범위 밖 | {본 App 이 책임지지 않는 영역. 없으면 "없음"} |

## 기능 레지스트리

### 기본 식별·설명
| 기능 ID | 기능명 | 기능 설명 | 기능 상태 | 구현 상태 | 테스트 상태 | 우선순위 |
|---|---|---|---|---|---|---|
| F001 | {기능명} | {한 줄 설명} | Draft / Ready / In Progress / Done | Not Started / Implementing / Implemented / Blocked | 미작성 / 작성중 / 통과 / 실패 | P0 / P1 / P2 |

> **우선순위 정의**: P0 = MVP 필수 / 출시 차단. P1 = 이번 릴리즈 권장. P2 = Backlog 또는 향후 확장 후보.

> **상태 일관성 규칙**: 아래 표는 기능 상태 / 구현 상태 / 테스트 상태 3축의 허용 조합. 표 밖 조합 사용 시 사유를 본 행 옆 셀에 명기.

| 기능 상태 | 허용 구현 상태 | 허용 테스트 상태 |
|---|---|---|
| Draft | Not Started | 미작성 |
| Ready | Not Started | 미작성 |
| In Progress | Implementing / Blocked | 미작성 / 작성중 |
| Done | Implemented | 통과 |

### 문서 연결
| 기능 ID | 관련 App PRD | 관련 FRD | 관련 API Spec | 관련 UI Spec | 관련 Data Spec |
|---|---|---|---|---|---|
| F001 | [App PRD §{X}]({App}-PRD.md) | [{App}-FRD-001](FRD/{App}-FRD-001.md) | 미작성/추후 | 미작성/추후 | 미작성/추후 |

### 검증·근거·확인
| 기능 ID | 관련 Test Case | 수용 기준 | 요구 근거 | 확인 필요 여부 |
|---|---|---|---|---|
| F001 | [{App}-FRD-001 §18](FRD/{App}-FRD-001.md#18-테스트-관점) | [{App}-FRD-001 §17](FRD/{App}-FRD-001.md#17-수용-기준) | {요구사항 원본 인용} → [{App}-FRD-001](FRD/{App}-FRD-001.md) | 없음 |

### 기능 요구 추적
> 기능별 목적, 사용자 영향, 문서 영향, 완료 기준을 빠르게 확인하기 위한 표. 코드 경로·파일명·구현 방식은 쓰지 않는다.

| 기능 ID | 작업 유형 | 사용자 영향 | 문서 영향 | 완료 기준 |
|---|---|---|---|---|
| F001 | 신규 / 변경 / 버그수정 / 리팩터링 | {사용자에게 보이는 변화 또는 없음} | FC / FRD / ADR / ADR-CATALOG | [{App}-FRD-001 §17](FRD/{App}-FRD-001.md#17-수용-기준) |

### 타 App 협력 흐름
> 본 App 의 기능이 타 App 기능과 협력할 때 등재. cross-cutting 시나리오(예: Client F001 로그인 → APIGW F003 라우팅 → MASTER F005 토큰 발급) 추적용. 협력이 없으면 "본 App 은 외부 App 과의 직접 협력이 없다" 한 줄로 마감.

| 기능 ID | 협력 App | 협력 기능 ID | 협력 형태 |
|---|---|---|---|
| F001 | {App} | F{NNN} | 호출 / 이벤트 / 공유 데이터 |

---

## 별도 문서 미작성 항목 안내
> 본 프로젝트의 초기 작업 범위에서 별도 문서를 만들지 않는 항목을 명시.

- **API Spec**: {각 FRD의 §17에 인라인 / OpenAPI 별도 / 미작성}
- **UI Spec**: {별도 / 미작성}
- **Data Spec**: {[솔루션 PRD 부록 D·E](../PRD.md) (있을 시) 인용 / 별도 / 미작성}
- **Test Case**: {ATDD 단계에서 별도 작성 / 미작성}

---

## 확장 후보 기능 (Backlog)
> 본 절은 향후 확장 후보를 추적한다. F101부터 시작(현재 기능 F001~F099, Backlog F101~).

| 기능 ID | 기능명 | 설명 | 상태 | 우선순위 | 근거 |
|---|---|---|---|---|---|
| F101 | {기능명} | {설명} | Backlog | P1 / P2 | [App PRD §4]({App}-PRD.md#4-비목표), {요구사항 §X} |
