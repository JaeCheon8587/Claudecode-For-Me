# {App}-ARCHITECTURE — {App명} 호스트 아키텍처

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다.
> App별 ARCHITECTURE. 솔루션 공통 룰은 [솔루션 ARCHITECTURE](../ARCHITECTURE.md) SSOT 우선. 본 문서는 호스트 특이 사항만 보유.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-ARCHITECTURE |
| 버전 | {예: 0.1 (Draft)} |
| App 코드 | {App} |
| 작성 가정 | 솔루션 공통 룰 ([../ARCHITECTURE.md](../ARCHITECTURE.md)) 준수. 본 문서는 App 호스트 특이 사항만 |
| 관련 문서 | [솔루션 ARCHITECTURE](../ARCHITECTURE.md) · [{App}-PRD]({App}-PRD.md) · [{App}-FC]({App}-FC.md) · [{App}-ADR-CATALOG]({App}-ADR-CATALOG.md) · [FRD 폴더](FRD/) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

## 1. App 개요

| 항목 | 값 |
|---|---|
| App 코드 | {App} |
| 한 줄 설명 | {App 역할 1줄} |
| TFM/런타임 | {예: net6.0 / .NET Worker / ASP.NET Web API / WPF} |
| 진입점 경로 | `Src/{App}/.../Program.cs` 또는 {실제 진입점 경로} |
| 호스트 종류 | {WPF / .NET Worker / ASP.NET / etc.} |

## 2. 핵심 책임 (4단계 마커)

- **반드시** {핵심 책임 1}.
- **반드시** {핵심 책임 2}.
- **허용** {외부 IO 통신 / 다른 책임}.
- **금지** {도메인 규칙·다른 App 무관 기능}.
- **절대 금지** {다른 App 프로젝트 직접 참조}.

## 3. 외부 IO Adapter 위치 정책

- {Adapter 위치. 예: DB Adapter 는 Infrastructure 만 / HTTP Client 는 Application Port + Infrastructure 구현체}.
- {외부 의존 별 위치 룰. 예: Kafka 발행 = Infrastructure / Redis 조회 = Application Port}.

## 4. App 특이 도메인/패턴 룰 (있을 때만)

- {예: 본 App 은 stateless / 메시지 발행만 / 외부 호출 안 함}.
- {특이 상태 머신·생명주기 룰. "없음" 가능}.

## 5. 솔루션 SSOT 인용

본 App 작업 시 솔루션 공통 룰 **반드시** 준수:
- [§2 채택 레이어 매핑](../ARCHITECTURE.md#2-솔루션-아키텍처)
- [§4 레이어별 책임](../ARCHITECTURE.md#4-레이어별-책임)
- [§5 카탈로그 매트릭스](../ARCHITECTURE.md#5-레이어--아티팩트-카탈로그)
- [§6.1 절대 금지 매트릭스](../ARCHITECTURE.md#61-절대-금지-매트릭스)
- [§7.1 폴더 → 레이어 매핑](../ARCHITECTURE.md#71-폴더--레이어-자동-판정-표)

솔루션 룰과 본 App 룰 충돌 시 **솔루션 ARCHITECTURE 우선**.
