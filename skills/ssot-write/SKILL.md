---
name: ssot-write
description: TASK 문서를 입력으로 받아 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 같은 영구 SSOT 문서를 갱신한다. process 디렉터리에 실행계획과 진행로그를 남기고, read-only 서브에이전트의 영향 분석/일관성 감사를 받은 뒤 메인 에이전트가 SSOT 파일을 직접 수정한다. ssot-write, "TASK 기반 SSOT 갱신", "TASK 다음 단계로 설계문서 반영" 요청 시 사용한다.
---

# ssot-write

`docs/<App>/TASK/<App>-TASK-<NNN>.md`를 Scope Authority 로 삼아 영구 SSOT 문서를 좁게 갱신한다.

**책임 경계**:
- 이 스킬은 TASK 이후 단계다. TASK 자체를 새로 작성하지 않는다.
- 메인 에이전트가 절차 오케스트레이터이자 최종 수정 책임자다.
- 서브에이전트는 read-only 영향 분석과 read-only 수정 후 감사만 수행한다.
- 실제 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 수정은 메인 에이전트만 수행한다.
- 후속 실행 문서 작성은 `work-packet-write` 단계로 넘긴다.

**절대 금지**:
- 서브에이전트가 파일을 생성·수정·삭제하지 않는다.
- 영구 SSOT 본문에 TASK markdown link 또는 TASK ID 직접 인용을 남기지 않는다.
- SSOT 변경 이력에 TASK ID 를 쓰지 않는다. "작업 범위 반영", "기능 요구 갱신" 같은 내용 중심 요약을 쓴다.
- TASK 영향 범위가 애매하거나 신규/기존 기능 판단이 불명확한데 임의로 SSOT 를 수정하지 않는다.

---

## Phase 0: 입력과 프로세스 파일

1. `$ARGUMENTS`에서 인자를 해석한다.
   - 필수: `<TASK-path>`
   - 선택: `--app <APP>`
   - 선택: `--name <slug>`; 없으면 TASK 파일 stem 사용
   - 선택: `--resume`
2. TASK 경로는 `docs/<App>/TASK/<App>-TASK-<NNN>.md` 형식이어야 한다.
   - `--app`이 있으면 경로의 `<App>`과 일치해야 한다.
   - `--app`이 없으면 경로에서 App 을 추출한다.
3. helper 경로를 결정한다.
   - 우선: `./scripts/docs_helpers.py`
   - 없으면: `${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py`
4. 가능하면 TASK 구조를 검증한다.
   ```bash
   python <HELP> check-task --repo . --app <APP> --task <TASK-path>
   ```
   실패하면 중단하고 보정 필요 사항을 보고한다.
5. `.process/<slug>/`를 생성 또는 재사용한다.
   - 실행계획: `ssot-write-build.md`
   - 진행로그: `ssot-write-progress.md`
6. 새 실행이면 `templates/ssot-write-build.md`와 `templates/ssot-write-progress.md`를 복사해 실제 값으로 채운다.
7. `--resume`이면 기존 `ssot-write-progress.md`를 읽고 `done`이 아닌 첫 단계부터 재개한다. 없으면 중단한다.

---

## Phase 1: TASK 검증

TASK 본문만 먼저 읽어 다음을 확인한다.

- 목적, 목표 상태, 비목표, 영향 범위, 완료 기준이 SSOT 갱신 판단에 충분한지.
- §9.2 엣지 케이스와 §9.3 오류 처리가 존재하는지.
- TASK 안에 영구 SSOT markdown link 가 있으면 TASK 품질 문제로 보고한다. SSOT 갱신은 중단한다.

필수 정보가 부족하면 사용자에게 질문하고 중단한다. 질문은 영향 SSOT 판단에 필요한 최소 항목만 한다.

진행로그에 `TASK 검증` 단계를 `doing` 후 `done` 또는 `blocked`로 append 한다.

---

## Phase 2: 영향 SSOT 분석

read-only 서브에이전트에 `templates/impact-auditor-input.md`를 실제 값으로 치환해 전달한다. 출력은 `templates/impact-auditor-output.md` 형식만 받는다.

서브에이전트가 없으면 메인 에이전트가 분석을 수행할 수 있지만, 결과 보고의 Audit 은 `AUDIT_BLOCKED - read-only subagent unavailable` 로 표시한다.

impact auditor output의 `Required SSOT Coverage Matrix`를 검토한다. `PRD / FC / FRD / ADR / ADR-CATALOG / ARCHITECTURE`가 모두 판정되어야 하며, `BLOCKED` 행이나 blocking question이 있으면 사용자 질문 후 중단한다.

영향 분석 기준:
- 신규 기능이면 필요한 PRD/FC/FRD를 갱신 또는 생성한다.
- 기존 기능 변경이면 기존 FC/FRD를 좁게 갱신한다.
- 구조·정책·경계 결정이 있으면 ADR을 생성 또는 갱신하고 ADR-CATALOG를 동기화한다.
- 운영성 작업(`refactor`, `maintenance`, `setup`, `migration`, `investigation`)이면 FRD 신설을 강제하지 않는다.
- ARCHITECTURE는 런타임 구조, 진입점, 배포/운영 흐름, 주요 의존성 경계가 바뀔 때만 갱신한다.
- 모호한 영향 범위, 신규/기존 기능 판단, ADR 필요성 판단은 사용자에게 질문하고 중단한다.

영구 SSOT 작성 규칙은 `DOCUMENT_GUIDE v0.9`의 SSOT upsert 규칙을 좁게 재사용한다.

진행로그에는 서브에이전트 결과의 요약과 판정만 기록한다. 전문을 복사하지 않는다.

---

## Phase 3: SSOT 수정 계획 확정

메인 에이전트가 영향 분석 결과를 검토해 수정 계획을 확정한다.

계획에는 다음만 포함한다.
- `CREATE` 또는 `UPDATE` 대상 SSOT 경로
- 각 파일에서 바꿀 절 또는 표
- 변경 이유 한 줄
- 신규 번호가 필요하면 번호 산출 방식
- 사용자 확인이 필요한 모호점

확정된 계획은 `.process/<slug>/ssot-write-build.md`의 `Confirmed SSOT Action Matrix`에 기록한다. 이 matrix는 Phase 4 수정 범위와 Phase 5 감사 입력의 기준이다.

사용자 확인이 필요한 항목이 있으면 여기서 중단한다. 확인 없이 임의 생성·임의 갱신하지 않는다.

---

## Phase 4: SSOT 파일 수정

메인 에이전트가 직접 파일을 수정한다.

수정 원칙:
- 변경은 TASK가 요구하는 범위로 제한한다.
- 템플릿이 있으면 관련 SSOT 템플릿을 읽고 구조를 맞춘다.
- 기존 문서의 표기, 버전, 변경 이력 형식을 따른다.
- 변경 이력에는 TASK ID 대신 내용 중심 요약을 쓴다.
- 영구 SSOT 본문에 TASK 파일 링크, TASK ID, `.process` 링크를 남기지 않는다.
- FC와 FRD 번호, ADR과 ADR-CATALOG 행, PRD 주요 기능 요약이 서로 일치하도록 한다.

권장 순서:
1. ADR 또는 ARCHITECTURE처럼 결정·구조 기준이 되는 문서
2. FRD
3. PRD
4. FC
5. ADR-CATALOG

실제 수정 결과를 진행로그에 append 한다.

---

## Phase 5: 수정 후 일관성 감사

read-only 서브에이전트에 `templates/consistency-auditor-input.md`를 실제 값으로 치환해 전달한다. 출력은 `templates/consistency-auditor-output.md` 형식만 받는다.

감사 입력에는 Phase 3에서 확정해 build 파일에 기록한 `Confirmed SSOT Action Matrix`와 impact audit result summary를 포함한다.

감사 범위:
- 이번 실행에서 생성·수정한 SSOT 파일
- TASK 파일
- `.process/<slug>/ssot-write-build.md`
- `.process/<slug>/ssot-write-progress.md`
- `git status`와 `git diff --name-only`
- 가능하면 `python <HELP> check --repo . --app <APP>`

감사 실패 시 메인 에이전트가 SSOT 파일을 보강하고 감사를 다시 요청할 수 있다. 서브에이전트는 어떤 경우에도 파일을 수정하지 않는다.

---

## Phase 6: 결과 보고

최종 응답은 다음 형식으로 간결히 보고한다.

```text
UPDATE/CREATE <SSOT paths>
Process: .process/<TASK-stem>/
Audit: PASS | FAIL | AUDIT_BLOCKED - read-only subagent unavailable
Next: work-packet-write
```

감사가 `FAIL`이면 실패 항목과 남은 수정 필요 사항을 1줄씩 덧붙인다.
