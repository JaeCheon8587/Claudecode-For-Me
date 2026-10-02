---
description: 승인된 Intent 로 개발 환경을 구성한다 — 승인 커밋 게이트 · base 브랜치 선택 · 워크트리 생성 · approved→in-dev 전이 · 매니페스트 기록. 여기까지 하고 보고에서 끝낸다. 개발 세션 시작은 사용자가 한다.
argument-hint: "<Intent-doc-path> [--name <slug>] [--base <ref>] [--force]"
---

개발 환경 구성 커맨드. **스펙 세션(메인 repo cwd)에서 실행한다.**

워크트리를 만들어 놓는 것까지가 이 커맨드의 일이다. 개발 절차는 `/forge-scope` 가 워크트리 안에서 수행한다 — 세션의 cwd 는 프로세스 시작 시점에 고정되므로, **워크트리 안에서 개발 세션을 시작하려면 그 전에 워크트리가 존재해야 한다.** 그래서 두 단계로 나눠져 있다.

> **후속 단계를 실행하지 않는다.** 페인·탭을 만들거나, 에이전트를 띄우거나, `/forge-scope` 를 대신 호출하지 않는다. 경로를 보고하고 끝낸다. 어디서 어떤 에이전트로 개발을 시작할지는 사용자가 정한다.

helper 경로:

```bash
FORGE="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

`$ARGUMENTS` 첫 인자 = Intent 경로(`docs/<App>/INTENT/<ID>.md`). `--name <slug>` · `--base <ref>` · `--force` 는 그대로 넘긴다.

Python 3.10+ 확인: `python --version`(없으면 `py -3 --version`). 없으면 중단하고 설치를 안내한다.

---

## 1 — 상태 확인 (판정만)

워크트리에 들어가는 건 디스크 파일이 아니라 **base 커밋의 사본**이다. 승인 직후의 Intent 는 아직 커밋되지 않았으므로 그대로 `init` 을 부르면 게이트에 막힌다(`Intent 가 마지막 커밋에 없다` / `사본이 다르다`, 그리고 dirty 검사).

1. Intent 메타 표의 `상태` 가 `approved` 인지 확인한다. `draft` 면 중단하고 requirement-spec Phase 5 승인을 안내한다. **여기서 Intent 를 고치지 않는다.**
2. Intent 와 카탈로그가 커밋됐는지 본다. **경로를 지정해서** 본다 — 인자 없는 `git status --porcelain` 은 untracked 디렉터리를 `?? docs/` 한 줄로 접어버려 어떤 파일이 빠졌는지 안 보인다:
   ```bash
   git status --porcelain -uall -- docs/<App>/INTENT/<ID>.md docs/<App>/<App>-INT-CATALOG.md
   ```
   카탈로그는 requirement-spec 이 python 을 못 써서 아예 없을 수도 있다 — 그러면 **있는 파일만** 대상으로 한다.
3. 커밋이 필요한지 기억해두고 **2 로 간다.** 커밋은 base 를 정한 뒤에 한다(아래 3 참조).

## 2 — base 브랜치 선택

```bash
python "$FORGE" branches --doc <Intent>
```

읽기 전용이다. stdout 마지막 줄 JSON 을 파싱한다.

- `$ARGUMENTS` 에 `--base <ref>` 가 이미 있으면 **이 단계를 건너뛴다.**
- `target_branch_exists: true` → 브랜치가 이미 있어 분기점을 바꿀 수 없다. **묻지 않고** 3 으로 가되 "resume — base 선택은 적용되지 않는다" 를 한 줄 보고한다.
- `candidates` 가 비어 있으면(커밋 없는 repo) 그대로 3 으로 가서 `init` 게이트 메시지를 받게 한다.
- `recommended_exists: false` → "Intent 가 선언한 base `<x>` 가 로컬·원격에 없다" 를 **먼저 보고**한 뒤 고르게 한다.
- `candidates` 를 표로 보여준다(최대 10행: `ref · kind · sha · date · subject`). 그 뒤 `AskUserQuestion` 1문항 "워크트리를 어느 브랜치에서 분기할까요?" — 옵션 **최대 3개**(도구 상한이 4, `Other` 는 자동 제공):
  1. `recommended`(존재할 때) — 맨 앞 = 기본, 라벨에 `(Intent Handoff)`
  2. `current` HEAD 브랜치 (1번과 같으면 건너뛴다)
  3. 남은 candidates 중 최근 커밋 1개
  - ref 가 길면 라벨은 축약하고 **전체 ref 는 description 에** 적는다.
  - 목록에 더 있으면 "그 밖은 `Other` 로 ref 직접 입력(`origin/*` 포함)" 을 description 에 명시한다.
- 사용자가 고르기 전에는 `--base` 를 붙이지 않는다. **임의 선택 금지.**

## 3 — 승인 커밋 게이트

1 에서 커밋이 필요하다고 판정했으면 여기서 한다. **2 보다 뒤인 이유**: 승인 커밋은 **현재 브랜치(HEAD)** 에 올라가는데, `init` 은 Intent 가 **고른 base 에** 있어야 통과시킨다. 순서를 뒤집으면 base 를 현재 브랜치가 아닌 것으로 고른 순간 `Intent 가 base '<ref>' 에 없다`(exit 2)로 **반드시** 막힌다.

- **이미 커밋돼 있으면** 이 단계를 건너뛴다(`init` 이 base 사본 일치를 검사한다).
- **미커밋 + 고른 base == 현재 브랜치**(`branches` 의 `current`) → `AskUserQuestion` 1회:
  - **승인 커밋** — Intent + 카탈로그 **두 파일만** 스테이징해 `docs(<ID>): Intent 승인` 으로 커밋한다. 그 밖의 파일은 건드리지 않는다.
  - **직접 커밋할게** — 중단하고, 커밋 후 다시 실행하도록 안내한다.
  - **중단**
- **미커밋 + 고른 base ≠ 현재 브랜치** → **중단**한다. 승인 커밋이 그 base 에 올라가지 않아 어차피 게이트에 막힌다. 사용자에게 두 길을 제시한다: ① base 를 현재 브랜치(`current`)로 바꾼다 ② 그 base 브랜치로 체크아웃한 뒤 `/forge-init` 을 다시 실행한다. **대신 체크아웃해주지 않는다.**

커밋 후 `git status --porcelain` 을 다시 보고 **잔여 dirty 파일을 보고**한다. 남아 있으면 `init` 이 dirty 로 막히므로, 그 파일들이 이 Intent 와 무관한지 사용자에게 확인해 `--force` 를 붙일지 정한다. **임의로 `--force` 를 붙이지 않는다.** (워크트리는 base 커밋의 사본이라 dirty 변경은 어차피 따라가지 않는다.)

## 4 — 워크트리 생성

```bash
python "$FORGE" init --doc <Intent> --quiet --base <선택한 ref> [--name <slug>] [--force]
```

- **exit 1** → 작업 공간 상태 문제. stderr 를 그대로 사용자에게 전하고 **중단**, 사용자 결정을 받는다:
  - `메인 repo 작업트리가 dirty` → 3 의 잔여 dirty 처리로 돌아간다. `--force` 는 dirty 파일이 이 Intent 와 무관하다고 **사용자가 명시**했을 때만 붙인다.
  - 브랜치가 다른 워크트리에 붙어 있음 → 그 워크트리를 `/forge-cancel <그 slug>` 로 정리한다(브랜치는 Handoff 로 정해지므로 `--name` 으로는 피할 수 없다. Intent 는 고치지 않는다).
  - `base '<ref>' 를 찾을 수 없다` / `쓸 수 없는 문자` → **2 로 돌아가 재선택.**
  - stale 워크트리 → `git worktree prune` 후 재실행.
  - 등록 안 된 `.worktree/<slug>` 디렉터리 → 사용자가 확인 후 수동 삭제하거나 `git worktree prune` 후 재실행.
- **exit 2** → stderr 사유를 그대로 전하고 **중단**. 게이트를 통과시키려고 Intent 를 고치지 않는다. 흔한 사유:
  - `Intent 상태가 'draft'` → requirement-spec Phase 5 에서 승인.
  - `INT_*` FAIL → requirement-spec 으로 돌아가 수정·재검증.
  - `커밋이 하나도 없다` / `마지막 커밋에 없다` → 3 의 승인 커밋, 또는 프로젝트 골격(소스·테스트·솔루션)을 먼저 커밋. `--force` 로도 우회되지 않는다.
  - `Intent 가 base '<ref>' 에 없다` → 승인 커밋이 다른 브랜치에 올라간 경우다(3 참조). base 를 그 브랜치로 바꾸거나, 그 base 로 체크아웃해 Intent 를 커밋한 뒤 재실행한다.
  - `Intent 가 base 의 사본과 다르다` → 디스크 수정본을 먼저 커밋하게 하거나 다른 base 를 고른다. `--force` 로 우회되지 않는다.
  - `Work Packet·TASK 입력은 … 폐지` → requirement-spec 으로 Intent 를 작성한다.

## 5 — 보고하고 끝낸다

**exit 0** → stdout 마지막 줄이 매니페스트 JSON 이다. `init` 이 이걸 두 곳에 파일로도 남긴다:

- `<worktree>/.process/forge/handoff.json` — 개발 세션이 상대경로로 읽는다
- `<메인 repo>/.process/forge/<slug>.json` — `/forge-cancel` · `list` 가 조회한다

둘 다 `.process/` 아래라 gitignore 대상이다. 매니페스트가 있으면 나중에 브랜치 이름을 추측할 필요가 없다.

다음을 보고한다:

- 워크트리 절대경로 · 브랜치명
- `base` · `base_commit` · `base_applied` — `base_applied: false` 면 브랜치가 이미 있어 분기점이 적용되지 않은 것이므로 한 줄 명시한다
- `status_committed` — `true` 면 신규 시작, `false` 면 **resume**(Intent 가 이미 `in-dev`)
- 매니페스트 두 경로
- `submodule_log` 가 비어 있지 않으면 그대로 전달한다(메인 repo 에 populate 안 된 서브모듈은 링크되지 않고 로그만 남는다)
- `copied` / `skipped` — 가드레일 복사 결과
- **다음 단계 안내 1줄**: "이 워크트리에서 개발 세션을 시작한 뒤 `/forge-scope .process/forge/handoff.json`"
  - 세션을 띄우는 것도 커맨드로 할 수 있다 — 예: `/dispatch-session <워크트리 절대경로> --agent opus-orchestrator --prompt "/forge-scope .process/forge/handoff.json"`. **예시 문장일 뿐 여기서 실행하지 않는다.** 어디에 띄울지는 그 커맨드가 사용자에게 묻는다.

여기서 종료한다. 개발 세션을 띄우지 않는다.

---

## 참고

- 브랜치는 Intent Handoff 의 `브랜치명`(유효한 ref 일 때), 아니면 `intent/<문서 ID>` 다. **분기점(base)과 브랜치 이름은 별개다** — base 는 2 에서 고른 ref 이고, `init` 이 워크트리 Intent 의 Handoff `base branch` 행을 그 값으로 치환해 `in-dev` 전이 커밋에 함께 넣는다.
- `init` 의 `chore(<ID>): 상태 in-dev` 커밋은 스크립트의 결정적 전이다.
- 가드레일 복사(`CLAUDE.md`·`.claude/settings.json`·`.claude/rules`·`Docs`·`docs`)는 base 와 무관하게 **메인 repo 작업트리**에서 온다. 작업 공간 수준 가드레일이라 의도된 동작이다.
- 정리는 `/forge-cancel <slug>` — 메인 repo 에서 실행한다.
