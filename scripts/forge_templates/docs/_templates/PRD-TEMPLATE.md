# PRD-{SYSTEM_CODE}-{NNN} — {프로젝트명}

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다.
> 작성 규칙은 [DOCUMENT_GUIDE.md](../DOCUMENT_GUIDE.md), 식별자 규약은 [ADR-0008](../ADR.md#adr-0008-문서-식별자명명-규약) 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | PRD-{SYSTEM_CODE}-{NNN} |
| 버전 | {예: 0.1 (Draft)} |
| 작성 가정 | {SYSTEM_CODE 결정 근거 / 본 문서 작성 시 깔린 가정} |
| 관련 문서 | [Feature Catalog](Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md) · [ADR](ADR.md) · [UI_GUIDE](UI_GUIDE.md) · [ARCHITECTURE](ARCHITECTURE.md) |

> 본 문서는 상위 시야의 제품 요구사항 문서이며, 기능별 상세 동작은 [FRD](FRD/) 문서로 위임한다.

---

## 1. 제품 배경
- {왜 이 제품을 만드는가 — 한 줄 요약}
- {배경 사실 / 시장·기술 컨텍스트}

## 2. 문제 정의
- {본 제품이 답하려는 핵심 질문 1}
- {핵심 질문 2}

## 3. 목표
- {달성하려는 목표 1}
- {목표 2}

## 4. 비목표
- {명시적으로 안 만들 것 1}
- {비목표 2 — 향후 확장 후보는 [Feature Catalog Backlog](Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md)에 등재}

## 5. 사용자 / 이해관계자
| 구분 | 역할 | 관심사 |
|---|---|---|
| {사용자 그룹} | {역할 한 줄} | {주요 관심사} |

## 6. 핵심 시나리오
| # | 시나리오 | 기대 결과 |
|---|---|---|
| S1 | {시나리오 이름} | {기대 결과} |

> 상세 흐름은 [UI_GUIDE](UI_GUIDE.md), 기능별 흐름은 [FRD](FRD/) 참조.

## 7. 제품 범위
{시스템 구성 요약. 호스트·서비스·공통 영역 등 분리 구성 명기}

## 8. 주요 기능 요약
| 기능 ID | 기능명 | 한 줄 설명 |
|---|---|---|
| F001 | {기능명} | {설명} |

> 컬럼 전체는 [Feature Catalog](Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md) 참조.

## 9. 비기능 요구사항
| 분류 | 요구사항 |
|---|---|
| 데이터 영속성 | {DB / 메모리 / 캐시 정책} |
| 동시성 | {단일 / 멀티 프로세스 가정} |
| 보안 | {인증 / 권한 / 암호화 정책} |
| 에러 응답 | 표준 포맷(`{ "errorCode": string, "message": string }`). 카탈로그는 [부록 B](#부록-b--errorcode-카탈로그) 참조 |
| 로깅 | {레벨·출력 분리 정책} |
| 응답 시간 | {SLA 또는 "명시 없음"} |

## 10. 제약사항
- {기술 제약 — DDD/레이어 규칙 인용}
- {도메인 제약 — 단일 라인·상태 종착 등}

## 11. Feature Catalog 연결
전체 기능 레지스트리: [FC-{SYSTEM_CODE}-{NNN}](Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md)

| 기능 ID | 관련 FRD |
|---|---|
| F001 | [FRD-F001](FRD/FRD-F001.md) |

---

## 부록 A — {요구사항 원본 → 본 PRD 절 매핑}
> 원본 요구사항(고객 요청서·RFP 등)이 있는 경우 본 PRD 어느 절로 흡수되었는지 매핑한다.

| 원본 절 | 본 PRD 절 |
|---|---|
| {요구사항 §X} | {PRD §Y} |

## 부록 B — errorCode 카탈로그
> 본 부록이 errorCode의 단일 정의 위치. 새 코드 도입 시 본 표에 먼저 등재 후 코드에 반영.

| errorCode | HTTP | 의미 | 발생 기능 |
|---|---|---|---|
| `{CODE}` | {HTTP 상태} | {의미} | {기능 ID 목록} |

응답 본문 공통 형식: `{ "errorCode": <상기 코드>, "message": <설명 문자열> }`.

## 부록 C — 도메인 상태 머신
> 상태 전이가 있는 도메인이면 본 부록에 단일 정의. 없으면 본 부록 삭제.

```mermaid
stateDiagram-v2
    [*] --> {InitialState}
    {State1} --> {State2}: {전이 트리거}
```

**전이 규칙**
- {State1} → {State2}: {조건·금지 사항}

## 부록 D — 도메인 모델
> 본 부록이 핵심 엔티티 속성의 단일 정의 위치. FRD §8/§9는 본 표를 인용.

### {Entity1} 엔티티
| 속성 | 타입 | 제약 | 출처 |
|---|---|---|---|
| `{prop}` | {type} | {제약} | {요구사항 §X 또는 [ADR-NNNN]} |

> **불변식**: {도메인 규칙 한 줄씩}

## 부록 E — 공통 Contract DTO 카탈로그
> 본 부록이 공통 데이터 영역의 DTO 단일 정의 위치. [ADR-{Contract 결정}](ADR.md) 인용.

| DTO | 종류 | 사용 기능 | 주요 필드 |
|---|---|---|---|
| `{DtoName}` | Request / Response | {기능 ID} | {필드 요약} |

> **재사용 원칙**: {OrderResponse 식 응답 재사용 정책 등}
> **직렬화**: {JSON / Protobuf 등 + 시간·숫자 형식}
