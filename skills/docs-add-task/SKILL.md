---
name: docs-add-task
description: v0.7 per-App SSOT 체계에서 신규 기능 또는 기존 수정/개선/refactor 설계 문서를 in-place 작성한다. 문서별 upsert — 영향 자산마다 "수정 필요하면 수정, 추가 필요하면 추가". FRD 는 신규 기능이면 신설(20절)·기존 영향이면 갱신(한 작업서 신설+갱신 혼합 허용), FC 는 신규 행 추가·기존 행 상태 갱신, App-PRD 는 신규 기능 시 §3.1/§7 갱신. ADR 도 upsert — 새 결정이면 신설, 기존 결정 변경이면 기존 ADR 수정(supersede/in-place), 결정 없으면 생략. ADR op 따라 ADR-CATALOG 동기화. TASK 는 항상 생성(휘발성). 작성 후 codex 로 요구사항서↔생성문서 정합을 자동 채점한다(기준=`.requirements/` 요구사항서 불변, 99% 또는 3회까지 검증↔보강 수렴). 사용자가 신규 기능(예: "주문 검색 기능 추가") 또는 기존 수정/개선/refactor(예: "주문 검색에 페이지네이션 추가") 를 자연어로 요청할 때 트리거.
argument-hint: "[신규 기능 또는 수정/개선/refactor 자연어 prompt]"
---

# docs-add-task

docs/.templates v0.7 체계 (per-App PRD/FC/ARCHITECTURE/FRD/ADR/ADR-CATALOG/TASK) 에서 **설계 문서를 문서별 upsert 로 작성**. `parse-fc` 로 영향 자산을 식별해 각 문서를 **신설/갱신/생략** 분기한다. 신규 기능과 기존 수정을 한 작업에서 동시에 처리할 수 있다 (혼합 허용). TASK 는 항상 생성, ADR 은 결정 유무에 따라 신설/수정/생략. source repo in-place 수정.

---

## 핵심 원칙

- **v0.7 전용**.
- **In-place** 수정. preview 없음.
- **문서별 upsert** — NEW/CHANGE 모드 라벨 없음. 영향 자산마다 존재 여부 보고 신설/갱신/생략 결정. 한 작업서 신규 FRD 신설 + 기존 FRD 갱신 혼합 가능.
- **TASK 항상 생성** — 모든 경우 TASK 1개 생성 (유일 예외 = Backlog, Phase 2 참조). TASK 휘발성 — 본 skill 은 생성만, 삭제는 사용자 수동.
- **ADR upsert (생략 허용)** — 새 결정 → ADR 신설 / 기존 결정 변경 → 기존 ADR 수정(AI 가 supersede vs in-place 판단) / 결정 없음 → **ADR 생략**. (현행 "TASK 1개 = ADR 1개 항상 강제" 룰 폐기. DOCUMENT_GUIDE §2 "필요 시 ADR 등재" 와 정렬.)
- **외부 SSOT 인용 금지 (v0.7 양방향 룰)** — TASK 본문에 영구 SSOT 마크다운 링크 사용 X. 영향 SSOT 는 §6 표에 텍스트로만 명시. 역으로 영구 SSOT 도 TASK 인용 X.
- **AI 가 영향 자산·op 자동 식별** — 사용자가 모드·FRD ID·ADR op 지정하지 않음. AI 가 FC 파싱 + ADR-CATALOG 인덱스 매칭. 신규 기능 0건이어도 자동 신설 강행 금지 — 모호 시 사용자 확인 1회.
- **FRD 본문 부분 갱신 (기존 FRD)** — 변경 이력 표 + AI 판단 영향 section 텍스트만. TASK ID 인용 X.
- **TASK §7·§11 빈 절 생략** — 결정 필요 사항(§7)·미확인 사항(§11) 은 실제 미해결 항목 있을 때만 작성. 0건이면 절 전체 생략, `"없음"` placeholder 행 금지 (후속 스킬 블로킹 방지). Phase 9 참조.
- **부분 실패 시 rollback X**.
- **템플릿 대조 강제** — FRD/ADR/TASK/FC/PRD 본문 생성·수정 직전 해당 `.templates/App/.../X-TEMPLATE.md` 1회 `Read`. 절 구조·메타 행 수·placeholder 원본 대조 후 채움. 기억 의존 구조 생성 금지 (drift 방지). 템플릿 부재 시 경고 후 진행.
- **토큰 절약** — ADR 후보 탐색은 `ADR-CATALOG.md`(compact 인덱스) 1회 Read → 매칭된 후보 ADR 1개만 Read. 전 ADR 파일 스캔 금지.
- **요구사항서 영구 기록** — 기준 요구사항서를 `.requirements/req-<App>-TASK-<NNN>.md` 에 보존(TASK 1:1 추적). 입력이 이미 `.requirements/` 면 재사용. 이 파일 = Phase 13 검증 기준(불변).
- **요구사항 정합 자동 검증 (codex)** — 작성 후 codex 가 요구사항서 대비 생성문서 반영률(%) 채점. 99% 또는 3회까지 검증↔보강 반복. 기준=요구사항서(불변, 채점 대상서 제외), 수정=설계문서. codex 미설치·요구사항서 부재 시 graceful skip(본체 작성 결과는 유지).

---

## 사전 준비 — helper 경로 (CLAUDE_PLUGIN_ROOT fallback)

helper 스크립트(`docs_helpers.py`·`docs_conformance.py`)는 **소비자 repo 에 복사되지 않는다** (forge-scope·doc-driven-review 와 동일 컨벤션 — v3.0.1 부트스트랩 복사 폐지). dev repo(로컬 `./scripts/` 보유)면 로컬, 아니면 플러그인 설치 경로를 쓴다:

```bash
HELP="scripts/docs_helpers.py";      [ -f "$HELP" ] || HELP="${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py"
CONF="scripts/docs_conformance.py";  [ -f "$CONF" ] || CONF="${CLAUDE_PLUGIN_ROOT}/scripts/docs_conformance.py"
```

> **Claude Code 의 Bash 호출은 셸 상태를 보존하지 않는다.** helper 를 실행하는 **모든 Bash 블록 맨 앞에 위 2줄을 함께 둔다**(또는 해석된 절대경로를 인라인). 이후 Phase 들은 `python "$HELP" ...` / `python "$CONF" ...` 로 표기한다. cwd 는 **소비자 repo 루트 유지** — helper 는 `--repo .` 로 대상 docs 를 해석하므로 스크립트 파일 위치만 플러그인 경로면 된다.
>
> ⚠ **이 fallback 없으면**: 로컬 사본이 없는 소비자 repo 에서 Phase 0 가 즉시 file-not-found 로 실패하고, `docs_conformance.py` 미복사 시 Phase 13 가 file-not-found(exit 2)를 "codex 미설치"로 오인해 **정합 검증을 통째로 silent skip** 한다.

---

## Phase 0: 대상 App 결정

```
python "$HELP" list-apps --repo .
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
  - `신규` / `refactor` / `maintenance` / `migration` / `setup` / `investigation` / `feature` / `변경` / `버그수정`
- `완료 상태` — 작업 완료 후 관찰 가능한 상태 (§1)

**선택**
- `priority` (default `P1`)
- `steps` — §8 작업 단계 (없으면 AI 가 prompt 에서 추론)
- `completion_criteria` — §9 (default `미작성/추후`)
- `risks` — §10
- `adr_decision` (override 가능, 없으면 AI 추론)
- `reference_doc` — 기준 요구사항서. 입력에 요구 문서 경로가 포함되면 그 파일 채택. 없으면(NL-only) prompt 원문 + purpose + 완료상태 + (있으면) acceptance 를 모아 Phase 3 에서 `.requirements/` 에 기록. (Phase 13 검증 기준, 불변)

**필수 입력 게이트**: `purpose` 또는 `완료 상태` 를 prompt 에서 추출 실패 시 → `AskUserQuestion` 1회로 수집. 추론·placeholder 날조 금지. 무응답 시에만 `미작성/추후` placeholder. (Backlog 는 FRD/TASK 미생성이므로 `purpose` 만 필수.)

---

## Phase 2: 영향 자산 식별 + op 판정

```
python "$HELP" parse-fc --repo . --app <App>
```

응답 JSON 의 `features[]` 사용. ADR 후보 식별을 위해 `docs/<App>/<App>-ADR-CATALOG.md` 1회 `Read`.

AI 작업 (자산별 op 결정):

### 2.1 FRD op
1. 사용자 prompt 의 의도와 각 feature 의 `name + summary` 매칭 (의미론적).
2. **영향 기존 FRD ID 목록** 산출 (다수 가능) → 각각 **갱신**.
3. **신규 기능** 식별 (기존 feature 와 매칭 안 되는 명백 신규) → **신설** (다수 가능).
4. **중복 기능 탐지** — 매칭 0건이라도 prompt 와 의도가 강하게 겹치는 기존 F(부분 매칭) 있으면 신설 강행 전 후보 보류. 명백 신규만 신설 직행.

| 조건 | FRD op |
|---|---|
| 기존 feature 매칭 + FRD 파일 존재 | **갱신** (Phase 4b) |
| 기존 feature 매칭 + FRD 파일 부재 | **신설** — 단 **FC 행의 기존 F-id 재사용** (next-id 금지, Phase 3 참조) |
| 명백 신규 (매칭 없음) | **신설** — next-id frd 새 번호 (Phase 4a) |
| 0건 + 운영성 work_type ∈ {`refactor`,`maintenance`,`setup`,`migration`,`investigation`} | **FRD 무변경** (운영 경로 — TASK + 필요시 ADR만) |
| 0건 + 기능 의도 work_type ∈ {`신규`,`feature`,`변경`,`버그수정`} + 모호 | `AskUserQuestion` 아래 참조 |

**0건 + 기능 의도 + 모호 시 `AskUserQuestion`** (false-negative 보호 — `parse-fc` 의미 매칭이 기존 기능을 놓쳤을 수 있음. 자동 신설 강행 금지):
- 옵션 1: "신규 기능 — FRD 신설" (Recommended)
- 옵션 2: "기존 기능 누락 식별 — FRD ID 직접 지정" (사용자가 F<NN> 입력 → 갱신)
- (3 스텝서 유사 기존 F 탐지 시) 해당 `F<NN>` 을 옵션 2 후보로 함께 제시 — 중복 FRD 방지.

### 2.2 ADR op
1. AI 가 prompt 에서 **결정 사항 N개** 식별.
2. 각 결정을 ADR-CATALOG 인덱스(Accepted/Proposed 행)와 의미 매칭:

| 조건 | ADR op |
|---|---|
| 새 결정 (매칭 ADR 없음) | **신설** (Phase 5a) |
| 기존 결정 변경 (매칭 ADR 있음) | **기존 ADR 수정** — AI 가 supersede vs in-place 판단 (Phase 5b) |
| 결정 사항 없음 (N=0) | **ADR 생략** (Phase 5c) |

3. **다중 결정 (N≥2)** → `AskUserQuestion`:
   - "첫 결정만 본 TASK 의 ADR 로 등재. 나머지는 별도 `/docs-add-task` 실행 권장" (Recommended)
   - "결정 N개를 하나의 ADR 에 통합 narrative"

**Backlog 예외** (특수 early-exit): 사용자가 "backlog" / "확장 후보" 명시 시 — FRD·ADR·TASK **미생성**. FC `## 확장 후보 기능 (Backlog)` 표 행 추가 + App-PRD §3.1 "이번 릴리즈 제외" 갱신만. Phase 8(ADR-CATALOG) 생략, Phase 10 직행 (FC·PRD 변경만 확정).

판정 결과를 자산별 op 목록으로 정리 (FRD 신설 N + 갱신 M, ADR 신설/수정/없음, FC/PRD/ADR-CATALOG 파생 op) → Phase 3 진행.

---

## Phase 3: 번호 할당 + 컨텍스트 수집

```
python "$HELP" next-id --repo . --app <App> --kind task
python "$HELP" git-user --repo .
```

op 에 따라 추가 호출:
- **신규 FRD (명백 신규) 있으면** 건수만큼 `next-id --kind frd`.
  - 단 "FC 행 존재 + FRD 파일 부재" 케이스는 **FC 행의 기존 F-id 재사용** — next-id frd 호출하지 않는다.
- **신규 ADR (신설 또는 supersede 의 후속 ADR) 있으면** 건수만큼 `next-id --kind adr`.
- **영향 기존 FRD 각각**:
  ```
  python "$HELP" parse-frd --repo . --app <App> --frd-id <F_NNN>
  ```
  응답에서 `version`(patch bump 기준) · `sections`(컨텍스트 임베드용) · `ac_max`/`tc_max`/`q_max`(추가 시 다음 번호) 추출.
- **기존 ADR 수정 대상이면** 그 ADR 파일 1개 `Read` — 버전(bump 기준) + 본문(결정/결과 절) 확보.

- exit 2 (`FAIL LIMIT`, F099/TASK099/ADR099 초과) 시 즉시 중단 + 보고.
- 오늘 일자 = 시스템 ISO 날짜 (`YYYY-MM-DD`).

### 요구사항서 기록 (`.requirements/`, Phase 13 검증 기준)

TASK 번호 확정 후 기준 요구사항서를 영구 기록한다 (`reference_doc`):
- `.requirements/` 없으면 생성.
- 입력이 이미 `.requirements/` 내 문서면 그대로 `reference_doc` 채택 (중복 생성 X).
- 아니면 `.requirements/req-<App>-TASK-<NNN>.md` 에 기록:
  - 외부 요구 문서 제공 → 내용 복사 + 헤더(문서 ID·일자·연결 TASK `<App>-TASK-<NNN>`).
  - NL-only → prompt 원문 + purpose/완료상태/acceptance 를 구조화해 기록.
- 이 경로 = `reference_doc` (불변). 커밋 강제 X (사용자 시점 자유). Phase 13 은 명시 경로로만 채점하므로 working-tree 에 있어도 자기참조 오염 없음.

---

## Phase 4: FRD 준비 (upsert)

> 신설 대상은 4a, 갱신 대상은 4b. 둘 다 있으면 각각 수행.

### Phase 4a: 신규 FRD 내용 준비

`.templates/App/FRD/APP-FRD-001-TEMPLATE.md` 기준 20 section + 메타 표 + 변경 이력 표.

**FRD 번호** = 명백 신규면 `next-id frd` 결과, "FC 행 존재 + FRD 부재" 면 FC 행의 기존 F-id 의 NNN.

#### 메타 표 6 행
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

#### 변경 이력 표
```
## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | <YYYY-MM-DD> | 초안 | <git-user> |
```

#### 20 Section 본문

각 section 채움 우선순위 (빈칸·"N/A" 금지):
1. **prompt 명시** → 값 그대로.
2. **prompt + 도메인으로 합리 추론 가능** → 추론값 + 줄 끝 `(추론)` 표기 (검증 대상 가시화).
3. **진짜 불명** → "없음"/"미작성/추후" + **§20 에 `Q-F<NNN>-<다음번호>` 행 등재** (silent 없음 금지). 기본행 `Q-F<NNN>-001` 유지, 추가 Q는 002부터.

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
| 16 | FC/ADR-CATALOG/ADR 반영 여부 | 항상 3 행, **ADR op 반영** (아래 참조) |
| 17 | 수용 기준 | AC-F<NNN>-001 ~ 행 |
| 18 | 테스트 관점 | TC-F<NNN>-001 행 |
| 19 | 요구 근거 | App-PRD / FC 행 링크 + notes |
| 20 | 미확인 사항 | Q-F<NNN>-001 행 (Open 또는 "없음") |

**§16 3 행 — ADR op 반영** (FRD 자기 작업 결과, **TASK 인용 금지**). ADR 행·ADR-CATALOG 행은 실제 op 로 채운다:
```
| 문서 | 반영 여부 | 반영 내용 | 비고 |
|---|---|---|---|
| FC | 필요 | 신규 F<NNN> 등재 (5 표) | 완료 |
| ADR | 필요 / 없음 | <App>-ADR-<NNN> 신설 / 기존 <App>-ADR-<MMM> 수정 / 없음 | 완료 / - |
| ADR-CATALOG | 필요 / 없음 | Proposed 행 추가 / Superseded 갱신 / 행 갱신 / 없음 | 완료 / - |
```
(ADR 생략이면 ADR·ADR-CATALOG 행 "반영 여부 = 없음", 비고 "-".)

**AC/TC/Q ID 자동**:
- `AC-F<NNN>-001` 1행 최소
- `TC-F<NNN>-001 | 미작성/추후 | 미작성/추후 | 미작성/추후 | 미작성/추후` 1행
- `Q-F<NNN>-001 | 없음 | - | - | - | -` 또는 사용자 명시

**코드 상세 금지** (template 룰): 코드 경로·클래스·메서드·API 경로·테스트 명령 FRD 본문 기재 X.

### Phase 4b: 기존 FRD 갱신 내용 준비

각 영향 기존 FRD 에 대해:

#### 버전 bump
`parse-frd` 응답의 `version` 에서 patch +1.
- `0.1 (Draft)` → `0.2 (Draft)` / `0.2` → `0.3`
- regex `^(\d+)\.(\d+)` 매치 후 group(2) +1. 메타 표 `| 버전 |` 셀 값 교체.

#### 변경 이력 표 행 1 추가
```
| <new_ver> | <오늘> | <work_type>: <한 줄 요약> | <git-user> |
```
**TASK ID 인용 X**. 변경 요약 = TASK title 텍스트만.

#### 영향 section 갱신 (AI 판단)
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

**section 텍스트 갱신**: 기존 텍스트 유지 + 추가 항목 append. 형식 `\n- <YYYY-MM-DD> <work_type>: <한 줄 요약>` 또는 표 행 추가. prompt 미명시 도메인 추론 항목 = 줄 끝 `(추론)`. 영향 없는 section 무변경.

---

## Phase 5: ADR 준비 (upsert)

`.templates/App/ADR/APP-ADR-001-TEMPLATE.md` 기준. ADR op (Phase 2.2) 따라 분기.

### Phase 5a: 신규 ADR 내용 준비

#### 메타 표
```
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-ADR-<NNN> |
| 버전 | 0.1 (Draft) |
| 상태 | Proposed |
| 작성 가정 | <신규 FRD 동반 신설 / 기존 변경 동반. 결정 narrative 는 본 ADR 본문> |
| 관련 문서 | [<App>-ADR-CATALOG](../<App>-ADR-CATALOG.md) · [<App>-PRD](../<App>-PRD.md) · [<App>-FC](../<App>-FC.md) · [<App>-ARCHITECTURE](../<App>-ARCHITECTURE.md) · [FRD 폴더](../FRD/) · [DOCUMENT_GUIDE](../../DOCUMENT_GUIDE.md) |
```

#### 변경 이력
- 0.1 | <오늘> | 초안 | <git-user>

#### 본문 (## ADR-<NNN>: <제목>)
- **제목** = AI 가 결정 명세 보고 추론. "결정 사항 없음" 인데 신설된 경우는 없다 (결정 없음 → 5c 생략).
- **상태** = `Proposed (<오늘>)` — 본문 `- **상태**:` 줄.
- **컨텍스트** = 신규 FRD 동반이면 FRD §1·§2 요약, 기존 변경 동반이면 TASK 명세 요약.
- **결정** = AI 추론. **fallback 전 실 결정 ≥1 탐색 의무** — 데이터 경계·정책·권한·성능·호환성 중 본 작업이 강제하는 선택지 검토. 진짜 없을 때만 → `"본 작업은 특이 결정 없이 도메인 표준 패턴을 따른다."` (단 이 경우 애초 5c 생략 검토).
- **결과** = 가능해지는 것 + 후속 작업.
- **대안 검토** = 없음 → `"대안 검토 없음 (단순 구현)"`. 있으면 옵션 A/B.
- **§ 코드 인용** = `"신규 — 코드 인용 없음 (구현 시 첨부)"`.
- **§ 문서 반영** (필수, **TASK 인용 X**):
  - `[<App>-ADR-CATALOG]` — Proposed 행 추가
  - `[<App>-PRD]` / `[<App>-FC]` / `[<App>-FRD-<NNN>]` — 반영 절 또는 "없음"

### Phase 5b: 기존 ADR 수정 (AI 판단: supersede vs in-place)

매칭된 기존 ADR (Phase 3 에서 Read) 에 대해, 결정 변경 성격으로 분기:

**supersede** (구조적 결정 교체 — ADR 불변 관례 준수):
1. **신규 ADR 생성** (5a) — 새 결정 narrative. §본문에 "기존 <App>-ADR-<MMM> 대체" 명시.
2. **기존 ADR 상태 변경** — 2곳 모두:
   - 메타 표 `| 상태 |` 행 → `Superseded`
   - 본문 `- **상태**:` 줄 → `Superseded (<오늘>)`
   - 변경 이력 행 1 추가 (`| <bump> | <오늘> | <App>-ADR-<신규NNN> 로 대체 | <git-user> |`), 버전 patch bump.
3. ADR-CATALOG 는 Phase 8 supersede 경로.

**in-place** (기존 결정 세부 보완 — 구조 불변):
1. 기존 ADR 버전 patch bump (Phase 3 Read 한 버전 기준, FRD bump 로직 동일).
2. 변경 이력 행 1 추가 (`| <bump> | <오늘> | <work_type>: <보완 요약> | <git-user> |`).
3. 본문 §결정·§결과 절 텍스트 갱신 (기존 유지 + 추가, 도메인 추론은 `(추론)`).
4. ADR-CATALOG 는 Phase 8 in-place 경로 (행 일자·요지 갱신).

### Phase 5c: ADR 생략

결정 사항 없음 → ADR 파일·ADR-CATALOG 무변경. TASK §6 ADR 행 = "없음 / 불필요".

---

## Phase 6: FC 준비 (upsert per 기능 행)

`docs/<App>/<App>-FC.md`. 기능별 op 따라:

### 6a 신규 기능 행 추가 (5표 전부)

#### 1) `### 기본 식별·설명`
```
| F<NNN> | <name> | <summary> | Draft | Not Started | 미작성 | <priority> |
```
#### 2) `### 문서 연결`
```
| F<NNN> | [App PRD §7](<App>-PRD.md#7-주요-기능-요약-본-app-한정) | [<App>-FRD-<NNN>](FRD/<App>-FRD-<NNN>.md) | 미작성/추후 | 미작성/추후 | 미작성/추후 |
```
#### 3) `### 검증·근거·확인`
```
| F<NNN> | [<App>-FRD-<NNN> §18](FRD/<App>-FRD-<NNN>.md#18-테스트-관점) | [<App>-FRD-<NNN> §17](FRD/<App>-FRD-<NNN>.md#17-수용-기준) | <purpose 요약> → [<App>-FRD-<NNN>](FRD/<App>-FRD-<NNN>.md) | 없음 |
```
#### 4) `### 기능 요구 추적`
```
| F<NNN> | <work_type> | <user_impact 또는 "없음"> | FC / FRD / ADR / ADR-CATALOG | [<App>-FRD-<NNN> §17](FRD/<App>-FRD-<NNN>.md#17-수용-기준) |
```
#### 5) `### 타 App 협력 흐름`
협력 명시 없으면 무행. 있으면:
```
| F<NNN> | <협력 App> | F<NNN> | 호출 / 이벤트 / 공유 데이터 |
```
신규 행은 항상 `Draft / Not Started / 미작성` (consistency 룰표 상단 값 고정).

### 6b 기존 기능 행 갱신

각 영향 기존 F<NNN> 행:
- `### 기본 식별·설명` 행:
  - `기능 상태`: 의미적으로 적합 (예: 진행 작업 → `In Progress`)
  - `구현 상태`: `Implementing` 또는 `Blocked`
  - `테스트 상태`: `작성중`

  v0.7 일관성 룰:
  | 기능 상태 | 허용 구현 상태 | 허용 테스트 상태 |
  |---|---|---|
  | Draft | Not Started | 미작성 |
  | Ready | Not Started | 미작성 |
  | In Progress | Implementing / Blocked | 미작성 / 작성중 |
  | Done | Implemented | 통과 |
- `### 기능 요구 추적` 행: `문서 영향` 열 텍스트 끝에 `+ TASK <오늘>` 추가/갱신.

---

## Phase 7: App-PRD 준비 (조건부)

`docs/<App>/<App>-PRD.md`:
- **신규 기능 있을 때만**:
  - §3.1 (릴리즈 범위): `이번 릴리즈 포함` 셀 끝에 `, F<NNN>` 추가. placeholder `{본 App 의 현 릴리즈 범위}` 만 있으면 `F<NNN>` 로 교체.
  - §7 (주요 기능 요약): `| F<NNN> | <name> | <summary> | <release_scope> |` 행 추가.
- **Backlog**: §3.1 `이번 릴리즈 제외` 셀 갱신.
- **기존 변경만**: PRD 무변경.

---

## Phase 8: ADR-CATALOG 준비 (upsert, ADR op 따름)

`docs/<App>/<App>-ADR-CATALOG.md`. ADR op 별:

- **신규 ADR** → `## Proposed` 표 행 1 추가:
  ```
  | [<App>-ADR-<NNN>](ADR/<App>-ADR-<NNN>.md) | <ADR 제목> | <오늘> | <영향 모듈 또는 "F<NNN> 기능"> | <결정 기한 = 오늘+14일> | 개발 리드 |
  ```
  `Proposed` 절 없으면 절 + 표 헤더 자동 신설.
- **supersede** → ① 기존 ADR 행을 `## Deprecated / Superseded` 표로 (없으면 절+헤더 신설):
  ```
  | [<App>-ADR-<MMM>](ADR/<App>-ADR-<MMM>.md) | <기존 제목> | <오늘> | [<App>-ADR-<신규NNN>](ADR/<App>-ADR-<신규NNN>.md) | <교체 사유 한 줄> |
  ```
  기존 행이 Accepted/Proposed 표에 있었으면 그 행 제거 후 위로 이동. ② 신규 ADR 은 `## Proposed` 행 추가 (위 신규 경로).
  - ⚠ **check 규칙**: 기존 ADR 파일 stem 이 catalog 어딘가(Deprecated/Superseded 행)에 반드시 남아야 함 — 행 완전 삭제 금지.
- **in-place** → 기존 ADR 의 catalog 행(있는 절 그대로)에서 일자·요지 갱신. 행 이동 없음.
- **ADR 없음** → ADR-CATALOG 무변경.

---

## Phase 9: TASK 준비 (항상 생성)

`.templates/App/TASK/APP-TASK-001-TEMPLATE.md` 기준.

### 메타 표 (5 행, 관련 문서 행 없음)
```
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-TASK-<NNN> |
| 버전 | 0.1 (Draft) |
| 상태 | Draft |
| 작업 유형 | <work_type> |
| 작성 가정 | 영향 영구 SSOT 사전 갱신 완료. 본 TASK 는 AI 실행용 휘발성 작업 지시서. |
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
| 7 | 결정 필요 사항 | **실제 결정 항목 있을 때만** D-T<NNN>-001~ 행 작성. 항목 0건 → **§7 절 전체 생략** (heading+표 모두 X). `"없음"` placeholder 행 금지 |
| 8 | 작업 단계 | steps 표 (단계/작업/산출물/선행 조건/상태=Todo) |
| 9 | 완료 기준 | AC-T<NNN>-001 행 — **Given/When/Then** (Then=기대결과 literal 우선) + **검증 대상(§8 단계/§3)** 열. **§9.1 단위 테스트 명세** 표 동반(전부 **단위 테스트**, TS-T<NNN>-001~): 테스트명·프로젝트·클래스·함수·선행 조건/픽스처·검증 대상·도입 근거·검증 AC. 그린필드는 프로젝트/클래스/함수 "신규 — 구현 시 확정" |
| 10 | 리스크와 되돌림 기준 | risks 표 또는 "없음" 행 |
| 11 | 미확인 사항 | **실제 미확인 항목 있을 때만** Q-T<NNN>-001~ 행 작성. 항목 0건 → **§11 절 전체 생략** (heading+표 모두 X). `"없음"` placeholder 행 금지 |
| 12 | 컨텍스트 임베드 | 영향 FRD 본문에서 §8/§9/§15 복제·요약 (마크다운 링크 X) |

**§7·§11 빈 절 생략 룰 (필수)**: §7 결정 필요 사항 / §11 미확인 사항 은 **실제 미해결 항목이 1건 이상일 때만** heading+표를 작성한다. 항목 0건이면 **절 전체(heading `## 7.`/`## 11.` + 표) 를 아예 출력하지 않는다**. `"없음"` placeholder 행을 남기지 않는다 — 후속 스킬(DDR/branch-review 등)이 placeholder 를 미결 항목으로 오인해 블로킹하는 것을 막기 위함. 절 생략으로 §번호 공백(예: §6 → §8)이 생겨도 정상 (`check` 는 TASK 섹션 수를 검사하지 않음).

**§6 영구 SSOT 갱신 여부** (Phase 11 쓰기 마지막에 실제 결과로 채움 — 템플릿 형식 따름, op 반영):
```
| SSOT | 영향 여부 | 갱신 내용 요지 | 갱신 상태 |
|---|---|---|---|
| <App>-PRD | 없음 / 필요 | <§3.1 F<NNN> 추가 등 또는 "없음"> | 완료 / 불필요 / 실패 |
| <App>-FC | 필요 | <신규 F<NNN> 5표 행 추가 / F<NNN> 행 상태 갱신> | 완료 / 실패 |
| <App>-FRD-<NNN> | 필요 | <F<NNN> 신설 (20절) / 영향 절 갱신> | 완료 / 실패 |
| <App>-ADR-<NNN> (신규/기존) | 없음 / 필요 | <신설 / supersede / in-place 수정 / "없음"> | 완료 / 불필요 / 실패 |
| <App>-ADR-CATALOG | 없음 / 필요 | <Proposed 추가 / Superseded 갱신 / 행 갱신 / "없음"> | 완료 / 불필요 / 실패 |
| <App>-ARCHITECTURE | 없음 / 필요 | <요지 또는 "없음"> | 완료 / 불필요 |
```
("실패" 는 본 skill 의 부분실패(rollback X) 보고용 확장값. ADR 생략 시 ADR·ADR-CATALOG 행 = "없음 / 불필요".)

**§12 컨텍스트 임베드 룰** (v0.7 양방향 인용 금지):
- 신규 FRD면 방금 작성한 §8/§9/§15, 기존 FRD면 `parse-frd` 의 §8/§9/§15 텍스트를 **복제·요약** (마크다운 링크 X).
- **충분조건**: TASK 실행자가 영향 FRD 를 열지 않고 작업 가능한 최소 충분 정보. 본 작업에 필요한 룰·제약·입출력만 발췌. 전문 덤프 금지(토큰), 1줄 요약 금지(self-contained 실패).
- 형식: `### 12.1 외부 계약 / 데이터 소스`, `### 12.2 데이터 구조 / 정책`, `### 12.2.1 코드 일치 필수 literal`, `### 12.3 코드 경로 / 통합 지점`, `### 12.4 검증 명령 (선택)`
- **§12.2.1** = 코드가 정확 일치해야 할 literal(예외 메시지·상태 코드·타입/네임스페이스·설정 키) verbatim. 신규라 미정이면 FRD 명시 값 우선, 없으면 "없음". §12.3 신규 코드 경로 = "신규 — 구현 시 결정".

---

## Phase 10: 사전 확정

전체 변경 사항을 op 별로 사용자에게 출력:

```
## 작성 계획 (upsert)

### 생성 파일
- CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md (최대 12 section — 빈 §7/§11 생략)
- (신규 FRD 있으면) CREATE docs/<App>/FRD/<App>-FRD-<NNN>.md (20 section)
- (신규 ADR 있으면) CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md (Proposed, narrative)

### 갱신 파일
- (기존 FRD) UPDATE docs/<App>/FRD/<App>-FRD-<N>.md (버전 bump + 변경이력 + 영향 절)
  - §8 상세 기능 요구사항 ← <사유> / §13 비기능 ← <사유>
- (기존 ADR supersede) UPDATE <App>-ADR-<MMM>.md → Superseded
- (기존 ADR in-place) UPDATE <App>-ADR-<MMM>.md (버전 bump + 결정/결과 절)
- (신규 기능 있으면) UPDATE docs/<App>/<App>-PRD.md (§3.1 F<NNN>, §7 행)
- UPDATE docs/<App>/<App>-FC.md (신규 행 추가 / 기존 행 상태 갱신)
- (ADR op 있으면) UPDATE docs/<App>/<App>-ADR-CATALOG.md (Proposed 추가 / Superseded / 행 갱신)

### 핵심 채움 값
- 기능명/한 줄 설명/목적/work_type/우선순위/ADR op·제목/영향 FRD 목록
```

`AskUserQuestion`:
- 옵션 1: "확정하고 작성 진행" (Recommended)
- 옵션 2: "수정 필요" (영향 FRD/ADR op 추가·제거 포함)

수정 → 사용자 입력 반영 후 재제시. (영향 FRD 확인은 본 게이트로 통합 — 별도 게이트 두지 않음.)

---

## Phase 11: in-place 쓰기 (통합 순서)

1. **ADR** — 신규 `Write` / 기존 수정 `Edit` (supersede 면 신규 Write + 기존 Edit 둘 다).
2. **FRD** — 신규 `Write` (20절) / 기존 `Edit` (메타 버전 / 변경 이력 / 영향 section). 다수 가능.
3. **App-PRD** — 조건부 `Edit` (§3.1 + §7).
4. **FC** — `Edit` (신규 행 추가 / 기존 행 상태 컬럼).
5. **ADR-CATALOG** — `Edit` (Proposed 추가 / Superseded 이동 / 행 갱신). ADR 없으면 skip.
6. **TASK 파일** — `Write` (마지막 — §6 SSOT 표에 1~5 실제 결과 "완료/불필요/실패" 채움).

각 단계 실패 = 다음 진행 (rollback X). 결과 보고 partial status.

---

## Phase 12: 자기 검증

```
python "$HELP" check --repo . --app <App>
```

FAIL 있어도 source 유지. 출력 그대로 사용자 노출. 수동 처리 안내.

**내용 cross-ref 자가검증** (`check` 는 구조만 봄 — 아래 의미 정합은 AI 가 쓴 파일 대조 후 텍스트 보고. **실제 op 조건부**):
- [ ] (신규 FRD 있으면) FRD 메타 기능 ID == FC 신규 F 행 번호 일치
- [ ] (신규 FRD 있으면) FRD §16 "필요" 선언 == 실제 FC/ADR/ADR-CATALOG 수행됨 (선언-실행 일치). ADR 생략이면 §16 ADR 행 "없음" 인지 확인
- [ ] FC 행 (기능상태·구현상태·테스트상태) = 일관성 룰표 허용 조합
- [ ] AC/TC ID 연속 (중복·누락 없음)
- [ ] (ADR op 있으면) ADR-CATALOG 행 doc-id == ADR 파일 doc-id 일치. supersede 면 기존 ADR stem 이 Deprecated/Superseded 행에 남아있는지 확인 (check ADR_CATALOG FAIL 방지)
불일치 항목 = 보고 + 수동 수정 안내 (자동 재수정 안 함, rollback X 룰 일관). ADR 생략 시 ADR-CATALOG 항목 skip.

---

## Phase 13: 요구사항 정합 수렴 검증 (codex, 자동)

작성된 설계문서가 기준 요구사항서를 충분히 반영했는지 codex 로 채점하고, 부족분을 보강한 뒤 재검증하는 수렴 루프. **검증자=codex, 수정자=메인 에이전트(인라인).**

**전제 (skip 조건 — 본체 작성 결과는 유지, 실패 처리 X)**:
- `reference_doc` 부재 → skip + `[docs-add-task] 요구사항서 없음 — 정합 검증 생략`.
- 1라운드 `docs_conformance.py` exit 2 → `[docs-add-task] codex 미설치 — 정합 검증 생략`.

**`targets`** = 이번 실행에 작성·갱신한 문서 전체 (Phase 14 보고 목록 = TASK + 신규/기존 FRD + ADR + FC + PRD + ADR-CATALOG 중 실제 변경분). `reference_doc` 는 포함하지 않는다.

**루프** (threshold 99%, max 3):

```
for i in 1..3:
  1. Bash 실행:
     python "$CONF" --reference <reference_doc> --targets <targets...>
  2. exit 2 → codex 미설치 skip. exit 4 → 문서 크기 초과 skip. (둘 다 경고 후 종료)
  3. conformance 파싱: .review/req-conformance-<reference_doc stem>.md frontmatter `conformance: N%`
     (없으면 stdout 마지막 `Conformance: N%`).
  4. N ≥ 99 → 수렴 ✅, break.
  5. i == 3 → cap, break (마지막 라운드는 보강 안 함).
  6. 보강: .review/req-conformance-<stem>.md 의 "부족 항목"(✗/⚠ + 보강 지시) 보고
     해당 설계문서 편집 (FRD/TASK/ADR 우선, 영향 시 FC/PRD/ADR-CATALOG 동반).
     - 금지: reference_doc 수정, .review/ 수정.
     - 준수: v0.7 룰 (템플릿 구조 대조·양방향 인용 금지·코드상세 금지).
     - 편집은 working-tree 에 즉시 반영 → 다음 라운드가 동일 targets 재채점.
```

**보고**:
- 수렴: `요구사항 정합: <N1%→N2%→…> ✅ 99% 도달 (iter k/3)`
- cap: `요구사항 정합: <궤적> ⛔ 99% 미달 (3/3) — 남은 부족 항목:` + Requirements Coverage ✗/⚠ 행 요약(요구·사유).

> 검증은 명시 `targets` 기준 — docs-add-task 외 미커밋 변경과 무관(git diff 미사용). reference_doc 는 targets 에 없어 자기참조 채점 불가.

---

## Phase 14: 결과 보고

실제 수행한 op 만 출력:
```
CREATE docs/<App>/TASK/<App>-TASK-<NNN>.md
[신규 FRD] CREATE docs/<App>/FRD/<App>-FRD-<NNN>.md
[신규 ADR] CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md
[기존 FRD] UPDATE docs/<App>/FRD/<App>-FRD-<N>.md (history + sections)
[기존 ADR] UPDATE docs/<App>/ADR/<App>-ADR-<MMM>.md (Superseded / in-place)
[신규 기능] UPDATE docs/<App>/<App>-PRD.md (§3.1, §7)
UPDATE docs/<App>/<App>-FC.md (rows added/updated)
[ADR op] UPDATE docs/<App>/<App>-ADR-CATALOG.md (Proposed / Superseded / 갱신)
Reference: .requirements/req-<App>-TASK-<NNN>.md
Checks: <P> PASS, <F> FAIL
요구사항 정합: <궤적> <✅ 99% 도달 (iter k/3) | ⛔ 99% 미달 (3/3) | 생략(codex 미설치/요구사항서 부재)>
```

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
- App 다수 → AskUserQuestion.
- 영향 FRD 0건 + 기능 의도(신규/feature/변경/버그수정) + 모호 → 사용자 확인 → 신규면 FRD 신설, 기존 누락이면 FRD ID 지정 후 갱신.
- FC/PRD/ADR-CATALOG 파일 부재 → 작성 거절 + "App 부트스트랩 누락" 보고.
- NNN 한계 (F099/TASK099/ADR099 초과) → exit 2 + 중단.
- FRD 파일 부재 (FC 에 등재됐으나 실제 파일 없음) → **FC 행의 기존 F-id 로 FRD 신설** (skip 아님 — upsert). next-id frd 호출하지 않고 기존 F-id 재사용.
- 다중 결정 (ADR N≥2) → 사용자 분할 권고.
- Backlog + 일반 신설 충돌 → 사용자 재확인.
