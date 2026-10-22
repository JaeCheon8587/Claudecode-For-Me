---
description: 이름 하나로 개발 환경(워크트리)을 만든다 — base 브랜치 선택 · 워크트리 생성 · 문서 사본 복사 · 매니페스트 기록. Task 는 읽지 않는다. 여기까지 하고 보고에서 끝낸다. 개발 세션 시작은 사용자가 한다.
argument-hint: "<name> [--base <ref>] [--branch <branch>] [--force]"
---

개발 환경 구성 커맨드. **메인 repo cwd 에서 실행한다.**

워크트리를 만들어 놓는 것까지가 이 커맨드의 일이다. 개발은 사용자가 그 워크트리에서 시작한 세션이 한다 — 세션의 cwd 는 프로세스 시작 시점에 고정되므로, **워크트리 안에서 개발 세션을 시작하려면 그 전에 워크트리가 존재해야 한다.** 그래서 두 단계로 나눠져 있다.

> **후속 단계를 실행하지 않는다.** 페인·탭을 만들거나, 에이전트를 띄우거나, 개발을 대신 시작하지 않는다. 경로를 보고하고 끝낸다. 어디서 어떤 에이전트로 개발을 시작할지는 사용자가 정한다.

helper 경로:

```bash
WT_SETUP="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

`$ARGUMENTS` 첫 인자 = 워크트리 이름 — `.worktree/<이름>` 에 만들고 브랜치는 `work/<이름>` 이다. 영문 · 숫자 · `. _ -` 로 쓴다(예: `login-api`). `--base <ref>` · `--branch <branch>` · `--force` 는 그대로 넘긴다. 이름이 없으면 한 줄로 묻는다 — 임의로 짓지 않는다.

**Task 를 읽지 않는다.** 어떤 Task 를 개발할지는 개발 세션에 넣는 프롬프트가 정한다(`/task-split` 이 만들어 준다). 워크트리 하나에서 Task 여러 개를 개발할 수 있다. Task 경로(`.task/TSK-<NNN>.md`)를 인자로 받았으면 쓰지 않고, 이름을 다시 받는다.

> **문서는 커밋하지 않는다.** 문서 폴더(`docs` · `Docs`)와 `.task/` 는 팀 밖으로 나가지 않는 설계 문서다(팀 정책). `init` 이 이 clone 의 `.git/info/exclude` 에 올려 `git add -A` 에도 잡히지 않게 하고, 메인 작업트리의 정본을 워크트리에 **복사**한다. 승인 커밋을 만들거나 문서를 `git add` 하지 않는다. 문서 폴더 표기(`docs` · `Docs`)는 `init` 이 디스크 표기로 맞춘다 — 이 차이로 멈추거나 폴더 이름을 바꾸지 않는다.

Python 3.10+ 확인: `python --version`(없으면 `py -3 --version`). 없으면 중단하고 설치를 안내한다.

---

## 1 — base 브랜치 선택

```bash
python "$WT_SETUP" branches --name <이름> [--branch <branch>]
```

읽기 전용이다. stdout 마지막 줄 JSON 을 파싱한다.

- `$ARGUMENTS` 에 `--base <ref>` 가 이미 있으면 **이 단계를 건너뛴다.**
- `target_branch_exists: true` → 브랜치가 이미 있어 분기점을 바꿀 수 없다. **묻지 않고** 2 로 가되 "resume — base 선택은 적용되지 않는다" 를 한 줄 보고한다.
- `candidates` 가 비어 있으면(커밋 없는 repo) 그대로 2 로 가서 `init` 메시지를 받게 한다.
- `candidates` 를 표로 보여준다(최대 10행: `ref · kind · sha · date · subject`). 그 뒤 `AskUserQuestion` 1문항 "워크트리를 어느 브랜치에서 분기할까요?" — 옵션 **최대 3개**(도구 상한이 4, `Other` 는 자동 제공):
  1. `current` 현재 브랜치 — 맨 앞 = 기본, 라벨에 `(현재 브랜치)`
  2. · 3. 남은 candidates 중 최근 커밋 2개
  - ref 가 길면 라벨은 축약하고 **전체 ref 는 description 에** 적는다.
  - 목록에 더 있으면 "그 밖은 `Other` 로 ref 직접 입력(`origin/*` 포함)" 을 description 에 명시한다.
- 사용자가 고르기 전에는 `--base` 를 붙이지 않는다. **임의 선택 금지.**

## 2 — 워크트리 생성

```bash
python "$WT_SETUP" init <이름> --quiet --base <선택한 ref> [--branch <branch>] [--force]
```

- **exit 1** → 작업 공간 상태 문제. stderr 를 그대로 사용자에게 전하고 **중단**, 사용자 결정을 받는다:
  - `메인 repo 작업트리가 dirty` → 워크트리에는 커밋된 코드만 들어간다. 커밋 · stash 할지, 이 작업과 무관한 변경이라 `--force` 로 갈지 사용자가 정한다. **임의로 `--force` 를 붙이지 않는다.** 문서 폴더 · `.task/` 의 변경은 dirty 로 치지 않는다.
  - 브랜치가 다른 워크트리에 붙어 있음 → 다른 이름이나 `--branch` 로 새 브랜치를 쓰거나, 그 워크트리를 `/worktree-delete <그 slug>` 로 정리한다.
  - `base '<ref>' 를 찾을 수 없다` → **1 로 돌아가 재선택.**
  - `폴더 이름을 만들 수 없다` · `브랜치 이름 … 를 쓸 수 없다` → 이름(또는 `--branch`)을 다시 받는다.
  - stale 워크트리 → `git worktree prune` 후 재실행.
  - 등록 안 된 `.worktree/<이름>` 디렉터리 → 사용자가 확인 후 수동 삭제하거나 `git worktree prune` 후 재실행.
- **exit 2** → `커밋이 하나도 없다` — 프로젝트 골격(소스 · 테스트 · 솔루션)을 먼저 커밋하게 안내하고 **중단**한다. 문서 폴더 · `.task/` 는 커밋하지 않는다. `--force` 로 우회되지 않는다.

## 3 — 보고하고 끝낸다

**exit 0** → stdout 마지막 줄이 매니페스트 JSON 이다. `init` 이 이걸 두 곳에 파일로도 남긴다:

- `<worktree>/.process/worktree/handoff.json` — 개발 세션 참고용(분기점 `base_commit` 등)
- `<메인 repo>/.process/worktree/<slug>.json` — `finish` · `/worktree-delete` · `list` 가 읽고 쓴다

둘 다 `.process/` 아래라 커밋되지 않는다. 매니페스트가 있으면 나중에 브랜치 이름을 추측할 필요가 없다.

다음을 보고한다:

- 워크트리 절대경로 · 브랜치명
- `base` · `base_commit` · `base_applied` — `base_applied: false` 면 브랜치가 이미 있어 분기점이 적용되지 않은 것이므로 한 줄 명시한다
- `created: false` 면 **resume** — 이미 있던 워크트리다. 그 뒤 새로 생긴 문서 파일만 복사됐다
- `copied` / `skipped` — 가드레일 · 문서 사본 복사 결과. `.task/` 가 `skipped` 면 "워크트리에 Task 가 없다 — `/task-split` 으로 Task 를 만든 뒤 이 커맨드를 같은 이름으로 다시 실행하면 복사된다" 를 한 줄 덧붙인다
- `exclude_added` 가 비어 있지 않으면 `info/exclude` 에 올린 항목을 한 줄로
- `tracked_docs` 가 비어 있지 않으면 **경고** — 이미 커밋된 문서라 exclude 로 숨지 않고, 워크트리에는 커밋된 사본이 들어간다. 추적을 끊을지(`git rm --cached`) 사용자가 정한다. **대신 하지 않는다.**
- `submodule_log` 가 비어 있지 않으면 그대로 전달한다(메인 repo 에 populate 안 된 서브모듈은 링크되지 않고 로그만 남는다)
- **다음 단계 안내 3줄**:
  - 개발: "이 워크트리에서 개발 세션을 시작해 `/task-split` 이 준 개발 프롬프트를 넣는다 — 세션은 워크트리의 `.task/TSK-<NNN>.md` 사본을 읽는다"
  - 마감: "Task 하나의 개발 커밋을 마칠 때마다 워크트리 안에서 `python "<WT_SETUP 절대경로>" finish TSK-<NNN>` — 메인 정본 Task `approved → in-review` · Task 카탈로그 재생성. 커밋은 만들지 않는다". `<WT_SETUP 절대경로>` 는 위 helper 경로를 펼친 값으로 쓴다 — 개발 세션이 그대로 붙여 실행할 수 있게.
  - 정리: "브랜치를 머지한 뒤 메인 repo 에서 `/worktree-delete <이름>` — 머지를 확인하고, 마감한 Task 를 `done` 으로 바꾸고 진행 표시를 지운 뒤 워크트리를 지운다"
  - 세션을 띄우는 것도 커맨드로 할 수 있다 — 예: `/dispatch-session <워크트리 절대경로> --agent opus-orchestrator --prompt "<개발 프롬프트>"`. **예시 문장일 뿐 여기서 실행하지 않는다.** 어디에 띄울지는 그 커맨드가 사용자에게 묻는다.

여기서 종료한다. 개발 세션을 띄우지 않는다.

---

## 참고

- 브랜치는 `work/<이름>` 이고 `--branch` 로 바꿀 수 있다. **분기점(base)과 브랜치 이름은 별개다** — base 는 1 에서 고른 ref 이고, 고르지 않았으면 그때의 현재 브랜치다. `/worktree-delete` 가 이 base 에 머지됐는지 본다.
- 문서 사본은 **스냅샷**이다. 워크트리를 만든 뒤 정본을 고쳐도 따라가지 않는다. 새로 만든 Task 파일은 같은 이름으로 다시 실행하면 복사된다(있는 파일은 덮지 않는다).
- 개발 세션은 문서(Task · Intent)를 고치지 않는다 — 사본이라 고쳐도 정본에 반영되지 않는다. 기능이 바뀌어야 하면 메인에서 `requirement-spec` 으로 Intent 를 고치고 `/task-split` 으로 Task 를 다시 만든다. Task 상태는 `finish` 가, 진행 표시는 `/worktree-delete` 가 메인 정본에서 바꾼다.
- 가드레일 복사(`CLAUDE.md`·`.claude/settings.json`·`.claude/rules`)와 문서 사본은 base 와 무관하게 **메인 repo 작업트리**에서 온다. 문서 폴더는 `docs`·`Docs` 중 디스크에 있는 표기 하나로 복사하고 `copied`/`skipped` 에도 그 표기로 1번만 보고한다. 문서 폴더 · `.task/` 는 링크하지 않는다 — 링크가 남은 채 워크트리를 강제로 지우면 정본까지 지워진다.
- 정리는 `/worktree-delete <이름>` — 메인 repo 에서 실행한다.
