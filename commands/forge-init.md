---
description: 승인된 Task 로 개발 환경을 구성한다 — 승인 커밋 게이트 · base 브랜치 선택 · 워크트리 생성 · approved→in-dev 전이 · 매니페스트 기록. 여기까지 하고 보고에서 끝낸다. 개발 세션 시작은 사용자가 한다.
argument-hint: "<Task-doc-path> [--name <slug>] [--base <ref>] [--force]"
---

개발 환경 구성 커맨드. **스펙 세션(메인 repo cwd)에서 실행한다.**

워크트리를 만들어 놓는 것까지가 이 커맨드의 일이다. 개발은 사용자가 그 워크트리에서 시작한 세션이 한다 — 세션의 cwd 는 프로세스 시작 시점에 고정되므로, **워크트리 안에서 개발 세션을 시작하려면 그 전에 워크트리가 존재해야 한다.** 그래서 두 단계로 나눠져 있다.

> **후속 단계를 실행하지 않는다.** 페인·탭을 만들거나, 에이전트를 띄우거나, 개발을 대신 시작하지 않는다. 경로를 보고하고 끝낸다. 어디서 어떤 에이전트로 개발을 시작할지는 사용자가 정한다.

helper 경로:

```bash
FORGE="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

`$ARGUMENTS` 첫 인자 = Task 경로(`.task/TSK-<NNN>.md`, 레포 루트). `--name <slug>` · `--base <ref>` · `--force` 는 그대로 넘긴다.

입력은 **Task** 다. Intent(`docs/<App>/INTENT/<ID>.md`)는 기능 문서라 개발 입력이 아니다 — 기능이 바뀌면 Intent 를 먼저 고쳐 바뀐 항목에 진행 표시(`[TSK-<NNN> 진행 중]` · `[TSK-<NNN> 삭제 예정]`)를 붙이고, 그 항목을 Task 의 Scope 로 옮겨 승인한다. Task 메타 `대상 Intent` 가 이 작업이 고친 Intent 목록이다(App 이 여럿일 수 있다).

> **문서 폴더 `docs` · `Docs` 는 같은 폴더다.** 레포마다 표기가 다를 뿐이다 — 이 문서의 `docs/` 는 둘 다를 뜻한다(대상 Intent 경로에 해당한다. `.task/` 는 소문자 하나뿐이다). `branches` · `init` 이 디스크 표기와 커밋된 표기로 알아서 맞춘다(탐색기에서 폴더 이름만 바꿔 둘이 어긋난 레포 포함). 이 차이로 멈추거나 사용자에게 묻지 않고, 폴더 이름을 바꾸지도 않는다.

Python 3.10+ 확인: `python --version`(없으면 `py -3 --version`). 없으면 중단하고 설치를 안내한다.

---

## 1 — 상태 확인 (판정만)

워크트리에 들어가는 건 디스크 파일이 아니라 **base 커밋의 사본**이다. 승인 직후의 Task 와 진행 표시를 붙인 Intent 는 아직 커밋되지 않았으므로 그대로 `init` 을 부르면 게이트에 막힌다(`Task 가 마지막 커밋에 없다` / `사본과 다르다`, 그리고 dirty 검사).

1. Task 메타 표의 `상태` 가 `approved` 인지 확인한다. `draft` 면 중단하고 Task 승인(메타 `상태` · `승인` · `검증` 행)을 안내한다. **여기서 Task 를 고치지 않는다.** Intent 도 고치지 않는다.
2. Task 를 검사한다 — 승인 커밋을 한 뒤에 `init` 게이트에서 막히지 않도록 여기서 먼저 잡는다:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" check-task --repo . --file .task/TSK-<NNN>.md
   ```
   `FAIL` 이 하나라도 있으면 그 줄을 그대로 보고하고 **중단**한다. 형식뿐 아니라 대상 Intent 대조(Scope 문장 = Intent 문장, 진행 표시, 다른 Task 와의 충돌, 대상 Intent 의 Open questions)까지 본다. `WARN` 은 보고만 하고 계속한다.
3. Task · 대상 Intent · 두 카탈로그가 커밋됐는지 본다. **경로를 지정해서** 본다 — 인자 없는 `git status --porcelain` 은 untracked 디렉터리를 `?? .task/` · `?? docs/` 한 줄로 접어버려 어떤 파일이 빠졌는지 안 보인다:
   ```bash
   git status --porcelain -uall -- '.task/TSK-<NNN>.md' '.task/task-catalog.md' ':(icase)docs/<App>/INTENT/<ID>.md' ':(icase)docs/<App>/<App>-INT-CATALOG.md'
   ```
   `대상 Intent` 마다 뒤의 두 경로(Intent · 그 App 의 INT 카탈로그)를 반복한다. `:(icase)` 를 빼지 않는다 — git 은 경로를 대소문자 구분으로 비교해서, 문서 폴더가 `Docs` 인 레포에 `docs/…` 로 물으면 이미 커밋된 파일의 변경(카탈로그 등)이 출력에서 빠진다(Linux 에서는 전부). 그러면 승인 커밋이 빠지거나 일부만 들어가 `init` 이 dirty·게이트에서 멈춘다. 출력에 찍힌 경로를 3 에서 그대로 스테이징한다.
4. 커밋이 필요한지 기억해두고 **2 로 간다.** 커밋은 base 를 정한 뒤에 한다(아래 3 참조).

## 2 — base 브랜치 선택

```bash
python "$FORGE" branches --doc <Task>
```

읽기 전용이다. stdout 마지막 줄 JSON 을 파싱한다.

- `$ARGUMENTS` 에 `--base <ref>` 가 이미 있으면 **이 단계를 건너뛴다.**
- `target_branch_exists: true` → 브랜치가 이미 있어 분기점을 바꿀 수 없다. **묻지 않고** 3 으로 가되 "resume — base 선택은 적용되지 않는다" 를 한 줄 보고한다.
- `candidates` 가 비어 있으면(커밋 없는 repo) 그대로 3 으로 가서 `init` 게이트 메시지를 받게 한다.
- `recommended_exists: false` → "Task 가 선언한 base `<x>` 가 로컬·원격에 없다" 를 **먼저 보고**한 뒤 고르게 한다.
- `candidates` 를 표로 보여준다(최대 10행: `ref · kind · sha · date · subject`). 그 뒤 `AskUserQuestion` 1문항 "워크트리를 어느 브랜치에서 분기할까요?" — 옵션 **최대 3개**(도구 상한이 4, `Other` 는 자동 제공):
  1. `recommended`(존재할 때) — 맨 앞 = 기본, 라벨에 `(Task Handoff)`
  2. `current` HEAD 브랜치 (1번과 같으면 건너뛴다)
  3. 남은 candidates 중 최근 커밋 1개
  - ref 가 길면 라벨은 축약하고 **전체 ref 는 description 에** 적는다.
  - 목록에 더 있으면 "그 밖은 `Other` 로 ref 직접 입력(`origin/*` 포함)" 을 description 에 명시한다.
- 사용자가 고르기 전에는 `--base` 를 붙이지 않는다. **임의 선택 금지.**

## 3 — 승인 커밋 게이트

1 에서 커밋이 필요하다고 판정했으면 여기서 한다. **2 보다 뒤인 이유**: 승인 커밋은 **현재 브랜치(HEAD)** 에 올라가는데, `init` 은 Task · 대상 Intent 가 **고른 base 에** 있어야 통과시킨다. 순서를 뒤집으면 base 를 현재 브랜치가 아닌 것으로 고른 순간 `Task 가 base '<ref>' 에 없다`(exit 2)로 **반드시** 막힌다.

- **이미 커밋돼 있으면** 이 단계를 건너뛴다(`init` 이 base 사본 일치를 검사한다).
- **미커밋 + 고른 base == 현재 브랜치**(`branches` 의 `current`) → `AskUserQuestion` 1회:
  - **승인 커밋** — 아래 순서로 `docs(<ID>): Task 승인` 커밋을 만든다. 그 밖의 파일은 건드리지 않는다.
    1. 생성물 두 종을 다시 만든다 — 카탈로그는 Task · Intent 에서 파생하는 인덱스라 손으로 고치지 않고, 다시 만드는 것은 Task · Intent 를 고치는 것이 아니다:
       ```bash
       python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" task-catalog --repo . --write
       python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" intent-catalog --repo . --app <App> --write   # 대상 Intent 의 App 마다
       ```
    2. 1-3 의 경로 지정 `git status` 를 다시 실행한다 — 처음 생긴 카탈로그도 여기서 잡힌다.
    3. 찍힌 경로(Task · task-catalog · 진행 표시를 붙인 Intent · INT 카탈로그)를 그대로 `git add -- <경로>` 해 커밋한다 — 표기를 바꿔 쓰면(`Docs` ↔ `docs`) 이미 커밋된 파일이 스테이징에서 빠진다 — Windows·macOS 에서는 오류도 없이.
  - **직접 커밋할게** — 중단하고, 커밋 후 다시 실행하도록 안내한다.
  - **중단**
- **미커밋 + 고른 base ≠ 현재 브랜치** → **중단**한다. 승인 커밋이 그 base 에 올라가지 않아 어차피 게이트에 막힌다. 사용자에게 두 길을 제시한다: ① base 를 현재 브랜치(`current`)로 바꾼다 ② 그 base 브랜치로 체크아웃한 뒤 `/forge-init` 을 다시 실행한다. **대신 체크아웃해주지 않는다.**

커밋 후 `git status --porcelain` 을 다시 보고 **잔여 dirty 파일을 보고**한다. 남아 있으면 `init` 이 dirty 로 막히므로, 그 파일들이 이 Task 와 무관한지 사용자에게 확인해 `--force` 를 붙일지 정한다. **임의로 `--force` 를 붙이지 않는다.** (워크트리는 base 커밋의 사본이라 dirty 변경은 어차피 따라가지 않는다.)

## 4 — 워크트리 생성

```bash
python "$FORGE" init --doc <Task> --quiet --base <선택한 ref> [--name <slug>] [--force]
```

- **exit 1** → 작업 공간 상태 문제. stderr 를 그대로 사용자에게 전하고 **중단**, 사용자 결정을 받는다:
  - `메인 repo 작업트리가 dirty` → 3 의 잔여 dirty 처리로 돌아간다. `--force` 는 dirty 파일이 이 Task 와 무관하다고 **사용자가 명시**했을 때만 붙인다.
  - 브랜치가 다른 워크트리에 붙어 있음 → 그 워크트리를 `/forge-cancel <그 slug>` 로 정리한다(브랜치는 Task Handoff 로 정해지므로 `--name` 으로는 피할 수 없다. Task 는 고치지 않는다).
  - `base '<ref>' 를 찾을 수 없다` / `쓸 수 없는 문자` → **2 로 돌아가 재선택.**
  - stale 워크트리 → `git worktree prune` 후 재실행.
  - 등록 안 된 `.worktree/<slug>` 디렉터리 → 사용자가 확인 후 수동 삭제하거나 `git worktree prune` 후 재실행.
- **exit 2** → stderr 사유를 그대로 전하고 **중단**. 게이트를 통과시키려고 Task · Intent 를 고치지 않는다. 흔한 사유:
  - `Task 상태가 'draft'` → Task 를 승인한다(메타 `상태` · `승인` · `검증`).
  - `TSK_*` FAIL → `docs_helpers.py check-task` 로 확인하고, Task · Intent 를 고쳐 다시 승인한다.
  - `커밋이 하나도 없다` / `마지막 커밋에 없다` → 3 의 승인 커밋, 또는 프로젝트 골격(소스·테스트·솔루션)을 먼저 커밋. `--force` 로도 우회되지 않는다.
  - `Task 가 base '<ref>' 에 없다` · `Intent 가 base '<ref>' 에 없다` → 승인 커밋이 다른 브랜치에 올라간 경우다(3 참조). base 를 그 브랜치로 바꾸거나, 그 base 로 체크아웃해 승인 커밋을 만든 뒤 재실행한다.
  - `… base 의 사본과 다르다` → 디스크 수정본(Task 또는 진행 표시를 붙인 Intent)을 먼저 커밋하게 하거나 다른 base 를 고른다. `--force` 로 우회되지 않는다.
  - `Intent 는 기능 문서라 개발 입력이 아니다` → Intent 경로를 넣었다. 바뀐 항목을 Task 로 옮겨 승인하고 그 Task 경로를 넣는다.
  - `Work Packet·TASK 입력은 … 폐지` → 옛 0.x 문서를 넣었다. Task 경로를 넣는다.

## 5 — 보고하고 끝낸다

**exit 0** → stdout 마지막 줄이 매니페스트 JSON 이다. `init` 이 이걸 두 곳에 파일로도 남긴다:

- `<worktree>/.process/forge/handoff.json` — 개발 세션이 상대경로로 읽는다
- `<메인 repo>/.process/forge/<slug>.json` — `/forge-cancel` · `list` 가 조회한다

둘 다 `.process/` 아래라 gitignore 대상이다. 매니페스트가 있으면 나중에 브랜치 이름을 추측할 필요가 없다.

다음을 보고한다:

- 워크트리 절대경로 · 브랜치명
- `base` · `base_commit` · `base_applied` — `base_applied: false` 면 브랜치가 이미 있어 분기점이 적용되지 않은 것이므로 한 줄 명시한다
- `status_committed` — `true` 면 신규 시작, `false` 면 **resume**(Task 가 이미 `in-dev`)
- `intents` — 대상 Intent 와 워크트리 안 경로 (개발 세션이 읽는다)
- 매니페스트 두 경로
- `submodule_log` 가 비어 있지 않으면 그대로 전달한다(메인 repo 에 populate 안 된 서브모듈은 링크되지 않고 로그만 남는다)
- `copied` / `skipped` — 가드레일 복사 결과
- **다음 단계 안내 2줄**:
  - 개발: "이 워크트리에서 개발 세션을 시작해 개발을 지시한다 — 작업 계약은 워크트리 Task 와 매니페스트 `.process/forge/handoff.json`"
  - 마감: "개발 커밋을 마친 뒤 워크트리 안에서 `python "<FORGE 절대경로>" finish` — 진행 표시 정리 · Task `in-dev → in-review` · 카탈로그 재생성 · 커밋 1개". `<FORGE 절대경로>` 는 위 helper 경로를 펼친 값으로 쓴다 — 개발 세션이 그대로 붙여 실행할 수 있게.
  - 세션을 띄우는 것도 커맨드로 할 수 있다 — 예: `/dispatch-session <워크트리 절대경로> --agent opus-orchestrator --prompt "<작업 지시>"`. **예시 문장일 뿐 여기서 실행하지 않는다.** 어디에 띄울지는 그 커맨드가 사용자에게 묻는다.

여기서 종료한다. 개발 세션을 띄우지 않는다.

---

## 참고

- 브랜치는 Task Handoff 의 `브랜치명`(유효한 ref 일 때), 아니면 `task/<문서 ID>` 다. **분기점(base)과 브랜치 이름은 별개다** — base 는 2 에서 고른 ref 이고, `init` 이 워크트리 Task 의 Handoff `base branch` 행을 그 값으로 치환해 `in-dev` 전이 커밋에 함께 넣는다.
- `init` 의 `chore(<ID>): 상태 in-dev` 커밋은 스크립트의 결정적 전이다 — Task 와 `.task/task-catalog.md` 두 파일. Intent 는 바뀌지 않는다(진행 표시는 승인 커밋에 이미 있다).
- 마감 전이(`in-dev → in-review`, 진행 표시 정리)는 개발을 마친 세션이 워크트리 안에서 `worktree_setup.py finish` 로 한다 — 자동으로 부르는 절차는 없다.
- 가드레일 복사(`CLAUDE.md`·`.claude/settings.json`·`.claude/rules`·문서 폴더)는 base 와 무관하게 **메인 repo 작업트리**에서 온다. 작업 공간 수준 가드레일이라 의도된 동작이다. 문서 폴더는 `docs`·`Docs` 중 디스크에 있는 표기 하나로 복사하고 `copied`/`skipped` 에도 그 표기로 1번만 보고한다.
- 정리는 `/forge-cancel <slug>` — 메인 repo 에서 실행한다.
