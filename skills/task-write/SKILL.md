---
name: task-write
description: 요구사항 문서나 자연어 요청을 App TASK 문서 1개로 작성한다. Opus Main이 build.md와 progress.md를 기준으로 Opus Planner, Sonnet Writer, Opus Critic을 실제 독립 에이전트로 최대 3회 순환 호출한다. TASK만 생성하며 FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 같은 영구 SSOT 문서는 분석·수정하지 않는다. "Task 작성", "작업 지시서만 만들어줘", "요구사항으로 TASK 생성", "task-write" 요청 시 사용한다.
---

# task-write

요구사항을 원천 의도로 삼아 `docs/<App>/TASK/<App>-TASK-<NNN>.md` 작업 범위 계약 1개를 `Planner → Writer → Critic` 한 사이클로 작성한다. Critic은 Plan을 무시하고 요구사항의 핵심 의미가 실제 TASK 파일에 올바르게 반영됐는지만 비교하며 구조 검증까지 수행한다. Critic이 실패하면 **반드시 Planner부터** REPAIR cycle을 시작한다.

## 책임 경계

- TASK는 Scope Authority다. 목적·범위·비목표·완료 기준·엣지 케이스·오류 처리·테스트 기준만 정의한다.
- 이 스킬은 **TASK 파일 1개만 생성**한다. 코드 구현을 하지 않는다.
- SSOT 영향 후보를 작성하지 않는다. 그 판단은 후속 `ssot-write` 계열 스킬 책임이다.

## 절대 금지

- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE`를 생성·수정·upsert 하지 않는다.
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 같은 영구 SSOT 문서를 분석하지 않는다.
- 영구 SSOT 문서의 갱신 후보, 영향 후보, 링크 목록, 변경 계획을 TASK 안에 작성하지 않는다.
- App 판단·TASK 범위 역산을 위해 FC/FRD/ADR-CATALOG 등 SSOT를 파싱하지 않는다.

## 절대 규칙

- Main Orchestrator는 **무조건 Opus**다.
- Planner와 Critic은 Opus, Writer는 Sonnet이다.
- 세 역할은 **반드시** `general-purpose` 실제 독립 에이전트로 호출한다.
- Main이 역할을 대신하거나 하나의 에이전트가 여러 역할을 수행하면 **절대로 안 된다.**
- Main은 **완전 비대화형**이다. 사용자에게 질문하거나 승인을 구하면 **절대로 안 된다.** App·요구사항이 부족하면 질문 없이 `FAILED`로 종료한다.
- 모든 역할 입력은 **무조건 파일 경로만** 전달한다. 파일 내용, Critic finding 요약, 수정 힌트를 prompt에 붙이면 **절대로 안 된다.**
- Planner는 `plan.json`, Writer는 계획된 TASK 파일과 `changes.json`, Critic은 `review.json`만 쓴다.
- 모든 산출물 JSON의 경로 필드는 **`REPO_ROOT` 기준 상대경로**(`docs/<App>/...` 또는 `Docs/<App>/...`)로 기록한다. 위임 KEY는 절대경로지만 Planner `target_path`, Writer `result_paths`·`task_path`, Critic 경로 근거, `handoff.json` 경로는 절대경로를 그대로 복사하지 말고 상대경로로 통일한다. Main의 경로 대조는 **문자열 동일** 비교이므로 절대/상대가 섞이면 검증이 깨진다.
- Main은 `build.md`, `progress.md`, `requirement.md`, 성공 시 `handoff.json`만 쓴다.
- Main은 **모든 Agent 호출 직전에 `build.md`와 `progress.md`를 반드시 다시 읽는다.**
- `build.md` 고정 실행 설계와 `progress.md` 현재 상태 작성이 끝나기 전에 Planner를 호출하면 **절대로 안 된다.**
- Agent 결과를 받은 직후 Main은 다음 호출보다 먼저 `progress.md`를 **반드시 갱신한다.**
- Critic 응답은 `SUCCESS REVIEW_PATH=<path>` 또는 `FAIL REVIEW_PATH=<path>`만 허용한다.
- Critic에게 `PLAN_PATH`를 전달하면 **절대로 안 된다.** Critic은 요구사항의 핵심 의미와 실제 TASK 파일만 비교한다.
- `changes.json`은 실제 TASK 경로 색인일 뿐 완료 증거가 아니다. Critic은 **반드시 실제 TASK 파일 본문을 직접 읽는다.**
- Critic은 **무조건** `요구사항 모순`, `핵심 누락`, `범위 위반`, `근거 없는 추가` 네 의미 check와 구조 검증을 수행한다. 하나라도 실패하면 **무조건 FAIL**이다.
- 코드 경로·파일명·클래스/메서드명·테스트명·빌드 명령·검증용 literal을 TASK에 그대로 복제하지 않았다는 이유만으로 FAIL하면 **절대로 안 된다.** 단, 그 값이 요구사항의 핵심 제품 동작·운영 정책·아키텍처 결정이면 의미 보존 여부를 검토한다.
- Critic이 `FAIL`이면 Writer로 바로 돌아가면 **절대로 안 된다.** `PLAN_PATH + REVIEW_PATH`를 Planner에게 전달한다.
- Critic은 **무조건 최대 3회**다. 세 번째 `FAIL`은 `MANUAL_REQUIRED`로 종료한다.
- 사용자 승인 질문, git stage, git commit을 수행하면 **절대로 안 된다.**
- 중단 후 재개, baseline, diff replay, SHA proof, audit를 추가하면 **절대로 안 된다.** 중단된 실행은 지원하지 않는다.
- 모든 자연어 산출물은 **반드시 한국어**로 작성한다.

## 고정 구성

| 구성요소 | 소유 파일 | 책임 |
|---|---|---|
| Main Opus | `build.md`, `progress.md`, `requirement.md`, `handoff.json` | 인자 파싱·App 결정·번호 할당·요구사항 캡처·경로 전달·사이클 전이 (비대화형) |
| Planner Opus | `plan.json` | 최초 FULL 계획 또는 Critic FAIL 전용 REPAIR 계획 작성 |
| Writer Sonnet | TASK 파일, `changes.json` | 최신 plan 실행과 cycle 간 변경 기록 누적 |
| Critic Opus | `review.json` | 요구사항 핵심 의미와 실제 TASK 파일을 네 의미 축으로 비교하고 구조 검증해 SUCCESS/FAIL 반환 |

Gate Controller나 Runner 에이전트를 만들면 **절대로 안 된다.** read-only auditor 별도 위임도 두지 않는다. 구조 검증은 Critic이 수행한다.

## 실행 준비

Main이 다음을 **비대화형**으로 수행한다. 어떤 단계도 사용자에게 질문하지 않는다.

1. 대상 repository의 실제 `docs` 또는 `Docs` 대소문자를 확인한다.
2. helper 경로를 정한다. 우선 `./scripts/docs_helpers.py`, 없으면 `${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py`.
3. TASK 템플릿 경로를 정한다. 우선 `docs/.templates/App/TASK/APP-TASK-001-TEMPLATE.md`, 없으면 `${CLAUDE_PLUGIN_ROOT}/docs/.templates/App/TASK/APP-TASK-001-TEMPLATE.md`. 못 찾으면 중단하고 경로 누락을 보고한다.
4. `$ARGUMENTS`를 분리한다. `--app <APP>`, `--from <path>`, 나머지 텍스트는 자연어 작업 요청.
5. App을 결정한다. `--app`이 있으면 그 값을 쓴다. 없으면 `python <HELP> list-apps --repo .`로 후보를 찾는다. 후보 1개면 자동 선택, **여러 개거나 없으면 질문 없이** `progress.status=FAILED`(App 미결정)로 종료한다. 신규 App 부트스트랩은 하지 않는다.
6. 요구사항 원문을 캡처한다.
   - `--from`이 있으면 그 파일을 `REQUIREMENT_PATH`로 삼는다. `.requirements/` 하위면 기준 문서로 기록한다.
   - `--from` 없이 자연어 요청만 있으면 `<process>/requirement.md`에 원문을 저장하고 그 경로를 `REQUIREMENT_PATH`로 삼는다.
   - 둘 다 없으면 질문 없이 `progress.status=FAILED`(요구사항 없음)로 종료한다.
7. `python <HELP> next-id --repo . --app <APP> --kind task`로 다음 번호를 얻어 `docs/<App>/TASK/<App>-TASK-<NNN>.md` target 경로를 정한다. helper가 없으면 기존 `<App>-TASK-*.md`를 보고 판단한다. **기존 파일이 있으면 덮어쓰지 말고 중단**한다.
8. process는 **무조건 대상 repository root**의 `<REPO_ROOT>/.process/<App>-TASK-<NNN>/`을 사용한다. TASK 폴더 아래에 만들면 **절대로 안 된다.** 같은 경로에 기존 실행물이 있으면 덮어쓰지 말고 새 suffix를 사용한다.
9. `templates/build.md`와 `templates/progress.md`로 `<process>/build.md`와 `<process>/progress.md`를 생성한다.

`build.md`에는 repository, App, task_id, TASK, requirement, template, helper, process, 역할 모델, artifact 절대경로, 최대 cycle 3, 고정 전이를 기록한다. `progress.md`에는 현재 cycle·stage·result·next action과 사이클 이력을 기록한다.

두 문서는 Main 오케스트레이션의 **고정 실행 설계**와 현재 상태다. Main은 기억이나 직전 대화만으로 다음 역할을 선택하면 **절대로 안 된다.**

## Agent bootstrap

역할 정의는 `CLAUDE_PLUGIN_ROOT/agents`가 있으면 사용하고, 아니면 `SKILL_ROOT`의 두 단계 위 repository root 아래 `agents/`를 사용한다.

```text
agents/task-planner.md
agents/task-writer.md
agents/task-critic.md
```

named `task-planner|writer|critic` type을 조회하거나 availability probe를 호출하면 **절대로 안 된다.** 첫 Agent 호출은 실제 Planner bootstrap이어야 한다.

모든 Agent prompt 첫 줄은 다음 고정 문장이다.

```text
Read AGENT_DEFINITION_PATH first and obey it as the complete role contract; then process only the path keys below.
```

그 아래에는 필요한 `KEY=절대경로`만 둔다.

## Cycle 1

### Planner

Main은 `build.md + progress.md`를 읽고 progress를 `PLANNER/IN_PROGRESS`로 갱신한 뒤 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
REQUIREMENT_PATH
TEMPLATE_PATH
TASK_PATH
PLAN_PATH
```

Planner는 `plan.json`을 쓰고 다음 중 하나만 반환한다.

```text
SUCCESS PLAN_PATH=<path>
FAIL PLAN_PATH=<path>
```

Main은 경로가 예상 `PLAN_PATH`와 같고 파일이 존재하는지만 확인한다. Planner `FAIL`(요구사항 불충분)은 `progress.md=FAILED`로 종료한다. Main이 계획 의미를 판단하면 **절대로 안 된다.**

### Writer

`plan.status=READY`이면 Main은 두 진행 문서를 다시 읽고 progress를 `WRITER/IN_PROGRESS`로 갱신한 뒤 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
PLAN_PATH
TEMPLATE_PATH
CHANGES_PATH
```

Writer는 계획된 target TASK 파일 1개만 작성하고 `changes.json`을 쓴 뒤 다음 중 하나만 반환한다.

```text
SUCCESS CHANGES_PATH=<path>
FAIL CHANGES_PATH=<path>
```

Main은 경로와 파일 존재, `plan.target_path`와 `changes.result_paths`가 **문자열까지 동일한**(둘 다 `REPO_ROOT` 기준 상대경로) TASK 파일 1개인지만 확인한다. Main이 변경 의미를 판단하면 **절대로 안 된다.** Writer `FAIL`은 `progress.md=FAILED`로 종료한다.

### Critic

Main은 두 진행 문서를 다시 읽고 progress를 `CRITIC/IN_PROGRESS`로 갱신한 뒤 호출한다.

```text
AGENT_DEFINITION_PATH
REPO_ROOT
REQUIREMENT_PATH
CHANGES_PATH
REVIEW_PATH
```

`PLAN_PATH`는 **절대로 전달하지 않는다.**

Critic은 다음 두 대상만 비교한다.

```text
기준: REQUIREMENT_PATH의 목적·완료 상태·범위·비목표·제약
결과: changes.result_paths의 실제 TASK 파일 본문
```

`changes.json`의 설명을 결과 증거로 사용하면 **절대로 안 된다.** Critic은 네 의미 check(요구사항 모순·핵심 누락·범위 위반·근거 없는 추가)와 `check-task` 구조 검증을 수행하고, 상세 비판을 `review.json`에 쓴 뒤 다음 중 하나만 반환한다.

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
REQUIREMENT_PATH
TEMPLATE_PATH
TASK_PATH
PLAN_PATH
REVIEW_PATH
```

Planner는 요구사항, 기존 `plan.json`, `review.json`을 직접 읽고 `mode=REPAIR` 계획으로 `plan.json`을 원자적으로 덮어쓴다. REPAIR 계획은 FAIL finding을 해결하는 요소만 포함하며 `reference_finding_ids`로 모든 FAIL finding을 연결한다. 이후 Writer와 Critic을 동일하게 호출한다. Main이 review를 축약하거나 새 계획을 만들면 **절대로 안 된다.**

Writer는 REPAIR 대상만 수정한다. 기존 `changes.json`의 modification 기록을 삭제하면 **절대로 안 된다.** target TASK 파일 1개에 `repair_actions`와 이번 cycle modification을 추가한다.

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
  "result": "APPLIED",
  "app": "<APP>",
  "work_type": "...",
  "task_path": "docs/<App>/TASK/<App>-TASK-<NNN>.md",
  "requirement_path": "...",
  "plan_path": "...",
  "changes_path": "...",
  "review_path": "...",
  "cycles": 1,
  "next": "ssot-write"
}
```

모든 경로 필드는 `REPO_ROOT` 기준 상대경로로 쓴다. `task_path`·`changes_path`는 `changes.json`의 상대경로를 그대로 가져오고, 나머지도 절대경로로 재구성하지 않는다.

`work_type`은 최신 `plan.json`, `task_path`·`changes_path`는 누적 `changes.json`에서 그대로 가져온다. Main이 의미를 요약하거나 새 요구를 추가하면 **절대로 안 된다.**

마지막으로 `progress.status=SUCCESS`, `current_stage=DONE`, `next_action=ssot-write`로 갱신한다.

## 산출물 계약

READY 성공은 최대 7개 top-level process 파일을 사용한다.

```text
build.md
progress.md
requirement.md
plan.json
changes.json
review.json
handoff.json
```

`requirement.md`는 자연어 요청 캡처일 때만 존재한다(`--from`이면 생략). 각 cycle은 최신 `plan.json`과 `review.json`을 덮어쓴다. `changes.json`은 같은 파일에서 이전 cycle 기록을 누적 보존한다. 과거 artifact를 별도 파일로 보존하거나 report·event log·state 파일을 만들면 **절대로 안 된다.** 사이클 결과만 `progress.md` 이력 표에 남긴다.

## 결과 보고

다음 형식으로 간결히 보고한다.

```text
CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md
Reference: <요구사항 기준 문서 또는 "대화 입력">
Review: SUCCESS | MANUAL_REQUIRED (cycles: N)
Next: ssot-write 단계에서 TASK 기반으로 영구 SSOT 문서를 갱신
```

`FAILED` 종료(App 미결정·요구사항 없음·Planner/Writer FAIL)면 `CREATE` 대신 실패 사유와 `progress.status`를 보고한다.
