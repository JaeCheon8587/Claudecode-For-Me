---
name: docs-add-frd
description: v0.7 per-App SSOT 체계에서 신규 기능 FRD + ADR 를 in-place 작성한다. FRD + ADR 파일 생성, App-PRD §3.1/§7 갱신, FC 5표 행 추가, ADR-CATALOG Proposed 행 추가. 사용자가 신규 기능을 자연어로 요청 (예: "주문 검색 기능 추가") 할 때 트리거.
argument-hint: "[신규 기능 자연어 prompt]"
---

# docs-add-frd

docs/.templates v0.7 체계 (per-App PRD/FC/ARCHITECTURE/FRD/ADR/ADR-CATALOG) 에서 **신규 기능 FRD + ADR 항상 동반 생성**. source repo in-place 수정. preview 없음.

---

## 핵심 원칙

- **v0.7 전용** — Legacy (`PRD-<CODE>-001.md`, 19-section FRD 등) 미지원.
- **In-place** — `docs/<App>/...` 경로에 직접 쓰기. preview-dir 없음.
- **ADR 항상 강제** — FRD 1개 = ADR 1개 동반. 결정 사항 없을 시 placeholder 자동 채움.
- **AI 자동 채움** — 사용자 prompt 에 없는 선택 항목은 "미작성/추후" 또는 "없음" 텍스트.
- **TASK 인용 금지** — 본 skill 은 TASK 미관여 (v0.7 휘발성 룰).
- **부분 실패 시 rollback X** — 결과 보고에 partial status 명시.

---

## Phase 0: 대상 App 결정

```
python scripts/docs_helpers.py list-apps --repo .
```

응답 JSON 의 `apps[].code` 이용:
- 0건 → 중단. 가이드: "`/CLAUDE.md` Backend Services Overview 표에 App 행 추가 + `docs/<App>/` 폴더 부트스트랩 후 재시도."
- 1건 → 자동 채택.
- 2건 이상 → `AskUserQuestion` 으로 사용자 선택.

`unbootstrapped` 가 비어있지 않으면 (CLAUDE.md 등재됐으나 `docs/<App>/` 부재) 경고 보고.

---

## Phase 1: 입력 수집

사용자 prompt 에서 다음 추출 (자연어 파싱):

**필수** (없으면 `AskUserQuestion`)
- `name` — 기능명 (10자 이내 권장)
- `summary` — 한 줄 설명
- `purpose` — 기능 목적 (`§1` 기능 요약)
- `actor` — 사용자 역할 (`§3`)
- `work_type` — `신규` (default) / `변경` / `버그수정`

**선택** (없으면 자동 placeholder)
- `priority` (default `P1`)
- `dependencies`, `scope_in`, `scope_out`, `preconditions`
- `main_flow`, `alternative_flow`, `exception_flow`
- `acceptance_criteria`, `test_cases`
- `data_entities`, `ui_surfaces`, `api_paths`, `non_functional`, `notes`
- `release_scope` (default `이번 릴리즈 포함`)

Backlog 신설 시 (사용자 명시 "backlog" / "확장 후보"):
- FRD 파일 생성 X. FC `## 확장 후보 기능 (Backlog)` 표 행만 추가.
- 본 Phase 종료, Phase 4 직행 (FC 만 갱신).

---

## Phase 2: 번호 할당

```
python scripts/docs_helpers.py next-id --repo . --app <App> --kind frd
python scripts/docs_helpers.py next-id --repo . --app <App> --kind adr
python scripts/docs_helpers.py git-user --repo .
```

- 활성 FRD NNN, ADR NNN 산출
- exit 2 (`FAIL LIMIT`) 시 즉시 중단 + 보고
- Backlog 모드 시 `next-id --kind frd --backlog`

오늘 일자 = ISO 형식 (`YYYY-MM-DD`). 시스템 날짜 사용.

---

## Phase 3: FRD 파일 내용 준비

`.templates/App/FRD/APP-FRD-001-TEMPLATE.md` 기준 20 section + 메타 표 + 변경 이력 표.

### 메타 표 6 행

```
| 항목 | 값 |
|---|---|
| 문서 ID | <App>-FRD-<NNN> |
| 버전 | 0.1 (Draft) |
| 기능 ID | F<NNN> |
| 상태 | Draft |
| 작성 가정 | <prompt 에서 추출 또는 "본 기능은 ..."> |
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

각 section 룰 (입력 없으면 "미작성/추후" 또는 "없음"):

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
| 17 | 수용 기준 | AC-F<NNN>-001 ~ 행 (acceptance_criteria) |
| 18 | 테스트 관점 | TC-F<NNN>-001 행 (test_cases 또는 placeholder) |
| 19 | 요구 근거 | App-PRD / FC 행 링크 + notes |
| 20 | 미확인 사항 | Q-F<NNN>-001 행 (Open 또는 "없음") |

**§16 항상 채움** (이 skill 의 작업 결과 즉시 반영):
```
| 문서 | 반영 여부 | 반영 내용 | 비고 |
|---|---|---|---|
| FC | 필요 | 신규 F<NNN> 등재 (5 표) | 완료 |
| ADR | 필요 | <App>-ADR-<NNN> 신설 | 완료 |
| ADR-CATALOG | 필요 | Proposed 행 추가 | 완료 |
```

**AC/TC/Q ID 자동**:
- `AC-F<NNN>-001` 행 1개 최소
- `TC-F<NNN>-001 | 미작성/추후 | 미작성/추후 | 미작성/추후 | 미작성/추후` 1개
- `Q-F<NNN>-001 | 없음 | - | - | - | -` 또는 사용자 명시

---

## Phase 4: ADR 파일 내용 준비

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

**제목** = AI 가 FRD 명세 보고 추론. "결정 사항 없음" 케이스 = `"<기능명> 표준 구현 채택"`.

**컨텍스트** = FRD §1·§2 요약.

**결정** = AI 가 추론.
- 결정 사항 존재 (사용자가 옵션·정책·제약 언급) → 명시.
- 결정 사항 없음 → `"본 기능은 특이 결정 없이 도메인 표준 패턴을 따른다."`

**결과** = 가능해지는 기능 + 후속 작업.

**대안 검토** = 결정 사항 없으면 `"대안 검토 없음 (단순 구현)"`. 있으면 옵션 A/B 명시.

**§ 코드 인용**: 신규 기능 = `"신규 — 코드 인용 없음 (구현 시 첨부)"`.

**§ 문서 반영** (필수):
- `[<App>-ADR-CATALOG](../<App>-ADR-CATALOG.md)` — Proposed 행 추가
- `[<App>-PRD](../<App>-PRD.md)` — §3.1 / §7 갱신
- `[<App>-FC](../<App>-FC.md)` — F<NNN> 행 추가 (5표)
- `[<App>-FRD-<NNN>](../FRD/<App>-FRD-<NNN>.md)` — §16 반영

---

## Phase 5: FC 갱신 내용 준비

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

---

## Phase 6: App-PRD 갱신 내용 준비

`docs/<App>/<App>-PRD.md` 다음 절 갱신:

### §3.1 (릴리즈 범위)
- `이번 릴리즈 포함` 셀 텍스트 끝에 `, F<NNN>` 추가. 셀에 `{본 App 의 현 릴리즈 범위}` placeholder 만 있으면 `F<NNN>` 로 교체.
- Backlog 모드 시 `이번 릴리즈 제외` 셀 갱신.

### §7 (주요 기능 요약)
- 표 행 1 추가:
```
| F<NNN> | <name> | <summary> | <release_scope> |
```

---

## Phase 7: ADR-CATALOG 갱신 내용 준비

`docs/<App>/<App>-ADR-CATALOG.md` `## Proposed` 표 행 1 추가:

```
| [<App>-ADR-<NNN>](ADR/<App>-ADR-<NNN>.md) | <ADR 제목> | <오늘> | <영향 모듈 또는 "F<NNN> 기능"> | <결정 기한 = 오늘+14일> | <결정 필요자 = "개발 리드"> |
```

`Proposed` 절 자체가 없으면 절 + 표 헤더 자동 신설.

---

## Phase 8: 사전 확정

모든 변경 사항을 사용자에게 텍스트로 출력:

```
## 작성 계획

### 생성 파일
- CREATE docs/<App>/FRD/<App>-FRD-<NNN>.md (20 section + 메타 + 이력)
- CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md (Proposed, narrative 추론)

### 갱신 파일
- UPDATE docs/<App>/<App>-PRD.md
  - §3.1 릴리즈 범위: F<NNN> 추가
  - §7 주요 기능 요약: 행 1 추가
- UPDATE docs/<App>/<App>-FC.md
  - 5표 모두 F<NNN> 행 추가
- UPDATE docs/<App>/<App>-ADR-CATALOG.md
  - Proposed 행 1 추가

### 핵심 채움 값
- 기능명: <name>
- 한 줄 설명: <summary>
- 목적: <purpose>
- 작업 유형: <work_type>
- 우선순위: <priority>
- ADR 제목: <ADR 추론 제목>
```

`AskUserQuestion`:
- 옵션 1: "확정하고 작성 진행" (Recommended)
- 옵션 2: "수정 필요"

확정 → Phase 9. 수정 → 사용자 입력 반영 후 Phase 8 재진입.

---

## Phase 9: in-place 쓰기

작성 순서 (의존도 낮은 것부터, 부분 실패 시 partial OK):

1. **ADR 파일** `Write` (docs/<App>/ADR/<App>-ADR-<NNN>.md)
2. **FRD 파일** `Write` (docs/<App>/FRD/<App>-FRD-<NNN>.md)
3. **App-PRD** `Edit` §3.1 + §7
4. **FC** `Edit` 5표 행 추가
5. **ADR-CATALOG** `Edit` Proposed 행 추가

각 단계 실패 = 다음 단계 진행, 결과 보고에 `PARTIAL <항목>` 명시.

---

## Phase 10: 자기 검증

```
python scripts/docs_helpers.py check --repo . --app <App>
```

FAIL 있어도 source 유지. 출력 그대로 사용자에 노출. 수동 처리 안내.

---

## Phase 11: 결과 보고

```
CREATE docs/<App>/FRD/<App>-FRD-<NNN>.md
CREATE docs/<App>/ADR/<App>-ADR-<NNN>.md
UPDATE docs/<App>/<App>-PRD.md (§3.1, §7)
UPDATE docs/<App>/<App>-FC.md (5 tables)
UPDATE docs/<App>/<App>-ADR-CATALOG.md (Proposed +1)
Checks: <P> PASS, <F> FAIL
```

Cross-cutting 감지 시 (errorCode 신설, 솔루션 도메인 entity 변경 등):
```
[Warning] 솔루션 PRD 동기화 필요:
- docs/PRD.md §3.1·§8·부록 B/D/E 검토 권장 (자동 수정 안 함)
```

호스트 영향 감지 시:
```
[Warning] docs/<App>/<App>-ARCHITECTURE.md §1·§2 검토 권장
```

---

## 에러 케이스

- App 0건 → 중단 + 부트스트랩 가이드
- App 다수 → `AskUserQuestion`
- NNN 한계 (F099 초과) → exit 2 + 중단
- 필수 필드 부족 → `AskUserQuestion`
- FC/PRD/ADR-CATALOG 파일 부재 → 작성 거절 + "App 부트스트랩 누락" 보고
- Backlog 모드 + 일반 FRD 모드 충돌 → 사용자 재확인
