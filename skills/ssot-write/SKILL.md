---
name: ssot-write
description: TASK 문서를 입력으로 받아 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 같은 영구 SSOT 문서를 멀티 에이전트로 갱신한다. 메인 Opus는 원문을 직접 읽거나 파일을 수정하지 않고 오케스트레이션만 수행하며, Opus planner/auditor가 판단하고 Sonnet actor가 확정 범위의 파일 수정을 수행한다. ssot-write, "TASK 기반 SSOT 갱신", "TASK 다음 단계로 설계문서 반영", "컨텍스트를 보존하며 SSOT 갱신" 요청 시 사용한다.
---

# ssot-write

`docs/<App>/TASK/<App>-TASK-<NNN>.md`를 Scope Authority로 삼아 영구 SSOT 문서를 좁게 갱신한다.

## 실행 아키텍처

이 스킬은 메인 에이전트의 컨텍스트를 보존하는 멀티 에이전트 오케스트레이션이다.

| 역할 | 모델 | 책임 | 쓰기 권한 |
|---|---|---|---|
| Main orchestrator | Opus 세션 | 인자 해석, 에이전트 호출, 상태 gate, 사용자 질문, 최종 보고 | 없음 |
| Planning thinker | `model: "opus"` | TASK 검증, SSOT 영향 분석, 수정 계획 확정 | 전용 `.process` 계획 산출물만 |
| SSOT actor | `model: "sonnet"` | 확정 계획에 따른 SSOT 생성·수정, 명시된 보정 | 대상 SSOT와 전용 `.process` 실행 산출물 |
| Consistency auditor | `model: "opus"` | 수정 결과, 구조·ID·문서 간 일관성 감사 | 전용 `.process` 감사 산출물만 |

모든 서브에이전트는 `subagent_type: "general-purpose"`로 호출하고 effort는 세션 값을 상속한다. 이 스킬은 메인 모델을 바꾸지 못하므로 Opus 세션에서 시작해야 한다.

### 메인 컨텍스트 보존 계약

- 메인은 TASK 본문, SSOT 본문, 전체 diff, 에이전트 산출물 전문을 읽지 않는다.
- 메인은 서브에이전트에 파일 내용을 복사하지 않고 repo root, 입력 경로, process 경로, 역할 템플릿 경로만 전달한다.
- 상세 분석과 인계는 `.process/<slug>/` 파일로 전달한다. 다음 에이전트가 그 파일을 직접 읽는다.
- 각 서브에이전트는 메인에 아래 envelope만 반환한다. `SUMMARY`는 최대 5개 bullet이다.

```text
STATUS: READY | PASS | FAIL | BLOCKED
ARTIFACT: <process artifact path>
SUMMARY: <maximum 5 bullets>
QUESTION: <none or one blocking question>
CHANGED: <paths or none>
```

- 메인은 envelope의 `STATUS`, `QUESTION`, `CHANGED`만으로 다음 단계를 결정한다.
- `BLOCKED`면 질문을 그대로 사용자에게 전달하고, 답을 받은 뒤 해당 역할을 새로 호출한다.
- 서브에이전트를 사용할 수 없으면 메인이 대신 분석하거나 수정하지 않는다. `AUDIT_BLOCKED - required subagent unavailable`로 중단한다.

## 책임 경계

- 이 스킬은 TASK 이후 단계다. TASK 자체를 새로 작성하거나 수정하지 않는다.
- planning thinker가 판단하고, SSOT actor만 영구 SSOT를 수정한다.
- actor는 확정된 `Confirmed SSOT Action Matrix` 밖의 결정을 내리지 않는다.
- 후속 실행 문서 작성은 `work-packet-write` 단계로 넘긴다.

**절대 금지**:

- 메인 orchestrator가 TASK/SSOT 본문을 읽거나 파일을 생성·수정·삭제하지 않는다.
- planning thinker 또는 auditor가 TASK/SSOT를 생성·수정·삭제하지 않는다.
- actor가 TASK를 수정하거나 확정 matrix 밖의 SSOT를 수정하지 않는다.
- 영구 SSOT 본문이나 변경 이력에 TASK markdown link 또는 TASK ID 직접 인용을 남기지 않는다.
- 영향 범위, 신규/기존 기능, ADR 필요성이 애매한데 임의로 진행하지 않는다.

---

## Phase 0: bootstrap / resume 위임

1. 메인이 `$ARGUMENTS`에서 다음만 해석한다.
   - 필수: `<TASK-path>`
   - 선택: `--app <APP>`
   - 선택: `--name <slug>`; 없으면 TASK 파일 stem
   - 선택: `--resume`
2. 메인은 Sonnet actor를 bootstrap 모드로 호출한다.
3. bootstrap actor는 다음을 수행한다.
   - TASK 경로와 App 일치 여부 확인
   - helper 탐색 및 가능하면 `check-task` 실행
   - 새 실행이면 템플릿으로 `.process/<slug>/ssot-write-build.md`와 `ssot-write-progress.md` 생성
   - resume이면 progress를 읽어 재개할 첫 단계를 판정
4. bootstrap actor는 progress를 갱신하고 envelope만 반환한다. TASK 검증의 내용 판단은 하지 않는다.

bootstrap에도 `templates/ssot-actor-input.md`를 사용하고 `Mode: bootstrap`을 지정한다.

---

## Phase 1-3: Opus planning thinker

`templates/impact-planner-input.md`의 경로 placeholder만 dispatch prompt에 제공한다. planner가 템플릿을 직접 읽어 실행하게 한다.

planner는 다음을 한 호출에서 수행한다.

1. TASK의 목적, 목표 상태, 비목표, 영향 범위, 완료 기준, §9.2 엣지 케이스, §9.3 오류 처리를 검증한다.
2. TASK에 영구 SSOT markdown link가 있거나 정보가 부족하면 `BLOCKED`로 판정한다.
3. PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE를 각각 `CREATE / UPDATE / SKIP / BLOCKED`로 판정한다.
4. 모호점이 없으면 `.process/<slug>/ssot-write-impact.md`를 작성한다.
5. `.process/<slug>/ssot-write-build.md`의 `Confirmed SSOT Action Matrix`를 확정하고 progress를 갱신한다.
6. 메인에는 envelope만 반환한다.

판단 기준:

- 신규 기능이면 필요한 PRD/FC/FRD를 갱신 또는 생성한다.
- 기존 기능 변경이면 기존 FC/FRD를 좁게 갱신한다.
- 구조·정책·경계 결정이면 ADR과 ADR-CATALOG를 동기화한다.
- 운영성 작업(`refactor`, `maintenance`, `setup`, `migration`, `investigation`)은 FRD 신설을 강제하지 않는다.
- ARCHITECTURE는 런타임 구조, 진입점, 배포·운영 흐름, 주요 의존성 경계가 바뀔 때만 갱신한다.
- 영구 SSOT 작성 규칙은 `DOCUMENT_GUIDE v0.9`의 SSOT upsert 규칙을 좁게 재사용한다.

planner는 `model: "opus"`로 호출한다. 메인은 planner의 상세 matrix를 자기 컨텍스트로 다시 읽거나 재판단하지 않는다. 구조적으로 완결된 `READY` envelope이면 Phase 4로 라우팅한다.

---

## Phase 4: Sonnet SSOT actor

`templates/ssot-actor-input.md`를 사용해 `Mode: apply`로 Sonnet actor를 호출한다. actor는 TASK, impact artifact, build의 confirmed matrix, 대상 SSOT와 관련 템플릿을 직접 읽는다.

actor 규칙:

- `CREATE`와 `UPDATE` 행만 실행한다. `SKIP` 행은 수정하지 않는다.
- 확정 matrix에 없는 경로·절·표로 범위를 확장하지 않는다.
- 아키텍처·정책·신규 번호 판단을 새로 하지 않는다. 계획이 불충분하면 `BLOCKED`로 반환한다.
- 기존 문서의 표기, 버전, 변경 이력 형식을 따른다.
- 변경 이력에는 TASK ID 대신 내용 중심 요약을 쓴다.
- FC/FRD 번호, ADR/ADR-CATALOG 행, PRD 주요 기능 요약을 서로 일치시킨다.
- `.process/<slug>/ssot-write-action.md`와 progress를 갱신한다.
- 메인에는 변경 경로를 포함한 envelope만 반환하고 diff 본문을 보내지 않는다.

권장 수정 순서:

1. ADR 또는 ARCHITECTURE
2. FRD
3. PRD
4. FC
5. ADR-CATALOG

actor는 `model: "sonnet"`으로 호출한다.

---

## Phase 5: Opus consistency auditor

`templates/consistency-auditor-input.md`를 사용해 Opus auditor를 호출한다. auditor는 TASK, impact/build/action artifacts, 변경된 SSOT, git status/diff, helper 결과를 직접 검사한다.

감사 범위:

- confirmed matrix의 모든 `CREATE / UPDATE / SKIP` 행
- actor가 실제 변경한 SSOT 파일과 누락·범위 초과 여부
- FC/FRD 및 ADR/ADR-CATALOG ID 일관성
- PRD/FC/FRD/ADR/ARCHITECTURE 간 의미 일관성
- TASK 링크·ID가 영구 SSOT에 남지 않았는지
- 가능하면 `python <HELP> check --repo . --app <APP>` 결과

auditor는 `.process/<slug>/ssot-write-audit.md`와 progress만 쓸 수 있고 SSOT는 수정하지 않는다. `model: "opus"`로 호출하며 메인에는 envelope만 반환한다.

`FAIL`이면 메인은 감사 전문을 읽지 않고 Sonnet actor를 `Mode: repair`로 다시 호출한다. repair actor가 audit artifact의 file-specific fixes만 적용한 뒤 Opus 감사를 다시 실행한다. repair/audit 반복은 최대 2회다. 이후에도 실패하면 남은 artifact 경로와 요약을 보고하고 중단한다.

---

## Phase 6: 결과 보고

감사가 통과하면 Sonnet actor를 `Mode: finalize`로 호출해 progress의 결과 보고 단계를 완료하고 최종 changed-path envelope를 받는다. 메인은 이 envelope와 process 경로만 사용해 간결히 보고한다.

```text
UPDATE/CREATE <SSOT paths>
Process: .process/<TASK-stem>/
Audit: PASS | FAIL | AUDIT_BLOCKED - required subagent unavailable
Next: work-packet-write
```

감사가 `FAIL`이면 `.process/<slug>/ssot-write-audit.md` 경로와 남은 수정 요약만 덧붙인다.
