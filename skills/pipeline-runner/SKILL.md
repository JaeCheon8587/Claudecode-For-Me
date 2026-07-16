---
name: pipeline-runner
description: requirement-spec 산출물 이후 작업 규모를 7축으로 판단하고 후속 스킬 파이프라인을 설계한다. pipeline-build.md와 pipeline-progress.md를 생성한 뒤 사용자 승인 후 task-write, ssot-write, work-packet-write, forge-scope, ddr-loop, branch-review를 인라인 실행한다. "requirement-spec 이후 실행", "작업 파이프라인 실행", "pipeline-runner" 요청 시 사용한다.
---

# pipeline-runner

`pipeline-runner`는 `.requirements/requirement-{slug}.md`를 입력으로 작업 규모를 판단하고, 후속 스킬 체인을 결정한 뒤, build/progress 문서를 기준으로 실행하는 오케스트레이터다.

## 핵심 원칙

- **문서 기반 실행**: 모든 신규 실행은 `.process/pipeline-<slug>/pipeline-build.md`와 `pipeline-progress.md`를 먼저 만든다.
- **승인 게이트**: `Approval: pending` 상태에서는 후속 스킬을 실행하지 않는다. 사용자 승인 후에만 실행한다.
- **인라인 실행**: 다른 스킬을 런타임 API처럼 호출하지 않는다. 각 단계에서 해당 `skills/<skill>/SKILL.md`를 읽고 이 세션에서 그대로 수행한다.
- **progress 기준 재개**: `--resume`은 `pipeline-progress.md`를 읽어 `done`이 아닌 첫 단계부터 재개한다.
- **상태 기록 우선**: 단계 시작, 완료, blocked, 사용자 결정, 산출물 경로는 반드시 progress에 기록한다.
- **템플릿 계약 강제**: build/progress 문서는 템플릿 heading과 table header를 보존한다. 섹션 이름 변경, 생략, 축약, 자유 서술형 대체 금지.

## 분리 문서

긴 기준은 필요할 때 아래 문서를 읽는다.

- 라우팅 기준: `references/routing-rules.md`
- 스킬 입출력 카탈로그: `references/skill-catalog.md`
- build 템플릿: `templates/pipeline-build.md`
- progress 템플릿: `templates/pipeline-progress.md`
- pipeline init helper: `scripts/pipeline_runner_init.py`
- pipeline validator: `scripts/pipeline_runner_check.py`

## Init Helper

build/progress 생성은 helper가 담당한다. 에이전트가 `pipeline-build.md` 또는 `pipeline-progress.md`를 직접 Write로 새로 작성하지 않는다.

helper 경로:
1. 우선: `./scripts/pipeline_runner_init.py`
2. 없으면: `${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_runner_init.py`

필수 실행:

```bash
python <PIPELINE_INIT> init \
  --requirement <requirement-path> \
  --app <APP> \
  --name <slug> \
  --pipeline "<selected pipeline>" \
  --total-score <score> \
  --size <XS/S|M|L|XL> \
  --forced-conditions "<conditions>" \
  --risk-notes "<notes>"
```

선택:
- `--scores-json <json-or-path>`: 7축 점수와 evidence를 구조화해 전달한다.
- `--steps-json <json-or-path>`: Step Parameters/Step Status row를 구조화해 전달한다.
- `--force`: 같은 process dir을 덮어쓸 때만 사용한다. 기본은 기존 process dir이 있으면 중단이다.

helper가 하는 일:
- `templates/pipeline-build.md`와 `templates/pipeline-progress.md`를 읽는다.
- placeholder만 치환한다.
- heading, table header, section order를 보존한다.
- 생성 직후 `pipeline_runner_check.py template`과 동일한 검사를 실행한다.

금지:
- build/progress heading을 직접 번역하지 않는다.
- table header를 직접 바꾸지 않는다.
- helper 없이 build/progress를 자유 형식으로 새로 작성하지 않는다.

## Validator Helper

Template Contract Gate와 approval/progress/output 검증은 helper로 확인한다.

helper 경로:
1. 우선: `./scripts/pipeline_runner_check.py`
2. 없으면: `${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_runner_check.py`

필수 실행:
- build/progress 생성 직후:
  `python <PIPELINE_CHECK> template --process .process/pipeline-<slug>`
- 승인 직후, Phase 4 진입 전:
  `python <PIPELINE_CHECK> approval --process .process/pipeline-<slug>`
- 각 step 완료 후:
  `python <PIPELINE_CHECK> progress --process .process/pipeline-<slug>`
- 최종 보고 전:
  `python <PIPELINE_CHECK> outputs --process .process/pipeline-<slug> --repo .`

helper exit code:
- `0`: pass
- `1`: contract fail. 후속 스킬 실행 금지.
- `2`: usage/input error. 경로를 고친 뒤 재실행.

## Phase 0 — 입력 해석

1. `$ARGUMENTS`를 해석한다.
   - 필수: `<requirement-path>`
   - 선택: `--app <APP>`
   - 선택: `--name <slug>`
   - 선택: `--resume`
2. `<requirement-path>`는 requirement-spec 산출물인 `.requirements/requirement-{slug}.md`를 권장 입력으로 삼는다.
3. slug는 `--name`이 있으면 그 값을 쓰고, 없으면 requirement 파일명에서 `requirement-` 접두어와 `.md`를 제거한다.
4. process dir은 `.process/pipeline-<slug>/`다.

## Phase 1 — 신규/재개 판정

- 신규 실행:
  1. requirement 문서를 읽는다.
  2. `references/routing-rules.md`와 `references/skill-catalog.md`를 읽는다.
  3. 7축 점수, 강제 조건, 선택 파이프라인, step rows를 결정한다.
  4. `python <PIPELINE_INIT> init ...`로 `.process/pipeline-<slug>/pipeline-build.md`와 `pipeline-progress.md`를 생성한다.
  5. `pipeline-build.md`의 `Approval`은 `pending`으로 둔다.
  6. Template Contract Gate를 통과해야 한다.
  7. 사용자에게 선택된 파이프라인, 점수, 강제 조건, 위험요소를 보여주고 승인을 요청한다.
- `--resume`:
  1. 기존 `pipeline-build.md`와 `pipeline-progress.md`를 읽는다.
  2. `Approval`이 approved인지 확인한다.
  3. `Step Status`에서 `done`이 아닌 첫 단계를 현재 단계로 삼는다.
  4. 파일이 없거나 slug가 맞지 않으면 중단한다.

## Template Contract Gate

신규 실행과 `--resume` 모두 Phase 4 진입 전에 build/progress 문서 구조를 검증한다.

규칙:
- `templates/pipeline-build.md`와 `templates/pipeline-progress.md`의 heading과 table header를 보존한다.
- 섹션 이름 변경, 필수 섹션 생략, 표 header 축약, 자유 서술형 대체를 금지한다.
- 값이 없거나 해당 없음이면 섹션을 삭제하지 말고 `none`, `pending`, `skipped`, `AUDIT_BLOCKED` 중 하나로 채운다.
- `{{...}}` placeholder가 남아 있으면 Template Contract Gate 실패다.

필수 build 섹션:
- `## Input`
- `## Scale Assessment`
- `## Routing Decision`
- `## Step Parameters`
- `## Approval`
- `## Risk Notes`

필수 progress 섹션:
- `## Current State`
- `## Step Status`
- `## Output Registry`
- `## Decisions / Deviations`
- `## Append-only Log`
- `## Final Output`

필수 table header:
- build `Scale Assessment`: `| Axis | Score | Evidence |`
- build `Step Parameters`: `| Order | Skill | Input | Required Params | Expected Output | Gate | Next Input |`
- progress `Step Status`: `| Order | Skill | Status | Input | Output | Notes |`

Gate 실패 처리:
- 후속 스킬 실행 금지.
- `pipeline-progress.md`가 존재하면 `Current State`를 `Status: blocked`, `Current Step: template-contract-gate`로 갱신한다.
- `Append-only Log`에 누락/불일치 항목을 기록하고 사용자에게 보고한다.
- 반드시 `python <PIPELINE_CHECK> template --process .process/pipeline-<slug>` 결과가 exit code 0이어야 Phase 3 또는 Phase 4로 진행할 수 있다.

## Phase 2 — 규모 판단과 라우팅

`references/routing-rules.md`의 7축 점수표와 총점+강제 조건 규칙을 적용한다.

필수 기록:
- 각 축의 `Score`와 `Evidence`
- 총점과 규모 구간
- 강제 조건
- 선택된 파이프라인
- `ssot-write` 포함 시 `work-packet-write` 포함 여부
- override가 있으면 위험 노트

## Phase 3 — 승인 게이트

신규 실행은 build/progress를 작성한 뒤 반드시 멈춘다.

- `pipeline-build.md`의 `Approval` `Status`가 정확히 `approved`가 아니면 Phase 4 진입 금지.
- 사용자가 승인하면 `pipeline-build.md`의 `Approval`을 `approved`로 갱신하고, `Approved By`, `Approved At`도 채운다.
- 승인되면 `pipeline-progress.md`의 `Current State`를 `Status: in-progress`, `Current Step: <first-skill>`로 갱신하고, `Append-only Log`에 approval 이벤트를 추가한 뒤 Phase 4로 간다.
- Phase 4 진입 전 반드시 `python <PIPELINE_CHECK> approval --process .process/pipeline-<slug>`를 실행하고 exit code 0을 확인한다.
- 사용자가 거절하거나 수정을 요청하면 build/progress에 기록하고 실행하지 않는다.
- 승인 없이 후속 스킬을 시작하지 않는다.

## Phase 4 — 단계 실행

각 단계는 `pipeline-build.md`의 `Step Parameters`와 `pipeline-progress.md`의 `Step Status`를 기준으로 수행한다.

1. 단계 시작 전 progress의 해당 행을 `doing`으로 갱신하고, `Current State`의 `Current Step`을 해당 skill로 갱신한다.
2. `references/skill-catalog.md`에서 해당 스킬의 입력, 출력, 게이트를 확인한다.
3. `Append-only Log`에 start 이벤트를 추가한다.
4. 해당 `skills/<skill>/SKILL.md`를 읽고 그대로 수행한다.
   - `ssot-write`는 인라인 역할극으로 수행하면 **절대로 안 된다.** `model: opus`가 적용되는 실제 `ssot-write` 스킬을 호출한다.
   - ssot-write Main은 Opus이며 Planner(Opus), Writer(Sonnet), Critic(Opus)을 역할 정의 파일을 먼저 읽는 `general-purpose` bootstrap 독립 agent로 순차 호출한다. named `ssot-*` type 조회와 availability probe는 **절대로 금지한다.**
   - Main은 모든 Agent 호출 직전에 ssot-write process의 `build.md`와 `progress.md`를 다시 읽는다.
   - 에이전트 간 정보는 `plan.json`, `changes.json`, `review.json` 파일 경로로만 전달한다. pipeline main이 artifact 내용을 재작성하거나 역할을 대신하면 **절대로 안 된다.**
   - Writer가 계획된 SSOT를 직접 수정하고 파일·섹션 단위 결과를 `changes.json`에 누적 기록한다.
   - Critic에게 `PLAN_PATH`를 전달하면 **절대로 안 된다.** Critic은 TASK 핵심 의미와 `changes.result_paths`의 실제 SSOT 투영만 비교하며 전체 실행에서 **최대 3회**다.
   - Critic은 모순·핵심 누락·금지 범위 포함·근거 없는 추가 결정 네 의미 check만 수행하며 하나라도 FAIL이면 전체 결과는 **무조건 FAIL**이다.
   - Critic `FAIL`은 **반드시 Planner부터** REPAIR cycle을 시작한다. Planner는 FAIL finding 관련 target만 계획하며 Writer로 바로 돌아가면 **절대로 안 된다.**
   - NOOP도 Writer만 생략하고 Critic 검토를 거친다. ssot-write 내부에는 승인·commit 단계가 없다.
   - 신규 ssot-write 실행에서 `scripts/ssot_runner.py`를 호출하면 **절대로 안 된다.** 이 스크립트는 기존 Contract v5-v8 process 재개 전용이다.
   - Gate Controller, `state.json`, baseline, diff replay, audit, 중단 후 재개를 요구하면 **절대로 안 된다.**
   - 모든 자연어 과정·질문·산출물·최종 보고는 한국어를 사용한다.
5. 산출물 경로를 `Output Registry`와 해당 단계 행에 기록한다.
6. 게이트를 통과하면 단계 행을 `done`으로 갱신하고 `Append-only Log`에 result 이벤트를 추가한다.
7. 실패, 미확인 사항, 사용자 질문이 생기면 단계 행을 `blocked`로 갱신하고 중단한다.

### Post-step reconciliation

하위 스킬 실행이 끝나면 즉시 pipeline-runner 상태로 돌아와 `pipeline-progress.md`를 갱신한다.

- expected output이 존재하면 해당 단계 `Output`과 `Output Registry`를 채운다.
- 하위 스킬 감사가 불가하거나 제한 실행에서 생략되면 `Notes`에 `AUDIT_BLOCKED` 또는 `bounded e2e stop` 사유를 기록한다.
- 사용자 요청으로 특정 단계까지만 실행하는 경우, 그 단계 expected output이 존재하면 해당 단계를 `done`으로 처리하고 나머지 단계는 `skipped`로 표시한 뒤 종료한다.
- 다음 단계로 넘어가기 전 반드시 progress에 append-only log를 추가한다.
- progress가 `doing`인 상태로 최종 응답하지 않는다. 완료면 `done`, 제한 종료면 `skipped`, 막힘이면 `blocked`로 닫는다.
- 각 step 완료 후 반드시 `python <PIPELINE_CHECK> progress --process .process/pipeline-<slug>`를 실행한다. 실패하면 다음 step으로 진행하지 않는다.

### Step output gates

pipeline-runner는 하위 스킬 완료 보고를 그대로 믿지 않고 산출물을 직접 확인한다.

- `task-write`: TASK 파일 존재, TASK 경로를 `Output Registry`에 기록, audit 결과 또는 `AUDIT_BLOCKED` 기록.
- `ssot-write`: process의 `build.md`, `progress.md`, `plan.json`, `review.json`, `handoff.json`을 확인한다. `progress.md` Status와 `handoff.json.status`가 모두 `SUCCESS`이고 Critic 최종 result가 `SUCCESS`일 때만 work-packet-write로 진행한다. plan이 `READY`면 `changes.json`도 필수이며, `NOOP`이면 Writer/changes만 생략한다. `FAILED`·`MANUAL_REQUIRED`는 pipeline blocked다.
- `work-packet-write`: Work Packet 파일 존재, 상태가 `Ready`인지 확인. `Draft`이면 `blocked`.
- `forge-scope`: worktree 존재, branch 존재, forge-scope build/progress 존재, 실행한 build/test 명령과 결과 기록.
- `ddr-loop`: ddr-loop build/progress 존재, conformance 결과 또는 cap 도달 결과 기록.
- `branch-review`: review report 존재, Recommendation 기록.

Step output gate 실패 시 다음 단계로 진행하지 않는다. 해당 step은 `blocked`, `Current State`는 `blocked`, `Append-only Log`에는 실패한 산출물 조건을 기록한다.
최종 보고 전 반드시 `python <PIPELINE_CHECK> outputs --process .process/pipeline-<slug> --repo .`를 실행한다.

단계별 입력 연결:
- `task-write` 출력 TASK는 다음 단계 입력이다.
- `ssot-write` 출력 process는 `work-packet-write --process` 입력이다.
- `work-packet-write` 출력 Work Packet이 `Ready`이면 `forge-scope` 입력이다.
- `work-packet-write`가 없는 경로에서는 TASK가 `forge-scope` legacy 입력이다.
- `ddr-loop`은 forge slug를 입력으로 삼고, Work Packet 기반 forge 산출물이 있으면 `--docs`를 생략한다.
- `branch-review`는 최종 브랜치 diff를 검토한다.

## Phase 5 — 종료

모든 단계가 `done` 또는 `skipped`로 닫히면 `Final Output`을 채우고 간결히 보고한다. 하나라도 `doing`이면 최종 응답 금지이며, `done`, `blocked`, `skipped` 중 하나로 먼저 닫아야 한다.

보고 항목:
- Pipeline process dir
- Selected pipeline
- TASK
- SSOT paths 또는 none
- Work Packet 또는 none
- Forge branch/slug
- DDR result 또는 skipped
- Branch review report

## 실패 처리

| 상황 | 처리 |
|---|---|
| requirement path 없음 | 중단하고 경로를 요구 |
| build/progress 없음 + `--resume` | 중단 |
| 승인 없음 | 후속 스킬 실행 금지 |
| `ssot-write` 포함인데 `work-packet-write` 누락 | build 작성 단계에서 수정 |
| Work Packet `Draft` | `forge-scope` 실행 금지, blocked 기록 |
| 단계 산출물 경로 불명확 | progress에 blocked 기록 후 중단 |
| 사용자 override로 `ssot-write -> forge-scope` 직접 연결 | `SSOT not enforced in forge-scope input` 위험을 build에 기록 |
