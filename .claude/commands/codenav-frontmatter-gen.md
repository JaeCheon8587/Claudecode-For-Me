---
description: C# 클래스의 description 빈칸을 AI로 일괄 채워 `// ---` frontmatter 블록을 삽입한다. dry-run 기본, --apply 시에만 파일 수정. 범위 한정: --projects (.csproj 단위), --files (명시 파일), --staged (git 스테이징).
argument-hint: "[--projects A.csproj,B.csproj] [--files F.cs ...] [--staged] [--limit N] [--apply] [--allow-dirty]"
---

CodeNavigator frontmatter 자동 생성 명령. `codenav frontmatter gen` CLI 를 호출해 description 빈칸인 C# 클래스에 `// ---` 블록을 삽입한다.

인자: $ARGUMENTS

## 인자 파싱

- `--projects <CSV>` (선택): 처리 범위를 지정한 `.csproj` 의 폴더 트리로 제한. 쉼표 구분. 예: `--projects Mirero.PCC.XLab.Loader.ApiMonitor.csproj,Mirero.PCC.XLab.Loader.Core.csproj`. 접미사 `.csproj` 생략 가능. 대소문자 무시.
- `--files F1.cs F2.cs ...` (선택): 명시 파일만 처리. `--projects` 보다 우선.
- `--staged` (선택): `git diff --cached` 의 `.cs` 만 처리. `--files` 와 함께 사용 가능 (합집합). `--projects` 보다 우선.
- 셋 다 미지정 → repo 전체 스캔 (기존 동작).
- `--limit N` (기본 50): 이 호출에서 처리할 최대 클래스 수. `0` = 무제한 (후보 전부 처리).
- `--apply`: 명시되면 실제 파일 수정. 없으면 dry-run.
- `--allow-dirty`: git working tree 가 dirty 여도 실행. 기본은 거부.
- `--root <path>`: repo root. 기본 cwd.

## 실행 절차

### 0. 사전 체크

1. `codenav` CLI 위치 탐지 (다음 순서):
   - **프로젝트 venv**: `<cwd>/tools/codenavigator/Scripts/codenav.exe` (Windows) 또는 `<cwd>/tools/codenavigator/bin/codenav` (Unix).
   - **launcher**: `<cwd>/codenav.ps1` 존재 시 사용.
   - **PATH 글로벌**: `where codenav` / `which codenav`.
   - 모두 부재 → 다음 안내 후 중단:
     ```
     codenav 가 설치되어있지 않음. 둘 중 하나:

       [프로젝트별 격리 권장]
       python -m venv tools/codenavigator
       tools/codenavigator/Scripts/pip install codenavigator
       # 루트에 codenav.ps1 launcher 작성

       [글로벌]
       pip install codenavigator
     ```
2. `where claude` (PowerShell) / `which claude` (bash) 로 `claude` CLI 존재 확인. 없으면 AI 호출 실패 (`written=0` 예상) — 사용자에게 미리 알림.
3. `--apply` 인자 받은 경우라도 **항상 먼저 dry-run** 한 번 수행.

### 1. Dry-run

```
codenav frontmatter gen --limit <N> [--projects <CSV>|--files F.cs ...|--staged] --verbose
```

stderr 의 `[DRY]` 라인을 수집해 사람이 읽을 표 형식으로 정리:

| 파일 | 라인 | 클래스 | 생성된 description |
|---|---|---|---|

샘플 5개 이내. 전체 카운트 (`scanned_files`, `candidates`, `generated`, `failures`) 도 한 줄로 요약.

### 2. 사용자 확인

사용자가 `--apply` 를 인자로 줬어도, 미리보기 보여준 뒤 한 번 더 확인 받음:
> "위 결과로 적용해도 됩니까? (`/yes` 또는 `apply`)"

응답이 명확한 승인일 때만 다음 단계 진행. "그냥 해", "go", "yes", "apply", "응" 정도면 통과.

### 3. Apply

```
codenav frontmatter gen --limit <N> [--projects <CSV>|--files F.cs ...|--staged] --apply --verbose
```

`--allow-dirty`, `--projects`, `--files`, `--staged` 인자가 있었으면 그대로 전달.

### 4. 사후 보고

- `written` (실제 삽입된 블록 수)
- `failures` (AI 호출 실패한 클래스 — 다음 실행에서 재시도 가능)
- 권장 다음 단계: `codenav reindex --full` 로 SQLite 인덱스 동기화, `git diff` 로 변경 검토.

## 주의

- 이 명령은 **파일을 직접 수정**한다. 실행 전 git working tree 가 깨끗해야 사고 시 `git restore` 로 복원 가능.
- `claude` CLI 가 PATH 에 없으면 AI 호출 실패 → `written=0`. 사용자에게 명확히 알려야 한다.
- 한 번에 50개 초과 처리는 권장 X. 점진 적용.
- 이미 XML doc 또는 frontmatter 있는 클래스는 자동 스킵 (idempotent). 중복 삽입 없음.
