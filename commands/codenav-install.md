---
description: 프로젝트 루트의 tools/codenavigator 폴더에 codenavigator (PyPI) 격리 설치 + codenav.ps1/codenav.sh launcher + .gitignore 자동 작성.
argument-hint: "(인자 없음)"
---

codenavigator 도구를 현재 워크스페이스에 격리 설치한다.

## 무엇을 하는가

1. `python --version` 으로 Python 3.11+ 확인.
2. `cwd/tools/codenavigator/` 부재 확인. 이미 있으면 skip + 안내.
3. `python -m venv tools/codenavigator` 로 venv 생성.
4. `tools/codenavigator/Scripts/pip install codenavigator` (Windows) 또는 `tools/codenavigator/bin/pip install codenavigator` (Unix).
5. launcher 작성:
   - `cwd/codenav.ps1` (PowerShell wrapper)
   - `cwd/codenav.sh` (Bash wrapper, chmod +x)
6. `cwd/.gitignore` 에 `tools/codenavigator/` 라인 없으면 추가.
7. **PreToolUse hook 셋업** — `.claude/hooks/codenav-prefer.ps1` 복사 + `.claude/settings.json` 에 hook 정의 merge.
8. **docs/codenav-guide.md 작성**(문서 폴더가 `Docs/` 면 그 폴더 — 8.1) + CLAUDE.md 에 한 줄 + 링크 추가.
9. `tools/codenavigator/Scripts/codenav --help` 검증 (CLI dispatch 동작 확인).
10. 결과 요약.

## 실행 절차 (AI 에이전트 가이드)

### 1. 사전 점검

```bash
python --version    # 또는 py -3 --version
# 3.11 이상 아니면 안내 후 중단:
#   "Python 3.11+ 필요. 현재: <ver>. https://python.org 에서 업그레이드."
```

### 2. 이미 설치 여부 확인

```
Test-Path tools/codenavigator/Scripts/codenav.exe   # Windows
test -f tools/codenavigator/bin/codenav             # Unix
```

존재 → skip + 다음 안내 출력:
```
codenavigator 이미 설치됨: tools/codenavigator/
업그레이드: tools/codenavigator/Scripts/pip install --upgrade codenavigator
재설치: 폴더 삭제 후 /codenav-install 재실행.
```

부재 → 단계 3 진행.

### 3. venv 생성

```bash
python -m venv tools/codenavigator
```

실패 시 `py -3 -m venv tools/codenavigator` fallback.

### 4. PyPI install

Windows:
```powershell
tools\codenavigator\Scripts\pip install --quiet codenavigator
```

Unix:
```bash
tools/codenavigator/bin/pip install --quiet codenavigator
```

실패 시:
- 네트워크 → "PyPI 접근 실패. 프록시/방화벽 확인."
- 패키지 부재 → "PyPI 에서 codenavigator 못 찾음. https://pypi.org/project/codenavigator/ 접근 가능?"

### 5. launcher 작성

`cwd/codenav.ps1` 부재 시 신규 작성:

```powershell
#!/usr/bin/env pwsh
& "$PSScriptRoot\tools\codenavigator\Scripts\codenav.exe" @Args
exit $LASTEXITCODE
```

`cwd/codenav.sh` 부재 시 신규 작성:

```bash
#!/usr/bin/env bash
exec "$(dirname "$0")/tools/codenavigator/bin/codenav" "$@"
```

`chmod +x codenav.sh` (Unix).

### 6. .gitignore 갱신

`cwd/.gitignore` 부재 시 신규 생성. 존재 시 `tools/codenavigator/` 라인 grep → 없으면 append:

```
# codenavigator venv (codenav.ps1 launcher 가 호출)
tools/codenavigator/
```

### 7. PreToolUse hook 셋업

#### 7.1 hook 파일 작성

`cwd/.claude/hooks/codenav-prefer.ps1` 부재 시:

1. `cwd/.claude/hooks/` 폴더 생성 (부재 시).
2. 플러그인 templates 의 `codenav-prefer.ps1` 본문 그대로 복사.
   - 소스: `${CLAUDE_PLUGIN_ROOT}/commands/codenav-templates/codenav-prefer.ps1`
   - Claude Code 가 Read tool 로 플러그인 템플릿 읽고 Write tool 로 사용자 워크스페이스에 작성.

이미 존재 → skip + "`.claude/hooks/codenav-prefer.ps1` 이미 존재" 안내.

#### 7.2 .claude/settings.json merge

`cwd/.claude/settings.json` 처리:

- **부재** → 신규 작성:
  ```json
  {
    "enabledPlugins": {
      "claudecode-for-me@claudecode-for-me": true
    },
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "Grep|Glob",
          "hooks": [
            {
              "type": "command",
              "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\codenav-prefer.ps1\"",
              "timeout": 5
            }
          ]
        }
      ]
    }
  }
  ```
- **존재** → JSON 파싱 → `hooks.PreToolUse` 키 검사:
  - 이미 `codenav-prefer.ps1` 호출하는 hook 있음 → skip + 안내.
  - PreToolUse 키 부재 → 위 hook 객체 추가 (기존 키 보존).
  - 다른 PreToolUse hook 만 있음 → matcher `Grep|Glob` 하위에 codenav-prefer hook 만 append.
- **JSON malformed** → "settings.json JSON parse 실패. 수동 merge 필요." 안내 후 skip.

### 8. <문서 폴더>/codenav-guide.md + CLAUDE.md 셋업

#### 8.1 문서 폴더 결정

문서 폴더 `docs` · `Docs` 는 같은 폴더다 — 레포마다 표기만 다르다. 아래 `<문서 폴더>` 는 디스크에 있는 실제 표기다.

1. `cwd` 바로 아래에 이름이 대소문자 무시로 `docs` 인 폴더(`docs/` · `Docs/` 등)가 하나 있으면 그 폴더를 그대로 쓴다. 표기를 바꾸거나 `docs/` 를 따로 만들지 않는다.
   - 확인: `(Get-ChildItem -Directory -Force | Where-Object Name -ieq 'docs').Name` (PowerShell) · `ls -d */ | grep -ix 'docs/'` (bash — 끝에 `/` 가 붙는다). 찍힌 이름이 `<문서 폴더>` 다.
   - `Test-Path docs` 만으로 정하지 않는다 — Windows·macOS 는 `Docs` 에도 True 라서 실제 표기를 알 수 없다.
2. 이름이 둘 이상 찍히면(대소문자 구분 FS 에서만 생긴다 — 예전 버전이 `Docs` 레포에 `docs/` 를 따로 만든 경우) `docs/` 를 쓴다. `docs_helpers.py` 와 같은 선택이다. 폴더를 옮기거나 합치지 않고, 10 의 결과 요약에 "`docs/` · `Docs/` 공존 — 정리는 사용자 결정" 을 한 줄 보고한다.
3. 하나도 없으면 `cwd/docs/` 를 새로 만든다(새 폴더는 소문자). `<문서 폴더>` = `docs`.

#### 8.2 codenav-guide.md 작성

- `<문서 폴더>/codenav-guide.md` 부재 → 플러그인 templates 의 `CODENAV-GUIDE-TEMPLATE.md` 본문 그대로 복사 (헤더의 `{프로젝트명}` 치환, TEMPLATE 경고 줄 제거).
  - 소스: `${CLAUDE_PLUGIN_ROOT}/commands/codenav-templates/CODENAV-GUIDE-TEMPLATE.md`
- 존재 → skip + "이미 존재. 갱신은 사용자 결정" 안내.

#### 8.3 CLAUDE.md merge

`cwd/CLAUDE.md` 처리:

- **부재** → 신규 작성:
  ```markdown
  # <프로젝트명>

  ## 코드 검색
  - 본 워크스페이스의 클래스/심볼 검색 가이드: [<문서 폴더>/codenav-guide.md](<문서 폴더>/codenav-guide.md)
  ```
  프로젝트명 = `cwd` 디렉토리명 (예: samples_Test). `<문서 폴더>` 는 8.1 의 실제 표기로 치환한다 — `Docs` 레포면 `[Docs/codenav-guide.md](Docs/codenav-guide.md)`.
- **존재** → 본문 grep `codenav-guide` → 부재면 끝에 다음 두 줄 append:
  ```markdown

  ## 코드 검색
  - 본 워크스페이스의 클래스/심볼 검색 가이드: [<문서 폴더>/codenav-guide.md](<문서 폴더>/codenav-guide.md)
  ```
  존재 → skip + "CLAUDE.md 에 이미 codenav-guide 링크 있음" 안내. 단 그 링크의 경로가 `<문서 폴더>/codenav-guide.md` 와 대소문자만 다르면(예전 실행이 `Docs` 레포에 단 `docs/` 링크) 링크의 표시 텍스트와 대상 경로를 실제 표기로 고친다 — 그 링크 밖은 건드리지 않는다. 두 폴더 공존이면 고치지 않는다 — 두 경로가 서로 다른 파일일 수 있다(8.1 의 2).

### 9. 검증

```
./codenav.ps1 --help    # 또는 ./codenav.sh --help
```

기대 출력: `usage: codenav [-h] [--root ROOT] {status,search,reindex,delete,ui,frontmatter} ...`

설치 버전 확인은 별도:
```
tools/codenavigator/Scripts/pip show codenavigator | Select-String Version
```

검증 추가 항목:
- `Test-Path .claude/hooks/codenav-prefer.ps1` → True.
- `Test-Path .claude/settings.json` → True, JSON parse 성공.
- `Test-Path <문서 폴더>/codenav-guide.md` → True.
- `Select-String "codenav-guide" CLAUDE.md` → 매칭.
- `Select-String -CaseSensitive -SimpleMatch "(<문서 폴더>/codenav-guide.md)" CLAUDE.md` → 매칭 — 링크 대상이 실제 표기와 대소문자까지 같다. 매칭이 없으면(두 폴더 공존이라 고치지 않았거나, 사용자가 `./docs/…` 처럼 다른 형식으로 쓴 링크) 결과 요약에 불일치로 보고만 한다 — 8.3 규칙 밖으로 고치지 않는다.

### 10. 결과 요약 (사용자에게)

```
✓ codenavigator <ver> 설치 완료
  위치: <cwd>/tools/codenavigator/
  launcher: codenav.ps1 (Windows) / codenav.sh (Unix)

추가 셋업:
  .claude/hooks/codenav-prefer.ps1   [신규 / 이미 존재]
  .claude/settings.json              [신규 / hook merge / skip]
  <문서 폴더>/codenav-guide.md       [신규 / 이미 존재]
  CLAUDE.md                          [신규 / 링크 append / 링크 표기 수정 / skip]
  ⚠ docs/ · Docs/ 공존 — 정리는 사용자 결정   (8.1 의 2 일 때만)

사용:
  .\codenav.ps1 --root . reindex --full --no-ai
  .\codenav.ps1 --root . search "키워드"

다음 단계:
  /codenav-bootstrap          # baseline 인덱스 생성
  /codenav-frontmatter-gen    # AI 가 description 채움
```

## 주의

- `tools/codenavigator/` 가 venv 라 크기 큼 (~30MB). `.gitignore` 필수.
- 글로벌 `pip install codenavigator` 와 별개. 이 명령은 **프로젝트 격리** 만.
- 다른 프로젝트에서도 사용하려면 그 프로젝트에서 `/codenav-install` 재실행.
- Claude Code 가 sandbox 안에서 `python -m venv` 실패하면 사용자에게 직접 실행 안내:
  ```
  python -m venv tools/codenavigator
  tools/codenavigator/Scripts/pip install codenavigator
  ```
