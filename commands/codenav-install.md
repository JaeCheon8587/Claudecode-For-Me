---
description: 프로젝트 루트의 Tools/codenavigator 폴더에 codenavigator (PyPI) 격리 설치 + codenav.ps1/codenav.sh launcher + .gitignore 자동 작성.
argument-hint: "(인자 없음)"
---

codenavigator 도구를 현재 워크스페이스에 격리 설치한다.

## 무엇을 하는가

1. `python --version` 으로 Python 3.11+ 확인.
2. `cwd/Tools/codenavigator/` 부재 확인. 이미 있으면 skip + 안내.
3. `python -m venv Tools/codenavigator` 로 venv 생성.
4. `Tools/codenavigator/Scripts/pip install codenavigator` (Windows) 또는 `Tools/codenavigator/bin/pip install codenavigator` (Unix).
5. launcher 작성:
   - `cwd/codenav.ps1` (PowerShell wrapper)
   - `cwd/codenav.sh` (Bash wrapper, chmod +x)
6. `cwd/.gitignore` 에 `Tools/codenavigator/` 라인 없으면 추가.
7. `Tools/codenavigator/Scripts/codenav --version` (또는 launcher 통해) 검증.
8. 결과 요약 (설치 경로, 사용법 한 줄).

## 실행 절차 (AI 에이전트 가이드)

### 1. 사전 점검

```bash
python --version    # 또는 py -3 --version
# 3.11 이상 아니면 안내 후 중단:
#   "Python 3.11+ 필요. 현재: <ver>. https://python.org 에서 업그레이드."
```

### 2. 이미 설치 여부 확인

```
Test-Path Tools/codenavigator/Scripts/codenav.exe   # Windows
test -f Tools/codenavigator/bin/codenav             # Unix
```

존재 → skip + 다음 안내 출력:
```
codenavigator 이미 설치됨: Tools/codenavigator/
업그레이드: Tools/codenavigator/Scripts/pip install --upgrade codenavigator
재설치: 폴더 삭제 후 /codenav-install 재실행.
```

부재 → 단계 3 진행.

### 3. venv 생성

```bash
python -m venv Tools/codenavigator
```

실패 시 `py -3 -m venv Tools/codenavigator` fallback.

### 4. PyPI install

Windows:
```powershell
Tools\codenavigator\Scripts\pip install --quiet codenavigator
```

Unix:
```bash
Tools/codenavigator/bin/pip install --quiet codenavigator
```

실패 시:
- 네트워크 → "PyPI 접근 실패. 프록시/방화벽 확인."
- 패키지 부재 → "PyPI 에서 codenavigator 못 찾음. https://pypi.org/project/codenavigator/ 접근 가능?"

### 5. launcher 작성

`cwd/codenav.ps1` 부재 시 신규 작성:

```powershell
#!/usr/bin/env pwsh
& "$PSScriptRoot\Tools\codenavigator\Scripts\codenav.exe" @Args
exit $LASTEXITCODE
```

`cwd/codenav.sh` 부재 시 신규 작성:

```bash
#!/usr/bin/env bash
exec "$(dirname "$0")/Tools/codenavigator/bin/codenav" "$@"
```

`chmod +x codenav.sh` (Unix).

### 6. .gitignore 갱신

`cwd/.gitignore` 부재 시 신규 생성. 존재 시 `Tools/codenavigator/` 라인 grep → 없으면 append:

```
# codenavigator venv (codenav.ps1 launcher 가 호출)
Tools/codenavigator/
```

### 7. 검증

```
./codenav.ps1 --version    # 또는 ./codenav.sh --version
```

기대 출력: `codenav 1.x.x` 또는 codenavigator 패키지 버전.

### 8. 결과 요약 (사용자에게)

```
✓ codenavigator <ver> 설치 완료
  위치: <cwd>/Tools/codenavigator/
  launcher: codenav.ps1 (Windows) / codenav.sh (Unix)

사용:
  .\codenav.ps1 --root . reindex --full --no-ai
  .\codenav.ps1 --root . search "키워드"

다음 단계:
  /codenav-bootstrap          # baseline 인덱스 생성
  /codenav-frontmatter-gen    # AI 가 description 채움
```

## 주의

- `Tools/codenavigator/` 가 venv 라 크기 큼 (~30MB). `.gitignore` 필수.
- 글로벌 `pip install codenavigator` 와 별개. 이 명령은 **프로젝트 격리** 만.
- 다른 프로젝트에서도 사용하려면 그 프로젝트에서 `/codenav-install` 재실행.
- Claude Code 가 sandbox 안에서 `python -m venv` 실패하면 사용자에게 직접 실행 안내:
  ```
  python -m venv Tools/codenavigator
  Tools/codenavigator/Scripts/pip install codenavigator
  ```
