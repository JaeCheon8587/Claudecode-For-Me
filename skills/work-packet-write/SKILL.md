---
name: work-packet-write
description: TASK 문서와 반영된 영구 SSOT를 연결해 AI 코드 실행용 Work Packet 문서만 생성한다. App WORK_PACKET 폴더에 App-WP-NNN 형식 문서를 작성하며 TASK/SSOT/코드는 수정하지 않는다. "Work Packet 작성", "패킷 문서 만들어줘", "TASK 다음 forge 입력 문서 생성", "work-packet-write" 요청 시 사용한다.
---

# work-packet-write

`docs/<App>/TASK/<App>-TASK-<NNN>.md`를 Scope Authority 로 삼고, 반영된 SSOT를 Truth Authority 로 연결하는 얇은 실행 manifest 를 만든다.

**책임 경계**:
- 이 스킬은 `task-write`와 `ssot-write` 이후 단계다.
- Work Packet 파일만 생성한다.
- TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일은 수정하지 않는다.
- Work Packet 은 요구사항이나 SSOT 본문을 복제하지 않고, 실행자가 읽을 문서·범위·충돌 규칙·검증 입력만 지정한다.
- 후속 구현은 `forge-scope` 단계로 넘긴다.

**절대 금지**:
- TASK 또는 영구 SSOT를 생성·수정·삭제하지 않는다.
- 코드 파일을 수정하지 않는다.
- SSOT 본문을 Work Packet 에 길게 복제하지 않는다.
- TASK 와 Required SSOT 충돌이 명백한데 임의로 Ready 로 쓰지 않는다.
- Required SSOT 존재 여부가 불명확한데 임의 링크를 만들지 않는다.
- `CREATE/UPDATE target path`가 비어 있거나 파일이 없는데 Ready 로 쓰지 않는다.
- Work Packet 생성 시 상태는 `Draft` 또는 `Ready`만 사용한다. `In Progress` / `Done` / `Dropped`는 후속 운영 상태다.

---

## Phase 0: 입력

1. `$ARGUMENTS`에서 인자를 해석한다.
   - 필수: `<TASK-path>`
   - 선택: `--app <APP>`
   - 선택: `--process <process-dir>`
   - 선택: `--name <title>`
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

---

## Phase 1: 근거 문서 수집

다음만 읽는다.

- TASK 파일
- `--process`가 있으면 `<process-dir>/ssot-write-build.md`
- `--process`가 없으면 `.process/<TASK-stem>/ssot-write-build.md`가 존재할 때만 읽는다.
- build 파일의 `Confirmed SSOT Action Matrix`
- `Confirmed SSOT Action Matrix`에서 `CREATE` 또는 `UPDATE` 대상인 SSOT 파일
- TASK가 직접 실행 경계 판단에 필요한 최소 기존 SSOT 파일
- Work Packet 템플릿: `docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md`

`Confirmed SSOT Action Matrix`를 읽으면 이를 Work Packet의 기준 입력으로 삼는다.

- `CREATE` / `UPDATE` 대상은 기본 `Required`로 본다.
- `CREATE/UPDATE target path`가 비어 있거나 파일이 없으면 임의 링크를 만들지 않는다.
- `CREATE/UPDATE target path` 누락 또는 파일 미존재 행은 Work Packet 상태를 `Draft`로 만들고, 해당 `Source matrix row`를 `Blocking / Open Questions`에 기록한다.
- 실행에 직접 필요 없는 `SKIP` 행은 Required SSOT Execution Matrix에 넣지 않는다.
- `Optional`은 CREATE/UPDATE를 느슨하게 낮추는 용도가 아니라, TASK 실행 판단에 실제로 도움이 되는 예외 입력에만 허용한다.
- Work Packet에는 각 행의 `Source matrix row`를 남겨 ssot-write 판단과 연결한다.

`Confirmed SSOT Action Matrix`가 없으면 TASK와 기존 SSOT로 Required SSOT를 좁게 추론하되, Work Packet 상태는 기본 `Draft`로 두고 `Blocking / Open Questions`에 matrix 부재와 필요한 결정을 적는다. TASK/SSOT만으로 Required SSOT 판단이 모호하면 `Draft` + blocking question으로 생성한다. 문서 경로·SSOT 존재 여부를 신뢰할 수 없어 Work Packet 자체가 오해를 만들 위험이 크면 중단한다.

---

## Phase 2: 번호와 경로

1. 다음 Work Packet 번호를 얻는다.
   ```bash
   python <HELP> next-id --repo . --app <APP> --kind wp
   ```
2. helper 사용이 불가하면 `docs/<App>/WORK_PACKET/`의 기존 `<App>-WP-*.md`를 보고 다음 번호를 판단한다.
3. 출력 경로는 `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md`다.
4. 기존 파일이 있으면 덮어쓰지 말고 중단한다.

---

## Phase 3: Work Packet 작성

템플릿 구조를 따른다. 모든 `{...}` placeholder 와 `TEMPLATE` 경고를 제거한다.

작성 원칙:
- 상태는 `Draft` 또는 `Ready`만 사용한다. `In Progress` / `Done` / `Dropped`는 생성하지 않는다.
- `Execution Gate`를 반드시 작성한다.
- 실행 준비가 충분하고 blocking issue가 없고 Required SSOT target path가 모두 존재하면 `Ready`, 충돌이나 미확인 사항 또는 target path 누락/미존재가 남으면 `Draft`로 둔다.
- `Draft`에는 후속 구현 금지(`Draft = do not implement`) 의미와 `Blocking / Open Questions` 해결 우선순위를 명확히 쓴다.
- `연결 TASK`는 반드시 TASK markdown link 로 둔다.
- `Required SSOT Execution Matrix`를 반드시 작성한다.
- `Required SSOT Execution Matrix`에는 `SSOT type / Action / Document / Read range / Why required / Source matrix row / Priority` 컬럼을 둔다.
- `Required SSOT Execution Matrix`에는 이번 구현자가 반드시 읽어야 하는 문서만 넣는다.
- `CREATE` / `UPDATE` 행은 기본 `Required`로 반영한다. target path가 없거나 파일이 없으면 matrix에 임의 링크를 만들지 말고 `Blocking / Open Questions`에 해당 source row를 기록한다.
- `Source matrix row`에는 `Confirmed SSOT Action Matrix`의 행 번호 또는 식별 가능한 원문 행 라벨을 적는다.
- `읽을 범위`는 파일 전체보다 절·표·행 단위로 좁게 쓴다.
- `Blocking / Open Questions`를 반드시 작성한다. `Ready`이면 `none`으로 명시하고, 미확정 사항이 있으면 `Draft`로 둔다.
- `실행 규칙`에는 TASK 우선/SSOT 충돌/모호성 중단 규칙을 남긴다.
- `실행 경계`에는 반드시 수행, 금지, 허용, 중단 조건을 채운다.
- `검증 입력`에는 TASK §9, §9.1, §9.2, §9.3과 실행할 빌드/테스트 후보를 적는다. 모르면 `"코드베이스 기준으로 탐색"`이라고 쓴다.
- `Readiness Checklist`는 실제 상태에 맞게 체크한다. 확인하지 못한 항목은 체크하지 않는다.
- `Implementation Output Contract`를 반드시 작성하고 `Changed files`, `Scope match`, `Tests run`, `Not run`, `Deviations` 항목을 포함한다.

---

## Phase 4: 자체 검증

쓰기 후 다음을 확인한다.

- [ ] Work Packet 파일 외 문서를 수정하지 않았다.
- [ ] TASK 링크가 존재하고 경로가 맞다.
- [ ] Expected Required SSOT Execution Matrix를 `Confirmed SSOT Action Matrix`에서 도출했다.
- [ ] Required SSOT Execution Matrix 링크가 실제 존재한다.
- [ ] `CREATE/UPDATE target path` 누락 또는 파일 미존재가 있으면 Work Packet 상태가 `Draft`이고 Blocking / Open Questions에 source row가 있다.
- [ ] `Ready`이면 blocking issue가 없고 Required SSOT target path가 모두 존재한다.
- [ ] `Draft`이면 후속 구현 금지 의미가 Execution Gate에 명확하다.
- [ ] CREATE/UPDATE 대상 누락, SKIP 대상 오포함, 과도한 read range가 없다.
- [ ] Blocking / Open Questions가 존재하고 상태와 일치한다.
- [ ] Implementation Output Contract가 존재하고 필수 완료 보고 항목 5개를 포함한다.
- [ ] SSOT 본문을 길게 복제하지 않았다.
- [ ] 실행 규칙, 실행 경계, 검증 입력이 비어 있지 않다.
- [ ] 미치환 `{...}` placeholder 와 `TEMPLATE` 경고가 없다.
- [ ] `Next`가 `forge-scope`다.

---

## Phase 5: read-only 감사

Phase 5 검증은 서브 에이전트에 위임해야 한다. 서브 에이전트는 read-only auditor 로만 동작한다.

서브 에이전트에 허용되는 작업:
- 생성된 Work Packet 읽기
- 연결 TASK 읽기
- Required SSOT Execution Matrix 링크 대상 파일 존재 확인
- `.process/<TASK-stem>/ssot-write-build.md` 또는 `--process` build 파일 읽기
- git status / git diff --name-only 확인

서브 에이전트에 금지되는 작업:
- 파일 생성·수정·삭제
- TASK/SSOT/코드 수정
- Work Packet 직접 수정

서브 에이전트 위임에는 별도 템플릿 파일을 사용한다.

- 입력 템플릿: `templates/phase5-auditor-input.md`
- 출력 템플릿: `templates/phase5-auditor-output.md`

서브 에이전트 호출 시 `model: "sonnet"` 을 지정한다 (구조 표 비교·체크리스트 감사 — Sonnet 충분, 비용 절감). effort는 세션 값을 상속한다. 서브 에이전트 실행 기능이 없으면 종전대로 `AUDIT_BLOCKED` 처리.

서브 에이전트 입력에는 반드시 다음을 채워 전달한다.

- `Confirmed SSOT Action Matrix`
- `Expected Required SSOT Execution Matrix` (Work Packet matrix와 동일 컬럼: `SSOT type / Action / Document / Read range / Why required / Source matrix row / Priority`)
- `Impact / source summary`

감사는 Work Packet에 적힌 링크만 신뢰하지 않고, expected matrix 대비 실제 Work Packet의 누락/불필요/범위 과대 여부를 확인한다.
감사는 expected matrix와 observed Work Packet matrix를 같은 컬럼의 표 대 표로 비교한다.
감사는 `Draft`인데 구현 가능한 것처럼 적힌 경우, `Ready`인데 blocking이 있는 경우, 또는 `CREATE/UPDATE target path` 누락/미존재가 있는데 Ready인 경우 FAIL로 판정한다.

감사 실패 시 보강은 메인 에이전트가 Work Packet 파일에만 수행한다. 서브 에이전트 실행 기능이 없으면 결과에 `AUDIT_BLOCKED - read-only subagent unavailable`을 명시한다.

---

## Phase 6: 결과 보고

다음 형식으로 간결히 보고한다.

```text
CREATE docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md
Task: docs/<App>/TASK/<App>-TASK-<NNN>.md
Audit: PASS | FAIL | AUDIT_BLOCKED - read-only subagent unavailable
Next: forge-scope
```
