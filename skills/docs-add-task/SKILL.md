---
name: docs-add-task
description: v0.7 per-App SSOT 체계에서 신규 기능 또는 기존 수정/개선/refactor 설계 문서를 in-place 작성한다. TASK + ADR 항상 생성. 신규 기능이면 FRD 신규 생성·App-PRD §3.1/§7 갱신·FC 5표 행 추가(NEW 모드), 기존 수정이면 AI 가 FC 보고 영향 FRD 다수 자동 식별 후 변경 이력 + 영향 section 갱신·FC 행 상태 갱신(CHANGE 모드). 양 모드 모두 ADR-CATALOG Proposed 행 추가. 사용자가 신규 기능(예: "주문 검색 기능 추가") 또는 기존 수정/개선/refactor(예: "주문 검색에 페이지네이션 추가") 를 자연어로 요청할 때 트리거.
argument-hint: "[신규 기능 또는 수정/개선/refactor 자연어 prompt]"
---

# docs-add-task

docs/.templates v0.7 체계 (per-App PRD/FC/ARCHITECTURE/FRD/ADR/ADR-CATALOG/TASK) 에서 **설계 문서를 항상 TASK + ADR 동반 생성**. `parse-fc` 로 영향 FRD 식별 → **NEW 모드**(신규 기능, 영향 FRD 0건) / **CHANGE 모드**(기존 수정, 영향 FRD ≥1건) 자동 분기. source repo in-place 수정.

---

## 핵심 원칙

- **v0.7 전용**.
- **In-place** 수정. preview 없음.
- **TASK 항상 생성** — 모든 모드에서 TASK 1개 생성 (유일 예외 = Backlog 모드, Phase 2 참조). TASK 휘발성 — 본 skill 은 생성만, 삭제는 사용자 수동.
- **NEW 모드 = FRD 신규 생성 / CHANGE 모드 = 기존 영향 FRD 갱신** — FRD 만 생애주기 분기. TASK·ADR 은 양 모드 공통 생성.
- **ADR 항상 강제** — TASK 1개 = ADR 1개.
- **외부 SSOT 인용 금지 (v0.7 양방향 룰)** — TASK 본문에 영구 SSOT 마크다운 링크 사용 X. 영향 SSOT 는 §6 표에 텍스트로만 명시.
- **AI 가 모드·영향 FRD 자동 식별** — 사용자가 모드·FRD ID 지정하지 않음. AI 가 FC 파싱 + prompt 매칭. 0건이어도 자동 NEW 강행 금지 — 사용자 확인 1회.
- **FRD 본문 부분 갱신 (CHANGE)** — 변경 이력 표 + AI 판단 영향 section 텍스트만. TASK ID 인용 X.
- **부분 실패 시 rollback X**.
- **쓰기 후 Codex 2축 검증-fix 루프** — 기본 ON (`--no-verify` 스킵), max 3회·임계 conformance 99%. fix=Claude (manifest 범위만). cap 소진해도 rollback X. codex 미설치 시 구조 check 폴백.
- **템플릿 대조 강제** — FRD/ADR/TASK/FC/PRD 본문 생성 직전 해당 `.templates/App/.../X-TEMPLATE.md` 1회 `Read`. 절 구조·메타 행 수·placeholder 원본 대조 후 채움. 기억 의존 구조 생성 금지 (drift 방지). 템플릿 부재 시 경고 후 진행.

---

## Phase 0: 대상 App 결정

```
python scripts/docs_helpers.py list-apps --repo .
```

응답 JSON 의 `apps[].code` 이용:
- 0건 → 중단 + 부트스트랩 가이드.
- 1건 → 자동 채택.
- 2건 이상 → `AskUserQuestion` 으로 사용자 선택.

`unbootstrapped` 비어있지 않으면 (CLAUDE.md 등재됐으나 `docs/<App>/` 부재) 경고 보고.

---

## Phase 1: 입력 수집

사용자 prompt 에서 파싱:

**필수**
- `title` — TASK 작업명 (e.g. "주문 검색 페이지네이션 추가", 신규면 "주문 검색 기능 추가")
- `purpose` — 작업 목적 (§1)
- `work_type` — 다음 중 선택:
  - `신규` (NEW 모드 전용 — 신규 기능) / `refactor` / `maintenance` / `migration` / `setup` / `investigation` / `feature` / `변경` / `버그수정`
- `완료 상태` — 작업 완료 후 관찰 가능한 상태 (§1)

**선택**
- `priority` (default `P1`)
- `steps` — §8 작업 단계 (없으면 AI 가 prompt 에서 추론)
- `completion_criteria` — §9 (default `미작성/추후`)
- `risks` — §10
- `adr_decision` (override 가능, 없으면 AI 추론)
- `--no-verify` (flag) — Phase 12 검증-fix 루프 생략, 구조 check + cross-ref 만 (12.5 폴백).

**필수 입력 게이트**: `purpose` 또는 `완료 상태` 를 prompt 에서 추출 실패 시 → `AskUserQuestion` 1회로 수집. 추론·placeholder 날조 금지. 무응답 시에만 `미작성/추후` placeholder. (Backlog 모드는 FRD/TASK 미생성이므로 `purpose` 만 필수.)

---

## Phase 2: 모드 판정 + 영향 FRD 식별

```
python scripts/docs_helpers.py parse-fc --repo . --app <App>
```

응답 JSON 의 `features[]` 사용.

AI 작업:
1. 사용자 prompt 의 의도와 각 feature 의 `name + summary` 매칭 (의미론적)
2. 영향 FRD ID 목록 산출 (다수 가능)
3. **중복 기능 탐지** — 매칭 0건이라도 prompt 와 의도가 강하게 겹치는 기존 F(부분 매칭) 있으면 NEW 강행 전 후보 보류. 명백 신규만 NEW 직행.
4. 아래 표로 모드 판정:

| 조건 | 모드 | 처리 |
|---|---|---|
| 영향 FRD ≥1건 | **CHANGE** | Phase 3C~ 진행 |
| 0건 + 운영성 work_type ∈ {`refactor`,`maintenance`,`setup`,`migration`,`investigation`} | **CHANGE** | FRD 무관 운영 경로 (Phase 3C~) |
| 0건 + 기능 의도 work_type ∈ {`신규`,`feature`,`변경`,`버그수정`} | 판정 필요 | `AskUserQuestion` 아래 참조 |

**0건 + 기능 의도 시 `AskUserQuestion`** (false-negative 보호 — `parse-fc` 의미 매칭이 기존 기능을 놓쳤을 수 있음. 자동 NEW 강행 금지):
- 옵션 1: "신규 기능 — FRD 신설" (NEW 모드) (Recommended)
- 옵션 2: "기존 기능 누락 식별 — FRD ID 직접 지정" (CHANGE 모드, 사용자가 FRD ID 입력)
- (3 스텝서 유사 기존 F 탐지 시) 해당 `F<NN>` 을 옵션 2 후보로 함께 제시 — 중복 FRD 생성 방지.

판정 결과:
- **NEW 모드** → Phase 3N~9N 진행 (FRD 신규 생성).
- **CHANGE 모드** → Phase 3C~10C 진행 (기존 FRD 갱신).

**Backlog 예외** (NEW 모드 특수 early-exit): 사용자가 "backlog" / "확장 후보" 명시 시 — FRD·ADR·TASK **미생성**. FC `## 확장 후보 기능 (Backlog)` 표 행 추가 + App-PRD §3.1 "이번 릴리즈 제외" 갱신만. Phase 8N(ADR-CATALOG) 생략, Phase 10 직행 (FC·PRD 변경만 확정).

---

# ═══ NEW 모드 (신규 기능: FRD 신설) ═══

> 영향 FRD 0건 + 신규 기능 확정 시. FRD 20절 신규 생성 + TASK + ADR + App-PRD §3.1/§7 + FC 5표 행 추가 + ADR-CATALOG Proposed. CHANGE 모드는 본 블록 건너뛰고 Phase 3C 로.

## Phase 3N: 번호 할당

```
python scripts/docs_helpers.py next-id --repo . --app <App> --kind frd
python scripts/docs_helpers.py next-id --repo . --app <App> --kind task
python scripts/docs_helpers.py next-id --repo . --app <App> --kind adr
python scripts/docs_helpers.py git-user --repo .
```

- 활성 FRD NNN, TASK NNN, ADR NNN 산출.
- exit 2 (`FAIL LIMIT`, F099/TASK099/ADR099 초과) 시 즉시 중단 + 보고.
- **parse-frd 미호출** (기존 FRD 부재).
- 오늘 일자 = 시스템 ISO 날짜 (`YYYY-MM-DD`).

---

## Phase 4N: FRD 파일 내용 준비

`.templates/App/FRD/APP-FRD-001-TEMPLATE.md` 기준 20 section + 메타 표 + 변경 이력 표.

### 메타 표 6 행
```
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-FRD-<NNN> |
| 버전 | 0.1 (Draft) |
| 기능 ID | F<NNN> |
| 상태 | Draft |
| 작성 가정 | <prompt 추출 또는 "본 기능은 ..."> |
| 관련 문서 | [<App>-PRD](../<App>-PRD.md) · [<App>-FC](../<App>-FC.md) · [<App>-ARCHITECTURE](../<App>-ARCHITECTURE.md) · [<App>-ADR-CATALOG](../<App>-ADR-CATALOG.md) |
```

### 변경 이력 표
```
## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | <YYYY-MM-DD> | 초안 | <git-user> |
```

### 20 Section 본문

각 section 채움 우선순위 (빈칸·"N/A" 금지):
1. **prompt 명시** → 값 그대로.
2. **prompt + 도메인으로 합리 추론 가능** → 추론값 + 줄 끝 `(추론)` 표기 (검증 대상 가시화).
3. **진짜 불명** → "없음"/"미작성/추후" + **§20 에 `Q-F<NNN>-<다음번호>` 행 등재** (silent 없음 금지 — 미결정은 추적되어야). 기본행 `Q-F<NNN>-001` 유지, 추가 Q는 002부터.

section별 채움 룰:

| § | 제목 | 채움 룰 |
|---|---|---|
| 1 | 기능 요약 | 작업 유형/기능 목적/기대 결과/완료 기준/우선순위/의존 기능 표 |
| 2 | 범위 | 포함/제외/변경 UX/불변 표 |
| 3 | 사용자 역할 | actor 1줄 list |
| 4 | 사전 조건 | preconditions list |
| 5 | 기본 흐름 | main_flow numbered list |
| 6 | 대안 흐름 | alternative_flow list 또는 "없음" |
| 7 | 예외 흐름 | exception_flow 표 또는 E1 placeholder 행 |
| 8 | 상세 기능 요구사항 | acceptance / business rules bulleted |
| 9 | 입출력 개념 | 입력/출력 표 |
| 10 | 상태 정의 | "없음" 또는 상태 표 |
| 11 | 권한 조건 | 역할/허용/거부 표 |
| 12 | 데이터 처리 원칙 | 보존/기간/중복/실패/민감 bulleted |
| 13 | 비기능 요구사항 | 성능/보안/로깅/에러 표 |
| 14 | 로그/알림/이력 정책 | 정보/오류/알림/이력 bulleted |
| 15 | UI / 외부 연계 영향 | UI/외부연계/운영 표 (api_paths 는 외부 연계 행에) |
| 16 | FC/ADR-CATALOG/ADR 반영 여부 | 항상 3 행 자동 (아래 참조) |
| 17 | 수용 기준 | AC-F<NNN>-001 ~ 행 |
| 18 | 테스트 관점 | TC-F<NNN>-001 행 |
| 19 | 요구 근거 | App-PRD / FC 행 링크 + notes |
| 20 | 미확인 사항 | Q-F<NNN>-001 행 (Open 또는 "없음") |

**§16 항상 3 행** (FRD 자기 작업 결과 반영, **TASK 인용 금지** — 휘발성 룰):
```
| 문서 | 반영 여부 | 반영 내용 | 비고 |
|---|---|---|---|
| FC | 필요 | 신규 F<NNN> 등재 (5 표) | 완료 |
| ADR | 필요 | <App>-ADR-<NNN> 신설 | 완료 |
| ADR-CATALOG | 필요 | Proposed 행 추가 | 완료 |
```

**AC/TC/Q ID 자동**:
- `AC-F<NNN>-001` 1행 최소
- `TC-F<NNN>-001 | 미작성/추후 | 미작성/추후 | 미작성/추후 | 미작성/추후` 1행
- `Q-F<NNN>-001 | 없음 | - | - | - | -` 또는 사용자 명시

**코드 상세 금지** (template 룰): 코드 경로·클래스·메서드·API 경로·테스트 명령 FRD 본문 기재 X.

---

## Phase 5N: ADR 파일 내용 준비 (신규 FRD 동반)

`.templates/App/ADR/APP-ADR-001-TEMPLATE.md` 기준.

### 메타 표
```
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-ADR-<NNN> |
| 버전 | 0.1 (Draft) |
| 상태 | Proposed |
| 작성 가정 | 본 FRD 작업과 동반 신설. 결정 narrative 는 본 ADR 본문 |
| 관련 문서 | [<App>-ADR-CATALOG](../<App>-ADR-CATALOG.md) · [<App>-PRD](../<App>-PRD.md) · [<App>-FC](../<App>-FC.md) · [<App>-ARCHITECTURE](../<App>-ARCHITECTURE.md) · [FRD 폴더](../FRD/) · [DOCUMENT_GUIDE](../../DOCUMENT_GUIDE.md) |
```

### 변경 이력
- 0.1 | <오늘> | 초안 | <git-user>

### 본문 (## ADR-<NNN>: <제목>)

- **제목** = AI 가 FRD 명세 보고 추론. "결정 사항 없음" = `"<기능명> 표준 구현 채택"`.
- **컨텍스트** = **FRD §1·§2 요약**.
- **결정** = AI 추론. **fallback 전 실 결정 ≥1 탐색 의무** — 데이터 경계·정책·권한·성능·호환성 중 본 기능이 강제하는 선택지 검토. 진짜 없을 때만 → `"본 기능은 특이 결정 없이 도메인 표준 패턴을 따른다."`
- **결과** = 가능해지는 기능 + 후속 작업.
- **대안 검토** = 없음 → `"대안 검토 없음 (단순 구현)"`. 있으면 옵션 A/B.
- **§ 코드 인용** = `"신규 — 코드 인용 없음 (구현 시 첨부)"`.
- **§ 문서 반영** (필수, **TASK 인용 X**):
  - `[<App>-ADR-CATALOG]` — Proposed 행 추가
  - `[<App>-PRD]` — §3.1 / §7 갱신
  - `[<App>-FC]` — F<NNN> 행 추가 (5표)
  - `[<App>-FRD-<NNN>]` — §16 반영

---

## Phase 6N: FC 갱신 내용 준비 (5표 전부 행 추가)

`docs/<App>/<App>-FC.md` 5표 모두 행 1 추가.

### 1) `### 기본 식별·설명`
```
| F<NNN> | <name> | <summary> | Draft | Not Started | 미작성 | <priority> |
```

### 2) `### 문서 연결`
```
| F<NNN> | [App PRD §7](<App>-PRD.md#7-주요-기능-요약-본-app-한정) | [<App>-FRD-<NNN>](FRD/<App>-FRD-<NNN>.md) | 미작성/추후 | 미작성/추후 | 미작성/추후 |
```

### 3) `### 검증·근거·확인`
```
| F<NNN> | [<App>-FRD-<NNN> §18](FRD/<App>-FRD-<NNN>.md#18-테스트-관점) | [<App>-FRD-<NNN> §17](FRD/<App>-FRD-<NNN>.md#17-수용-기준) | <purpose 요약> → [<App>-FRD-<NNN>](FRD/<App>-FRD-<NNN>.md) | 없음 |
```

### 4) `### 기능 요구 추적`
```
| F<NNN> | <work_type> | <user_impact 또는 "없음"> | FC / FRD / ADR / ADR-CATALOG | [<App>-FRD-<NNN> §17](FRD/<App>-FRD-<NNN>.md#17-수용-기준) |
```

### 5) `### 타 App 협력 흐름`
협력 명시 없으면 무행. 있으면:
```
| F<NNN> | <협력 App> | F<NNN> | 호출 / 이벤트 / 공유 데이터 |
```

NEW 모드는 항상 `Draft / Not Started / 미작성` (consistency 룰표 상단 값 고정).

---

## Phase 7N: App-PRD 갱신 내용 준비

`docs/<App>/<App>-PRD.md`:

### §3.1 (릴리즈 범위)
- `이번 릴리즈 포함` 셀 끝에 `, F<NNN>` 추가. 셀에 placeholder `{본 App 의 현 릴리즈 범위}` 만 있으면 `F<NNN>` 로 교체.
- Backlog 모드 시 `이번 릴리즈 제외` 셀 갱신.

### §7 (주요 기능 요약)
```
| F<NNN> | <name> | <summary> | <release_scope> |
```

---

## Phase 8N: ADR-CATALOG 갱신 내용 준비

`docs/<App>/<App>-ADR-CATALOG.md` `## Proposed` 표 행 1 추가:
```
| [<App>-ADR-<NNN>](ADR/<App>-ADR-<NNN>.md) | <ADR 제목> | <오늘> | <영향 모듈 또는 "F<NNN> 기능"> | <결정 기한 = 오늘+14일> | 개발 리드 |
```
`Proposed` 절 없으면 절 + 표 헤더 자동 신설.

---

## Phase 9N: TASK 파일 내용 준비 (NEW 변형)

`.templates/App/TASK/APP-TASK-001-TEMPLATE.md` 기준. CHANGE 모드 Phase 5C 와 동일 구조, 차이는 아래.

- 메타 작업 유형 = `feature` (신규 구현) 또는 `신규`.
- **§6 SSOT 표 NEW 변형** (Phase 11N 쓰기 결과 기반 "완료/실패"):
```
| SSOT | 영향 여부 | 갱신 내용 요지 | 갱신 상태 |
|---|---|---|---|
| <App>-PRD | 필요 | §3.1 F<NNN> 추가 + §7 행 | 완료 / 실패 |
| <App>-FC | 필요 | 신규 F<NNN> 5표 행 추가 | 완료 / 실패 |
| <App>-FRD-<NNN> | 필요 | F<NNN> 신설 (20절) | 완료 / 실패 |
| <App>-ADR-<NNN> | 필요 | 신설 (결정 narrative) | 완료 / 실패 |
| <App>-ADR-CATALOG | 필요 | Proposed 행 추가 | 완료 / 실패 |
| <App>-ARCHITECTURE | 없음 / 필요 | <요지 또는 "없음"> | 완료 / 불필요 |
```
- **§8 작업 단계** = 그린필드. 신규 구현이라 "처음부터 구현" 단계. 코드 부재 — 단계는 forward-looking (구현 시 확정).
- **§12 컨텍스트 임베드** = 방금 만든 FRD §8/§9/§15 텍스트 복제·요약 (마크다운 링크 X). 신규라 placeholder 다수 가능 — 있는 만큼. §12.3 코드 경로 = "신규 — 구현 시 결정". §12.2.1 코드 일치 필수 literal = FRD 명시 값(상태 코드·메시지·타입명) verbatim, 없으면 "없음".
  - **충분조건**: TASK 실행자가 영향 FRD 를 열지 않고 작업 가능한 최소 충분 정보. §8 룰·§9 입출력 제약·§15 연계 중 **본 작업에 필요한 것만** 발췌. 전문 덤프 금지(토큰), 1줄 요약 금지(self-contained 실패).

NEW 모드 본문 준비 완료 → **Phase 10 (사전 확정)** 으로.

---

# ═══ CHANGE 모드 (기존 수정: 영향 FRD 갱신) ═══

> 영향 FRD ≥1건 또는 운영성 work_type. 기존 FRD 본문 갱신 + TASK + ADR + FC 상태 갱신 + ADR-CATALOG. NEW 모드는 본 블록 건너뜀.

## Phase 3C: 영향 FRD 확인

CHANGE 모드 영향 FRD 목록 (Phase 2 식별 결과) 사용자 제시 + `AskUserQuestion`:
- 옵션 1: "이대로 진행" (Recommended)
- 옵션 2: "추가/제거 필요"

수정 → 사용자 입력 받은 후 재제시.

---

## Phase 4C: 번호 할당 + 컨텍스트 수집

```
python scripts/docs_helpers.py next-id --repo . --app <App> --kind task
python scripts/docs_helpers.py next-id --repo . --app <App> --kind adr
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

## Phase 5C: 다중 ADR 케이스 처리

AI 가 prompt 에서 결정 사항 N개 식별:
- N ≤ 1 → 그대로 진행
- N ≥ 2 → `AskUserQuestion`:
  - "첫 결정만 본 TASK 의 ADR 로 등재. 나머지는 별도 `/docs-add-task` 실행 권장" (Recommended)
  - "결정 N개를 하나의 ADR 에 통합 narrative"

---

## Phase 6C: TASK 파일 내용 준비

`.templates/App/TASK/APP-TASK-001-TEMPLATE.md` 기준.

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
| 9 | 완료 기준 | AC-T<NNN>-001 행 — **Given/When/Then** (Then=기대결과 literal 우선) + **검증 대상(§8 단계/§3)** 열. **§9.1 단위 테스트 명세** 표 동반(전부 **단위 테스트**): 테스트명·프로젝트·클래스·함수·선행 조건/픽스처·검증 대상·도입 근거·검증 AC. 그린필드는 프로젝트/클래스/함수 "신규 — 구현 시 확정" |
| 10 | 리스크와 되돌림 기준 | risks 표 또는 "없음" 행 |
| 11 | 미확인 사항 | Q-T<NNN>-001 행 또는 "없음" |
| 12 | 컨텍스트 임베드 | 영향 FRD 본문에서 §8/§9/§15 복제·요약 (마크다운 링크 X) |

**§6 영구 SSOT 갱신 여부** (Phase 11 쓰기 마지막에 채움 — Phase 8C 갱신 완료 후):
```
| SSOT | 영향 여부 | 갱신 내용 요지 | 갱신 상태 |
|---|---|---|---|
| <App>-PRD | 없음 / 필요 | <요지 또는 "없음"> | 완료 / 불필요 / 실패 |
| <App>-FC | 필요 | F<NNN> 행 상태 갱신 | 완료 / 실패 |
| <App>-FRD-<NNN> | 필요 | <영향 절 요지> | 완료 / 실패 |
| <App>-ADR-<NNN> | 필요 | 신설 (결정 narrative) | 완료 / 실패 |
| <App>-ADR-CATALOG | 필요 | Proposed 행 추가 | 완료 / 실패 |
| <App>-ARCHITECTURE | 없음 / 필요 | <요지 또는 "없음"> | 완료 / 불필요 |
```

**§12 컨텍스트 임베드 룰** (v0.7 양방향 인용 금지):
- 각 영향 FRD 의 §8/§9/§15 텍스트를 **복제·요약** (마크다운 링크 X)
- **충분조건**: TASK 실행자가 영향 FRD 를 열지 않고 작업 가능한 최소 충분 정보. 본 작업에 필요한 룰·제약·입출력만 발췌. 전문 덤프 금지, 1줄 요약 금지.
- 형식: `### 12.1 외부 계약 / 데이터 소스`, `### 12.2 데이터 구조 / 정책`, `### 12.2.1 코드 일치 필수 literal`, `### 12.3 코드 경로 / 통합 지점`, `### 12.4 검증 명령 (선택)`
- **§12.2.1** = 코드가 정확 일치해야 할 literal(예외 메시지·상태 코드·타입/네임스페이스·설정 키) verbatim. 없으면 "없음".

---

## Phase 7C: ADR 파일 내용 준비

NEW 모드 Phase 5N 메타·이력 구조와 동일. 차이:
- ADR 본문 §컨텍스트 = TASK 명세 요약 (FRD 본문 아님)
- §결정 = AI 가 TASK 의 work_type + steps 보고 narrative
  - `refactor` → "기존 구조 X 를 Y 로 전환"
  - `maintenance` → "표준 운영 절차, 특이 결정 없음"
  - `feature` (기존 기능 확장) → "확장 정책 결정"
- § 문서 반영:
  - `[<App>-ADR-CATALOG]` — Proposed 행 추가
  - `[<App>-FC]` — F<NNN> 행 상태 갱신
  - `[<App>-FRD-<NNN>]` — 영향 절 (다수)
  - `[<App>-TASK-<NNN>]` — **인용 X** (휘발성 룰)

---

## Phase 8C: 영향 FRD 본문 갱신 내용 준비

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
- prompt 미명시인데 도메인 추론으로 채운 항목 = 줄 끝 `(추론)` 표기 (NEW 3단룰과 대칭).

영향 없는 section 무변경.

---

## Phase 9C: FC 행 갱신 내용 준비

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

## Phase 10C: ADR-CATALOG 갱신

NEW 모드 Phase 8N 과 동일 (`## Proposed` 표 행 1 추가, 절 없으면 신설).

CHANGE 모드 본문 준비 완료 → **Phase 10 (사전 확정)** 으로.

---

# ═══ 합류: 사전 확정 → 쓰기 → 검증 → 보고 (모드 공통) ═══

## Phase 10: 사전 확정

전체 변경 사항 사용자에게 출력. **모드별 작성 목록 분기**:

### NEW 모드
```
## 작성 계획 (NEW — 신규 기능)

### 생성 파일
- CREATE docs/<App>/FRD/<App>-FRD-<NNN>.md (20 section + 메타 + 이력)
- CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md (Proposed, narrative)
- CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md (12 section, §12=신규 FRD 임베드)

### 갱신 파일
- UPDATE docs/<App>/<App>-PRD.md (§3.1 F<NNN> 추가, §7 행 +1)
- UPDATE docs/<App>/<App>-FC.md (5표 모두 F<NNN> 행 추가)
- UPDATE docs/<App>/<App>-ADR-CATALOG.md (Proposed 행 +1)

### 핵심 채움 값
- 기능명/한 줄 설명/목적/work_type/우선순위/ADR 제목
```

### CHANGE 모드
```
## 작성 계획 (CHANGE — 기존 수정)

### 생성 파일
- CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md (12 section)
- CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md (Proposed, narrative)

### 영향 FRD 갱신 (갱신할 절 + 사유 명시)
- UPDATE docs/<App>/FRD/<App>-FRD-<N1>.md (버전 bump + 변경이력)
  - §8 상세 기능 요구사항 ← <rate limiting 룰 추가> (prompt 의도)
  - §13 비기능 요구사항 ← <성능/보안 기준 변경>
- UPDATE docs/<App>/FRD/<App>-FRD-<N2>.md (있을 경우, 갱신 절 동일 형식)

### FC 행 갱신
- F<N1>: 구현 상태 → Implementing, 테스트 상태 → 작성중

### ADR-CATALOG
- Proposed 행 1 추가 (<App>-ADR-<NNN>)

### 핵심 채움 값
- TASK 제목/work_type/영향 FRD/ADR 제목
```

`AskUserQuestion`:
- 옵션 1: "확정하고 작성 진행" (Recommended)
- 옵션 2: "수정 필요"

수정 → 사용자 입력 반영 후 재제시.

---

## Phase 11: in-place 쓰기 (모드별 순서)

### NEW 모드
1. **ADR 파일** `Write`
2. **FRD 파일** `Write` (20절)
3. **App-PRD** `Edit` (§3.1 + §7)
4. **FC** `Edit` (5표 행 추가)
5. **ADR-CATALOG** `Edit` (Proposed 행 추가)
6. **TASK 파일** `Write` (마지막 — §6 SSOT 표에 1~5 결과 "완료/실패" 채움)

### CHANGE 모드
1. **ADR 파일** `Write`
2. **영향 FRD 본문** `Edit` (다수 — 메타 버전 행 / 변경 이력 / 영향 section)
3. **FC** `Edit` (영향 행 상태 컬럼)
4. **ADR-CATALOG** `Edit` (Proposed 행 추가)
5. **TASK 파일** `Write` (마지막 — §6 SSOT 표에 1~4 결과 "완료/실패" 채움)

각 단계 실패 = 다음 진행. 결과 보고 partial status.

---

## Phase 12: 검증-fix 수렴 루프 (기본 ON, --no-verify 스킵)

> Phase 11 쓰기 결과를 Codex 가 2축(prompt 의도 + v0.7 룰) 채점 → 미달 시 Claude 가 manifest 범위 내 문서만 fix → 재검증. 임계(conformance 99%) 또는 cap(3회) 까지 반복. `--no-verify` 지정 또는 codex 미설치 시 12.5 폴백(구 동작).

### 12.0 manifest 작성 (휘발)

Phase 11 의 생성/수정 파일 목록 + 변경 요지를 JSON 으로 `.git/info/docs-add-task-manifest.json` 에 `Write`:
```json
{ "app": "<App>", "mode": "NEW|CHANGE",
  "created": ["docs/<App>/FRD/<App>-FRD-NNN.md", "..."],
  "modified": [{"path": "docs/<App>/<App>-FC.md", "summary": "<요지>"}, "..."] }
```
삭제 산출물 없음 (docs-add-task 는 삭제 안 함) — created/modified 만.

### 12.1 수렴 루프 (i = 1..3)

**(a) 구조 게이트**
```
python scripts/docs_helpers.py check --repo . --app <App>
```
exit 1 (FAIL) 이면 그 FAIL 항목을 이번 라운드 결함으로 합산.

**(b) Codex 2축 검증**
```
python scripts/docs_verify.py --repo . --app <App> --mode <NEW|CHANGE> \
   --prompt "<원본 사용자 prompt>" \
   --manifest-file .git/info/docs-add-task-manifest.json
```
- exit 2 (codex 미설치) → 루프 중단 → **12.5 폴백**.
- exit 0 → stdout 마지막 `Conformance: N%` 추출 + `## Defects` 목록 수집.
- exit 1 (conformance 추출 실패 등) → conformance 미상 취급: Defects 있으면 fix 라운드 진행, 없으면 보수적 종료 (12.3, 결과 "검증 불완전" 표기).

**(c) 종료 판정**
- conformance ≥ 99 → 수렴 → 12.3.
- i == 3 → cap 도달 → 12.3 (rollback X, 마지막 상태 유지).
- 아니면 (d).

**(d) fix (Claude 인라인)**
`## Defects` 항목 중 **manifest (created/modified) 경로에 속한 것만** `Edit` 으로 수정.
- 범위 밖 파일 지적 (예: ARCHITECTURE/PRD) 은 고치지 않고 12.3 의 [Warning] 으로 수집.
- 구조 게이트 FAIL 도 범위 내면 수정.
- fix 후 manifest 갱신 불필요 (파일 목록 불변) → i+1 로 12.1(a) 재진입.

### 12.2 conformance 궤적 기록

각 라운드 pct 를 누적 (예: `88% → 96% → 99%`). 12.3 보고에 사용.

### 12.3 종료 보고

- `Verify: <궤적>  (<수렴 ✅ N fix rounds | cap ⛔ 99% 미달>)`
- cap 미달 시 남은 `## Defects` 그대로 노출 + "수동 처리 안내".
- 범위 밖 지적 = `[Warning] <파일> 검토 권장 (자동 수정 안 함)`.

### 12.4 정리

`.git/info/docs-add-task-manifest.json` 삭제 (휘발).

### 12.5 codex 미설치 / --no-verify 폴백 (구 동작)

```
python scripts/docs_helpers.py check --repo . --app <App>
```
결과만 노출 + 아래 AI cross-ref 5항목 수동 대조 보고 (자동 수정 안 함):
- [ ] FRD 메타 기능 ID == FC 신규/영향 F 행 번호 일치
- [ ] FRD §16 "필요" 선언 == 실제 FC/ADR/ADR-CATALOG 수행됨 (선언-실행 일치)
- [ ] FC 행 (기능상태·구현상태·테스트상태) = 일관성 룰표 허용 조합 (Phase 9C)
- [ ] AC/TC ID 연속 (중복·누락 없음)
- [ ] ADR-CATALOG Proposed 행 doc-id == 신규 ADR 파일 doc-id 일치
불일치 항목 = 보고 + 수동 수정 안내. NEW=5항목 전부 / CHANGE=§16 항목은 FRD §16 갱신 없으면 skip.
codex 미설치 시: `[Warning] codex 미설치로 자동 검증-fix 생략. /codex:setup 후 재실행 권장.`

---

## Phase 13: 결과 보고

### NEW 모드
```
CREATE docs/<App>/FRD/<App>-FRD-<NNN>.md
CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md
CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md
UPDATE docs/<App>/<App>-PRD.md (§3.1, §7)
UPDATE docs/<App>/<App>-FC.md (5 tables)
UPDATE docs/<App>/<App>-ADR-CATALOG.md (Proposed +1)
Checks: <P> PASS, <F> FAIL
Verify: 88% → 96% → 99% (수렴, 2 fix rounds)
```

### CHANGE 모드
```
CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md
CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md
UPDATE docs/<App>/FRD/<App>-FRD-<N1>.md (history + sections)
UPDATE docs/<App>/FRD/<App>-FRD-<N2>.md (history + sections)
UPDATE docs/<App>/<App>-FC.md (rows updated)
UPDATE docs/<App>/<App>-ADR-CATALOG.md (Proposed +1)
Checks: <P> PASS, <F> FAIL
Verify: 88% → 96% → 99% (수렴, 2 fix rounds)
```

스킵/폴백 시: `Verify: [skipped: --no-verify]` 또는 `Verify: [skipped: no codex]`.

호스트 영향 (work_type=refactor/migration 이면서 진입점/런타임 영향) 감지 시:
```
[Warning] docs/<App>/<App>-ARCHITECTURE.md §1·§2 검토 권장 (자동 수정 안 함)
```

Cross-cutting (errorCode/도메인 entity 변경) 감지 시:
```
[Warning] 솔루션 PRD (docs/PRD.md) 부록 B/D/E 검토 권장
```

TASK 휘발성 안내:
```
[Note] 본 TASK 는 작업 완료 후 삭제 가능 (v0.7 휘발성 룰).
영구 추적은 영향 FRD §변경 이력 + ADR-CATALOG 에 보존됨.
```

---

## 에러 케이스

- App 0건 → 중단 + 부트스트랩 가이드 ("`/CLAUDE.md` Backend Services Overview 표에 App 행 추가 + `docs/<App>/` 폴더 부트스트랩 후 재시도").
- App 다수 → AskUserQuestion
- 영향 FRD 0건 + 기능 의도(신규/feature/변경/버그수정) → 사용자 확인 → 신규 기능이면 **NEW 모드 진입** (FRD 신설), 기존 누락이면 FRD ID 지정 후 CHANGE.
- FC/PRD/ADR-CATALOG 파일 부재 → 작성 거절 + "App 부트스트랩 누락" 보고.
- NNN 한계 (F099/TASK099/ADR099 초과) → exit 2 + 중단.
- FRD 파일 부재 (CHANGE 모드, FC 에 등재됐으나 실제 파일 없음) → 해당 FRD 갱신 건 skip + 경고.
- 다중 결정 → 사용자 분할 권고.
- Backlog 모드 + 일반 NEW 모드 충돌 → 사용자 재확인.
