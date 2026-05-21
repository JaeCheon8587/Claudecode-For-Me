# CodeNavigator-FRONTMATTER — In-Source Frontmatter 양식

> 본 문서는 C# 클래스 description/tags 메타데이터를 소스 코드 안에 작성하기 위한 주석 양식 규약. CodeNavigator parser(`tools/CodeNavigator/src/codenav/parser_cs.py`)가 본 양식을 읽어 SQLite 인덱스의 `description`·`tags` 컬럼을 채운다.

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-FRONTMATTER |
| 버전 | 0.1 (Draft) |
| 관련 문서 | [CodeNavigator-PRD](CodeNavigator-PRD.md) · [CodeNavigator-FC](CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](CodeNavigator-ARCHITECTURE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-22 | 초안 — `// ---` YAML 블록 frontmatter 규약 정의 | 정재천 |

---

## 1. 목적

bootstrap parser-only 모드(AI enrichment 비활성)에서 description 컬럼이 비는 문제 해결. `///` XML doc 작성이 없는 코드베이스에서도 개발자가 직접 작성한 메타데이터를 parser가 읽어 인덱스에 반영하도록 한다.

기존 `/// <summary>` XML doc 메커니즘은 그대로 살아있다. 본 frontmatter는 XML doc이 없을 때만 사용되는 **보조 채널**이다.

## 2. 위치 규칙

frontmatter 블록은 **클래스 선언 바로 위**에 배치한다.

- 적용 대상: `class`, `struct`, `interface`, `record`.
- 빈 줄 1~2개까지는 frontmatter와 클래스 선언 사이에 허용한다.
- frontmatter와 클래스 선언 사이에 다른 코드, attribute, `///` XML doc 이 끼면 **매칭되지 않는다**(우선순위 단순화).
- 다중 클래스 파일에서는 각 클래스 위에 각자의 frontmatter를 둔다.

## 3. 문법

```csharp
// ---
// description: <한 줄 설명>
// tags: [<태그1>, <태그2>, ...]
// ---
public class <ClassName>
{
    ...
}
```

세부 규칙:

- 시작 라인: `// ---` (백슬래시 다음 공백 0~1개 허용).
- 종료 라인: `// ---` 동일.
- 사이 라인은 `// <key>: <value>` 형식.
- `//` 다음 공백은 0~1개 허용 (`//key:value` 와 `// key: value` 모두 인식).
- 키 이름은 소문자 영문/언더스코어.
- 알 수 없는 키는 silent skip — 미래 확장 여지를 둠.

## 4. 지원 키

| 키 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `description` | 문자열 1줄 | 권장 | 클래스 역할 한 줄 설명. 큰따옴표 옵션. 개행 금지. 없으면 description 컬럼 빈 채로 유지 |
| `tags` | 인라인 시퀀스 `[a, b, c]` | 선택 | 검색용 태그. 공백 옵션. 빈 리스트 `[]` 허용. 미지정 시 PascalCase 분해 결과를 자동 사용 |

향후 추가 후보(현재 미지원):
- `owner`: 담당자 식별자
- `domain`: DDD 도메인 경계
- `since`: 도입 버전

위 키들도 silent skip 되므로 미리 적어둬도 무해하다.

## 5. 우선순위

```
/// <summary> XML doc  >  // --- frontmatter  >  빈칸
```

- XML doc과 frontmatter가 둘 다 있으면 XML doc 우선 (기존 동작 보존).
- XML doc 없고 frontmatter만 있으면 frontmatter 사용.
- 둘 다 없으면 현재처럼 빈 description.

tags는 frontmatter 우선, 없으면 PascalCase 분해 자동 생성.

## 6. 예시

### 6.1 최소 예 (description만)

```csharp
// ---
// description: 문서 처리 서비스
// ---
public class DocumentService
{
}
```

### 6.2 전체 예 (description + tags)

```csharp
// ---
// description: 문서 영속화 리포지토리
// tags: [document, repository, persistence]
// ---
public class DocumentRepository
{
}
```

### 6.3 다중 클래스 파일

```csharp
namespace MyApp.Documents;

// ---
// description: 문서 처리 서비스
// tags: [document, service]
// ---
public class DocumentService
{
}

// ---
// description: 문서 유효성 검증
// tags: [document, validator]
// ---
public class DocumentValidator
{
}
```

### 6.4 XML doc과 공존 (XML doc 우선)

```csharp
// ---
// description: 이 값은 무시됨
// ---
/// <summary>실제 인덱스에 들어가는 description</summary>
public class DocumentService
{
}
```
> XML doc과 frontmatter 사이 어떤 라인도 없어야 하지만, 이 예시처럼 XML doc이 클래스 선언 직전에 있으면 frontmatter는 매칭되지 않고 무시된다.

### 6.5 잘못된 예 — silent skip

```csharp
// ---
// description: 닫는 마커 누락
public class BrokenFrontmatter
{
}
```
종료 `// ---` 가 없어 frontmatter 전체가 무시되고 description은 빈칸으로 남는다. parser는 에러를 내지 않는다.

```csharp
// ---
// description: 사이에 코드 끼움
// ---

[Obsolete]
public class WithAttribute
{
}
```
frontmatter와 클래스 선언 사이에 `[Obsolete]` attribute가 끼어 매칭 실패. attribute 처리를 추가하려면 별도 규약 확장 필요.

## 7. 범위

- 현재 클래스/struct/interface/record만 지원.
- 메서드 단위 frontmatter는 미지원. 메서드 description은 본 버전에서도 항상 빈칸.
- enum, delegate는 인덱스 대상이 아니므로 미지원.

## 8. AI 협업 가이드

Claude / Copilot / GPT 등이 새 클래스를 생성할 때, 가능하면 frontmatter를 함께 작성하도록 프롬프트에 다음 가이드를 포함한다:

> 새 C# 클래스를 만들 때는 선언 바로 위에 다음 형식의 frontmatter 주석을 추가한다:
> ```csharp
> // ---
> // description: <클래스 역할 한 줄>
> // tags: [<도메인>, <역할>, <기타>]
> // ---
> ```
> XML doc(`///`)을 작성하는 경우 frontmatter는 생략한다 (중복 방지).

## 9. 검증

본 양식을 적용한 뒤 다음으로 확인한다:

1. `python -m codenav reindex --full` 실행.
2. `http://127.0.0.1:8765/` 대시보드에서 해당 클래스 description 컬럼이 채워졌는지 확인.
3. 기존 XML doc이 있던 클래스는 그대로인지 확인 (회귀 방지).
