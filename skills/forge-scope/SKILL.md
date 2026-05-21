---
name: forge-scope
description: harness_framework forge-scope 경량 phase runner를 사용자 프로젝트에서 실행한다. 첫 호출 시 scripts/forge_*.py、CLAUDE.md、PHASE_SCHEMA.md、FORGE_SCOPE.md、Docs/_templates/ 를 자동 부트스트랩한 뒤 forge_scope.py를 실행한다. /claudecode-for-me:forge-scope 로 실행.
argument-hint: "<prompt> 또는 <doc-path> <prompt> 또는 tdd <doc-path> <prompt> 또는 <phase-dir> [options]"
input: 자유 텍스트 prompt 또는 doc-path + prompt + 선택적 CLI 옵션
output: phases/scoped/<phase-dir>/index.json + step{N}.md 산출물
requires-user-interaction: true
---

# Forge Scope — Skill

`forge-scope`는 `scripts/forge_scope.py` 를 통해 경량 scoped phase 실행을 관장한다.
`forge-full`보다 작은 범위(단일 FRD, 단일 기능, 버그픽스 등)를 빠르게 처리한다.
직접 코드 작성·설계를 수행하지 않고, 부트스트랩 검사 → Python 검사 → 인자 파싱 → 스크립트 실행 순으로 위임한다.

> **재귀 호출 경고**: `forge_scope.py`는 내부적으로 `claude` CLI를 subprocess로 spawn한다.
> 플러그인 명령 자체도 Claude Code 세션에서 실행되므로 중첩 호출이 발생한다.
> 이는 harness_framework의 의도된 동작이며 무한 재귀가 아니다.
> `FORGE_TRUST=1` 또는 `--trust` 없이 실행하면 child claude가 즉시 종료된다.

---

## 단계 1 — Python 사전 검사

아래 순서로 Python 3.10+ 존재를 확인한다.

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 명령이 없거나 버전이 3.10 미만이면 **즉시 중단**하고 사용자에게 아래 메시지를 출력한다:

```
[forge-scope] Python 3.10 이상이 필요합니다.
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
| `scripts/forge_templates/Docs/_templates/*` | `./Docs/_templates/` (각 파일) |

`./scripts/`, `./Docs/_templates/` 디렉토리가 없으면 먼저 생성한다.

부트스트랩 완료 후 복사된 파일 목록과 skip된 파일 목록을 사용자에게 한 번 출력한다.

### 단계 2b — 부트스트랩 산출물 commit (필수)

부트스트랩으로 신규 파일이 복사되었다면 **워크트리 생성 전에 메인 repo에 commit**한다.
워크트리는 현재 HEAD 기준으로 생성되므로 untracked 상태의 부트스트랩 파일은 워크트리에 존재하지 않아 step 실행이 실패한다.

```bash
git add scripts/forge_full.py scripts/forge_scope.py scripts/forge_cancel.py \
        CLAUDE.md PHASE_SCHEMA.md FORGE_SCOPE.md Docs/_templates/ .gitignore
git commit -m "chore: bootstrap forge-scope"
```

복사된 파일이 0개(이미 모두 존재)면 이 단계는 생략한다.

---

## 단계 3 — Git repo 확인 + 워크트리 동작 안내

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

실패(git repo 아님)이면 아래 경고를 출력하되 **중단하지 않고 계속 진행**한다:

```
[forge-scope] 현재 디렉토리가 git repository가 아닙니다.
forge_scope.py는 git worktree 기반으로 동작하므로 git repo 없이는 실행 불가능합니다.
'git init && git commit -m "init"' 으로 git을 초기화한 뒤 다시 시도하세요.
(경고만이며 스크립트는 계속 진행합니다)
```

### 워크트리 동작 요약

`forge_scope.py`는 phase 시작 시 메인 repo 안 `.worktrees/<phase-dir>/` 경로에 git worktree를 생성하고 branch `feat-<phase-dir>`에 attach한다. 다음이 모두 워크트리 안에서 발생한다:

- `phases/scoped/<phase-dir>/index.json` 및 `step{N}.md`
- step 실행으로 작성·수정되는 코드
- 모든 `git commit`

**메인 repo의 작업 트리는 영향을 받지 않는다.** 부모 Claude Code 세션은 메인 repo에 머문다. 완료 후 결과 확인·머지는 워크트리(`.worktrees/<phase-dir>/`)로 이동하거나, 메인에서 `git diff feat-<phase-dir>` / `git merge feat-<phase-dir>`로 수행한다.

워크트리는 phase 완료 후에도 유지된다. 정리는 사용자가 명시적으로 수행한다:

```bash
python scripts/forge_cancel.py <phase-dir> --yes   # 워크트리 + 브랜치 동시 제거
# 또는
git worktree remove .worktrees/<phase-dir> && git branch -D feat-<phase-dir>
```

---

## 단계 4 — 인자 파싱

`$ARGUMENTS`를 두 모드 중 하나로 해석한다.

### Mode 1 — prompt-only
`$ARGUMENTS`가 일반 텍스트로 시작하면 (`/Docs/`·`Docs/` 형식이 아님, 대소문자 무시):

1. `<phase-dir>`을 prompt 핵심 의도 1~3단어 kebab-case로 도출한다 (예: `login-feature`).
2. 사용자에게 phase-dir slug를 한 번 확인한다. 다른 이름을 원하면 그대로 따른다.
3. 실행:
   ```bash
   python ./scripts/forge_scope.py <phase-dir> --trust --yes --quiet \
     --prompt="<전체 $ARGUMENTS>"
   ```

### Mode 2c — TDD (contract-tdd preset)

`$ARGUMENTS` 첫 토큰이 `tdd` (대소문자 무시) 이면 contract-tdd 분기로 진입한다.

1. 첫 토큰 `tdd` 를 소비하고, 두 번째 토큰을 `Docs/...md` 형식 doc-path 로 해석 (Mode 2와 동일 정규화: 앞 `/` 제거, `Docs/` prefix 강제).
2. 나머지 텍스트를 `--prompt` 값으로 사용한다.
3. doc-path 가 부재(첫 토큰이 `tdd` 1개뿐)이거나 형식 위반 시 사용자에게 1회 안내 후 중단:
   ```
   [forge-scope] tdd 모드는 Docs/FRD/<FRD-ID>.md 경로 1개가 필요합니다.
   예: /forge-scope tdd Docs/FRD/F003.md 로그인 인증
   ```
4. `<phase-dir>` 은 FRD ID 또는 doc 파일명 stem 으로 도출한다 (예: `tdd-frd-f003`).
5. 실행:
   ```bash
   python ./scripts/forge_scope.py <phase-dir> --trust --yes --quiet \
     --preset=contract-tdd --compact-docs \
     --doc=<정규화된 doc 경로> \
     --prompt="<나머지 텍스트>"
   ```

> 다수 sln 환경(`Src/*/*.sln` 2개 이상)에서는 `FORGE_DEFAULT_SLN` env 또는 `forge-scope.json` 의 `default_sln` 으로 한 번 지정해두면 `--sln` 명시 불필요 (parent agent 가 자동으로 첨가하지 않음 — 사용자 환경 책임).

---

### Mode 2 — doc + prompt

`$ARGUMENTS`의 첫 토큰이 `/Docs/...md` 또는 `Docs/...md` 형식이면 (대소문자 무시):

- 첫 토큰의 앞 `/`를 제거하고, 경로 prefix를 `Docs/`로 정규화 (예: `/Docs/FRD/FRD-F003.md` → `Docs/FRD/FRD-F003.md`).
- 나머지 텍스트를 `--prompt` 값으로 사용한다.

FRD 파일이면 (`Docs/FRD/` 하위) — **frd-implementation (single-step)**:
```bash
python ./scripts/forge_scope.py <phase-dir> --trust --yes --quiet \
  --preset=frd-implementation --compact-docs \
  --doc=<정규화된 doc 경로> \
  --prompt="<나머지 텍스트>"
```

> FRD를 TDD 흐름(계약→red→green→회귀)으로 처리하려면 `tdd` 토큰을 앞에 붙여 호출한다 — Mode 2c 참고.

일반 문서이면:
```bash
python ./scripts/forge_scope.py <phase-dir> --trust --yes --quiet \
  --single-step --compact-docs \
  --doc=<정규화된 doc 경로> \
  --prompt="<나머지 텍스트>"
```

---

## 단계 5 — 환경변수 및 실행

### 환경변수 상속

| 변수 | 설명 |
|---|---|
| `FORGE_TRUST` | `1` / `true` / `yes` 로 설정 시 `--trust` 와 동일 효과 |
| `FORGE_CLAUDE_TIMEOUT` | step 실행 최대 시간(초). 기본 1800. |
| `ANTHROPIC_API_KEY` | API 키. `--bare` child 모드 사용 시 필수. |

### 실행 패턴

`forge-scope`는 수 분~수십 분이 소요될 수 있으므로 **`run_in_background=true`** 로 호출하고 즉시 turn을 종료한다.
완료 알림이 도착하면 `.worktrees/<phase-dir>/phases/scoped/<phase-dir>/index.json` 을 1회 read하여 최종 상태를 사용자에게 보고한다. (메인 repo의 `phases/scoped/` 에는 산출물이 존재하지 않는다 — 워크트리 안에만 있다.)

완료 보고 시 다음 경로를 사용자에게 명시한다:

- 워크트리: `.worktrees/<phase-dir>/`
- 브랜치: `feat-<phase-dir>`
- index: `.worktrees/<phase-dir>/phases/scoped/<phase-dir>/index.json`

**필수 금지** (부모 세션 토큰 절감):
- `Monitor` 사용 금지
- `ScheduleWakeup`(/loop) 사용 금지
- 진행 확인을 위한 자발적 `git log` / `tail` / `index.json` read 금지 (완료 알림 전)
- `--quiet` 생략 금지

---

## FRD 미결 항목 복구 (EXIT_BLOCKED(2) 수신 시)

`forge_scope.py`가 exit code 2 + stderr에 `§F (FRD 미결 항목 복구 흐름) 절차를 따르라` 메시지를 출력하면, 부모 세션은 `FORGE_SCOPE.md §7` 복구 절차를 따른다 (미결 항목 추출 → 사용자 결정 1회 → docs+코드 변경 → commit → stale 정리 → 재실행).

---

## 옵션 참고

| 옵션 | 설명 |
|---|---|
| `--preset=frd-implementation` | FRD 단건 구현. splitter 없이 single step. 기본 권장. |
| `--preset=auto` | auto-splitter. 여러 레이어 분해가 필요할 때만 사용. |
| `--preset=contract-tdd` | 문서 1개로 contract/red/green/regression 4-step 생성. sln 우선순위: `--sln` CLI > `FORGE_DEFAULT_SLN` env > `forge-scope.json` `default_sln` > auto-detect. 호출 단축형: `/forge-scope tdd <doc> <prompt>` (Mode 2c). |
| `--sln=<path>` | contract-tdd 가 사용할 .sln 경로 (repo root 기준). 미지정 시 `Src/*.sln` (1단계) → `Src/*/*.sln` (2단계) auto-detect. 다수 시 에러 + 후보 목록 출력. |
| `--single-step` | FRD 아닌 일반 단일 작업. |
| `--compact-docs` | 가드레일 문서를 핵심 섹션만 압축 주입. |
| `--yes` | plan 자동 승인. Claude Code spawn 시 항상 포함. |
| `--quiet` | 진행 표시기 억제. Claude Code spawn 시 항상 포함. |
| `--force` | 워크트리 dirty 검사 우회 (재실행 시 워크트리 안 수동 변경 흡수 허용). |
| `--push` | 실행 후 원격 push. |
| `--strict` | placeholder 패턴 발견 시 실패. |
| `--step-model` | step 실행 모델. 기본 `claude-sonnet-4-6`. |
