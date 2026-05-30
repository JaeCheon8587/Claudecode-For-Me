# DDD 아키텍처 및 코드 작성 규칙

## 1. 문서 목적과 범위

### 1.1 목적

이 문서는 AI 코딩 에이전트와 신규 개발자가 `Mirero.PCC.XLab` 솔루션에 신규 C# 코드를 추가할 때 레이어 위반을 재발시키지 않도록 **반드시** 지켜야 하는 단일 규칙 문서이다.

- 신규 코드 작성 기준이며, 기존 위반 파일의 위치는 정당화 근거로 사용하지 않는다.
- 모든 규칙은 **반드시** / **허용** / **금지** / **절대 금지** 중 하나로 판정한다.
- 이 문서만 읽고 신규 클래스 위치를 **반드시** 결정한다.

### 1.2 적용 범위

- 적용 언어: C#. 분석 루트: `Src/Mirero.PCC.XLab`. 진입점은 4개 호스트 (§3 참조).

### 1.3 제외 범위

- C++ 프로젝트(`.vcxproj`, `.vcproj`), `UIModule` 관련, 클라이언트 프로젝트(`App/Client`, `Client`, `WPF`, `WinForm`, `Desktop`, UI 호스트), 테스트 프로젝트(`z_Test` 중 4 호스트 그래프 미도달분), 빌드/배포/CI/CD 설정은 **무조건 제외**한다.

> ⚠️ **`_ROSCommon/**` 절대 수정 금지 (read-only 외부 git submodule)**
>
> `Src/Mirero.PCC.XLab/_ROSCommon`은 별도 저장소에서 관리되는 git submodule이다 (자체 `RosCommon.sln`, `Sync-RosCommonProjects.ps1` 보유). 본 솔루션에서 `_ROSCommon` 하위 파일을 **신규 생성·수정·삭제하는 것은 절대 금지**한다 — 상위 저장소 동기화 시 모든 변경이 손실된다. 수정이 필요하면 별도 저장소에서 변경한 뒤 동기화 스크립트로 가져온다. 신규 코드는 `_ROSCommon`을 **참조만** 한다 (모든 레이어에서 참조 자유 — §6.1 매트릭스 참조).

## 2. 솔루션 아키텍처

### 2.1 채택 5-레이어 매핑

| DDD 표준명 | 솔루션 규약 | 설명 |
|---|---|---|
| Domain | `Domain/**` | 비즈니스 불변식과 도메인 모델 |
| Application | `Application/**` | Use Case와 Port 인터페이스의 중심 레이어 |
| Infrastructure | `Infrastructure/**` | 외부 I/O 구현체와 기술 Adapter |
| Presentation | `App/**` | ASP.NET Core 호스트와 서비스 생명주기 조립 |
| Shared/Cross-Cutting | `Shared/**`, `Constants/**`, `ServiceModule/**`, `_ROSCommon/**` | 공통 코드와 기술 공통 모듈 (`_ROSCommon`은 read-only) |

### 2.2 변형 패턴 (Ports & Adapters)

- Port 인터페이스는 **반드시** `Application/**/Port`에 둔다.
- Application Contract 프로젝트는 DTO/Request/Response/Message 계약을 **반드시** 보관한다.
- Domain Contract 프로젝트는 Aggregate Repository 인터페이스와 도메인 계약만 **허용**한다.
- Infrastructure는 Application Port를 참조해 구현체를 제공하는 것이 **허용**된다.
- Presentation 호스트는 Application·Infrastructure 참조를 DI Composition Root에서만 **허용**한다. Controller/Hub가 Infrastructure 구현체를 직접 호출하는 것은 **금지**한다.

## 3. 호스트 4종 책임 분리

호스트 csproj 경로는 모두 `Src/Mirero.PCC.XLab/App/{Host}/Mirero.PCC.XLab.{Host}/Mirero.PCC.XLab.{Host}.csproj` 패턴이다.

### 3.1 APIGateway — 외부 HTTP/WebSocket 진입점과 라우팅 호스트

- **반드시** YARP Reverse Proxy, REST Controller, WebSocket 접속, 세션/헬스체크/하트비트 라우팅을 담당.
- **반드시** Master/Loader 업스트림 URL·Gateway 설정 조립, 토큰 요청·갱신·무효화 흐름을 Application Port와 Infrastructure HTTP Adapter로 연결.
- 비즈니스 상태 전이·DB Query·RabbitMQ 메시지 처리 규칙을 APIGateway 프로젝트에 두는 것은 **금지**.

### 3.2 Master — 중앙 관리 API와 기준 데이터/인증/버전/모니터링 호스트

- **반드시** 인증·토큰·Gateway 설정·버전 체크·헬스체크·기준 데이터 로딩·Heartbeat Polling 조립.
- **반드시** Master 전용 Controller·HostedService 생명주기, DB Query 등록·RabbitMQ 연결을 DI Composition Root에서 조립.
- Master Controller가 DB Provider·RabbitMQ 구현체를 직접 호출하는 것은 **금지**.
- 호스트는 **조립(`AddXxxHostedService(...)`, DI 등록)만** 수행한다. HTTP Client·Registry·Adapter **구현체는 모두 Infrastructure 또는 호스트 자신**에 두며, Application 프로젝트에 두는 것은 **금지**한다. HostedService 구현체는 Application 또는 Infrastructure 모두 **허용**(§5 표 참조). 단, `services.AddHostedService(...)` **등록 코드**는 Application 프로젝트에 두는 것을 **금지**한다.

### 3.3 Loader — 외부 데이터 수집과 기준 데이터 로딩 호스트

- **반드시** AuraAlarm, McEqpHist, Tool, Process, MaterialWorkStatus 수집 설정과 수집 HostedService 조립.
- **반드시** Query/Parser/DB Executor 등록 조립, RabbitMQ 연결·기준 데이터 응답 Registry·Heartbeat Polling을 호스트 생명주기에 연결.
- Loader 프로젝트에 도메인 계산 규칙·SQL 구현 상세를 직접 두는 것은 **금지**.
- 호스트는 **조립(`AddXxxHostedService(...)`, DI 등록)만** 수행한다. HTTP Client·Registry·Adapter **구현체는 모두 Infrastructure 또는 호스트 자신**에 두며, Application 프로젝트에 두는 것은 **금지**한다. HostedService 구현체는 Application 또는 Infrastructure 모두 **허용**(§5 표 참조). 단, `services.AddHostedService(...)` **등록 코드**는 Application 프로젝트에 두는 것을 **금지**한다.

### 3.4 PublisherHub — RabbitMQ와 WebSocket 사이의 실시간 발행 허브

- **반드시** Inbound/Outbound 메시지 Registry, RabbitMQ 수신, WebSocket 송신, Config Sync, Heartbeat 응답 처리 조립.
- **반드시** PublisherHub 설정·WebSocket 서버 생명주기 관리, Application PublisherHub 서비스와 Infrastructure PublisherHub Adapter를 DI로 연결.
- PublisherHub 프로젝트에 메시지 직렬화 규칙·비즈니스 라우팅 정책을 직접 구현하는 것은 **절대 금지**.
- 호스트는 **조립(`AddXxxHostedService(...)`, DI 등록)만** 수행한다. HTTP Client·Registry·Adapter **구현체는 모두 Infrastructure 또는 호스트 자신**에 두며, Application 프로젝트에 두는 것은 **금지**한다. HostedService 구현체는 Application 또는 Infrastructure 모두 **허용**(§5 표 참조). 단, `services.AddHostedService(...)` **등록 코드**는 Application 프로젝트에 두는 것을 **금지**한다.

### 3.5 Host-attached Tool — 호스트에 종속된 보조 진입점 (개발자 도구)

호스트 4종(§3.1~§3.4)에 종속된 개발자용 도구·검증·디버그 진입점. 운영 호스트와 같은 폴더 아래 별도 csproj로 위치하나 운영 책임을 갖지 않으며, on-demand·단일 사용자·localhost 사용을 전제한다.

- **반드시** csproj 명은 `Mirero.PCC.XLab.{Host}.{Tool}` 형식을 따른다 (예: `Mirero.PCC.XLab.Loader.ApiMonitor`).
- **반드시** 운영 호스트 csproj(`App/{Host}/Mirero.PCC.XLab.{Host}.csproj`)를 직접 참조하지 **않는다**. Application Port(`Application.{Host}.Port`)·Infrastructure 어댑터(`Infrastructure.{Host}.*`)·Shared/Cross-Cutting만 참조 **허용**.
- **반드시** on-demand·단일 사용자·localhost 사용을 전제한다. 운영 SLA·인증·다중 사용자·HA·접근통제는 **비적용**으로 명시한다.
- **반드시** 운영 호스트와 동일 폴더(`App/{Host}/`) 아래 별도 csproj로 위치한다(§7.2 추가 행 참조).
- **반드시** §4(레이어 책임)·§5(아티팩트 카탈로그)·§6(참조 방향) 매트릭스를 운영 호스트와 동일하게 준수한다. 호스트 도구라는 이유로 레이어 위반을 정당화하는 것은 **금지**한다.
- **반드시** PRD/FC/FRD 문서를 `docs/{HostTool}/` 하위에 별도로 둔다 (운영 호스트 문서와 분리).
- 본 절은 §3.1~§3.4의 호스트 4종 규약을 변경하지 않는다. 호스트 4종 책임 분리는 그대로 유지되며, 본 절은 그 호스트들에 부속된 도구 진입점의 위치·참조·전제만 규정한다.

## 4. 레이어별 책임

### 4.1 Domain

- **반드시** 둘 것: Entity, ValueObject, AggregateRoot, DomainEvent, DomainService, 도메인 불변식·상태 전이·값 검증·도메인 용어. Aggregate 저장소 계약일 때만 Repository 인터페이스를 `Domain.*.Contracts`에 **허용**.
- **허용**할 것: 같은 Domain 또는 Domain 공통 프로젝트 참조. `Shared/**`, `Constants/**`, `_ROSCommon/**` 등 Shared/Cross-Cutting 자유 참조 **허용** (단, `ServiceModule/**`은 **금지**).
- **금지**할 것: Application Service·DTO·Request·Response·Port 인터페이스 **금지**. DB·HTTP·RabbitMQ·WebSocket·Serializer·Logger 구현체 **금지**. ASP.NET Core·HostedService·Controller·Hub·DI 등록 코드 **금지**. `ServiceModule/**` 참조 **금지** (Domain 순수성 보존).
- **절대 금지**: Application·Infrastructure·Presentation 네임스페이스 `using`.

### 4.2 Application

- **반드시** 둘 것: Use Case, Application Service, Port 인터페이스, DTO, Request, Response, Message Contract. 외부 시스템 호출은 **반드시** Port로 추상화. 트랜잭션 흐름·메시지 처리 흐름·호스트 독립 상태머신.
- **허용**할 것: Domain 모델·Domain 계약 참조 **허용**. Application 내부 프로젝트 간 참조 **허용**. Shared/Cross-Cutting 전체(`Shared/**`, `Constants/**`, `ServiceModule/**`, `_ROSCommon/**`) 자유 참조 **허용**. HostedService/BackgroundService **구현체** 보유 **허용**(§5 Worker/HostedService Application 칸=허용). 단, 호스트 등록 람다(`services.AddHostedService(...)`)는 **반드시** Presentation Composition Root에서만 작성한다.
- **금지**할 것: Infrastructure 구현체·DB Provider·RabbitMQ Client·HTTP Client·WebSocket Client **금지**. Controller·Hub·Runner·HostedService 등록 코드 **금지**. `Oracle.*`, `RabbitMQ.*`, `System.Net.WebSockets` 직접 사용 **금지**.
- **절대 금지**: Infrastructure·Presentation 네임스페이스 `using`.

### 4.3 Infrastructure

- **반드시** 둘 것: Repository 구현체, DB Query/Parser/Provider, HTTP Client, RabbitMQ Adapter, WebSocket Adapter, Serializer, Registry 구현체. Application Port 구현체와 외부 시스템 Adapter. 외부 예외 변환·재시도·직렬화·프로토콜 매핑.
- **허용**할 것: Application Port·Contract 참조 **허용**. Domain 모델·Domain 계약 참조 **허용**. Infrastructure 내부 공통 구현 참조 **허용** (순환 참조 **금지**). Shared/Cross-Cutting 기술 모듈 참조 **허용**.
- **금지**할 것: 도메인 불변식·상태 전이를 Infrastructure 구현체에 두는 것 **금지**. Use Case 흐름 결정 **금지**.
- **절대 금지**: Controller·Hub·View·ViewModel·WPF·UIModule 참조. Presentation·UIModule 네임스페이스 `using`.

### 4.4 Presentation

- **반드시** 둘 것: `Program`, Builder, Runner, Controller, Hub, HostedService 등록, DI Composition Root, Swagger/AsyncAPI 노출 설정. 호스트별 설정 로딩과 서비스 생명주기 시작/종료. Application Port와 Infrastructure 구현체 연결은 **반드시** DI 등록 코드에서 수행.
- **허용**할 것: Application 참조 **허용**. Infrastructure 참조는 DI Composition Root와 호스트 조립 코드에서만 **허용**. Shared/Cross-Cutting 참조 **허용**. 같은 호스트 내부 `Builder`/`Runner`/`Extension`/`Controller` 참조 **허용**.
- **금지**할 것: Controller/Hub에서 Infrastructure 구현체를 직접 생성·호출 **금지**. Domain Entity를 외부 API 응답 모델로 직접 노출 **금지**. 도메인 불변식·상태 전이·DB Query·메시지 직렬화 규칙 **금지**.
- **절대 금지**: UIModule·Client 프로젝트 참조.

### 4.5 Shared/Cross-Cutting

- **반드시** 둘 것: 공통 상수, 공통 메시지 기반 타입, 공통 데이터 값, 로깅 추상화, 토큰 공통 모델, Windows Service/AspNetService 공통 호스트 유틸리티. 기술 중립 타입은 **반드시** Shared Kernel 하위에. 기술 프레임워크 래퍼는 **반드시** Cross-Cutting Technical 하위에.
- **허용**할 것: Shared/Cross-Cutting 내부 참조 **허용**. `Constants/**`은 상수·enum만 **허용**. `_ROSCommon/**`과 `ServiceModule/**`은 외부 기술 래퍼·공통 기술 모듈만 **허용** (참조만).
- **금지**할 것: Domain 규칙·Application Use Case·Infrastructure Adapter 구현·Presentation 호스트 코드 **금지**. 특정 호스트 전용 정책 **금지**. ⚠️ **`_ROSCommon/**`에 신규 파일 추가·기존 파일 수정은 절대 금지** (read-only 외부 submodule, §1.3 참조).
- **절대 금지**: Domain·Application·Infrastructure·Presentation 프로젝트 참조.

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
| Hub | **금지** | **금지** | **금지** | **허용** | 공통 추상화만 **허용** |
| Worker/HostedService | **금지** | 구현체 **허용** | 구현체 **허용** | 등록·생명주기만 **허용** | 공통 베이스만 **허용** |
| Config/Options | 도메인 정책 값만 **허용** | 유스케이스 설정만 **허용** | 외부 시스템 설정만 **허용** | 호스트 설정 바인딩만 **허용** | 공통 설정 모델만 **허용** |

> 표의 모든 'Shared/Cross-Cutting **허용**'은 `_ROSCommon/**`을 **제외**한다 — 신규 파일 추가는 절대 금지 (§1.3 참조).

## 6. 레이어 참조 방향

- Domain은 **반드시** 안쪽 핵심이다. Application·Infrastructure·Presentation을 **절대 참조 금지**한다.
- Application은 **반드시** Domain과 Port 계약만 조율한다. Infrastructure·Presentation을 **절대 참조 금지**한다.
- Infrastructure는 **반드시** Application Port 또는 Domain 계약을 구현하거나 소비한다. Presentation을 **절대 참조 금지**한다.
- Presentation 호스트는 **반드시** 조립 루트로 동작한다. 비즈니스 규칙을 직접 소유하는 것을 **금지**한다.
- Shared/Cross-Cutting은 **반드시** 공통 기능만 제공한다. Domain/Application/Infrastructure/Presentation을 **절대 참조 금지**한다.

### 6.1 절대 금지 매트릭스

매트릭스에 명시된 **금지**·**절대 금지** 조합만 위반으로 판정한다. **허용** 조합은 별도 제한 없이 자유 참조한다.

**예외 (단 1건)**: Domain → `ServiceModule/**`은 **금지**. Domain 순수성 보존을 위해 기술 프레임워크 래퍼 직접 참조 차단. 그 외 모든 Shared/Cross-Cutting 항목(`Shared/**`, `Constants/**`, `_ROSCommon/**` 등)은 Domain에서도 자유 참조 가능.

`_ROSCommon/**`은 §1.3에 따라 read-only이므로 모든 레이어에서 신규 파일 추가·수정만 금지, 참조는 자유.

| From \ To | Domain | Application | Infrastructure | Presentation | Shared/Cross-Cutting |
|---|---|---|---|---|---|
| Domain | **허용** | **금지** | **금지** | **금지** | **허용** |
| Application | **허용** | **허용** | **금지** | **금지** | **허용** |
| Infrastructure | **허용** | **허용** | **허용** | **금지** | **허용** |
| Presentation | **금지** | **허용** | **허용** | **허용** | **허용** |
| Shared/Cross-Cutting | **금지** | **금지** | **금지** | **금지** | **허용** |

## 7. 프로젝트 매핑 규칙

### 7.1 폴더 → 레이어 자동 판정 표

| 최상위 폴더 | 레이어 | 네임스페이스 prefix | 비고 |
|---|---|---|---|
| `Domain/**` | Domain | `Mirero.PCC.XLab.Domain` | |
| `Application/**` | Application | `Mirero.PCC.XLab.Application` | `**/Port` = `I*` 인터페이스, `**/Contract` = DTO 전용 |
| `Infrastructure/**` | Infrastructure | `Mirero.PCC.XLab.Infrastructure` | |
| `App/{Host}/**` | Presentation | `Mirero.PCC.XLab.{Host}` | Host ∈ {APIGateway, Master, Loader, PublisherHub} |
| `Shared/**` | Shared/Cross-Cutting | `Mirero.PCC.XLab.Shared.*` | |
| `Constants/**` | Shared/Cross-Cutting | `Mirero.PCC.XLab.Constants.*` 또는 `Mirero.PCC.XLab.Constant.*` | 상수·enum만 |
| `ServiceModule/**` | Shared/Cross-Cutting | `Mirero.PCC.XLab.ServiceModule.*` | 본 솔루션 내부 코드 |
| `_ROSCommon/**` | Shared/Cross-Cutting (read-only) | `Mirero.*`, `Mirero.Asset.*`, `Mirero.ROSCommon.*` | ⚠️ git submodule, **신규 생성·수정·삭제 절대 금지** |

### 7.2 모서리 케이스 6행

폴더 패턴에서 자동 추론되지 않는 항목은 다음 규칙으로 판정한다.

| 패턴 | 분류 | 근거 |
|---|---|---|
| `_ROSCommon/Asset/*` | Shared/Cross-Cutting (read-only) | 외부 기술 래퍼. 모든 레이어에서 참조 허용 (§1.3에 따라 신규 파일 추가·수정만 금지) |
| `ServiceModule/WebsocketCore/*Client*` | Shared/Cross-Cutting | 이름에 `Client`가 포함되지만 WPF/데스크톱 UI 호스트가 아님 |
| `App/{Host}/Mirero.PCC.XLab.{Host}` | Presentation 단일 진입점 (운영) | 호스트당 운영 진입점 정확히 1개. 단, §3.5의 보조 진입점은 별도 csproj로 추가 허용 |
| `App/{Host}/Mirero.PCC.XLab.{Host}.{Tool}` | Presentation 보조 진입점 (§3.5) | 호스트당 운영 진입점 1 + 도구 진입점 N. 운영 csproj 참조 금지, on-demand·단일 사용자·localhost 전제 |
| `Application/**/Port` | Application Port 전용 | `I*` 인터페이스만, 구현체 **금지** |
| `Application/**/Contract` | Application Contract 전용 | DTO/Request/Response/Message만, 비즈니스 로직 **금지** |

### 7.3 매핑 재생성

```
find Src/Mirero.PCC.XLab/{Domain,Application,Infrastructure,App,Shared,Constants,ServiceModule,_ROSCommon} -name "*.csproj"
```

### 7.4 접미사 의미 표

같은 접미사가 레이어별로 다른 책임을 가진다. 신규 파일 명명 시 이 표를 따른다.

| 접미사 | Domain 의미 | Application 의미 | Infrastructure 의미 | Presentation 의미 | Shared 의미 |
|---|---|---|---|---|---|
| `Service` | 도메인 계산 규칙 | Use Case 조율 | 외부 시스템 래퍼 | **금지** | 공통 유틸리티 |
| `Handler` | 도메인 이벤트 처리 | 메시지/Use Case 처리 | 프로토콜 메시지 처리 | **금지** | 공통 기술 처리 |
| `Repository` | 인터페이스만 **허용** | 조회 Port만 **허용** | 구현체만 **허용** | **금지** | **금지** |
| `Dto` | **금지** | 계약 DTO | 외부 시스템 DTO | API View DTO | 공통 메시지 DTO |
| `Controller` | **금지** | **금지** | **금지** | ASP.NET Controller | **금지** |
| `Hub` | **금지** | **금지** | **금지** | SignalR/WebSocket Hub | 공통 추상화만 |
| `Factory` | 도메인 객체 생성 | Use Case 객체 생성 | Adapter 생성 | 호스트 조립 | 공통 객체 생성 |
| `Config`, `Options` | 도메인 정책 값 | Application 설정 | 외부 시스템 설정 | 호스트 설정 | 공통 설정 |
| `Client` | **금지** | 외부 Port 인터페이스만 | 외부 시스템 Client 구현 | **금지** | 공통 기술 Client |
