---
description: CodeNavigator parser-only baseline index 빌드. C# 클래스 골격 + frontmatter + XML doc만 읽어 SQLite 인덱스를 생성. AI enrichment 미사용.
argument-hint: "[repo-root] [scan-path] [--reset]"
---

CodeNavigator baseline index를 `codenav` CLI(`reindex --no-ai`) 로 생성/복구한다. **LLM 직접 .cs 파싱 금지** — 모든 파싱·저장은 Python 모듈이 수행.

인자: $ARGUMENTS

## 인자 해석

- 첫 번째 인자: `repo-root`. 없으면 현재 작업 디렉터리.
- 두 번째 인자: `scan-path`. 있으면 `--files <list>` 모드로 해당 경로만 스캔. 없으면 `--full`.
- `--reset` 인자: 현재 `reindex --full`이 이미 source_type='auto' 항목 중 스캔 범위 밖 파일을 자동 정리하므로 별도 처리 불필요. 사용자가 `--reset` 줘도 동일하게 `--full` 실행.

## 실행 절차

### 1. codenav CLI 위치 탐지

다음 순서로 어떤 명령으로 codenav 를 호출할지 결정:

1. **프로젝트 venv**: `<cwd>/Tools/codenavigator/Scripts/codenav.exe` (Windows) 또는 `<cwd>/Tools/codenavigator/bin/codenav` (Unix) 존재 → 절대경로로 호출.
2. **launcher**: `<cwd>/codenav.ps1` 존재 → `& .\codenav.ps1 @Args`.
3. **PATH 글로벌**: `where codenav` / `which codenav` 성공 → `codenav` 그대로.
4. 모두 부재 → 다음 안내 후 중단:
   ```
   codenav 가 설치되어있지 않음. 둘 중 하나:
   
     [프로젝트별 격리 권장]
     python -m venv Tools/codenavigator
     Tools/codenavigator/Scripts/pip install codenavigator
     # 루트에 codenav.ps1 launcher 작성
     #   & "$PSScriptRoot\Tools\codenavigator\Scripts\codenav.exe" @Args
   
     [글로벌]
     pip install codenavigator
   ```

이후 단계의 `codenav ...` 호출은 위에서 결정된 경로로 치환.

### 2. git repo 검사

- `--root` 가 git repo 인지 확인. 아니면 사용자 경고.

### 3. Bootstrap 실행

`scan-path` 없으면:
```
codenav --root <repo-root> reindex --full --no-ai --verbose
```

`scan-path` 있으면 해당 디렉터리 아래 `.cs` 목록을 수집해 `--files` 인자로 전달:
```
codenav --root <repo-root> reindex --files <file1.cs> <file2.cs> ... --no-ai --verbose
```

`--no-ai` 플래그 효과:
- `indexer.enrich_entries` 호출 스킵 → Claude CLI 부재해도 안전.
- description 빈 항목도 `stale=0` 으로 저장 (AI 실패 mark X).
- 빠름(파싱·INSERT 만 수행).

### 4. 결과 확인

```
codenav --root <repo-root> status
```

출력 캡처 후 사용자에게 요약:
- 총 클래스 수 / manual 수 / stale 수
- last-indexed 시각
- stale 파일 목록 (있으면)

stale 있으면 사용자에게 알림 — 보통 `--no-ai` 모드에선 0 이 정상. 0 아니면 이전 실행의 AI 실패 잔재 가능.

### 5. (선택) 검색 확인

샘플 검색 한 번:
```
codenav --root <repo-root> search "<적당한 키워드>" --limit 3
```

## 주의

- 본 명령은 **빠른 baseline 생성**이 목적. 의미 있는 description 채우기는 다음 둘 중 선택:
  1. `/codenav-frontmatter-gen` 으로 AI가 `// ---` 블록을 .cs 파일에 직접 삽입 (영구).
  2. `codenav reindex --full` (AI enrichment ON) 으로 SQLite 에만 AI description 저장 (휘발성).
- 사용자가 manually 만든 entry 는 절대 삭제하지 않음 — `source_type='manual'` 보호됨.
- `--no-ai` 모드는 `claude` CLI 가 PATH 에 없어도 정상 작동.
