# {레이어 모델명, 예: DDD} 아키텍처 및 코드 작성 규칙 ({SOLUTION_NAME})

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 채우거나 해당 줄을 삭제한다. 본 파일은 솔루션의 코드 레이어 규칙 단일 SSOT 역할이며, 충돌 시 본 문서가 우선한다.

| 항목 | 값 |
|---|---|
| 문서 ID | ARCHITECTURE (단일 파일) |
| 버전 | {예: 0.1 (Draft)} |
| SOLUTION_CODE | {예: XLAB} |
| 작성 가정 | {레이어 모델·언어·진입점 호스트 수} |
| 관련 문서 | [PRD](PRD.md) (있을 시) · [DOCUMENT_GUIDE](DOCUMENT_GUIDE.md) · [CLAUDE](../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

## 1. 문서 목적과 범위

### 1.1 목적

이 문서는 AI 코딩 에이전트와 신규 개발자가 `{SOLUTION_NAME}` 솔루션에 신규 코드를 추가할 때 레이어 위반을 재발시키지 않도록 **반드시** 지켜야 하는 단일 규칙 문서이다.

- 신규 코드 작성 기준이며, 기존 위반 파일의 위치는 정당화 근거로 사용하지 않는다.
- 모든 규칙은 **반드시** / **허용** / **금지** / **절대 금지** 중 하나로 판정한다.
- 이 문서만 읽고 신규 클래스 위치를 **반드시** 결정한다.

### 1.2 적용 범위

- 적용 언어: {언어, 예: C# / TypeScript / Kotlin}. 분석 루트: `{소스 루트, 예: Src/}`. 진입점은 {N}개 호스트(§3 참조).

### 1.3 제외 범위

- 빌드/배포/CI/CD 설정은 본 규칙 적용 외이다.
- 테스트 프로젝트(`{테스트 루트, 예: Src/Tests/**}`)는 §4·§5의 4단계 판정과 §6.1 매트릭스 적용 외이며, 별도 규칙(§7.1 Tests 항목)으로 처리한다.

## 2. 솔루션 아키텍처

### 2.1 채택 레이어 매핑

| 표준명 | 솔루션 규약 | 설명 |
|---|---|---|
| Domain | `Domain/**` | 비즈니스 불변식과 도메인 모델 |
| Application | `Application/**` | Use Case와 Port 인터페이스의 중심 레이어 |
| Infrastructure | `Infrastructure/**` | 외부 I/O 구현체와 기술 Adapter |
| Presentation | `App/**` 또는 `{호스트 루트}` | {호스트 종류} 진입점과 서비스 생명주기 조립 |
| Shared/Cross-Cutting | `Shared/**`, `{공통 모듈 루트들}` | 공통 코드와 기술 공통 모듈 |

### 2.2 변형 패턴 (Ports & Adapters)

- Port 인터페이스는 **반드시** `Application/**/Port`에 둔다 (`I*` 인터페이스만).
- Application Contract 폴더(`Application/**/Contract`)는 DTO/Request/Response/Message 계약을 **반드시** 보관한다.
- Domain Contract 폴더는 Aggregate Repository 인터페이스와 도메인 계약만 **허용**한다.
- Infrastructure는 Application Port를 참조해 구현체를 제공하는 것이 **허용**된다.
- Presentation 호스트는 Application·Infrastructure 참조를 DI Composition Root에서만 **허용**한다. Controller가 Infrastructure 구현체를 직접 호출하는 것은 **금지**한다.

## 3. 호스트 책임 분리 — App별 ARCHITECTURE 위임

호스트별 핵심 책임/금지/절대 금지는 각 App 의 `docs/{App}/{App}-ARCHITECTURE.md` 가 SSOT. 본 문서는 솔루션 공통 룰만 보유.

App 코드 후보는 [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md) 표가 단일 출처. 신규 App 도입 시 `/CLAUDE.md` 표 행 추가 + `docs/{App}/{App}-ARCHITECTURE.md` 신규 작성 (`.templates/App/APP-ARCHITECTURE-TEMPLATE.md` 기반).

> **충돌 시 우선순위**: 본 솔루션 ARCHITECTURE 룰 (§2, §4, §5, §6, §7) 이 App ARCHITECTURE 보다 우선. App 은 솔루션 룰 준수 + 호스트 특이 사항만 명시.

## 4. 레이어별 책임

### 4.1 Domain

- **반드시** 둘 것: Entity, ValueObject, AggregateRoot, DomainEvent, DomainService, 도메인 불변식·상태 전이·값 검증·도메인 용어. Aggregate 저장소 계약일 때만 Repository 인터페이스를 `Domain.*.Contracts`에 **허용**.
- **허용**할 것: 같은 Domain 또는 Domain 공통 프로젝트 참조. `Shared/**`, `Constants/**` 자유 참조 **허용**.
- **금지**할 것: Application Service·DTO·Request·Response·Port 인터페이스 **금지**. DB·HTTP·메시지 브로커·WebSocket·Serializer·Logger 구현체 **금지**. 호스트 프레임워크·DI 등록 코드 **금지**.
- **절대 금지**: Application·Infrastructure·Presentation 네임스페이스 `using`/`import`.

> 구체 아티팩트 위치는 [§5 레이어 ↔ 아티팩트 카탈로그](#5-레이어--아티팩트-카탈로그). 레이어 의존 룰은 [§6.1 절대 금지 매트릭스](#61-절대-금지-매트릭스).

### 4.2 Application

- **반드시** 둘 것: Use Case, Application Service, Port 인터페이스, DTO, Request, Response, Message Contract. 외부 시스템 호출은 **반드시** Port로 추상화. 트랜잭션 흐름·메시지 처리 흐름·호스트 독립 상태머신.
- **허용**할 것: Domain 모델·Domain 계약 참조 **허용**. Application 내부 프로젝트 간 참조 **허용**. Shared/Cross-Cutting 참조 **허용**.
- **금지**할 것: 외부 IO 구현체 직접 사용 **금지**. Controller·HostedService 등록 코드 **금지**. 구체 UI 자산 정의·사용 **금지**.
- **절대 금지**: Infrastructure·Presentation 네임스페이스 `using`.

> 구체 아티팩트 위치는 [§5 레이어 ↔ 아티팩트 카탈로그](#5-레이어--아티팩트-카탈로그). 레이어 의존 룰은 [§6.1 절대 금지 매트릭스](#61-절대-금지-매트릭스).

### 4.3 Infrastructure

- **반드시** 둘 것: Repository 구현체, DB Provider, HTTP Client, 메시지 브로커 Adapter, Serializer, Registry 구현체. Application Port 구현체와 외부 시스템 Adapter. 외부 예외 변환·재시도·직렬화·프로토콜 매핑.
- **허용**할 것: Application Port·Contract 참조 **허용**. Domain 모델·Domain 계약 참조 **허용**. Shared/Cross-Cutting 기술 모듈 참조 **허용**.
- **금지**할 것: 도메인 불변식·상태 전이를 구현체에 두는 것 **금지**. Use Case 흐름 결정 **금지**.
- **절대 금지**: Controller·View·구체 UI 자산 참조. Presentation 네임스페이스 `using`.

> 구체 아티팩트 위치는 [§5 레이어 ↔ 아티팩트 카탈로그](#5-레이어--아티팩트-카탈로그). 레이어 의존 룰은 [§6.1 절대 금지 매트릭스](#61-절대-금지-매트릭스).

### 4.4 Presentation

- **반드시** 둘 것: 진입점(`Program`/`main`), Builder, Runner, Controller, HostedService 등록, DI Composition Root. 호스트별 설정 로딩과 서비스 생명주기 시작/종료.
- **허용**할 것: Application 참조 **허용**. Infrastructure 참조는 DI Composition Root와 호스트 조립 코드에서만 **허용**.
- **금지**할 것: Controller에서 Infrastructure 구현체 직접 생성·호출 **금지**. Domain Entity를 외부 API 응답 모델로 직접 노출 **금지** — 응답은 반드시 ViewModel/DTO로 매핑.
- **절대 금지**: 다른 호스트의 프로젝트 직접 참조 (예: 호스트 1이 호스트 2 프로젝트를 참조).

> 구체 아티팩트 위치는 [§5 레이어 ↔ 아티팩트 카탈로그](#5-레이어--아티팩트-카탈로그). 레이어 의존 룰은 [§6.1 절대 금지 매트릭스](#61-절대-금지-매트릭스).

### 4.5 Shared/Cross-Cutting

- **반드시** 둘 것: 공통 상수, 공통 메시지 기반 타입, 공통 데이터 값, 로깅 추상화, 호스트 공통 유틸리티, 통신·인프라 기술 추상화.
- **허용**할 것: Shared/Cross-Cutting 내부 참조 **허용**. {공통 모듈별 허용 규칙 — 예: `Constants/**`은 상수만 / `ServiceModule/**`은 외부 기술 래퍼만}.
- **금지**할 것: Domain 규칙·Application Use Case·Infrastructure Adapter 구현·Presentation 호스트 코드 **금지**. 특정 호스트 전용 정책 **금지**.
- **절대 금지**: Domain·Application·Infrastructure·Presentation 프로젝트 참조.

> 구체 아티팩트 위치는 [§5 레이어 ↔ 아티팩트 카탈로그](#5-레이어--아티팩트-카탈로그). 레이어 의존 룰은 [§6.1 절대 금지 매트릭스](#61-절대-금지-매트릭스).

## 5. 레이어 ↔ 아티팩트 카탈로그

| 아티팩트 | Domain | Application | Infrastructure | Presentation | Shared/Cross-Cutting |
|---|---|---|---|---|---|
| Entity | **허용** | **금지** | **금지** | **금지** | **금지** |
| ValueObject | **허용** | **금지** | **금지** | **금지** | 공통 값 타입만 **허용** |
| AggregateRoot | **허용** | **금지** | **금지** | **금지** | **금지** |
| DomainEvent | **허용** | **금지** | **금지** | **금지** | 공통 메시지 기반 타입만 **허용** |
| DomainService | **허용** | **금지** | **금지** | **금지** | **금지** |
| UseCase | **금지** | **허용** | **금지** | **금지** | **금지** |
| ApplicationService | **금지** | **허용** | **금지** | **금지** | **금지** |
| Port 인터페이스 | Repository 계약만 **허용** | **허용** | **금지** | **금지** | 공통 Port만 **허용** |
| Repository 인터페이스 | Aggregate 계약만 **허용** | 외부 조회 Port만 **허용** | **금지** | **금지** | **금지** |
| Repository 구현체 | **금지** | **금지** | **허용** | **금지** | **금지** |
| DTO/Request/Response | **금지** | **허용** | 외부 시스템 매핑 전용만 **허용** | API 응답 ViewModel 전용만 **허용** | 공통 메시지 DTO만 **허용** |
| Handler | 도메인 이벤트 핸들러만 **허용** | 유스케이스 핸들러만 **허용** | 프로토콜 핸들러만 **허용** | **금지** | 공통 기술 핸들러만 **허용** |
| Controller | **금지** | **금지** | **금지** | **허용** | **금지** |
| Worker/HostedService | **금지** | 구현체 **허용** | 구현체 **허용** | 등록·생명주기만 **허용** | 공통 베이스만 **허용** |
| Config/Options | 도메인 정책 값만 **허용** | 유스케이스 설정만 **허용** | 외부 시스템 설정만 **허용** | 호스트 설정 바인딩만 **허용** | 공통 설정 모델만 **허용** |

## 6. 레이어 참조 방향

- Domain은 **반드시** 안쪽 핵심이다. Application·Infrastructure·Presentation을 **절대 참조 금지**한다.
- Application은 **반드시** Domain과 Port 계약만 조율한다. Infrastructure·Presentation을 **절대 참조 금지**한다.
- Infrastructure는 **반드시** Application Port 또는 Domain 계약을 구현하거나 소비한다. Presentation을 **절대 참조 금지**한다.
- Presentation 호스트는 **반드시** 조립 루트로 동작한다. 비즈니스 규칙을 직접 소유하는 것을 **금지**한다.
- Shared/Cross-Cutting은 **반드시** 공통 기능만 제공한다. Domain/Application/Infrastructure/Presentation을 **절대 참조 금지**한다.

### 6.1 절대 금지 매트릭스

매트릭스에 명시된 **금지**·**절대 금지** 조합만 위반으로 판정한다. **허용** 조합은 별도 제한 없이 자유 참조한다.

| From \ To | Domain | Application | Infrastructure | Presentation | Shared/Cross-Cutting |
|---|---|---|---|---|---|
| Domain | **허용** | **금지** | **금지** | **금지** | **허용** |
| Application | **허용** | **허용** | **금지** | **금지** | **허용** |
| Infrastructure | **허용** | **허용** | **허용** | **금지** | **허용** |
| Presentation | **금지** | **허용** | **허용** | **허용** | **허용** |
| Shared/Cross-Cutting | **금지** | **금지** | **금지** | **금지** | **허용** |

> 도메인이 특정 Cross-Cutting 모듈(예: UI 추상화·통신 추상화)에 의존하지 않아야 한다면 본 절에 예외를 명시하고 **반드시** 영향 App 의 ADR (`docs/{App}/ADR/{App}-ADR-{NNN}.md`) 를 인용한다. ADR 미존재 시 신규 ADR 등재 후 본 절에 인용. 카탈로그 갱신은 `docs/{App}/{App}-ADR-CATALOG.md`.

## 7. 프로젝트 매핑 규칙

### 7.1 폴더 → 레이어 자동 판정 표

| 최상위 폴더 | 레이어 | 네임스페이스 prefix | 비고 |
|---|---|---|---|
| `Domain/**` | Domain | `{SOLUTION_NAMESPACE}.Domain` | |
| `Application/**` | Application | `{SOLUTION_NAMESPACE}.Application` | `**/Port` = `I*` 인터페이스, `**/Contract` = DTO 전용 |
| `Infrastructure/**` | Infrastructure | `{SOLUTION_NAMESPACE}.Infrastructure` | |
| `{호스트 루트 패턴}` | Presentation | `{SOLUTION_NAMESPACE}.{Host}` | Host ∈ {호스트 목록} |
| `Shared/**` | Shared/Cross-Cutting | `{SOLUTION_NAMESPACE}.Shared.*` | |
| {추가 공통 폴더} | Shared/Cross-Cutting | `{SOLUTION_NAMESPACE}.{Module}.*` | {용도 한 줄} |
| `Tests/**` | Tests 루트 | `{SOLUTION_NAMESPACE}.{Layer}.Tests` 또는 `{SOLUTION_NAMESPACE}.Tests.{Scope}` | §4·§5의 4단계 판정 및 §6.1 매트릭스 적용 외. 단 운영 레이어에서 Tests 참조는 **절대 금지**. |

### 7.2 모서리 케이스

폴더 패턴에서 자동 추론되지 않는 항목은 다음 규칙으로 판정한다.

| 패턴 | 분류 | 근거 |
|---|---|---|
| `{호스트 루트}/{SOLUTION_NAMESPACE}.{Host}` | Presentation 단일 진입점 | 호스트당 정확히 1개 진입점 |
| `Application/**/Port` | Application Port 전용 | `I*` 인터페이스만, 구현체 **금지** |
| `Application/**/Contract` | Application Contract 전용 | DTO/Request/Response/Message만, 비즈니스 로직 **금지** |

### 7.3 매핑 재생성

```
{프로젝트 파일 검색 명령, 예: find {소스 루트} -name "*.csproj"}
```

### 7.4 접미사 의미 표

같은 접미사가 레이어별로 다른 책임을 가진다. 신규 파일 명명 시 이 표를 따른다.

| 접미사 | Domain 의미 | Application 의미 | Infrastructure 의미 | Presentation 의미 | Shared 의미 |
|---|---|---|---|---|---|
| `Service` | 도메인 계산 규칙 | Use Case 조율 | 외부 시스템 래퍼 | **금지** | 공통 유틸리티 |
| `Handler` | 도메인 이벤트 처리 | 메시지/Use Case 처리 | 프로토콜 메시지 처리 | **금지** | 공통 기술 처리 |
| `Repository` | 인터페이스만 **허용** | 조회 Port만 **허용** | 구현체만 **허용** | **금지** | **금지** |
| `Dto` | **금지** | 계약 DTO | 외부 시스템 DTO | API View DTO | 공통 메시지 DTO |
| `Controller` | **금지** | **금지** | **금지** | {프레임워크 Controller} | **금지** |
| `Factory` | 도메인 객체 생성 | Use Case 객체 생성 | Adapter 생성 | 호스트 조립 | 공통 객체 생성 |
| `Config`, `Options` | 도메인 정책 값 | Application 설정 | 외부 시스템 설정 | 호스트 설정 | 공통 설정 |
| `Client` | **금지** | 외부 Port 인터페이스만 | 외부 시스템 Client 구현 | **금지** | 공통 기술 Client |

> {도메인별 추가 접미사가 있으면 본 표에 행 추가}.
