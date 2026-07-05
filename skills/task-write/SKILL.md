---
name: task-write
description: 요구사항 문서나 자연어 요청을 App TASK 문서로 작성한다. TASK만 생성하며 FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 같은 영구 SSOT 문서는 분석·수정하지 않는다. "Task 작성", "작업 지시서만 만들어줘", "요구사항으로 TASK 생성", "task-write" 요청 시 사용한다.
---

# task-write

요구사항 입력을 `docs/<App>/TASK/<App>-TASK-<NNN>.md` 작업 범위 계약으로 작성한다.

**책임 경계**:
- TASK 는 Scope Authority 다. 목적·범위·비목표·완료 기준·엣지 케이스·오류 처리·테스트 기준만 정의한다.
- 이 스킬은 **TASK 파일만 생성**한다.
- SSOT 영향 후보를 작성하지 않는다. 그 판단은 후속 `ssot-write` 계열 스킬 책임이다.
- 코드 구현을 하지 않는다.

**절대 금지**:
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 를 생성하지 않는다.
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 를 수정하지 않는다.
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 를 upsert 하지 않는다.
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 같은 영구 SSOT 문서를 분석하지 않는다.
- 영구 SSOT 문서의 갱신 후보, 영향 후보, 링크 목록, 변경 계획을 TASK 안에 작성하지 않는다.

---

## Phase 0: 준비

1. `$ARGUMENTS`에서 옵션을 분리한다.
   - `--app <APP>`: 대상 App 명시.
   - `--from <path>`: 요구사항 문서 경로 명시.
   - 나머지 텍스트: 자연어 작업 요청.
2. 템플릿을 1회 읽는다.
   - 우선: `docs/.templates/App/TASK/APP-TASK-001-TEMPLATE.md`
   - 없으면: `${CLAUDE_PLUGIN_ROOT}/docs/.templates/App/TASK/APP-TASK-001-TEMPLATE.md`
   - 템플릿을 찾지 못하면 중단하고 경로 누락을 보고한다.
3. helper 경로를 결정한다.
   - 우선: `./scripts/docs_helpers.py`
   - 없으면: `${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py`
   - helper 가 없어도 TASK 작성은 가능하지만, App 탐색·번호 할당은 수동 판단이 필요하다고 보고한다.

---

## Phase 1: 입력 수집

입력 근거는 다음 우선순위로 구성한다.

1. `--from <path>`가 있으면 해당 파일을 읽고 요구사항 원문으로 삼는다.
2. 경로 없이 자연어 요청이 있으면 그 요청을 요구사항 원문으로 삼는다.
3. 둘 다 없으면 사용자에게 요구사항 입력을 요청하고, 응답 없이는 진행하지 않는다.

필수로 확보할 정보:
- 대상 App
- 작업명
- 작업 목적
- 완료 상태
- 작업 유형: `feature / refactor / maintenance / migration / setup / investigation / 기타`

필수 정보가 부족하면 사용자에게 질문한다. 단, 질문은 한 번에 하나만 한다.

---

## Phase 2: App 결정

1. `--app`이 있으면 그 값을 사용한다.
2. 없으면 helper 로 App 후보를 찾는다.
   ```bash
   python <HELP> list-apps --repo .
   ```
3. App 후보가 1개면 자동 선택한다.
4. App 후보가 여러 개면 사용자에게 대상 App을 질문한다.
5. App 후보가 없으면 중단한다. 이 스킬은 신규 App 부트스트랩을 하지 않는다.

**금지**:
- App 판단을 위해 FC/FRD/ADR-CATALOG 를 파싱하지 않는다.
- 대상 App이 불명확한데 임의 선택하지 않는다.
- 영구 SSOT 문서를 읽어서 TASK 범위를 역산하지 않는다.

---

## Phase 3: TASK 번호와 요구사항 기준

1. 다음 TASK 번호를 얻는다.
   ```bash
   python <HELP> next-id --repo . --app <APP> --kind task
   ```
   helper 사용이 불가하면 `docs/<App>/TASK/`의 기존 `<App>-TASK-*.md`를 보고 다음 번호를 판단한다.
2. 요구사항 기준 문서를 정한다.
   - `--from`이 `.requirements/` 하위 파일이면 그대로 기준으로 삼는다.
   - `--from`이 외부 파일이면 기준 경로로 기록하지 않고, TASK §6 입력 근거에 원본 경로를 적는다.
   - 자연어 요청만 있으면 별도 파일을 만들지 않고, TASK §6 `입력 근거`에 입력 원문 또는 요약을 기록한다.

---

## Phase 4: TASK 작성

`docs/<App>/TASK/<App>-TASK-<NNN>.md`를 새로 작성한다. 기존 파일이 있으면 덮어쓰지 말고 중단한다.

템플릿의 구조를 따른다. 출력 파일에는 템플릿 경고와 미치환 placeholder 를 남기지 않는다.

### 메타 표

```markdown
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-TASK-<NNN> |
| 버전 | 0.1 (Draft) |
| 상태 | Draft |
| 작업 유형 | <work_type> |
| 작성 가정 | <요구사항 입력 기준의 작업 범위 초안. SSOT 갱신 완료 가정 없음> |
```

`관련 문서` 메타 행을 추가하지 않는다. 관련 SSOT 링크는 Work Packet 책임이다.

### 본문 작성 규칙

| § | 제목 | 작성 규칙 |
|---|---|---|
| 1 | 작업 요약 | 목적·계기·완료 상태·반복 여부·우선순위 |
| 2 | 배경 | 현재 상태와 문제. 요구사항 근거가 없으면 날조하지 않는다 |
| 3 | 목표 상태 | 완료 후 관찰 가능한 상태. 가능하면 기대값/literal 포함 |
| 4 | 비목표 | 이번 TASK에서 하지 않을 일. 범위 확장 방지용 |
| 5 | 영향 범위 | 코드/사용자/운영/외부 이해관계자 수준의 범위. SSOT 후보는 쓰지 않는다 |
| 6 | 입력 근거 | 요구사항 원문·수용 기준 입력·제약/금지·미반영 입력 |
| 7 | 결정 필요 사항 | 실제 결정 필요 항목이 있을 때만 작성. 없으면 절 전체 생략 |
| 8 | 작업 단계 | 실행 가능한 단위. SSOT 문서 갱신 단계는 넣지 않는다 |
| 9 | 완료 기준 | Given/When/Then AC + §9.1 단위 테스트 + §9.2 엣지 케이스 + §9.3 오류 처리 |
| 10 | 리스크와 되돌림 기준 | 리스크가 없으면 "없음 — 사유" |
| 11 | 미확인 사항 | 실제 미확인 항목이 있을 때만 작성. 없으면 절 전체 생략 |
| 12 | 구현 참고 정보 | 이미 확실한 코드 경로/literal/검증 명령 후보만. SSOT 본문 복제 금지 |

### §9 작성 규칙

- AC 는 `AC-T<NNN>-001` 형식으로 작성한다.
- 단위 테스트는 `TS-T<NNN>-001` 형식으로 작성한다.
- 엣지 케이스는 `EC-T<NNN>-001` 형식으로 작성한다.
- 오류 처리는 `ER-T<NNN>-001` 형식으로 작성한다.
- 항목이 없으면 해당 하위절에 `없음 — <사유>` 한 줄을 둔다.
- 오류 메시지·상태 코드·설정 키 등 exact literal 은 §12.2에도 같은 값으로 둔다.

---

## Phase 5: 자체 검증

쓰기 전후로 다음을 확인한다.

Phase 5 검증은 서브 에이전트에 위임해야 한다. 서브 에이전트는 **read-only auditor** 로만 동작한다.

서브 에이전트에 허용되는 작업:
- 생성된 TASK 파일 읽기
- 요구사항 기준 문서 읽기
- git status / git diff --name-only 확인
- helper check-task 실행
- docs_conformance.py 를 TASK 파일 1개 대상으로 실행

서브 에이전트에 금지되는 작업:
- `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 본문 읽기
- SSOT 영향 분석
- SSOT 수정
- TASK 직접 수정

서브 에이전트는 pass/fail 체크리스트와 실패 사유만 반환한다. 검증 실패 시 보강은 메인 에이전트가 TASK 파일에만 수행한다. 서브 에이전트 실행 기능이 없으면 Phase 5 를 완료한 것으로 간주하지 말고, 독립 감사 위임이 불가했다고 결과에 명시한다.

서브 에이전트 위임에는 별도 템플릿 파일을 사용한다.

- 입력 템플릿: `templates/phase5-auditor-input.md`
- 출력 템플릿: `templates/phase5-auditor-output.md`

서브 에이전트 호출 시 `model: "sonnet"` 을 지정한다 (구조 체크리스트 감사 — Sonnet 충분, 비용 절감). effort는 세션 값을 상속한다.

메인 에이전트는 입력 템플릿의 placeholder 만 실제 값으로 치환해 서브 에이전트에 전달한다. 서브 에이전트는 출력 템플릿 형식만 반환해야 한다. TASK 작성 의도나 기대 판정은 전달하지 않는다.

- [ ] TASK 파일 외 문서를 수정하지 않았다.
- [ ] `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 를 생성·수정·upsert 하지 않았다.
- [ ] `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 같은 영구 SSOT 문서를 분석하지 않았다.
- [ ] `FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE` 갱신 후보 목록을 작성하지 않았다.
- [ ] §6 이 "영구 SSOT 갱신 여부"가 아니라 "입력 근거"다.
- [ ] §9.2 엣지 케이스와 §9.3 오류 처리가 존재한다.
- [ ] §7/§11은 실제 항목이 없으면 절 전체가 없다.
- [ ] 미치환 `{...}` placeholder 와 `TEMPLATE` 경고가 없다.
- [ ] TASK 본문에 영구 SSOT 마크다운 링크가 없다.

helper 가 있으면 구조 검사를 실행한다.

```bash
python <HELP> check-task --repo . --app <APP> --task docs/<App>/TASK/<App>-TASK-<NNN>.md
```

요구사항 기준 문서가 있으면 `docs_conformance.py`로 요구사항 ↔ TASK 정합을 검사할 수 있다. 이때 target 은 TASK 파일 1개만 지정한다.

```bash
python <CONF> --reference <reference_doc> --targets docs/<App>/TASK/<App>-TASK-<NNN>.md
```

정합 검증이 실패하면 TASK 만 보강한다. SSOT 문서는 수정하지 않는다.

---

## Phase 6: 결과 보고

다음 형식으로 간결히 보고한다.

```text
CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md
Reference: <요구사항 기준 문서 또는 "대화 입력">
Audit: PASS | FAIL | AUDIT_BLOCKED - read-only subagent unavailable
Next: ssot-write 단계에서 TASK 기반으로 영구 SSOT 문서를 갱신
```
