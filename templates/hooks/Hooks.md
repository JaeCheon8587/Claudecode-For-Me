# Hooks 운영 가이드

> 본 레포는 **pre-commit + pre-push** 훅으로 품질 게이트를 적용한다. 동일 quality 스크립트를 향후 CI에서 그대로 재사용한다.

| 항목 | 값 |
|---|---|
| 설치 명령 | `bash tools/install-hooks.sh` |
| 훅 위치 | `tools/hooks/pre-commit`, `tools/hooks/pre-push` |
| Quality 스크립트 | `tools/quality/{lint,build,test,secret-scan,dependency-check}.sh` (+ `dependency_check.py` 동반) |
| 설치 스코프 | 레포 로컬 (`git config --local core.hooksPath`) |
| 외부 의존 | dotnet SDK, Python 3.10+, [ruff](https://docs.astral.sh/ruff/), [gitleaks](https://github.com/gitleaks/gitleaks) |

---

## 1. 설치

```bash
bash tools/install-hooks.sh
```

수행 작업:
1. `git config --local core.hooksPath tools/hooks` (다른 레포 영향 없음)
2. `chmod +x` 적용 — Windows에서 권한이 추적되지 않으면 install-hooks 출력의 `git update-index --chmod=+x ...` 명령을 1회 실행.
3. 사전 도구 점검 — 부재 시 경고만 출력, install 자체는 성공.

수동 등가 명령:
```bash
git config --local core.hooksPath tools/hooks
```

---

## 2. 사전 도구 (Windows 기준)

| 도구 | 설치 |
|---|---|
| dotnet SDK | `winget install Microsoft.DotNet.SDK.9` 또는 https://dotnet.microsoft.com/download |
| Python 3.10+ | https://www.python.org/downloads/ 또는 pyenv |
| ruff | `pip install ruff` 또는 `winget install astral-sh.ruff` |
| gitleaks | `winget install Gitleaks.Gitleaks` 또는 `scoop install gitleaks` |
| pytest | `python -m pip install pytest` |

macOS는 `brew install gitleaks ruff python@3.10 dotnet`. Linux는 패키지 매니저별 동등 명령.
Python 개발 도구 버전은 레포 루트 `requirements-dev.txt`로 고정한다:

```bash
python -m pip install -r requirements-dev.txt
```

### 왜 필요한가

- `ruff`: Python 스크립트의 포맷, import 정렬, 미사용 import, 기본 lint 위반을 검사한다. C#은 `dotnet format`이 담당하고, Python은 `ruff`가 담당한다.
- `gitleaks`: 커밋/푸시 전에 Git 변경분과 history에서 API key, token, private key, password 같은 secret 패턴을 찾는다. 실제 키를 저장해 대조하는 방식이 아니라, secret처럼 생긴 문자열을 로컬 규칙으로 탐지해 유출을 막는다.

---

## 3. 자동 발화

| 트리거 | 훅 | 검사 |
|---|---|---|
| `git commit` | `pre-commit` | staged 정적 가드 + secret-scan + lint |
| `git push` | `pre-push` | secret-scan(all) + lint(all) + dependency-check(all) + build(all) + test(all) |

목표 시간: pre-commit < 5초(일반 커밋), pre-push < 60초(캐시 따뜻할 때). **첫 실행은 dotnet 분석기·테스트 워밍업으로 더 걸릴 수 있다 — 1회성 비용**.

---

## 4. 수동 실행 (CI에서도 동일)

```bash
# 전체 (CI 워크플로우는 이 5개를 그대로 호출)
bash tools/quality/secret-scan.sh      --all
bash tools/quality/lint.sh             --all
bash tools/quality/dependency-check.sh --all
bash tools/quality/build.sh            --all
bash tools/quality/test.sh             --all

# staged 한정
bash tools/quality/secret-scan.sh --staged
bash tools/quality/lint.sh        --staged
bash tools/quality/lint.sh        --staged --fix     # 자동 수정 (포맷·import 정렬만)
```

`build.sh`/`test.sh`/`dependency-check.sh`는 `--all` 전용. 그 외 인자(없음/`--staged`/임의 문자열) 호출 시 exit 2.

---

## 5. 실패 시 대응

모든 실패는 stderr에 표준 3줄 형식으로 출력된다:

```
FAIL: <check-name>
target: <path-or-test-id>
next: <copy-pasteable command>
```

`next:` 명령을 그대로 실행 → 재커밋/재푸시. 카탈로그:

| check | next 예시 |
|---|---|
| `dotnet-format` | `dotnet format <sln-path> --include <file>` |
| `ruff-format` | `ruff format <file>` |
| `ruff-lint` | `ruff check --fix <file>` 또는 수동 수정 |
| `gitleaks` | (수정 의무) `git restore --staged <file>` 후 secret 제거 — **우회 금지** |
| `dotnet-build` | `dotnet build <sln-path>` |
| `pytest` | `python -m pytest <file>::test_xxx -vv` |
| `size` | `git restore --staged <file>` (>5MB 차단) |
| `bom` | BOM 제거 후 재커밋 |
| `env` | 출력의 install 명령 실행 |
| `env-dotnet` | `winget install Microsoft.DotNet.SDK.9` 또는 https://dotnet.microsoft.com/download |
| `env-python` | https://www.python.org/downloads/ 에서 Python 3.10+ 설치 |
| `env-pip` | `python -m ensurepip --upgrade` 또는 Python 재설치 |
| `env-requirements` | `requirements-dev.txt` 복구 |
| `env-ruff` | `python -m pip install -r requirements-dev.txt` 또는 `winget install astral-sh.ruff` |
| `env-pytest` | `python -m pip install -r requirements-dev.txt` |
| `python-version-pin` | `python -m pip install -r requirements-dev.txt` |
| `python-pip-check` | `python -m pip check` 후 충돌 패키지 해소 (가상환경/사용자 사이트 권장) |
| `python-requirements-resolve` | `python -m pip install -r requirements-dev.txt` |
| `layer-dependency` | `Docs/ARCHITECTURE.md §6.1` (필요 시 §3.2/§4.4/§7.1 carve-out 포함) 참조 방향에 맞게 ProjectReference 제거 또는 의존 방향 수정 |
| `csproj-parse` | csproj XML 구문 확인 — `dotnet build` 출력 참조 |
| `dependency_check.py` | `tools/quality/dependency_check.py` 실행 로그 확인 |

진단 모드: `HOOKS_DEBUG=1 git commit -m wip` → 단계별 stderr 진단 + `set -x`.

---

## 6. `--no-verify` · `HOOKS_SKIP_TESTS` 정책

Git은 `--no-verify`/스킵 환경 변수를 막을 메커니즘이 없다. **본 레포는 정책으로 강제**:

- `git commit --no-verify`: **긴급 hotfix 전용**. 다음 PR 본문에 우회 사유·대체 검증 결과 기록 의무.
- `git push --no-verify`: 동일 정책.
- **secret scan 우회는 어떤 경우에도 금지** — `--no-verify`로 우회된 secret은 즉시 history rewrite 의무.
- `HOOKS_SKIP_TESTS=1`: pre-push의 **test 단계만** 스킵(secret/build/dependency-check는 스킵 불가). 사용 시 stderr `WARN`이 남으며, PR에 사유 기록 의무.
- `dependency-check`도 secret/build와 동일하게 어떤 환경 변수로도 스킵 불가.

---

## 7. CI 재사용

GitHub Actions 등에서 동일 스크립트를 호출:

```yaml
- run: bash tools/quality/secret-scan.sh      --all
- run: bash tools/quality/lint.sh             --all
- run: bash tools/quality/dependency-check.sh --all
- run: bash tools/quality/build.sh            --all
- run: bash tools/quality/test.sh             --all
```

CI 환경에서는 다음 변수가 자동/수동 적용 가능:

- `CI=true` 또는 `NO_COLOR=1` — 색상 비활성.
- `HOOKS_DEBUG=1` — 진단 출력.

---

## 8. 트러블슈팅

### Windows · Git Bash CRLF
훅 스크립트는 LF로 저장돼야 한다. CRLF로 변환되면 `bad interpreter` 또는 `\r: command not found` 오류. 검증:
```bash
git ls-files --eol tools/hooks tools/quality tools/install-hooks.sh
```
모두 `i/lf` 표기여야 한다. CRLF로 보이면 `git config core.autocrlf input` 후 재체크아웃.

### `core.fileMode` 권한
Windows는 기본적으로 `core.fileMode=false`라 `chmod +x` 비트가 추적되지 않는다. install-hooks가 안내하는 `git update-index --chmod=+x ...` 명령을 1회 실행 후 커밋.

### `dotnet format ... --include` 경로 이슈
`git diff`의 POSIX 경로를 그대로 사용. 실패 시 절대 경로로 재시도하거나 `--all`로 폴백:
```bash
bash tools/quality/lint.sh --all
```

### gitleaks 부재
PATH에 없으면 즉시 exit 2. `winget install Gitleaks.Gitleaks` 또는 https://github.com/gitleaks/gitleaks/releases.

### gitleaks v7 이하
`v8` 미만은 `--staged`/`--no-banner` 옵션 동작이 다르다. `gitleaks version`으로 확인 후 v8 이상으로 업그레이드.

### pre-push 시 uncommitted 변경
본 훅은 워킹트리 기준으로 검사하므로, 푸시 대상이 아닌 미커밋 변경의 lint 위반도 차단할 수 있다. push 전에 `git status`로 워킹트리 정리 권장.

---

## 9. 측정값

| 환경 | pre-commit (일반 커밋) | pre-push | 비고 |
|---|---|---|---|
| (환경 기록 후 채울 것) | _측정 후 기록_ | _측정 후 기록_ | 첫 실행 제외 |

기록 방법: `time git commit -m '<메시지>'` 결과를 `real`만 기록. 환경 추가 시 행만 늘릴 것.

---

## 10. 본 작업 범위 외

- E2E·통합 테스트 (CI 전용)
- 커버리지 게이트
- `.editorconfig` 도입
- `.gitattributes` 정책
- GitHub Actions 워크플로우 yaml
- husky/lefthook 등 외부 훅 매니저
- pre-push의 정확한 ref-range 분석 (현재는 워킹트리 단순화)
