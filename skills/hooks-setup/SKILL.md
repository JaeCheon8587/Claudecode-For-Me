---
name: hooks-setup
description: harness_framework hooks 12개(pre-commit/pre-push/quality scripts)를 사용자 프로젝트에 적응 배치한다. /claudecode-for-me:hooks-setup 으로 실행.
argument-hint: "[--trust] [--yes] [--quiet]"
input: 선택적 CLI 옵션
output: tools/hooks/, tools/quality/, Hooks.md, install-hooks.sh, ruff.toml, requirements-dev.txt
requires-user-interaction: true
---

# Hooks Setup — Skill

`hooks-setup`는 `scripts/hooks_setup.py` 를 통해 harness_framework hooks 12개를 사용자 프로젝트에 적응 배치한다.
직접 파일을 작성하지 않고, 사전 검사 → 부트스트랩 → 스크립트 실행 순으로 위임한다.

> **재귀 호출 경고**: `hooks_setup.py`는 내부적으로 `claude` CLI를 subprocess로 spawn한다 (파일당 1회, 총 12회).
> 플러그인 명령 자체도 Claude Code 세션에서 실행되므로 중첩 호출이 발생한다.
> 이는 의도된 동작이며 무한 재귀가 아니다.
> `FORGE_TRUST=1` 또는 `--trust` 없이 실행하면 hooks_setup.py가 즉시 종료된다.

---

## 단계 1 — Python 사전 검사

아래 순서로 Python 3.10+ 존재를 확인한다.

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 명령이 없거나 버전이 3.10 미만이면 **즉시 중단**하고 사용자에게 아래 메시지를 출력한다:

```
[hooks-setup] Python 3.10 이상이 필요합니다.
설치 방법:
  - Windows: https://www.python.org/downloads/  (PATH 추가 체크 필수)
  - macOS/Linux: pyenv, brew, 또는 패키지 매니저 사용
설치 후 터미널을 재시작하고 다시 시도하세요.
```

- Python 이 `py -3` 로만 가능한 경우, 이후 모든 `python` 호출을 `py -3` 로 대체한다.

---

## 단계 2 — claude CLI 검사

```bash
claude --version 2>&1
```

- 명령이 없으면 **즉시 중단**하고 사용자에게 출력한다:

```
[hooks-setup] claude CLI를 찾을 수 없습니다.
설치: https://docs.claude.com/en/docs/claude-code
설치 후 터미널을 재시작하고 다시 시도하세요.
```

---

## 단계 3 — 부트스트랩 (idempotent)

사용자 cwd에 아래 파일·디렉토리가 없으면 플러그인 내장 템플릿에서 복사한다.
**기존 파일은 절대 덮어쓰지 않는다** — 존재 시 skip 후 사용자에게 알린다.

플러그인 경로는 `${CLAUDE_PLUGIN_ROOT}` 환경변수로 얻는다 (Claude Code가 자동 주입).

| 복사 원본 (`${CLAUDE_PLUGIN_ROOT}/…`) | 복사 대상 (cwd 기준) |
|---|---|
| `scripts/hooks_setup.py` | `./scripts/hooks_setup.py` |
| `templates/hooks/` (전체 12파일) | `./.hooks_setup_staging/templates/hooks/` (각 파일) |

`./scripts/`, `./.hooks_setup_staging/templates/hooks/` 디렉토리가 없으면 먼저 생성한다.

부트스트랩 완료 후 복사된 파일 목록과 skip된 파일 목록을 사용자에게 한 번 출력한다.

---

## 단계 4 — Git repo 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

실패(git repo 아님)이면 아래 경고를 출력하되 **중단하지 않고 계속 진행**한다:

```
[hooks-setup] 현재 디렉토리가 git repository가 아닙니다.
hooks_setup.py의 브랜치·커밋 기능이 실패할 수 있습니다.
계속 진행하려면 먼저 'git init && git commit -m "init"' 을 실행하세요.
(경고만이며 스크립트는 계속 진행합니다)
```

---

## 단계 5 — 인자 파싱

`$ARGUMENTS`에서 `--trust`, `--yes`, `--quiet` 를 그대로 추출한다.
인자가 없으면 기본값 `--trust --yes --quiet` 를 사용한다.

---

## 단계 6 — 실행

`hooks-setup`는 12회 claude spawn으로 수 분~20분 소요될 수 있으므로 **`run_in_background=true`** 로 호출하고 즉시 turn을 종료한다.

```bash
python ./scripts/hooks_setup.py --trust --yes --quiet
```

완료 알림이 도착하면 `phases/hooks-setup/state.json` 을 1회 read하여 완료/실패 항목을 사용자에게 보고한다.

**필수 금지** (부모 세션 토큰 절감):
- `Monitor` 사용 금지
- `ScheduleWakeup`(/loop) 사용 금지
- 진행 확인을 위한 자발적 read 금지 (완료 알림 전)
- `--quiet` 생략 금지

---

## 단계 7 — install-hooks.sh (별도 동의 단계)

백그라운드 완료 후:

1. 사용자에게 `tools/install-hooks.sh` 실행 여부를 1회 확인한다.
2. 동의하면: `bash tools/install-hooks.sh` 실행.
3. 완료 후 `git config --local --get core.hooksPath` 로 설정 확인 및 보고.

install-hooks.sh는 `git config --local core.hooksPath tools/hooks` 를 설정하므로 사전 동의 필수.

---

## 재실행 멱등성

동일 명령 재호출 시 `phases/hooks-setup/state.json` 의 `completed` 항목은 자동 skip된다.
`error` 또는 `pending` 항목만 재시도한다.
