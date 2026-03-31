---
name: atdd-test
description: 설계서와 테스트 명세를 기반으로 실행 가능한 테스트 코드를 작성한다. 프로덕션 코드는 작성하지 않는다 — ATDD의 Red 단계. atdd-pipeline에서 Phase 3으로 호출되거나, /atdd-test로 독립 실행 가능.
argument-hint: "[기능명]"
input: .atdd/frd_{기능명}.md, .atdd/design_{기능명}.md, .atdd/test_{기능명}.md
output: 테스트 코드 파일
requires-user-interaction: false
---

# ATDD Test — 테스트 코드 작성 (Red 단계)

설계서와 테스트 명세를 입력받아 **실행 가능한 테스트 코드만** 생성한다.

이 스킬의 산출물은 컴파일이 안 되는 것이 정상이다. 테스트에서 참조하는 DTO, Service, Controller 등이 아직 존재하지 않기 때문이다. 이것이 ATDD의 Red 단계 — 실패하는 테스트가 먼저 존재하고, 다음 단계(atdd-implement)에서 이 테스트를 통과시키는 코드를 작성한다.

**이 스킬에서는 프로덕션 코드를 절대 작성하지 않는다.** DTO, Service, Controller, Repository, Program.cs 등 프로덕션 프로젝트의 파일은 하나도 생성하지 않는다.

---

## Phase 0: 입력 검증

1. `$ARGUMENTS`에서 `{기능명}`을 파싱한다.
2. 아래 3개 파일이 모두 존재하는지 확인한다:
   - `.atdd/frd_{기능명}.md`
   - `.atdd/design_{기능명}.md`
   - `.atdd/test_{기능명}.md`
   - 하나라도 누락 시 에러 메시지를 출력하고 종료한다.

---

## Phase 1: 분석

산출물 3개만 읽는다. 프로덕션 프로젝트 탐색은 하지 않는다 — 아직 프로덕션 코드가 없는 것이 정상이다.

1. `.atdd/frd_{기능명}.md` 읽기
2. `.atdd/design_{기능명}.md` 읽기
3. `.atdd/test_{기능명}.md` 읽기
4. 테스트 프로젝트의 `.csproj` (또는 `package.json` 등) 파일을 **1개만** 읽어서 테스트 프레임워크를 확인한다.

이 4개를 읽으면 Phase 1은 끝이다. 다른 파일을 탐색하지 않는다.

```
[Phase 1 완료] 분석 완료 — 테스트 코드 작성을 시작합니다.
```

---

## Phase 2: 테스트 코드 작성

`test_{기능명}.md`의 테스트 케이스를 실행 가능한 테스트 코드로 변환한다.

### 작성 순서

1. **정상 흐름(Happy Path) 테스트부터 작성한다.**
2. 예외/엣지 케이스 테스트를 이어서 작성한다.
3. `[DEFERRED]` 표기된 테스트는 주석으로 남기고 skip 처리한다 — 삭제하지 않는다.

### 작성 규칙

- 테스트 프레임워크는 기술 스택에 맞게 선택한다 (예: Jest for NestJS, JUnit for Spring Boot, xUnit/NUnit for ASP.NET Core).
- 테스트 파일은 **테스트 프로젝트에만** 생성한다. 프로덕션 프로젝트에 파일을 생성하지 않는다.
- Given/When/Then 구조를 코드 주석이나 describe/it 블록 이름으로 반영한다.
- 외부 의존성(DB, 외부 API)은 설계서의 인터페이스를 기반으로 모킹한다.
- 테스트에서 참조할 프로덕션 클래스의 네임스페이스/import는 설계서 기준으로 작성한다 (아직 존재하지 않아도 됨).

---

## Phase 3: 완료

테스트 파일 작성이 끝나면 아래를 출력한다:
```
[ATDD-TEST COMPLETE] 테스트 코드 작성 완료
- 생성된 파일: {테스트 파일 경로 목록}
- 테스트 케이스 수: {N}건 (DEFERRED 스킵: {N}건)
```

---

## Tone & Style

- 한국어를 기본 언어로 사용한다.
- 코드는 해당 기술 스택의 관례를 따른다.
- 이 스킬은 서브 에이전트에서 실행되므로 `AskUserQuestion`을 호출하지 않는다.
- 기존 테스트 코드가 있으면 그 스타일을 따른다.
