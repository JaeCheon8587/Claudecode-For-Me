---
name: work-packet-write
description: TASK와 반영된 영구 SSOT를 연결하는 실행용 Work Packet 문서 1개를 생성한다. Opus Main이 build.md와 progress.md만 기준으로 Opus Builder와 Opus Critic을 실제 독립 에이전트로 최대 3회 순환 호출한다. Main은 TASK/SSOT/WP 본문을 읽지 않아 context를 보호한다. Critic은 내용의 참·거짓이 아니라 링킹 정확성만 검사한다. "Work Packet 작성", "패킷 문서 만들어줘", "TASK 다음 forge 입력 문서 생성", "work-packet-write" 요청 시 사용한다.
---

# work-packet-write

`task-write → ssot-write` 이후 단계다. `docs/<App>/TASK/<App>-TASK-<NNN>.md`(Scope Authority)와 ssot-write가 남긴 `handoff.json.actions`(Truth Authority)를 근거로, 실행자가 읽을 문서·범위·충돌 규칙만 지정하는 **얇은 실행 manifest = Work Packet**을 `Builder → Critic` 한 사이클로 작성한다.

이 스킬의 **유일한 설계 동기는 Main 에이전트의 context window 보호**다. 무거운 evidence 읽기와 WP authoring, 링킹 감사를 전부 격리된 서브에이전트로 내리고, Main은 경로와 짧은 반환 토큰만 다룬다.

## 책임 경계

- 이 스킬은 **Work Packet 파일 1개만** 생성한다.
- TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일을 수정하지 않는다.
- Work Packet은 요구사항·SSOT 본문을 복제하지 않고, 실행자가 읽을 문서·범위·충돌 규칙·검증 입력만 지정한다.
- 후속 구현은 `forge-scope` 단계로 넘긴다.

## 절대 금지

- TASK 또는 영구 SSOT를 생성·수정·삭제하면 **절대로 안 된다.**
- 코드 파일을 수정하면 **절대로 안 된다.**
- SSOT 본문을 Work Packet에 **장문 복제하면 절대로 안 된다.**
- `CREATE/UPDATE target path`가 비어 있거나 파일이 없는데 임의 링크를 만들거나 `Ready`로 쓰면 **절대로 안 된다.**
- 사용자 승인 질문, git stage, git commit을 수행하면 **절대로 안 된다.**
- 중단 후 재개, baseline, diff replay, SHA proof를 추가하면 **절대로 안 된다.** 중단된 실행은 지원하지 않는다.

## 절대 규칙

- Main Orchestrator는 **무조건 Opus**다. Builder와 Critic도 **무조건 Opus**다.
- 두 역할은 **반드시** `general-purpose` 실제 독립 에이전트로 호출한다. Main이 역할을 대신하거나 한 에이전트가 두 역할을 수행하면 **절대로 안 된다.**
- Main은 **완전 비대화형**이다. 사용자에게 질문하거나 승인을 구하면 **절대로 안 된다.** 상위 handoff가 불량/부재면 질문 없이 `BLOCKED`로, 그 외 입력이 부족하면 `FAILED`로 종료한다.
- **Main은 TASK/SSOT/Work Packet/manifest/review의 본문을 절대로 읽지 않는다.** 이것이 context 보호의 핵심이다. Main이 이 파일들을 열면 **절대로 안 된다.**
- 모든 역할 입력은 **무조건 `KEY=절대경로`만** 전달한다. 파일 내용, Critic finding 요약, 수정 힌트를 prompt에 붙이면 **절대로 안 된다.**
- **경로 2원화**: dispatch key(Main→에이전트)는 **무조건 절대경로**다(`AGENT_DEFINITION_PATH`·`TEMPLATE_PATH`는 플러그인 소재라 절대경로 필수). manifest/review/handoff **JSON 내부 path 값**은 **무조건 REPO_ROOT 기준 상대경로**다. 이 둘을 섞으면 **절대로 안 된다.**
- Main은 **오케스트레이션을 오직 `build.md`와 `progress.md`만 보고** 수행한다. 기억이나 직전 대화만으로 다음 역할을 선택하면 **절대로 안 된다.**
- Main은 **모든 Agent 호출 직전에 `build.md`와 `progress.md`를 반드시 다시 읽는다.**
- `build.md` 고정 실행 설계와 `progress.md` 현재 상태 작성이 끝나기 전에 Builder를 호출하면 **절대로 안 된다.**
- Agent 결과를 받은 직후 Main은 다음 호출보다 먼저 `progress.md`를 **반드시 갱신한다.**
- **라우팅은 오직 에이전트 반환 문자열의 SUCCESS/FAIL 토큰으로만** 한다. `review.json`을 열면 Main context가 오염되므로 **절대로 열지 않는다.**
- Builder 반환은 `SUCCESS WP_PATH=<path>` 또는 `FAIL WP_PATH=<path>`만 허용한다.
- Critic 반환은 `SUCCESS REVIEW_PATH=<path> WP_STATE=Ready|Draft` 또는 `FAIL REVIEW_PATH=<path>`만 허용한다. 그 외 형식이면 **무조건 FAILED**로 종료한다.
- Critic에게 `MANIFEST_PATH`를 전달하면 **절대로 안 된다.** Critic은 독립성을 위해 handoff에서 expected를 스스로 재도출한다.
- Critic의 관심사는 **오직 링킹 정확성**이다. 내용의 참·거짓을 검사하면 **절대로 안 된다.** Critic은 `ROUTER-DISCIPLINE·LINK-COVERAGE·LINK-VALIDITY·LINK-TRACEABILITY·GATE-LINKAGE` 다섯 check를 수행하고 **하나라도 FAIL이면 무조건 FAIL**이다.
- Critic이 `FAIL`이면 **Builder부터** REPAIR cycle을 시작한다. `REVIEW_PATH`를 Builder에 전달한다.
- Critic은 **무조건 최대 3회**다. 세 번째 `FAIL`은 `MANUAL_REQUIRED`로 종료한다.
- 모든 자연어 산출물은 **반드시 한국어**로 작성한다.

## 고정 구성

| 구성요소 | 소유 파일 | 책임 |
|---|---|---|
| Main Opus | `build.md`, `progress.md`, `handoff.json` | 인자 파싱·gate·번호 할당·경로 전달·사이클 전이 (비대화형, 본문 미열람) |
| Builder Opus | Work Packet 파일, `manifest.json` | handoff·TASK·template 근거로 WP를 링킹 작성, cycle 간 변경 누적 |
| Critic Opus | `review.json` | WP 링킹을 handoff와 독립 대조해 5 check로 SUCCESS/FAIL 반환 |

Gate Controller나 Runner 에이전트를 만들면 **절대로 안 된다.** 별도 read-only auditor 위임도 두지 않는다. 링킹 검증은 Critic이 수행한다.

## Main context 보호 계약 (2단계 분리)

Main의 파일 접촉을 **SETUP 1회**와 **ORCHESTRATION 루프**로 엄격히 분리한다. 이 분리가 없으면 "build/progress만 보고 오케스트레이션"과 "handoff 확인"이 충돌한다.

- **SETUP**: `build.md`를 만들기 위한 1회 준비. handoff는 **top-level 필드만** 뽑는다. 전체 파일을 context에 로드하면 **절대로 안 된다.**
- **ORCHESTRATION 루프**: `build.md`와 `progress.md`만 근거로 전이한다. 에이전트 출력 파일 본문은 **절대로 읽지 않는다.**

## 실행 준비 (SETUP)

Main이 다음을 **비대화형**으로 수행한다.

1. 대상 repository의 실제 `docs` 또는 `Docs` 대소문자를 확인한다.
2. helper 경로를 정한다. 우선 `./scripts/docs_helpers.py`, 없으면 `${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py`.
3. WP 템플릿 경로를 정한다. 우선 `docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md`, 없으면 `${CLAUDE_PLUGIN_ROOT}/docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md`. 못 찾으면 중단하고 경로 누락을 보고한다.
4. `$ARGUMENTS`를 분리한다. 필수 `<TASK-path>`, 선택 `--app <APP>`·`--process <process-dir>`·`--name <title>`.
   - TASK 경로는 `<docs_root>/<App>/TASK/<App>-TASK-<NNN>.md` 형식이어야 한다(경로 문자열만 검증, **본문은 읽지 않는다**). `--app`이 있으면 경로의 App과 일치해야 한다.
5. ssot-write handoff를 찾는다. `--process`가 있으면 `<process-dir>/handoff.json`, 없으면 `<REPO_ROOT>/.process/<TASK-stem>/handoff.json`.
6. handoff의 **top-level 필드만** stdout으로 뽑는다(예: `python -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print(d.get('status'),d.get('result'),d.get('task_path'))" <handoff>`). 파일 전체를 Main context에 로드하면 **절대로 안 된다.**
   - `status==SUCCESS` 且 `result∈{APPLIED,NOOP}`가 아니면 질문 없이 `BLOCKED`로 종료한다.
   - handoff 파일 자체가 없으면 `BLOCKED`로 종료한다.
7. `python <HELP> check-task --repo . --app <APP> --task <TASK-path>`를 **stdout 요약만** 받아 실행한다. FAIL이면 `BLOCKED`/`FAILED`로 종료한다. TASK 본문을 Main context에 로드하면 **절대로 안 된다.**
8. `python <HELP> next-id --repo . --app <APP> --kind wp`로 번호를 얻어 `<docs_root>/<App>/WORK_PACKET/<App>-WP-<NNN>.md` target 경로를 정한다. **기존 파일이 있으면 덮어쓰지 말고 중단**한다.
9. process는 **무조건 대상 repository root**의 `<REPO_ROOT>/.process/<App>-WP-<NNN>/`을 사용한다. ssot-write의 `.process/<TASK-stem>/`을 **덮어쓰면 절대로 안 된다.** 같은 경로에 기존 실행물이 있으면 새 suffix를 사용한다.
10. `templates/build.md`와 `templates/progress.md`로 `<process>/build.md`와 `<process>/progress.md`를 생성한다. repository, App, wp_id, WP·TASK·handoff·template·helper·process·manifest·review·handoff(out) 절대경로, 역할 모델, 최대 cycle 3, 고정 전이를 기록한다.

## Agent bootstrap

역할 정의는 `CLAUDE_PLUGIN_ROOT/agents`가 있으면 사용하고, 아니면 repository root 아래 `agents/`를 사용한다.

```text
agents/wp-builder.md
agents/wp-critic.md
```

named `wp-builder|wp-critic` type을 조회하거나 availability probe를 호출하면 **절대로 안 된다.** 첫 Agent 호출은 실제 Builder bootstrap이어야 한다.

모든 Agent prompt 첫 줄은 다음 고정 문장이다.

```text
Read AGENT_DEFINITION_PATH first and obey it as the complete role contract; then process only the path keys below.
```

그 아래에는 필요한 `KEY=절대경로`만 둔다.

## Cycle 1

### Builder

Main은 `build.md + progress.md`를 읽고 progress를 `BUILDER/IN_PROGRESS`로 갱신한 뒤 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
TASK_PATH
HANDOFF_PATH
TEMPLATE_PATH
WP_PATH
MANIFEST_PATH
```

Builder는 Work Packet 파일 1개와 `manifest.json`을 쓰고 다음 중 하나만 반환한다.

```text
SUCCESS WP_PATH=<path>
FAIL WP_PATH=<path>
```

Main은 반환 `WP_PATH`가 예상 경로와 같고 **파일이 실제 존재하는지만** `os.path.exists`로 확인한다(본문은 읽지 않는다). 존재하지 않으면 **무조건 FAILED**로 종료한다. Builder `FAIL`은 `progress.md=FAILED`로 종료한다. Main이 변경 의미를 판단하면 **절대로 안 된다.**

### Critic

Main은 두 진행 문서를 다시 읽고 progress를 `CRITIC/IN_PROGRESS`로 갱신한 뒤 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
TASK_PATH
HANDOFF_PATH
TEMPLATE_PATH
WP_PATH
REVIEW_PATH
```

`MANIFEST_PATH`는 **절대로 전달하지 않는다.** Critic은 handoff에서 expected를 스스로 재도출해 실제 WP 링크와 대조한다.

Critic은 `review.json`에 5 링킹 check를 쓰고 다음 중 하나만 반환한다.

```text
SUCCESS REVIEW_PATH=<path> WP_STATE=Ready|Draft
FAIL REVIEW_PATH=<path>
```

Main은 **반환 토큰만** 읽고 progress에 기록한다. `review.json`을 열거나 finding을 해석해 Builder에 전달하면 **절대로 안 된다.** 정당한 Draft도 `SUCCESS`다.

## Critic FAIL 재빌드 (REPAIR)

Critic cycle 1 또는 2가 `FAIL`이면 Main은 cycle을 1 증가시키고 **Builder부터** 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
TASK_PATH
HANDOFF_PATH
TEMPLATE_PATH
WP_PATH
MANIFEST_PATH
REVIEW_PATH
```

Builder는 `review.json` finding, 기존 `manifest.json`, handoff를 직접 읽고 **링킹 결함만** 수정한다. 기존 manifest 기록을 삭제하면 **절대로 안 된다.** 이후 Critic을 동일하게 호출한다. Main이 review를 축약하거나 새 지시를 만들면 **절대로 안 된다.**

Critic cycle 3이 `FAIL`이면 다음으로 종료한다.

```text
progress.status=MANUAL_REQUIRED
progress.current_stage=DONE
progress.next_action=사용자 수동 확인
```

`handoff.json`을 작성하면 **절대로 안 된다.**

## SUCCESS와 handoff

Critic `SUCCESS` 뒤 Main은 `build.md + progress.md`를 다시 읽고 `handoff.json`을 작성한다. `wp_state`는 **Critic 반환 토큰의 `WP_STATE`**에서 가져온다(WP 파일을 읽지 않는다).

```json
{
  "status": "SUCCESS",
  "result": "APPLIED",
  "app": "<APP>",
  "wp_path": "docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md",
  "wp_state": "Ready | Draft",
  "task_path": "docs/<App>/TASK/<App>-TASK-<NNN>.md",
  "handoff_source_path": ".process/<TASK-stem>/handoff.json",
  "manifest_path": ".process/<App>-WP-<NNN>/manifest.json",
  "review_path": ".process/<App>-WP-<NNN>/review.json",
  "cycles": 1,
  "next": "forge-scope"
}
```

모든 path 필드는 **REPO_ROOT 기준 상대경로**로 쓴다. 절대경로로 재구성하면 **절대로 안 된다.** 마지막으로 `progress.status=SUCCESS`, `current_stage=DONE`, `next_action=forge-scope`로 갱신한다.

## 산출물 계약

`.process/<App>-WP-<NNN>/` 아래 top-level 파일만 사용한다.

```text
build.md
progress.md
manifest.json
review.json
handoff.json
```

각 cycle은 최신 `review.json`을 덮어쓴다. `manifest.json`은 이전 cycle 기록을 누적 보존한다. Work Packet은 `<docs_root>/<App>/WORK_PACKET/<App>-WP-<NNN>.md`에 생성된다. 과거 artifact를 별도 파일로 보존하거나 report·event log·state 파일을 만들면 **절대로 안 된다.**

## 결과 보고

다음 형식으로 간결히 보고한다.

```text
CREATE <docs_root>/<App>/WORK_PACKET/<App>-WP-<NNN>.md (WP_STATE: Ready | Draft)
Task: <docs_root>/<App>/TASK/<App>-TASK-<NNN>.md
Review: SUCCESS | MANUAL_REQUIRED (cycles: N)
Next: forge-scope
```

`BLOCKED`(상위 handoff 불량/부재)·`FAILED`(App 미결정·TASK 불량·Builder FAIL) 종료면 `CREATE` 대신 사유와 `progress.status`를 보고한다.
