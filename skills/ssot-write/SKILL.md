---
name: ssot-write
description: TASK의 핵심 의미를 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 영구 SSOT에 투영한다. Opus Main이 build.md와 progress.md를 기준으로 Opus Planner, Sonnet Writer, Opus Critic을 실제 독립 에이전트로 최대 3회 순환 호출한다. TASK 기반 SSOT 작성, 기존 SSOT 갱신, NOOP 검토가 필요할 때 사용한다.
---

# ssot-write

TASK를 원천 의도로 삼아 `Planner → Writer → Critic` 한 사이클을 실행한다. Critic은 Plan을 무시하고 TASK의 핵심 의미가 실제 SSOT에 올바르게 투영됐는지만 비교한다. Critic이 실패하면 **반드시 Planner부터** REPAIR cycle을 시작한다.

## 절대 규칙

- Main Orchestrator는 **무조건 Opus**다.
- Planner와 Critic은 Opus, Writer는 Sonnet이다.
- 세 역할은 **반드시** `general-purpose` 실제 독립 에이전트로 호출한다.
- Main이 역할을 대신하거나 하나의 에이전트가 여러 역할을 수행하면 **절대로 안 된다.**
- 모든 역할 입력은 **무조건 파일 경로만** 전달한다. 파일 내용, Critic finding 요약, 수정 힌트를 prompt에 붙이면 **절대로 안 된다.**
- Planner는 `plan.json`, Writer는 계획된 SSOT와 `changes.json`, Critic은 `review.json`만 쓴다.
- Main은 `build.md`, `progress.md`, 성공 시 `handoff.json`만 쓴다.
- Main은 **모든 Agent 호출 직전에 `build.md`와 `progress.md`를 반드시 다시 읽는다.**
- `build.md` 고정 실행 설계와 `progress.md` 현재 상태 작성이 끝나기 전에 Planner를 호출하면 **절대로 안 된다.**
- Agent 결과를 받은 직후 Main은 다음 호출보다 먼저 `progress.md`를 **반드시 갱신한다.**
- Critic 응답은 `SUCCESS REVIEW_PATH=<path>` 또는 `FAIL REVIEW_PATH=<path>`만 허용한다.
- Critic에게 `PLAN_PATH`를 전달하면 **절대로 안 된다.** Critic은 TASK의 핵심 의미와 실제 Writer 결과만 비교한다.
- `changes.json`은 실제 SSOT 경로 색인일 뿐 완료 증거가 아니다. Critic은 **반드시 실제 SSOT 본문을 직접 읽는다.**
- Critic은 **무조건** `모순`, `핵심 누락`, `금지 범위 포함`, `근거 없는 추가 결정` 네 의미 check만 수행한다. 하나라도 실패하면 **무조건 FAIL**이다.
- 코드 경로·파일명·클래스/메서드명·테스트명·빌드 명령·구현 검증용 literal을 SSOT에 그대로 복제하지 않았다는 이유만으로 FAIL하면 **절대로 안 된다.** 단, 그 값이 핵심 제품 동작·운영 정책·아키텍처 결정이면 의미 보존 여부를 검토한다.
- Critic이 `FAIL`이면 Writer로 바로 돌아가면 **절대로 안 된다.** `PLAN_PATH + REVIEW_PATH`를 Planner에게 전달한다.
- Critic은 **무조건 최대 3회**다. 세 번째 `FAIL`은 `MANUAL_REQUIRED`로 종료한다.
- Planner의 `NOOP`도 Critic 검토 없이 완료하면 **절대로 안 된다.** NOOP에서는 Writer만 생략한다.
- 사용자 승인 질문, git stage, git commit을 수행하면 **절대로 안 된다.**
- 중단 후 재개, baseline, diff replay, SHA proof, audit를 추가하면 **절대로 안 된다.** 중단된 실행은 지원하지 않는다.
- 모든 자연어 산출물은 **반드시 한국어**로 작성한다.

## 고정 구성

| 구성요소 | 소유 파일 | 책임 |
|---|---|---|
| Main Opus | `build.md`, `progress.md`, `handoff.json` | 경로 전달과 사이클 전이 |
| Planner Opus | `plan.json` | 최초 FULL 계획 또는 Critic FAIL 전용 REPAIR 계획 작성 |
| Writer Sonnet | SSOT, `changes.json` | 최신 plan 실행과 cycle 간 변경 기록 누적 |
| Critic Opus | `review.json` | TASK 핵심 의미와 실제 SSOT 투영을 네 의미 축으로 비교해 SUCCESS/FAIL 반환 |

Gate Controller나 Runner 에이전트를 만들면 **절대로 안 된다.** 신규 실행에서 `scripts/ssot_gate.py` 또는 legacy `scripts/ssot_runner.py`를 호출하면 **절대로 안 된다.**

## 실행 준비

1. 대상 repository의 실제 `docs` 또는 `Docs` 대소문자를 확인한다.
2. TASK가 실제 docs root 아래 존재하는지 확인한다.
3. process는 **무조건 대상 repository root**의 `<REPO_ROOT>/.process/<TASK-stem>/`을 사용한다. TASK 폴더 아래에 만들면 **절대로 안 된다.** 같은 경로에 기존 실행물이 있으면 덮어쓰지 말고 새 suffix를 사용한다.
4. `templates/build.md`와 `templates/progress.md`로 다음 파일을 생성한다.

```text
<process>/build.md
<process>/progress.md
```

`build.md`에는 repository, TASK, process, 역할 모델, artifact 절대경로, 최대 cycle 3, 고정 전이를 기록한다. `progress.md`에는 현재 cycle·stage·result·next action과 사이클 이력을 기록한다.

두 문서는 Main 오케스트레이션의 **고정 실행 설계**와 현재 상태다. Main은 기억이나 직전 대화만으로 다음 역할을 선택하면 **절대로 안 된다.**

## Agent bootstrap

역할 정의는 `CLAUDE_PLUGIN_ROOT/agents`가 있으면 사용하고, 아니면 `SKILL_ROOT`의 두 단계 위 repository root 아래 `agents/`를 사용한다.

```text
agents/ssot-planner.md
agents/ssot-writer.md
agents/ssot-critic.md
```

named `ssot-planner|writer|critic` type을 조회하거나 availability probe를 호출하면 **절대로 안 된다.** 첫 Agent 호출은 실제 Planner bootstrap이어야 한다.

모든 Agent prompt 첫 줄은 다음 고정 문장이다.

```text
Read AGENT_DEFINITION_PATH first and obey it as the complete role contract; then process only the path keys below.
```

그 아래에는 필요한 `KEY=절대경로`만 둔다.

## Cycle 1

### Planner

Main은 `build.md + progress.md`를 읽고 progress를 `PLANNER/IN_PROGRESS`로 갱신한 뒤 호출한다. Planner는 신규 요소를 추가할 때 대상 App SSOT의 개수·열거·정체성 단언 문장이 신규 요소와 정합하도록 그 절까지 갱신 계획에 **무조건** 포함한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
TASK_PATH
PLAN_PATH
```

Planner는 `plan.json`을 쓰고 다음 중 하나만 반환한다.

```text
SUCCESS PLAN_PATH=<path>
FAIL PLAN_PATH=<path>
```

Main은 경로가 예상 `PLAN_PATH`와 같고 파일이 존재하는지만 확인한다. Planner `FAIL`은 `progress.md=FAILED`로 종료한다.

### Writer

`plan.status=READY`이면 Main은 두 진행 문서를 다시 읽고 progress를 `WRITER/IN_PROGRESS`로 갱신한 뒤 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
PLAN_PATH
CHANGES_PATH
```

Writer는 계획된 target만 수정하고 `changes.json`을 쓴 뒤 다음 중 하나만 반환한다.

```text
SUCCESS CHANGES_PATH=<path>
FAIL CHANGES_PATH=<path>
```

Main은 경로와 파일 존재, `plan.actions.target_path`와 `changes.cycle_paths` 집합이 같은지만 확인한다. `changes.result_paths`와 `changes.files.path`는 전체 cycle 누적 결과 집합으로 동일해야 한다. Main이 변경 의미를 판단하면 **절대로 안 된다.** Writer `FAIL`은 `progress.md=FAILED`로 종료한다.

`plan.status=NOOP`이면 Writer를 호출하면 **절대로 안 된다.** 즉시 Critic으로 간다. 즉, **NOOP이면 Writer를 호출하면 절대로 안 된다.**

### Critic

Main은 두 진행 문서를 다시 읽고 progress를 `CRITIC/IN_PROGRESS`로 갱신한 뒤 호출한다.

READY 입력:

```text
AGENT_DEFINITION_PATH
REPO_ROOT
TASK_PATH
CHANGES_PATH
REVIEW_PATH
```

`PLAN_PATH`는 **절대로 전달하지 않는다.** NOOP 입력은 `CHANGES_PATH`만 생략한다.

Critic은 다음 두 대상만 비교한다.

```text
기준: TASK_PATH의 목적·핵심 동작·범위·비목표·아키텍처 결정·운영 제약
결과: changes.result_paths의 실제 SSOT 본문
```

`changes.json`의 설명을 결과 증거로 사용하면 **절대로 안 된다.** NOOP이면 TASK가 속한 App의 현재 영구 SSOT를 직접 찾아 결과로 사용한다.

Critic은 `checks[]`를 **무조건 정확히 네 개** 작성한다.

1. `SEMANTIC-CONTRADICTION`: 실제 SSOT가 TASK 핵심 의미와 모순되는가. 신규 요소 근거의 존재확인에 그치지 말고 대상 App SSOT의 정체성·개수·열거·폐쇄목록 단언 절을 전수 재읽기해 신규 요소와 상충하거나 신규 요소를 누락한 stale 단언이 남았는지 확인하며, REPAIR에서도 직전 finding 위치에 한정하지 않고 매 사이클 전수 재스캔한다.
2. `CORE-OMISSION`: 영구 SSOT에 보존해야 할 핵심 의미가 빠졌는가.
3. `PROHIBITED-SCOPE`: TASK가 금지하거나 후속으로 분리한 범위가 포함됐는가.
4. `UNSUPPORTED-ADDITION`: TASK 근거 없는 기능 범위·정책·아키텍처 결정이 추가됐는가.

각 check는 판단에 사용한 TASK 근거, 실제 SSOT 근거, `PASS|FAIL`을 포함한다. 코드 구현 세부가 그대로 복제되지 않았다는 이유만으로 FAIL하면 **절대로 안 된다.** 네 의미 check 중 하나라도 FAIL이면 전체 결과는 **무조건 FAIL**이다. Critic은 상세 비판을 `review.json`에 쓰고 다음 중 하나만 반환한다.

```text
SUCCESS REVIEW_PATH=<path>
FAIL REVIEW_PATH=<path>
```

Main은 반환 결과와 path를 직접 읽고 progress에 기록한다. finding 내용을 해석하거나 Writer에게 전달하면 **절대로 안 된다.**

## Critic FAIL 재계획

Critic cycle 1 또는 2가 `FAIL`이면 Main은 cycle을 1 증가시키고 **반드시 Planner부터** 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
TASK_PATH
PLAN_PATH
REVIEW_PATH
```

Planner는 TASK, 기존 `plan.json`, `review.json`을 직접 읽고 `mode=REPAIR` 계획으로 `plan.json`을 원자적으로 덮어쓴다. REPAIR action은 FAIL finding을 해결하는 파일만 포함하며 모든 action은 `reference_finding_ids`를 가진다. 이미 PASS한 파일을 전체 계획 반복 목적으로 다시 포함하면 **절대로 안 된다.** 이후 Writer와 Critic을 동일하게 호출한다. Main이 review를 축약하거나 새 계획을 만들면 **절대로 안 된다.**

Writer는 REPAIR target만 수정한다. 기존 `changes.json`의 file·modification 기록을 삭제하면 **절대로 안 된다.** `cycle_paths`에는 이번 REPAIR target만, `result_paths`와 `files`에는 전체 cycle의 누적 결과를 유지한다.

Critic cycle 3이 `FAIL`이면 다음으로 종료한다.

```text
progress.status=MANUAL_REQUIRED
progress.current_stage=DONE
progress.next_action=사용자 수동 확인
```

`handoff.json`을 작성하면 **절대로 안 된다.**

## SUCCESS와 handoff

Critic `SUCCESS` 뒤 Main은 `build.md + progress.md`를 다시 읽고 `handoff.json`을 작성한다.

```json
{
  "status": "SUCCESS",
  "result": "APPLIED | NOOP",
  "task_path": "...",
  "plan_path": "...",
  "changes_path": "... | null",
  "review_path": "...",
  "cycles": 1,
  "actions": []
}
```

READY의 `actions`는 누적 `changes.files`를 그대로 변환한다. 각 file의 `action_id`, `operation`, `path→target_path`, `source_paths`, `authority_paths`, `instruction`, `acceptance_criteria`, `repair_actions`, `modifications`를 보존한다. 따라서 REPAIR 뒤에도 이전 cycle의 실제 변경 기록이 사라지면 **절대로 안 된다.** Main이 의미를 요약하거나 새 요구를 추가하면 **절대로 안 된다.**

마지막으로 `progress.status=SUCCESS`, `current_stage=DONE`, `next_action=work-packet-write`로 갱신한다.

## 산출물 계약

READY 성공은 최대 6개 top-level process 파일을 사용한다.

```text
build.md
progress.md
plan.json
changes.json
review.json
handoff.json
```

각 cycle은 최신 `plan.json`과 `review.json`을 덮어쓴다. `changes.json`은 같은 파일에서 이전 cycle file·modification을 누적 보존한다. 과거 artifact를 별도 파일로 보존하거나 report·event log·state 파일을 만들면 **절대로 안 된다.** 사이클 결과만 `progress.md` 이력 표에 남긴다.
