---
description: 이미 존재하는 디렉터리에 herdr 페인을 열고 Claude 세션을 띄운 뒤(선택) 작업을 지시한다. 워크트리를 만들지 않고 브랜치를 고르지 않는다. 띄울 위치는 사용자가 고른다. herdr 세션 안에서만 동작한다.
argument-hint: "[<cwd-path>] [--agent <name>] [--prompt \"<text>\"] [--kind <kind>] [--name <agent-name>] [--direction right|down]"
---

세션 런처. **이미 있는 디렉터리**에 페인을 열고 거기서 에이전트를 기동한다.

세션의 cwd 는 프로세스 시작 시점에 고정된다. 그래서 워크트리 안에서 개발하려면 그 전에 워크트리가 있어야 하고, 이 커맨드는 그 **다음** 칸을 메운다 — `/forge-init` 이 환경을 만들고, 사용자가 이 커맨드로 세션을 띄운다.

> **범용이다.** forge 를 모른다. 매니페스트를 읽지 않고, Intent 를 보지 않는다. 위치 후보를 `git worktree list` 로 뽑으므로 forge 워크트리가 자연히 포함된다.

> **만들지 않는다.** 워크트리를 생성하지 않고 브랜치를 고르지 않는다 — 그건 `/forge-init` 의 일이다. `herdr worktree create` 를 쓰지 않는다(`git worktree add` 를 자기가 해버려 생성자가 둘이 된다). **열기만** 한다.

> **보고하고 끝낸다.** 띄운 세션을 폴링하지 않고, 그 세션이 묻는 것에 대신 답하지 않고, 포커스를 가져가지 않는다.

helper 경로:

```bash
NAMER="${CLAUDE_PLUGIN_ROOT}/scripts/herdr_name.py"
```

`$ARGUMENTS` 해석: 플래그가 아닌 첫 토큰 = cwd 경로(생략 가능). 나머지는 플래그.

---

## 1 — 전제 확인

```bash
echo "HERDR_ENV=${HERDR_ENV:-unset} PANE=${HERDR_PANE_ID:-unset}"
```

`HERDR_ENV` 가 `1` 이 아니면 **중단한다.** herdr 밖에서는 페인을 만들 방법이 없다 — 이 세션 자체가 herdr 안에 있어야 한다. 중단할 때 사용자가 손으로 할 수 있도록 최종 명령을 그대로 출력한다:

```
# herdr 페인에서:
cd <cwd>
claude --agent <agent-name>
# 그리고 세션 안에서: <prompt>
```

문법은 **설치된 바이너리가 authority** 다. 확신이 없으면 `herdr agent` · `herdr worktree` · `herdr pane split --help` 로 확인한다 — **bare `herdr` 는 TUI 를 띄우므로 금지.** 사용자 레벨 `herdr` 스킬이 있으면 그걸 먼저 로드한다(플러그인은 그 스킬의 존재를 가정하지 않는다).

> 이 문서의 명령 문법은 **herdr 0.8.2 (protocol 20)** 의 `--help` 로 확인한 것이다. 버전이 다르면 `--help` 가 이긴다.

## 2 — 대상 cwd 확정

인자에 경로가 있으면 그 경로를 쓴다. 없으면 후보를 만든다:

```bash
git worktree list --porcelain
```

- **첫 항목은 메인 워크트리다.** 후보에 넣되 `(메인 repo)` 라고 **명시 표기**한다. 라벨 없이 섞으면 워크트리로 오인한다.
- 경로는 **절대경로로 정규화**하고, 공백이 있을 수 있으므로 herdr 에 넘길 때 **항상 따옴표로 감싼다**. Windows 경로(`D:\WorkSpace\...`)는 구분자를 섞지 말고 그대로 넘긴다.
- 경로가 실제로 존재하는지 확인한다. 없으면 중단한다 — **만들지 않는다.**

**중복 기동 방지.** 확정한 cwd 에 이미 에이전트가 붙어 있는지 본다:

```bash
herdr agent list
```

- 출력에 cwd 가 있으면 그걸로 판정한다. 없으면 후보 에이전트에 `herdr agent get <target>` 을 돌려 cwd 를 찾는다.
- 어느 쪽으로도 cwd 를 알 수 없으면 **"중복 여부 확인 불가"를 보고**하고 사용자 판단에 맡긴다. 조용히 넘어가지 않는다.
- 같은 cwd 에 살아 있는 에이전트가 있으면 **기본은 중단**이다. 오케스트레이터 둘이 한 워크트리에 붙으면 `.orchestration/ledgers/` 를 둘이 쓰고 커밋이 경합한다. 사용자가 "그래도 띄워라" 라고 **명시**할 때만 진행한다.

## 3 — 띄울 위치 결정 (`AskUserQuestion` 필수)

경로가 인자로 왔더라도 **어떻게 띄울지**는 묻는다. **임의 선택 금지.** 후보는 실제 상태를 조사해 만든다:

```bash
herdr agent list
herdr pane layout --pane "$HERDR_PANE_ID"
```

1. **새 워크트리 워크스페이스** (권장) — `herdr worktree open --path "<abs>" --no-focus`. 사이드바에 라벨이 붙어 병렬 작업 관리가 된다.
2. **현재 탭 형제 페인** — `herdr pane split --current --direction <right|down> --cwd "<abs>" --no-focus`. 방향은 `pane layout` 기준으로 정한다 — 넓으면 `right`, 좁거나 높으면 `down`. 같은 방향으로 반복 분할해 못 쓸 만큼 좁아지지 않게 한다. `--direction` 이 인자로 왔으면 그 값을 쓴다.
3. **이미 떠 있는 유휴 에이전트에 그대로 지시** — **그 에이전트의 cwd 가 대상과 같다고 확인됐을 때만** 후보에 넣는다(2 참조). 다르거나 확인 불가면 이 옵션을 **아예 제시하지 않는다**. 제시할 때는 "그 세션의 기존 컨텍스트 위에서 돌려도 되는지" 까지 함께 확인한다. 이걸 고르면 4 를 건너뛰고 5 로 간다.

**페인 ID 는 응답 JSON 에서 읽는다.** 사이드바 순서나 예시에서 유추하지 않는다.

- `pane split` → `.result.pane.pane_id`
- `worktree open` → 응답 모양이 버전마다 다를 수 있다. **JSON 전체에서 `pane_id` 를 찾아** 쓰고, 두 개 이상이면 새로 열린 쪽을 고른다. 하나도 없으면 **응답 원문을 그대로 보고하고 중단**한다 — ID 를 지어내지 않는다.

## 4 — 기동

```bash
herdr agent start <name> --kind <kind> --pane <pane-id> -- --agent <agent-name>
```

- `<name>` 은 herdr 에이전트 이름이다. 규칙이 `^[a-z][a-z0-9_-]{0,31}$` 이고 살아 있는 에이전트 중 유일해야 하는데, 워크트리 slug 는 대문자와 점을 보존한다(`MyApp-INT-007`). **직접 손으로 만들지 말고 스크립트를 쓴다**:
  ```bash
  python "$NAMER" "<slug 또는 디렉터리명>" --taken "<herdr agent list 의 이름들, 쉼표 구분>"
  ```
  `--name` 이 인자로 왔으면 `python "$NAMER" "<값>" --strict --taken "..."` 로 **검증만** 한다. 어긋나면 **조용히 고치지 말고** 사용자에게 알리고 중단한다.
- `--kind` 기본값은 `claude`. 설치된 kind 목록은 `herdr agent start --help` 가 authority.
- **네이티브 인자는 `--` 뒤에만 온다.** `--agent opus-orchestrator` 가 거기 간다. `--agent` 가 인자로 없으면 `--` 뒤를 비우고 맨 세션으로 띄운다.
- **플러그인 에이전트를 bare name 으로 해석하는지는 미검증이다.** 기동 후 에이전트가 "unknown agent" 로 죽으면 `claudecode-for-me:<agent-name>` 으로 **1회만** 재시도하고, 어느 쪽이 통했는지 보고한다.
- **`agent_not_ready`** → 페인은 살아 있는데 입력을 못 받는 상태다. `herdr agent read <name>` 으로 무엇을 묻는지 확인해 **사용자에게 전달**한다 — **대신 답하지 않는다.** 워크트리 세션이 권한 allowlist 없이 떴을 때의 흔한 증상이다(`.claude/settings.json` 가드레일 복사가 실패한 경우).

**기동 직후 유휴를 기다린다:**

```bash
herdr agent wait <name> --until idle --timeout 60000
```

오케스트레이터는 `initialPrompt` 로 `.orchestration/ledgers/` 를 훑는다. `agent start` 의 "입력 가능" 은 그 완료를 뜻하지 않으므로, 기다리지 않고 프롬프트를 보내면 턴이 겹치거나 `agent_prompt_stalled` 가 난다.

## 5 — 작업 지시

`--prompt` 가 있을 때만 한다. 없으면 4 에서 끝내고 6 으로 간다.

```bash
herdr agent prompt <name> "<prompt>" --wait --timeout 120000
```

`<TARGET> <TEXT>` 는 **위치 인자**다(플래그가 아니다).

### 슬래시로 시작하는 프롬프트

`/forge-scope ...` 같은 프롬프트는 **전송을 확인해야 한다.** `agent prompt` 는 텍스트를 넣고 짧은 지연 후 Enter 를 보내는데, Claude Code 는 `/` 입력 시 자동완성 메뉴를 띄우므로 그 Enter 가 **제출이 아니라 메뉴 선택**으로 먹힐 수 있다. 동작이 버전에 따라 달라지므로 **값을 가정하지 말고 매번 확인하고 폴백한다**:

1. 위 명령을 그대로 보낸다.
2. `herdr agent read <name> --source recent-unwrapped --lines 40` 로 **실제로 제출됐는지** 본다 — 보낸 커맨드가 전사(transcript)에 사용자 입력으로 찍혔고 세션이 응답을 시작했으면 성공이다. 입력줄에 텍스트가 남아 있거나 자동완성 목록이 떠 있으면 **실패**다.
3. 실패면 **2단 전송**으로 폴백한다 — 텍스트와 Enter 를 나눠 보내고 사이에 메뉴를 닫는다. `<pane-id>` 는 3 에서 받은 값이고, 기존 에이전트를 재사용한 경우(3 의 옵션 3)에는 `herdr agent get <name>` 으로 얻는다:
   ```bash
   herdr pane send-text <pane-id> "<prompt>"   # 리터럴 텍스트만, Enter 없음
   herdr agent send-keys <name> esc            # 자동완성 메뉴를 닫는다 (`esc` 가 정식 이름)
   herdr agent send-keys <name> enter
   ```
   각 단계 뒤에 2 로 재확인한다. `esc` 가 메뉴가 아니라 **입력 자체를 지울** 수도 있으므로, `enter` 를 보내기 전에 입력줄에 텍스트가 남아 있는지 확인한다 — 비었으면 `enter` 를 보내지 말고 4 로 간다.
4. 그래도 안 되면 **중단하고 사용자에게 알린다.** 프롬프트 원문과 페인 ID 를 그대로 출력해 사용자가 직접 붙여 넣을 수 있게 한다.
5. 자연어로 풀어 보내지 않는다 — `/forge-scope` 의 `$ARGUMENTS` 계약을 우회하면 그 세션이 다른 절차를 밟는다. **임의로 지시문을 바꾸지 않는다.**

어느 경로로 전송됐는지 6 에서 보고한다.

### 오류 분기

- **`agent_blocked`** → 승인·질문 UI 에서 멈춰 있다. 입력을 보내지 않고 `herdr agent read` 로 내용을 확인해 **사용자에게 전달**한다. 대신 승인하지 않는다.
- **`agent_prompt_stalled`** → 5초 안에 상태 변화가 없었다. **재전송하지 말고** `herdr agent get` / `herdr agent read` 를 먼저 본다 — 중복 전송은 턴을 겹치게 한다.

## 6 — 보고하고 끝낸다

- 페인 ID · 에이전트 이름 · cwd · kind · 전달한 프롬프트 · 전송 경로(직접/2단) · 현재 상태
- 관전: `herdr agent read <name> --source recent-unwrapped --lines 120`
- **정리 순서 1줄** — 작업이 끝나면 ① 그 세션을 종료 ② 페인을 닫음 ③ `/forge-cancel <slug>`. 워크트리를 먼저 지우면 세션의 cwd 가 사라진다.
- **막힘 알림은 자동으로 오지 않는다** — `herdr notification` 에는 구독 기능이 없다(`show` 뿐). 띄운 세션이 승인을 기다려도 이 세션은 모르므로 **사용자가 직접 봐야 한다**는 것을 명시한다.

여기서 종료한다. 폴링하지 않고, 추가 프롬프트를 보내지 않고, 포커스를 옮기지 않는다(사용자가 명시 요청한 경우 제외).
