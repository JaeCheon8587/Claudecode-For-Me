# 객체지향 설계 규칙

이 문서는 `Mirero.PCC.XLab` 솔루션의 신규 C# 코드가 **반드시** 따라야 하는 객체지향 설계 규칙(SOLID 기반)을 정의한다. 레이어 분류는 `DDD_ARCHITECTURE_RULES.md`가, 클래스/함수의 책임 분해 규칙은 본 문서가 담당한다. 모든 레이어에 동일하게 적용한다.

## 1. 클래스 SRP (Single Responsibility Principle)

- 한 클래스는 **반드시** 하나의 변경 이유(reason to change)만 가진다.
- 다음 신호 중 2개 이상이 보이면 **반드시** 분리한다.
  - 클래스 이름이 `XxxAndYyy`, `XxxManager`, `XxxHelper` 류로 모호함
  - 필드/생성자 의존성이 **5개 이상**이거나 의존성 그룹이 둘 이상으로 명확히 갈림
  - `private` 메서드들이 서로 다른 필드 묶음에 접근 (응집도 저하 신호)
  - 한 메서드 내부에서 (a) 외부 시스템 대기, (b) 상태 비교, (c) DTO 매핑, (d) 발행, (e) 진단 로깅 중 3개 이상이 함께 수행됨
  - 같은 클래스가 서로 다른 두 변경 요청(예: "수집 주기 변경" + "발행 메시지 형식 변경")에 모두 수정됨
- 분리 시 **반드시** 새 클래스에 책임을 표현하는 명사형 이름을 부여한다 (`XxxTracker`, `XxxMapper`, `XxxDiagnostics`, `XxxInitWaiter` 등).
- HostedService/BackgroundService 구현체는 **반드시** 생명주기와 cycle 오케스트레이션만 담당한다. 상태 보유·DTO 매핑·진단 로깅 포매팅·외부 시스템 대기 로직을 직접 들고 있는 것은 **금지**한다.
- 상태(필드)와 그 상태를 읽고 갱신하는 로직은 **반드시** 같은 클래스에 둔다. 한 클래스가 필드를 보유하고 다른 클래스(특히 `static`)가 그 필드를 외부에서 받아 비교·변형하는 패턴(feature envy)은 **금지**한다.

## 2. 클래스 OCP (Open/Closed Principle)

- 변경 가능성이 있는 정책(매핑 규칙·분기 규칙·재시도 정책·선택 규칙 등)은 **반드시** 추상화(인터페이스 또는 작은 strategy 클래스)로 분리해 신규 정책 추가가 기존 코드 수정 없이 가능하도록 한다.
- 다음 패턴이 보이면 **반드시** OCP 위반으로 판정한다.
  - 분기마다 `if (type == "A") ... else if (type == "B") ...` 사슬이 한 메서드에서 3개 이상
  - 새 케이스를 추가할 때마다 **같은** 메서드 본문을 수정해야 함
  - `switch` 문이 같은 식별자로 여러 곳에 흩어져 있음 (shotgun surgery 신호)
- 구체 정책 클래스는 **허용**하되, **반드시** 인터페이스/추상 베이스를 통해 호출자에 주입한다. 호출자가 `new ConcretePolicy()`를 직접 생성하는 것은 **금지**한다.
- LoopingBackgroundService·MessageHandler·Selector 같은 템플릿/전략 자리는 **반드시** 확장 가능 지점을 인터페이스로 노출한다. 확장이 필요할 때마다 `if` 추가로 대응하는 것은 **금지**한다.

## 3. 클래스 DIP (Dependency Inversion Principle)

- 상위 정책(Application/Domain)은 **반드시** 추상(Port·인터페이스)에만 의존한다. 하위 구현(Infrastructure)에 직접 의존하는 것은 **절대 금지** (`DDD_ARCHITECTURE_RULES.md` §6.1 매트릭스).
- 외부 시스템 호출(DB·HTTP·RabbitMQ·WebSocket·파일·시계 등)은 **반드시** Port 인터페이스를 통해 수행한다. Application/Domain에서 `HttpClient`, `OracleConnection`, `RabbitMQ.Client.*`, `System.IO.File`, `DateTime.UtcNow` 직접 사용은 **금지**한다 (시계·랜덤 등은 `IClock`, `IRandomProvider` 같은 추상 사용).
- 의존성은 **반드시** 생성자 주입한다. `static`/`Singleton.Instance`/`ServiceLocator` 패턴으로 의존성을 가져오는 것은 **금지**한다 (단, `Constants/**`의 상수·enum, Shared 공통 유틸리티는 **허용**).
- 인터페이스 정의는 **반드시** 사용자(상위 레이어) 측에 둔다. 즉 Application Port 인터페이스는 `Application/**/Port`에 두고 Infrastructure가 그것을 구현한다. 인터페이스를 Infrastructure 프로젝트에 정의하고 Application이 참조하는 것은 **절대 금지**.
- DI 등록은 **반드시** Presentation Composition Root(`App/{Host}/**/Extension/ServiceCollectionExtensions.cs`)에서만 수행한다.

## 4. 함수 SRP

- 한 함수는 **반드시** 한 가지 일만 한다. 한 가지 일의 기준은 "함수 이름을 `AndYyy` 없이 한 동사구로 정확히 표현 가능한가" 이다.
- 다음 신호 중 하나라도 보이면 **반드시** 분리한다.
  - 함수 본문이 **30 라인을 초과**한다 (가이드, 강제 한도는 50 라인 — 그 이상은 **금지**)
  - 함수 이름이 `DoXxxAndYyy`, `ProcessAll`, `Handle` 류로 무엇을 하는지 불명확
  - 들여쓰기 깊이가 4 단계를 초과한다 (조건/루프 중첩이 깊으면 **반드시** guard clause 또는 helper 추출)
  - 함수 내에서 (a) 외부 호출, (b) 변환, (c) 분기 결정, (d) 부수효과(상태 갱신·로그·발행) 중 **3개 이상**을 한꺼번에 수행
  - 같은 함수에서 변경 이유가 둘 이상 (예: "조회 방식 변경" 또는 "매핑 형식 변경" 양쪽 모두에 수정 발생)
  - 한 함수의 매개변수가 **5개를 초과**한다 (그룹화해 별도 타입으로 묶거나 함수를 쪼갠다)
- 추출한 helper는 **반드시** `private static` 또는 `private`으로 두되, 호출 순서·의도가 상위 함수에서 한눈에 읽히도록 명명한다 (`Step1Xxx`, `DoXxxInternal` 같은 비의미 명명 **금지**).
- 함수 본문은 **반드시** "의도(intent)"를 표현한다. cycle 오케스트레이션 함수는 "수집 → 추적 → 매핑 → 발행 → 로그" 같은 5줄짜리 호출 시퀀스로 읽혀야 하며, 각 단계의 세부 구현이 인라인되어 있는 것은 **금지**한다.

## 5. 자기 점검 체크리스트

신규 파일/PR 작성 시 **반드시** 다음을 통과시킨다.

- [ ] 클래스의 변경 이유를 한 문장으로 적었을 때 "그리고/또" 가 들어가지 않는가
- [ ] 클래스가 보유한 필드 중 일부만 사용하는 메서드 그룹이 둘 이상으로 갈리지 않는가
- [ ] 모든 외부 의존성이 Port 인터페이스 + 생성자 주입으로 들어오는가
- [ ] 새 케이스(새 라인·새 메시지 타입·새 정책)를 추가할 때 기존 클래스 본문을 수정해야 하는가 (수정해야 하면 OCP 위반)
- [ ] 함수 본문이 30 라인 이내이며 한 동사구로 이름 짓는가
- [ ] HostedService 구현체가 lifecycle/cycle 오케스트레이션 외 책임(상태 보유, 매핑, 진단 로깅 등)을 들고 있지 않은가
