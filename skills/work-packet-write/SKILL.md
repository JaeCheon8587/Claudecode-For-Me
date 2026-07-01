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
- build 파일의 `Confirmed SSOT Action Matrix`에서 `CREATE` 또는 `UPDATE` 대상인 SSOT 파일
- TASK가 직접 실행 경계 판단에 필요한 최소 기존 SSOT 파일
- Work Packet 템플릿: `docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md`

`Confirmed SSOT Action Matrix`가 없으면 TASK와 기존 SSOT로 Required SSOT를 좁게 추론한다. 추론이 모호하면 질문하고 중단한다.

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
- 상태는 실행 준비가 충분하면 `Ready`, 충돌이나 미확인 사항이 남으면 `Draft`로 둔다.
- `연결 TASK`는 반드시 TASK markdown link 로 둔다.
- `Required SSOT`에는 이번 구현자가 반드시 읽어야 하는 문서만 넣는다.
- `읽을 범위`는 파일 전체보다 절·표·행 단위로 좁게 쓴다.
- `실행 규칙`에는 TASK 우선/SSOT 충돌/모호성 중단 규칙을 남긴다.
- `실행 경계`에는 반드시 수행, 금지, 허용, 중단 조건을 채운다.
- `검증 입력`에는 TASK §9, §9.1, §9.2, §9.3과 실행할 빌드/테스트 후보를 적는다. 모르면 `"코드베이스 기준으로 탐색"`이라고 쓴다.
- `Readiness Checklist`는 실제 상태에 맞게 체크한다. 확인하지 못한 항목은 체크하지 않는다.

---

## Phase 4: 자체 검증

쓰기 후 다음을 확인한다.

- [ ] Work Packet 파일 외 문서를 수정하지 않았다.
- [ ] TASK 링크가 존재하고 경로가 맞다.
- [ ] Required SSOT 링크가 실제 존재한다.
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
- Required SSOT 링크 대상 파일 존재 확인
- `.process/<TASK-stem>/ssot-write-build.md` 또는 `--process` build 파일 읽기
- git status / git diff --name-only 확인

서브 에이전트에 금지되는 작업:
- 파일 생성·수정·삭제
- TASK/SSOT/코드 수정
- Work Packet 직접 수정

서브 에이전트 위임에는 별도 템플릿 파일을 사용한다.

- 입력 템플릿: `templates/phase5-auditor-input.md`
- 출력 템플릿: `templates/phase5-auditor-output.md`

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
