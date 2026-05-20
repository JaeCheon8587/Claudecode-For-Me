# {App}-PRD — {App명}

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다.
> **본 App 의 product 요구사항** (시점 = 솔루션 내 단일 App 포커스). 솔루션 전체 시야 = [`../PRD.md`](../PRD.md) (있을 시) 또는 [`/CLAUDE.md`](../../CLAUDE.md). 기술 시야 (호스트/런타임/진입점) = [`{App}-ARCHITECTURE.md`]({App}-ARCHITECTURE.md). 기능 정의 SSOT = [`{App}-FC.md`]({App}-FC.md).
> **Single-S/W 솔루션 시** 본 App PRD 가 솔루션 PRD 역할 겸유 가능. 그 경우 § 부록 B/C/D/E 본문을 [`../_templates/PRD-TEMPLATE.md`](../_templates/PRD-TEMPLATE.md) 부록 양식에서 복사 후 본 App 한정으로 유지.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-PRD |
| 버전 | {예: 0.1 (Draft)} |
| 작성 가정 | {본 App 의 솔루션 내 도입 사유 / 본 문서 작성 시 깔린 가정} |
| 관련 문서 | [솔루션 PRD](../PRD.md) (있을 시) · [{App}-FC]({App}-FC.md) · [{App}-ARCHITECTURE]({App}-ARCHITECTURE.md) · [{App}-ADR-CATALOG]({App}-ADR-CATALOG.md) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

---

## 1. 배경
- {솔루션 내 이 App 이 왜 필요한가 — 한 줄 요약}
- {App 도입 배경 / 솔루션 내 위치}

## 2. 문제 정의
- {이 App 이 답하는 핵심 질문 1}
- {핵심 질문 2}

## 3. 목표
- {App 단위 달성 목표 1}
- {목표 2}

### 3.1 릴리즈 범위 (본 App 한정)
> 본 App 의 구현 범위. 솔루션 전체 릴리즈 범위 합산은 [`../PRD.md` §3.1](../PRD.md#31-릴리즈-범위) (있을 시).

| 구분 | 범위 |
|---|---|
| MVP 필수 | {본 App 의 MVP 결과} |
| 이번 릴리즈 포함 | {본 App 의 현 릴리즈 범위} |
| 이번 릴리즈 제외 | {본 App 의 제외 항목. 필요 시 [`{App}-FC.md`]({App}-FC.md) Backlog 등재} |

## 4. 비목표
> 솔루션 비목표는 [`../PRD.md` §4](../PRD.md#4-비목표) 인용 (있을 시). 본 절은 본 App 한정 비목표만.

- {본 App 의 비목표 1}
- {비목표 2 — 향후 확장 후보는 [`{App}-FC.md`]({App}-FC.md) Backlog 등재}

## 5. 사용자 / 이해관계자
> 솔루션 user persona 의 subset 인 경우 [`../PRD.md` §5](../PRD.md#5-사용자--이해관계자) 인용. 본 절은 본 App 의 user 한정.

| 구분 | 역할 | 관심사 |
|---|---|---|
| {사용자 그룹} | {역할 한 줄} | {본 App 사용 시 주요 관심사} |

## 6. 핵심 시나리오 (본 App 내부)
> 본 App 단독 user flow 만 본 절 보유. cross-app 협업 시나리오는 [`{App}-FC.md` § 타 S/W 협력 흐름]({App}-FC.md) 또는 [`../PRD.md` §6](../PRD.md#6-핵심-시나리오) SSOT.

| # | 시나리오 | 기대 결과 |
|---|---|---|
| S1 | {시나리오 이름} | {기대 결과} |

> 기능별 상세 흐름은 [`FRD/{App}-FRD-{NNN}.md`](FRD/) 참조.

## 7. 주요 기능 요약 (본 App 한정)
> 본 표는 [`{App}-FC.md`]({App}-FC.md) § 기능 레지스트리 § 기본 식별·설명 의 roll-up. **FC 가 SSOT**. 솔루션 전체 roll-up = [`../PRD.md` §8](../PRD.md#8-주요-기능-요약-솔루션-전체-roll-up) (있을 시).

| 기능 ID | 기능명 | 한 줄 설명 | 릴리즈 범위 |
|---|---|---|---|
| F001 | {기능명} | {한 줄 설명} | MVP / 이번 릴리즈 / Backlog |

## 8. 비기능 요구사항 (App 특화)
> 솔루션 공통 비기능은 [`../PRD.md` §9](../PRD.md#9-비기능-요구사항-솔루션-공통) 인용 (있을 시). 본 절은 본 App 특화 비기능만 (예: UI 반응시간·App 내부 동시성 가정).

| 분류 | 요구사항 |
|---|---|
| {App 특화 분류} | {본 App 한정 요구사항} |

## 9. 제약사항 (App 특화)
> 솔루션 공통 제약은 [`../PRD.md` §10](../PRD.md#10-제약사항-솔루션-공통) 인용 (있을 시). 본 절은 본 App 특화 제약만. ADR 결정은 [`{App}-ADR-CATALOG`]({App}-ADR-CATALOG.md) 본문 인용.

- {본 App 한정 도메인 제약}
- {ADR 결정 인용 — [`{App}-ADR-{NNN}`](ADR/{App}-ADR-{NNN}.md)}

## 10. Feature Catalog / FRD 진입점
> 본 App 의 FC + 주요 FRD 진입점. 전체 FRD 인덱스는 [`{App}-FC.md` § 문서 연결]({App}-FC.md) SSOT.
> "주요 FRD" 기준: MVP·이번 릴리즈 포함 기능.

| Feature Catalog | 주요 FRD |
|---|---|
| [`{App}-FC`]({App}-FC.md) | [`{App}-FRD-001`](FRD/{App}-FRD-001.md) |

---

## 부록 A — {요구사항 원본 → 본 App PRD 절 매핑}
> 본 App 한정 요구사항 원본 매핑. 솔루션 전체 요구사항 매핑은 [`../PRD.md` 부록 A](../PRD.md#부록-a-----요구사항-원본--본-prd-절-매핑) 위임.

| 원본 절 | 본 App PRD 절 |
|---|---|
| {요구사항 §X} | {App PRD §Y} |

## 부록 B — App 사용 errorCode (subset 인덱스, 선택)
> 솔루션 부록 B (errorCode) = [`../PRD.md` 부록 B](../PRD.md#부록-b--errorcode-카탈로그) **SSOT**. 본 부록은 *본 App 에서 사용·발생시키는* errorCode 의 subset 인덱스. App 특화 errorCode 신규 발생 시 솔루션 부록 B 등재 선행 후 본 표 갱신.
> 부록 D (도메인 모델) / 부록 E (Contract DTO) 는 본 App 에 보유 안 함 — 솔루션 SSOT 인용. 본 부록 미사용 시 절 자체 삭제.

| errorCode | 발생 기능 (`F{NNN}`) | 솔루션 부록 B 위치 |
|---|---|---|
| `{CODE}` | F{NNN} | [부록 B](../PRD.md#부록-b--errorcode-카탈로그) |

## 부록 C — App 한정 상태 머신 (조건부)
> **본 App 이 상태를 소유·전이하는 경우만 보유**. cross-app 상태 (한 entity 가 여러 App 거치며 전이) 는 [`../PRD.md` 부록 C](../PRD.md#부록-c--도메인-상태-머신-cross-app) SSOT. 본 App 한정 상태 머신 없으면 부록 자체 삭제.

**상태 소유**: {App}

```mermaid
stateDiagram-v2
    [*] --> {InitialState}
    {State1} --> {State2}: {전이 트리거 — F{NNN}}
```

**전이 규칙**
- {State1} → {State2}: {조건·금지 사항}
