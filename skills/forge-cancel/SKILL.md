---
name: forge-cancel
description: forge-full/scope 작업 브랜치와 phase 산출물을 삭제한다. 파괴적 작업 — 실행 전 사용자 확인 필수. 부트스트랩 후 forge_cancel.py 위임. /claudecode-for-me:forge-cancel 로 실행.
argument-hint: "<phase-dir> [--kind full|scoped] [--dry-run]"
input: phase-dir (kebab-case) + 선택적 --kind / --dry-run
output: feat-<phase-dir> 브랜치 삭제, phases/<kind>/<phase-dir>/ 삭제, index.json 항목 제거
requires-user-interaction: true
---

# Forge Cancel — Skill

`forge-cancel`은 `scripts/forge_cancel.py` 를 통해 진행 중인 forge phase를 취소한다.
**파괴적 작업**이므로 Python 검사 → 부트스트랩 → 사전 확인 → 사용자 승인 → 실행 순서를 반드시 따른다.

---

## 단계 1 — Python 사전 검사

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 없거나 3.10 미만이면 **즉시 중단** 후 아래 메시지 출력:

```
[forge-cancel] Python 3.10 이상이 필요합니다.
설치 방법:
  - Windows: https://www.python.org/downloads/  (PATH 추가 체크 필수)
  - macOS/Linux: pyenv, brew, 또는 패키지 매니저 사용
설치 후 터미널을 재시작하고 다시 시도하세요.
```

---

## 단계 2 — 부트스트랩 (idempotent)

`./scripts/forge_cancel.py` 가 없으면 플러그인에서 복사한다.
기존 파일은 덮어쓰지 않는다.

플러그인 경로는 `${CLAUDE_PLUGIN_ROOT}` 환경변수로 얻는다 (Claude Code가 자동 주입).

복사 대상 (없는 것만):
- `${CLAUDE_PLUGIN_ROOT}/scripts/forge_cancel.py` → `./scripts/forge_cancel.py`
- `${CLAUDE_PLUGIN_ROOT}/scripts/forge_full.py` → `./scripts/forge_full.py`
- `${CLAUDE_PLUGIN_ROOT}/scripts/forge_scope.py` → `./scripts/forge_scope.py`
- `${CLAUDE_PLUGIN_ROOT}/scripts/forge_templates/*` → `./CLAUDE.md`, `./PHASE_SCHEMA.md`, `./FORGE_SCOPE.md`, `./docs/_templates/*`

`./scripts/` 디렉토리가 없으면 먼저 생성한다.

---

## 단계 3 — 인자 파싱

`$ARGUMENTS` 의 첫 토큰을 `<phase-dir>` 로 사용한다.
나머지를 그대로 `forge_cancel.py` 에 전달한다.

`$ARGUMENTS` 가 비어 있으면:
```
[forge-cancel] 사용법: /claudecode-for-me:forge-cancel <phase-dir> [--kind full|scoped] [--dry-run]
```
를 출력하고 중단한다.

---

## 단계 4 — 사전 확인

실행 전 아래 정보를 확인해 사용자에게 명시한다:

1. `phases/full/<phase-dir>` 또는 `phases/scoped/<phase-dir>` 존재 여부
2. `feat-<phase-dir>` 브랜치 존재 여부
3. 현재 브랜치 및 `git status --porcelain` 결과
4. `--kind` 가 없으면 존재하는 쪽을 자동 탐지, 양쪽 모두 있으면 사용자에게 `full`/`scoped` 선택을 묻는다

현재 작업 트리가 dirty이고 현재 브랜치가 `feat-<phase-dir>` 가 아니면 **즉시 중단**한다.
이유: unrelated user changes 삭제 위험이 있다.

---

## 단계 5 — 사용자 확인 (필수)

**사용자 명시 승인 없이 절대 실행하지 않는다.**

아래 대상을 출력하고 확인받는다:

```
삭제 대상:
- branch  : feat-<phase-dir>
- phase dir: phases/<kind>/<phase-dir>/
- index   : phases/<kind>/index.json 의 해당 phase 항목

이 작업은 현재 forge 작업물을 폐기합니다.
진행할까요? [y/N]
```

---

## 단계 6 — 실행

사용자 승인 후 실행한다 (`--yes` 는 스크립트 내부 재확인을 건너뜀):

```bash
python ./scripts/forge_cancel.py <phase-dir> --kind <full|scoped> --yes
```

dry-run 요청 시:
```bash
python ./scripts/forge_cancel.py <phase-dir> --kind <full|scoped> --dry-run
```

스크립트가 자동으로 처리하는 것:
- 현재 브랜치가 `feat-<phase-dir>` 이면 dirty worktree를 폐기하고 base 브랜치(`master` 우선)로 checkout
- `feat-<phase-dir>` 로컬 브랜치 삭제
- `phases/<kind>/<phase-dir>/` 삭제
- `phases/<kind>/index.json` 에서 해당 phase 항목 제거

---

## 금지사항

- remote branch 삭제는 수행하지 않는다 — 원격 삭제가 필요하면 별도 사용자 확인 후 수동 진행
- `feat-<phase-dir>` 외 브랜치를 삭제하지 않는다
- `phases/full`·`phases/scoped` 양쪽에 같은 이름이 있으면 추측하지 않는다
- `docs/**`, `scripts/forge_full.py`, `scripts/forge_scope.py` 는 수정하지 않는다
