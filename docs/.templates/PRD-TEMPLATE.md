# {SOLUTION_CODE}-PRD — {프로젝트명}

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다.
> **솔루션 단일 PRD** (시스템 전체 시점). 다중 S/W 솔루션 시 채택. per-app 상세는 [`docs/{App}/{App}-PRD.md`]({App}/{App}-PRD.md) SSOT.
> **SYSTEM_CODE SSOT 는 [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md)**. 본 PRD §7 은 BSO 인용 + product 시야 공통 영역만 보유. ID 규약은 [DOCUMENT_GUIDE §5](DOCUMENT_GUIDE.md#5-식별자-규약).

| 항목 | 값 |
|---|---|
| 문서 ID | {SOLUTION_CODE}-PRD |
| 버전 | {예: 0.1 (Draft)} |
| 작성 가정 | {SOLUTION_CODE 결정 근거 / 본 문서 작성 시 깔린 가정} |
| 관련 문서 | [ARCHITECTURE](ARCHITECTURE.md) · [/CLAUDE.md](../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

> 본 문서는 **시스템 전체 시점**의 제품 요구사항. 단일 App 의 상세 product 요구사항은 [`docs/{App}/{App}-PRD.md`]({App}/{App}-PRD.md) 위임. App별 기능 정의 SSOT 는 [`{App}-FC.md`]({App}/{App}-FC.md). 부록 B·D·E 는 솔루션 전체 S/W 를 망라하는 cross-cutting 단일 정의 위치.

---

## 1. 제품 배경
- {왜 이 솔루션을 만드는가 — 한 줄 요약}
- {배경 사실 / 시장·기술 컨텍스트}

## 2. 문제 정의
- {본 솔루션이 답하는 핵심 질문 1 (cross-app)}
- {핵심 질문 2}

## 3. 목표
- {솔루션 단위 달성 목표 1}
- {목표 2}

### 3.1 릴리즈 범위
> 솔루션 전체 구현 범위. 모든 App roll-up. App 별 상세는 [`docs/{App}/{App}-PRD.md` §3.1]({App}/{App}-PRD.md) 참조.

| 구분 | 범위 |
|---|---|
| MVP 필수 | {솔루션 MVP 결과 — cross-app 망라} |
| 이번 릴리즈 포함 | {솔루션 현 릴리즈 범위 — 모든 App 합집합} |
| 이번 릴리즈 제외 | {솔루션 제외 항목. 필요 시 App FC Backlog 등재} |

## 4. 비목표
- {솔루션 비목표 1 — 명시적으로 안 만들 영역}
- {비목표 2 — 향후 확장 후보는 영향 App 의 [`{App}-FC.md`]({App}/{App}-FC.md) Backlog 등재}

## 5. 사용자 / 이해관계자
> 솔루션 전체 user persona. App 한정 user 는 [`{App}-PRD.md` §5]({App}/{App}-PRD.md) 위임.

| 구분 | 역할 | 관심사 |
|---|---|---|
| {사용자 그룹} | {역할 한 줄} | {주요 관심사} |

## 6. 핵심 시나리오 (cross-app)
> App 간 협업 시나리오만 본 절 보유. 단일 App 내 user flow 는 [`{App}-PRD.md` §6]({App}/{App}-PRD.md) SSOT.

| # | 시나리오 | 흐름 (App:기능 ID) | 기대 결과 |
|---|---|---|---|
| S1 | {시나리오 이름} | `{App-A}:F{NNN}` → `{App-B}:F{NNN}` → ... | {기대 결과} |

## 7. 제품 범위

### App 레지스트리
> **SYSTEM_CODE SSOT 는 [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md).** 본 절은 BSO 인용 + 솔루션 product 시야 요약. App 호스트/런타임 등 기술 시야는 [`docs/{App}/{App}-ARCHITECTURE.md`]({App}/{App}-ARCHITECTURE.md) SSOT.

| App | 솔루션 내 product 역할 | App PRD |
|---|---|---|
| {App} | {product 시야 한 줄 — 사용자에게 어떤 가치 제공} | [`{App}-PRD`]({App}/{App}-PRD.md) |

### 공통 영역 (product 시야)
> 솔루션 ARCHITECTURE 의 Shared/Common (technical 시야) 와 별개. 본 절은 사용자에게 노출되는 *공유 기능/데이터 영역* 만 기술.

- {예: 통합 인증 / 공유 카탈로그 / 알림 채널. 없으면 "없음"}

## 8. 주요 기능 요약 (솔루션 전체 roll-up)
> 모든 App `F{NNN}` 망라. 각 App `{App}-FC.md` § 기능 레지스트리 가 SSOT. App PRD §7 은 본 표의 App-한정 subset.

| App | 기능 ID | 기능명 | 한 줄 설명 | 릴리즈 범위 |
|---|---|---|---|---|
| {App} | F001 | {기능명} | {설명} | MVP / 이번 릴리즈 / Backlog |

> 기능 ID disambiguation 표기 (cross-app 인용 시): `{App}:F{NNN}` (예: `LOADER:F001`).

## 9. 비기능 요구사항 (솔루션 공통)
> 모든 App 에 적용되는 공통 비기능. App 특화 비기능은 [`{App}-PRD.md` §8]({App}/{App}-PRD.md) 위임.

| 분류 | 요구사항 |
|---|---|
| 데이터 영속성 | {DB / 메모리 / 캐시 정책} |
| 동시성 | {단일 / 멀티 프로세스 가정} |
| 보안 | {인증 / 권한 / 암호화 정책} |
| 에러 응답 | 표준 포맷(`{ "errorCode": string, "message": string }`). 카탈로그는 [부록 B](#부록-b--errorcode-카탈로그) SSOT |
| 로깅 | {레벨·출력 분리 정책} |
| 응답 시간 | {SLA 또는 "명시 없음"} |

## 10. 제약사항 (솔루션 공통)
> 코드/레이어 제약은 [`DDD_ARCHITECTURE_RULES.md`](.rules/DDD_ARCHITECTURE_RULES.md) / [`OBJECT_ORIENTED_DESIGN_RULES.md`](.rules/OBJECT_ORIENTED_DESIGN_RULES.md) SSOT 인용. 본 절은 product/도메인 제약 + 룰 파일 인용만.
> 솔루션 level architecture 결정은 App ADR 가 SSOT — cross-app 영향 ADR 는 영향 App 중 하나의 [`docs/{App}/ADR/{App}-ADR-{NNN}.md`]({App}/ADR/{App}-ADR-{NNN}.md) 본문 인용.

- {도메인 제약 1 — cross-app 적용}
- {기술 제약 — DDD/레이어 룰 인용}

## 11. App 별 PRD/FC/FRD 진입점
> per-App SSOT 인덱스. 전체 FRD 인덱스는 각 `{App}-FC.md` § 문서 연결 SSOT.

| App | App PRD | App FC | 주요 FRD |
|---|---|---|---|
| {App} | [`{App}-PRD`]({App}/{App}-PRD.md) | [`{App}-FC`]({App}/{App}-FC.md) | [`{App}-FRD-001`]({App}/FRD/{App}-FRD-001.md) |

---

## 부록 A — {요구사항 원본 → 본 PRD 절 매핑}
> 원본 요구사항(고객 요청서·RFP 등) 이 본 솔루션 PRD 어느 절로 흡수되었는지 매핑. App 한정 요구사항 매핑은 [`{App}-PRD.md` 부록 A]({App}/{App}-PRD.md) 위임.

| 원본 절 | 본 PRD 절 |
|---|---|
| {요구사항 §X} | {PRD §Y} |

## 부록 B — errorCode 카탈로그
> **본 부록은 솔루션 PRD SSOT** — 솔루션 전체 S/W 를 망라하는 errorCode 단일 정의 위치. 새 코드 도입 시 본 표 등재 선행 후 코드 반영. App PRD 는 본 표 인용 (App-한정 subset 인덱스 옵션).
> `발생 기능` 컬럼은 `{App}:F{NNN}` 형식.

| errorCode | HTTP | 의미 | 발생 기능 |
|---|---|---|---|
| `{CODE}` | {HTTP 상태} | {의미} | {App}:F{NNN}{, ...} |

응답 본문 공통 형식: `{ "errorCode": <상기 코드>, "message": <설명 문자열> }`.

## 부록 C — 도메인 상태 머신 (cross-app)
> **cross-app 상태 머신 SSOT** — 한 entity 의 상태가 여러 App 거치며 전이되는 경우만 본 부록 보유. 상태 소유 = 단일 App 인 경우 [`{App}-PRD.md` 부록 C]({App}/{App}-PRD.md) 위임. 없으면 본 부록 삭제.

**상태 소유**: {App-A → App-B → ...} (cross-app 전이 흐름)

```mermaid
stateDiagram-v2
    [*] --> {InitialState}
    {State1} --> {State2}: {전이 트리거 — {App}:F{NNN}}
```

**전이 규칙**
- {State1} → {State2}: {조건·금지 사항. cross-app 협력 명시}

## 부록 D — 도메인 모델
> **본 부록은 솔루션 PRD SSOT** — 솔루션 전체 S/W 를 망라하는 핵심 엔티티 속성 단일 정의 위치. App FRD §10/§11 은 본 표 인용. App PRD 는 본 표 인용 (App-한정 entity 변형 발생 시 본 표 갱신).

### {Entity1} 엔티티
| 속성 | 타입 | 제약 | 출처 |
|---|---|---|---|
| `{prop}` | {type} | {제약} | {요구사항 §X 또는 [{App}-ADR-{NNN}]({App}/ADR/{App}-ADR-{NNN}.md)} |

> **불변식**: {도메인 규칙 한 줄씩}

## 부록 E — 공통 Contract DTO 카탈로그
> **본 부록은 솔루션 PRD SSOT** — 솔루션 전체 S/W 를 망라하는 공통 데이터 영역 DTO 단일 정의 위치. App PRD 는 본 표 인용. `사용 기능` 컬럼은 `{App}:F{NNN}` 형식.

| DTO | 종류 | 사용 기능 | 주요 필드 |
|---|---|---|---|
| `{DtoName}` | Request / Response | {App}:F{NNN}{, ...} | {필드 요약} |

> **재사용 원칙**: {OrderResponse 식 응답 재사용 정책 등}
> **직렬화**: {JSON / Protobuf 등 + 시간·숫자 형식}
