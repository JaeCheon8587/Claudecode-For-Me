---
name: forge-full
description: harness_framework forge-full phase runner를 사용자 프로젝트에서 실행한다. 첫 호출 시 scripts/forge_*.py、CLAUDE.md、PHASE_SCHEMA.md、FORGE_SCOPE.md、docs/.templates/ 를 자동 부트스트랩한 뒤 forge_full.py를 실행한다. /claudecode-for-me:forge-full 로 실행.
argument-hint: "<phase-dir> [options]"
input: phase-dir (kebab-case) + CLI 옵션 (--prompt, --doc, --docs-mode, --trust, --yes, --quiet, --plan-only, --preset 등)
output: phases/full/<phase-dir>/index.json + step{N}.md 산출물
requires-user-interaction: true
---

# Forge Full — Skill

`forge-full`은 `scripts/forge_full.py` 를 통해 문서 기반 full phase 실행을 관장한다.
직접 코드 작성·설계를 수행하지 않고, 부트스트랩 검사 → Python 검사 → 스크립트 실행 순으로 위임한다.

> **재귀 호출 경고**: `forge_full.py`는 내부적으로 `claude` CLI를 subprocess로 spawn한다.
> 플러그인 명령 자체도 Claude Code 세션에서 실행되므로 중첩 호출이 발생한다.
> 이는 harness_framework의 의도된 동작이며 무한 재귀가 아니다.
> 단, `FORGE_TRUST=1` 또는 `--trust` 없이 실행하면 child claude가 즉시 종료된다.

---

## 단계 1 — Python 사전 검사

아래 순서로 Python 3.10+ 존재를 확인한다.

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 명령이 없거나 버전이 3.10 미만이면 **즉시 중단**하고 사용자에게 아래 메시지를 출력한다:

```
[forge-full] Python 3.10 이상이 필요합니다.
설치 방법:
  - Windows: https://www.python.org/downloads/  (PATH 추가 체크 필수)
  - macOS/Linux: pyenv, brew, 또는 패키지 매니저 사용
설치 후 터미널을 재시작하고 다시 시도하세요.
```

- Python 이 `py -3` 로만 가능한 경우, 이후 모든 `python` 호출을 `py -3` 로 대체한다.

---

## 단계 2 — 부트스트랩 (idempotent)

사용자 cwd에 아래 파일·디렉토리가 없으면 플러그인 내장 템플릿에서 복사한다.
**기존 파일은 절대 덮어쓰지 않는다** — 존재 시 skip 후 사용자에게 알린다.

플러그인 경로는 `${CLAUDE_PLUGIN_ROOT}` 환경변수로 얻는다 (Claude Code가 자동 주입).

| 복사 원본 (`${CLAUDE_PLUGIN_ROOT}/…`) | 복사 대상 (cwd 기준) |
|---|---|
| `scripts/forge_full.py` | `./scripts/forge_full.py` |
| `scripts/forge_scope.py` | `./scripts/forge_scope.py` |
| `scripts/forge_cancel.py` | `./scripts/forge_cancel.py` |
| `scripts/forge_templates/CLAUDE.md` | `./CLAUDE.md` |
| `scripts/forge_templates/PHASE_SCHEMA.md` | `./PHASE_SCHEMA.md` |
| `scripts/forge_templates/FORGE_SCOPE.md` | `./FORGE_SCOPE.md` |
| `scripts/forge_templates/docs/.templates/*` | `./docs/.templates/` (각 파일) |

`./scripts/`, `./docs/.templates/` 디렉토리가 없으면 먼저 생성한다.

부트스트랩 완료 후 복사된 파일 목록과 skip된 파일 목록을 사용자에게 한 번 출력한다.

---

## 단계 3 — Git repo 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

실패(git repo 아님)이면 아래 경고를 출력하되 **중단하지 않고 계속 진행**한다:

```
[forge-full] 현재 디렉토리가 git repository가 아닙니다.
forge_full.py의 브랜치 자동 생성(feat-<phase>) 및 커밋 기능이 실패할 수 있습니다.
계속 진행하려면 먼저 'git init && git commit -m "init"' 을 실행하세요.
(경고만이며 스크립트는 계속 진행합니다)
```

---

## 단계 4 — 인자 파싱 및 실행

`$ARGUMENTS` 를 그대로 `forge_full.py` 에 전달한다.
`$ARGUMENTS` 가 비어 있으면 `--help` 를 전달해 사용법을 출력한다.

### 환경변수

child 프로세스에 다음 환경변수를 상속시킨다 (부모 세션에 없으면 무시):

| 변수 | 설명 |
|---|---|
| `FORGE_TRUST` | `1` / `true` / `yes` 로 설정 시 `--trust` 와 동일 효과 |
| `FORGE_CLAUDE_TIMEOUT` | step 실행 최대 시간(초). 기본 1800. |
| `ANTHROPIC_API_KEY` | API 키. `--bare` child 모드 사용 시 필수. |

### 실행 패턴

`forge-full`은 시간이 오래 걸리므로 **`run_in_background=true`** 로 호출하고 즉시 turn을 종료한다.
완료 알림이 도착하면 `phases/full/<phase-dir>/index.json` 을 1회 read하여 최종 상태를 사용자에게 보고한다.

```bash
# 기본 실행 (fire-and-forget)
python ./scripts/forge_full.py <phase-dir> --trust --yes --quiet $ARGUMENTS_REMAINDER

# plan 미리보기만
python ./scripts/forge_full.py <phase-dir> --trust --plan-only $ARGUMENTS_REMAINDER
```

**필수**: `--quiet --yes` 는 Claude Code가 spawn할 때 항상 포함한다 (부모 세션 토큰 절감).
사용자가 터미널에서 직접 실행하면 `--quiet` 없이 실행 가능하다고 안내한다.

---

## 워크플로우 참조

`forge-full`의 탐색(§A), 논의(§B), Step 설계(§C), 파일 생성(§D), 실행(§E) 전체 상세는
`PHASE_SCHEMA.md`와 원본 `.claude/commands/forge-full.md` 명세를 따른다.
본 스킬은 흐름(부트스트랩→실행)만 관장하며, 구현 규칙은 해당 문서에 위임한다.
