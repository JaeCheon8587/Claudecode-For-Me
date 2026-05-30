---
name: codenav-frontmatter-gen
description: C# 클래스 description 빈칸을 AI로 일괄 채워주는 `// ---` frontmatter 블록 자동 생성기. `codenav frontmatter gen` CLI를 dry-run → 사용자 확인 → --apply 순서로 안전하게 실행. 사용자가 "프론트메터 생성", "C# description 채우기", "frontmatter 자동 생성", "CodeNavigator description 일괄 채우기", "클래스 설명 자동 작성" 등으로 요청 시 트리거.
argument-hint: "[--limit N] [--root repo-root]"
---

# CodeNavigator Frontmatter Generator

C# 클래스 중 `/// <summary>` XML doc도 없고 `// ---` frontmatter도 없는 항목을 찾아 AI로 description+tags를 생성한 뒤 클래스 선언 위에 `// ---` 블록을 삽입한다.

## 트리거 조건

다음 중 하나라도 해당하면 본 스킬을 호출:
- "프론트메터 생성", "frontmatter 자동 생성"
- "C# description 채우기", "클래스 설명 일괄 작성"
- "CodeNavigator description 빈칸 채워줘"
- "코드에 메타데이터 주석 자동 추가"

## 사전 조건 점검

1. **`codenav` CLI 존재 확인** — `where codenav` (PowerShell) / `which codenav` (bash). 없으면 `pip install codenavigator` 한 줄 안내 후 중단.
2. **git working tree 깨끗** — uncommitted change 가 있으면 사용자에게 commit/stash 권유. `--allow-dirty` 우회는 사용자가 명시 요청한 경우에만.
3. **`claude` CLI 가용성** — `where claude` (PowerShell) / `which claude` (bash) 로 확인. 없으면 AI 호출 불가 → 사용자에게 알림.

## 실행 절차

### 1. Dry-run (필수 — 절대 건너뛰지 말 것)

```
codenav frontmatter gen --limit 50 --verbose
```

기본 `--limit 50`. 사용자가 더 큰 배치를 원하면 인자로 받아 조정. 절대 일회성 100개 이상 권장 금지 — AI 토큰/품질 관리.

### 2. 결과 보고

stderr 로 나오는 `[DRY] <file>:<line> <ClassName> → <description>` 라인을 사용자에게 사람이 읽을 형식으로 정리해 보여준다:
- 대상 파일 수, 클래스 수
- 생성된 description 샘플 3~5개
- 실패 / 누락 항목

### 3. 사용자 확인

사용자가 "적용해", "apply", "go" 등 명시적 승인 줄 때까지 절대 `--apply` 호출 금지. 미리보기 결과가 마음에 안 들면 사용자 요구대로 limit/필터 조정 후 다시 dry-run.

### 4. Apply

```
codenav frontmatter gen --limit <같은 값> --apply --verbose
```

성공 후 결과 (`written` 개수, `failures`) 를 사용자에게 보고.

### 5. 후속 권장

- `codenav reindex --full` 실행해 SQLite 인덱스에 frontmatter description 반영.
- `git diff` 로 변경 확인. 부적절한 description 있으면 사용자가 수동 수정 또는 해당 클래스 frontmatter 삭제 후 재실행.

## 안전 원칙

- **idempotent**: 이미 XML doc 또는 frontmatter 있는 클래스는 자동 스킵. 중복 삽입 X.
- **dry-run 기본**: `--apply` 없이는 파일 변경 0건. 항상 dry-run 먼저.
- **git 깨끗 강제**: `--allow-dirty` 는 사용자 명시 요청 시만.
- **배치 제한**: 한 번에 최대 50개 (CLI 기본). 사용자가 명시 요청 시 늘림.
- **roll-back**: 적용 후 결과 마음에 안 들면 `git checkout -- .` 또는 `git restore` 로 즉시 복원 가능 (사전 git 깨끗 조건 덕분).

## 형식 참고

생성된 frontmatter 형식:
```csharp
// ---
// description: <한 줄 요약>
// tags: [<tag1>, <tag2>, ...]
// ---
public class Foo
{
    ...
}
```

자세한 양식 규약은 [codenavigator/docs/frontmatter.md](https://github.com/JaeCheon8587/codenavigator/blob/main/docs/frontmatter.md) 참조.
