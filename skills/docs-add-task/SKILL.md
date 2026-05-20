---
name: docs-add-task
description: v0.7 per-App SSOT 체계에서 기존 기능 수정/개선/refactor TASK + ARD 를 in-place 작성한다. TASK + ARD 파일 생성, AI 가 FC 보고 영향 FRD 다수 자동 식별 후 변경 이력 + 영향 section 갱신, FC 행 상태 갱신, ARD-CATALOG Proposed 행 추가. 사용자가 기존 기능 수정/개선/refactor 를 자연어로 요청 (예: "주문 검색에 페이지네이션 추가") 할 때 트리거.
argument-hint: "[수정/개선/refactor 자연어 prompt]"
---

# docs-add-task

Docs/_templates v0.7 체계 (per-App PRD/FC/ARCHITECTURE/FRD/ARD/ARD-CATALOG/TASK) 에서 **기존 기능 수정/개선/refactor TASK + ARD 항상 동반 생성**. AI 가 FC 파싱하여 **영향 FRD 다수 자동 식별**. source repo in-place 수정.

---

## 핵심 원칙

- **v0.7 전용**.
- **In-place** 수정. preview 없음.
- **TASK 휘발성** — 본 skill 은 생성만. 삭제는 사용자 수동.
- **ARD 항상 강제** — TASK 1개 = ARD 1개.
- **외부 SSOT 인용 금지 (v0.7 양방향 룰)** — TASK 본문에 영구 SSOT 마크다운 링크 사용 X. 영향 SSOT 는 §6 표에 텍스트로만 명시.
- **AI 가 영향 FRD 자동 식별** — 사용자가 FRD ID 지정하지 않음. AI 가 FC 파싱 + prompt 매칭.
- **FRD 본문 부분 갱신** — 변경 이력 표 + AI 판단 영향 section 텍스트만. TASK ID 인용 X.
- **부분 실패 시 rollback X**.

---

## Phase 0: 대상 App 결정

```
python scripts/docs_helpers.py list-apps --repo .
```

(/docs-add-frd Phase 0 와 동일)

---

## Phase 1: 입력 수집

사용자 prompt 에서 파싱:

**필수**
- `title` — TASK 작업명 (e.g. "주문 검색 페이지네이션 추가")
- `purpose` — 작업 목적 (§1)
- `work_type` — 다음 중 선택:
  - `refactor` / `maintenance` / `migration` / `setup` / `investigation` / `feature` / `변경` / `버그수정`
- `완료 상태` — 작업 완료 후 관찰 가능한 상태 (§1)

**선택**
- `priority` (default `P1`)
- `steps` — §8 작업 단계 (없으면 AI 가 prompt 에서 추론)
- `completion_criteria` — §9 (default `미작성/추후`)
- `risks` — §10
- `ard_decision` (override 가능, 없으면 AI 추론)

---

## Phase 2: 영향 FRD 자동 식별

```
python scripts/docs_helpers.py parse-fc --repo . --app <App>
```

응답 JSON 의 `features[]` 사용.

AI 작업:
1. 사용자 prompt 의 의도와 각 feature 의 `name + summary` 매칭 (의미론적)
2. 영향 FRD ID 목록 산출 (다수 가능)
3. 0건 + work_type ∈ {`feature`, `변경`, `버그수정`} → `AskUserQuestion` 확인 ("FRD 무관계 작업 맞나요? 또는 신규 기능이면 `/docs-add-frd` 권장")
4. 0건 + work_type ∈ {`refactor`, `maintenance`, `setup`, `migration`, `investigation`} → 운영성 작업으로 진행

식별 결과 사용자 제시 + `AskUserQuestion`:
- 옵션 1: "이대로 진행" (Recommended)
- 옵션 2: "추가/제거 필요"

수정 → 사용자 입력 받은 후 재제시.

---

## Phase 3: 번호 할당 + 컨텍스트 수집

```
python scripts/docs_helpers.py next-id --repo . --app <App> --kind task
python scripts/docs_helpers.py next-id --repo . --app <App> --kind ard
python scripts/docs_helpers.py git-user --repo .
```

영향 FRD 각각에 대해:
```
python scripts/docs_helpers.py parse-frd --repo . --app <App> --frd-id <F_NNN>
```

응답에서 추출:
- `version` — patch bump 기준
- `sections` — §5/§8/§9/§11/§15/§17 등 본문 (컨텍스트 임베드용)
- `ac_max`, `tc_max`, `q_max` — AC/TC/Q 추가 시 다음 번호

---

## Phase 4: 다중 ARD 케이스 처리

AI 가 prompt 에서 결정 사항 N개 식별:
- N ≤ 1 → 그대로 진행
- N ≥ 2 → `AskUserQuestion`:
  - "첫 결정만 본 TASK 의 ARD 로 등재. 나머지는 별도 `/docs-add-task` 실행 권장" (Recommended)
  - "결정 N개를 하나의 ARD 에 통합 narrative"

---

## Phase 5: TASK 파일 내용 준비

`_templates/App/TASK/APP-TASK-001-TEMPLATE.md` 기준.

### 메타 표 (5 행, 관련 문서 행 없음)
```
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-TASK-<NNN> |
| 버전 | 0.1 (Draft) |
| 상태 | Draft |
| 작업 유형 | <work_type> |
| 작성 가정 | 영향 FRD 사전 갱신 완료. 본 TASK 는 AI 실행용 휘발성 작업 지시서. |
```

### 변경 이력 표 (1 행)

### §1 작업 요약 ~ §12 컨텍스트 임베드

| § | 제목 | 채움 룰 |
|---|---|---|
| 1 | 작업 요약 | 목적/계기/완료 상태/반복 여부=일회성/우선순위 표 |
| 2 | 배경 | 현재 상태 + 미시행 시 문제 (prompt 추론) |
| 3 | 목표 상태 | 완료 후 코드·런타임 관찰 가능 결과 |
| 4 | 비목표 | 본 작업에서 다루지 않는 범위 |
| 5 | 영향 범위 | 코드 영역/사용자 흐름/운영 흐름/외부 이해관계자 표 |
| 6 | 영구 SSOT 갱신 여부 | **필수, 텍스트만** (아래 참조) |
| 7 | 결정 필요 사항 | "없음" 또는 D-T<NNN>-001 행 |
| 8 | 작업 단계 | steps 표 (단계/작업/산출물/선행 조건/상태=Todo) |
| 9 | 완료 기준 | AC-T<NNN>-001 행 |
| 10 | 리스크와 되돌림 기준 | risks 표 또는 "없음" 행 |
| 11 | 미확인 사항 | Q-T<NNN>-001 행 또는 "없음" |
| 12 | 컨텍스트 임베드 | 영향 FRD 본문에서 §8/§9/§15 복제·요약 (마크다운 링크 X) |

**§6 영구 SSOT 갱신 여부** (Phase 8 마지막에 채움 — Phase 7 갱신 완료 후):
```
| SSOT | 영향 여부 | 갱신 내용 요지 | 갱신 상태 |
|---|---|---|---|
| <App>-PRD | 없음 / 필요 | <요지 또는 "없음"> | 완료 / 불필요 / 실패 |
| <App>-FC | 필요 | F<NNN> 행 상태 갱신 | 완료 / 실패 |
| <App>-FRD-<NNN> | 필요 | <영향 절 요지> | 완료 / 실패 |
| <App>-ARD-<NNN> | 필요 | 신설 (결정 narrative) | 완료 / 실패 |
| <App>-ARD-CATALOG | 필요 | Proposed 행 추가 | 완료 / 실패 |
| <App>-ARCHITECTURE | 없음 / 필요 | <요지 또는 "없음"> | 완료 / 불필요 |
```

**§12 컨텍스트 임베드 룰** (v0.7 양방향 인용 금지):
- 각 영향 FRD 의 §8/§9/§15 텍스트를 **복제·요약** (마크다운 링크 X)
- 형식: `### 12.1 외부 계약 / 데이터 소스`, `### 12.2 데이터 구조 / 정책`, `### 12.3 코드 경로 / 통합 지점`, `### 12.4 검증 명령 (선택)`

---

## Phase 6: ARD 파일 내용 준비

`/docs-add-frd` Phase 4 와 동일. 차이:
- ARD 본문 §컨텍스트 = TASK 명세 요약 (FRD 본문 아님)
- §결정 = AI 가 TASK 의 work_type + steps 보고 narrative
  - `refactor` → "기존 구조 X 를 Y 로 전환"
  - `maintenance` → "표준 운영 절차, 특이 결정 없음"
  - `feature` (기존 기능 확장) → "확장 정책 결정"
- § 문서 반영:
  - `[<App>-ARD-CATALOG]` — Proposed 행 추가
  - `[<App>-FC]` — F<NNN> 행 상태 갱신
  - `[<App>-FRD-<NNN>]` — 영향 절 (다수)
  - `[<App>-TASK-<NNN>]` — **인용 X** (휘발성 룰)

---

## Phase 7: 영향 FRD 본문 갱신 내용 준비

각 영향 FRD 에 대해:

### 버전 bump

`parse-frd` 응답의 `version` 에서 patch +1.
- `0.1 (Draft)` → `0.2 (Draft)`
- `0.2` → `0.3`
- regex `^(\d+)\.(\d+)` 매치 후 group(2) +1

메타 표 `| 버전 |` 셀 값 교체.

### 변경 이력 표 행 1 추가

```
| <new_ver> | <오늘> | <work_type>: <한 줄 요약> | <git-user> |
```

**TASK ID 인용 X** (v0.7 룰). 변경 요약 = TASK title 텍스트만.

### 영향 section 갱신 (AI 판단)

work_type + prompt 의도로 영향 section 결정:

| 의도 | 영향 section |
|---|---|
| 새 흐름 추가 | §5 기본 흐름 |
| 대안 흐름 추가 | §6 대안 흐름 |
| 예외 처리 추가/변경 | §7 예외 흐름 표 |
| 비즈니스 룰 추가 | §8 상세 기능 요구사항 |
| 입출력 변경 | §9 입출력 개념 |
| 상태 추가 | §10 상태 정의 |
| 권한 변경 | §11 권한 조건 |
| 데이터 보존/처리 변경 | §12 데이터 처리 원칙 |
| 비기능 (성능/보안) 변경 | §13 비기능 요구사항 |
| 로그/알림 추가 | §14 |
| API/UI 영향 | §15 |
| 새 수용 기준 | §17 — `AC-F<NNN>-<ac_max+1>` 행 추가 |
| 새 테스트 케이스 | §18 — `TC-F<NNN>-<tc_max+1>` 행 추가 |

**section 텍스트 갱신**:
- 기존 텍스트 유지 + 추가 항목 append
- 형식: `\n- <YYYY-MM-DD> <work_type>: <한 줄 요약>` 또는 표 행 추가

영향 없는 section 무변경.

---

## Phase 8: FC 행 갱신 내용 준비

각 영향 FRD 의 F<NNN> 행에 대해 AI 자유롭게 갱신.

### `### 기본 식별·설명` 행
- `기능 상태`: 의미적으로 적합한 값 (예: 진행 작업 → `In Progress`)
- `구현 상태`: `Implementing` 또는 `Blocked`
- `테스트 상태`: `작성중`

v0.7 일관성 룰 따름:
| 기능 상태 | 허용 구현 상태 | 허용 테스트 상태 |
|---|---|---|
| Draft | Not Started | 미작성 |
| Ready | Not Started | 미작성 |
| In Progress | Implementing / Blocked | 미작성 / 작성중 |
| Done | Implemented | 통과 |

### `### 기능 요구 추적` 행
- `문서 영향` 열: 텍스트 끝에 `+ TASK <오늘>` 추가 또는 갱신

---

## Phase 9: ARD-CATALOG 갱신

/docs-add-frd Phase 7 동일.

---

## Phase 10: 사전 확정

전체 변경 사항 사용자에게 출력:

```
## 작성 계획

### 생성 파일
- CREATE Docs/<App>/TASK/<App>-TASK-<NNN>.md (12 section)
- CREATE Docs/<App>/ARD/<App>-ARD-<NNN>.md (Proposed, narrative)

### 영향 FRD 갱신
- UPDATE Docs/<App>/FRD/<App>-FRD-<N1>.md
  - 메타 표 버전 0.1 → 0.2
  - 변경 이력 +1
  - §5 / §15 텍스트 갱신
- UPDATE Docs/<App>/FRD/<App>-FRD-<N2>.md (있을 경우)
  - ...

### FC 행 갱신
- F<N1>: 구현 상태 → Implementing, 테스트 상태 → 작성중
- F<N2>: ...

### ARD-CATALOG
- Proposed 행 1 추가 (<App>-ARD-<NNN>)

### 핵심 채움 값
- TASK 제목: <title>
- 작업 유형: <work_type>
- 영향 FRD: F<N1>, F<N2>, ...
- ARD 제목: <ARD 추론 제목>
```

`AskUserQuestion`:
- 옵션 1: "확정하고 작성 진행" (Recommended)
- 옵션 2: "수정 필요"

수정 → 사용자 입력 반영 후 재제시.

---

## Phase 11: in-place 쓰기 (작성 순서)

1. **ARD 파일** `Write`
2. **영향 FRD 본문** `Edit` (다수)
   - 메타 버전 행
   - 변경 이력 행 추가
   - 영향 section 텍스트
3. **FC** `Edit` (영향 행 상태 컬럼)
4. **ARD-CATALOG** `Edit` (Proposed 행 추가)
5. **TASK 파일** `Write` (마지막 — §6 영향 SSOT 표에 1~4 결과 기반 "완료/실패" 텍스트 채움)

각 단계 실패 = 다음 진행. 결과 보고 partial status.

---

## Phase 12: 자기 검증

```
python scripts/docs_helpers.py check --repo . --app <App>
```

---

## Phase 13: 결과 보고

```
CREATE Docs/<App>/TASK/<App>-TASK-<NNN>.md
CREATE Docs/<App>/ARD/<App>-ARD-<NNN>.md
UPDATE Docs/<App>/FRD/<App>-FRD-<N1>.md (history + sections)
UPDATE Docs/<App>/FRD/<App>-FRD-<N2>.md (history + sections)
UPDATE Docs/<App>/<App>-FC.md (rows updated)
UPDATE Docs/<App>/<App>-ARD-CATALOG.md (Proposed +1)
Checks: <P> PASS, <F> FAIL
```

호스트 영향 (work_type=refactor/migration 이면서 진입점/런타임 영향) 감지 시:
```
[Warning] Docs/<App>/<App>-ARCHITECTURE.md §1·§2 검토 권장 (자동 수정 안 함)
```

Cross-cutting (errorCode/도메인 entity 변경) 감지 시:
```
[Warning] 솔루션 PRD (Docs/PRD.md) 부록 B/D/E 검토 권장
```

TASK 휘발성 안내:
```
[Note] 본 TASK 는 작업 완료 후 삭제 가능 (v0.7 휘발성 룰).
영구 추적은 영향 FRD §변경 이력 + ARD-CATALOG 에 보존됨.
```

---

## 에러 케이스

- App 0건 → 중단 + 가이드
- App 다수 → AskUserQuestion
- 영향 FRD 0건 + feature/변경/버그수정 → 사용자 확인 → 신규 기능이면 `/docs-add-frd` 권장
- NNN 한계 → exit 2 + 중단
- FRD 파일 부재 (FC 에 등재됐으나 실제 파일 없음) → 해당 FRD 갱신 건 skip + 경고
- 다중 결정 → 사용자 분할 권고
