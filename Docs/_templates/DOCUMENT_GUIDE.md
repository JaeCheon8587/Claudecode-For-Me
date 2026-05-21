# DOCUMENT_GUIDE — 문서 작성 가이드

> AI 코딩 에이전트가 신규 문서를 작성할 때 따라야 할 단일 SSOT. 작성 룰 충돌 시 본 가이드 우선. 코드 룰은 [DDD_ARCHITECTURE_RULES](DDD_ARCHITECTURE_RULES.md) / [OBJECT_ORIENTED_DESIGN_RULES](OBJECT_ORIENTED_DESIGN_RULES.md) / [BEHAVIORAL_GUIDELINES_RULES](BEHAVIORAL_GUIDELINES_RULES.md) 참조.
> **본 파일은 deploy 후 `Docs/DOCUMENT_GUIDE.md` 위치 기준**. 상대 경로는 `../CLAUDE.md`, 동위 룰 파일은 동일 폴더.

| 항목 | 값 |
|---|---|
| 문서 ID | DOCUMENT_GUIDE (단일 파일) |
| 버전 | 0.7 (Draft) |
| 작성 가정 | 솔루션 전체 문서 (PRD/FC/FRD/RFD/TASK/ADR/ADR-CATALOG/ARCHITECTURE) 의 작성 룰 통합 |
| 관련 문서 | [CLAUDE](../CLAUDE.md) · [_templates/](_templates/) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |
| 0.2 | YYYY-MM-DD | per-app 레이아웃 재정의. ADR 명칭 확정. SYSTEM_CODE 출처를 `/CLAUDE.md` 로 이전 | {이름} |
| 0.3 | YYYY-MM-DD | 템플릿 링크 실제 파일 경로(`_templates/App/...`) 정합. SOLUTION_CODE / SYSTEM_CODE 용어 분리. 솔루션 공통 양식 행 추가. 신규 App 시나리오 명문화. 템플릿 파일명도 ADR 로 통일 | {이름} |
| 0.4 | YYYY-MM-DD | 코드 상세를 쓰지 않는 리팩토링 계획(RFD)·일회성 작업 계획(TASK) 문서 유형 추가 | {이름} |
| 0.5 | YYYY-MM-DD | FRD도 코드 상세 금지 원칙 적용. 기능 요구·흐름·수용 기준 중심 문서로 재정의 | {이름} |
| 0.6 | YYYY-MM-DD | TASK 문서 수정 범위 룰 추가 — TASK 본문은 자기 자신 외 SSOT 문서 직접 수정 금지, 영향은 §5·§6 에 명시만 하고 실제 갱신은 별도 작업으로 분리 | {이름} |
| 0.7 | YYYY-MM-DD | 컨셉 재정의 — TASK = 휘발성 self-contained 작업 지시서 + 외부 SSOT 인용 금지 (양방향). 영향 SSOT 갱신은 작성 시점 사전 동반. AI 실행 시 SSOT 자동 수정 금지. RFD 양식 폐기 (리팩토링도 TASK 작업 유형 = refactor) | {이름} |
| 0.8 | 2026-05-20 | ADR 용어 통일 (템플릿 파일명·결과 파일명·문서 ID 전부 ADR 접두사) | {이름} |

## 0. 용어 정의

| 용어 | 의미 | 예시 | 사용 위치 |
|---|---|---|---|
| **SOLUTION_CODE** | 솔루션(레포 전체) 식별자 | `XLAB` | `Docs/ARCHITECTURE.md`, `/CLAUDE.md` 제목, (선택) 솔루션 단일 PRD |
| **SYSTEM_CODE** ≡ **APP_CODE** ≡ **{App}** | App(S/W 단위) 식별자. 3개 별칭은 동일 개념. **{App} 가 식별자 패턴 표기 기본** | `LOADER` | App별 문서 ID (`{App}-PRD`, `{App}-FRD-{NNN}` 등), 폴더명 `Docs/{App}/` |

SYSTEM_CODE 후보 단일 출처(SSOT): [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md) 표. 신규 App 도입 시 해당 표 행 추가가 모든 다른 작업보다 선행.

## 1. 문서 종류와 역할

### 1.1 솔루션 공통 (single-instance)

| 종류 | 위치 | 역할 | 성격 | 템플릿 |
|---|---|---|---|---|
| CLAUDE | `/CLAUDE.md` | AI 진입점 / 라우터 / SOLUTION_CODE·SYSTEM_CODE SSOT / Backend Services Overview | 라우터 | [_templates/CLAUDE-TEMPLATE.md](_templates/CLAUDE-TEMPLATE.md) |
| ARCHITECTURE | `Docs/ARCHITECTURE.md` | 솔루션 공통 레이어 모델 / 참조 매트릭스 / 폴더→레이어 매핑 / 접미사 | 콘텐츠 | [_templates/ARCHITECTURE-TEMPLATE.md](_templates/ARCHITECTURE-TEMPLATE.md) |
| (선택) 솔루션 PRD | `Docs/PRD.md` | 솔루션 시점 — 시스템 전체 배경/목표/범위 + cross-cutting SSOT 부록 (errorCode/도메인/DTO). 단일 App 솔루션 시 (선택) — 미채택 시 App PRD 가 cross-cutting 부록 겸유 | 콘텐츠 | [_templates/PRD-TEMPLATE.md](_templates/PRD-TEMPLATE.md) |
| 룰: DDD | `Docs/DDD_ARCHITECTURE_RULES.md` | C# 레이어 위반 방지 단일 룰 | 룰 | [_templates/DDD_ARCHITECTURE_RULES.md](_templates/DDD_ARCHITECTURE_RULES.md) |
| 룰: OOP | `Docs/OBJECT_ORIENTED_DESIGN_RULES.md` | SOLID 책임 분해 룰 | 룰 | [_templates/OBJECT_ORIENTED_DESIGN_RULES.md](_templates/OBJECT_ORIENTED_DESIGN_RULES.md) |
| 룰: Behavioral | `Docs/BEHAVIORAL_GUIDELINES_RULES.md` | LLM coding 행동 가이드 | 룰 | [_templates/BEHAVIORAL_GUIDELINES_RULES.md](_templates/BEHAVIORAL_GUIDELINES_RULES.md) |
| 본 가이드 | `Docs/DOCUMENT_GUIDE.md` | 문서 작성 SSOT (본 파일) | 룰 | [_templates/DOCUMENT_GUIDE.md](_templates/DOCUMENT_GUIDE.md) |

### 1.2 App별 (per-{App} 인스턴스)

| 종류 | 위치 | 역할 | 성격 | 템플릿 |
|---|---|---|---|---|
| App PRD | `Docs/{App}/{App}-PRD.md` | App 시점 — 솔루션 내 단일 App 의 배경/목표/범위/기능 (FC roll-up). 기술 시야 (호스트/런타임) 는 APP-ARCHITECTURE 위임. cross-cutting 부록은 솔루션 PRD 인용 | 콘텐츠 | [_templates/App/APP-PRD-TEMPLATE.md](_templates/App/APP-PRD-TEMPLATE.md) |
| App FC | `Docs/{App}/{App}-FC.md` | App별 기능 레지스트리 (5축 표) | 콘텐츠 인덱스 | [_templates/App/APP-FC-TEMPLATE.md](_templates/App/APP-FC-TEMPLATE.md) |
| App ARCHITECTURE | `Docs/{App}/{App}-ARCHITECTURE.md` | App별 호스트 아키텍처 (런타임/진입점/책임/구성요소) | 콘텐츠 | [_templates/App/APP-ARCHITECTURE-TEMPLATE.md](_templates/App/APP-ARCHITECTURE-TEMPLATE.md) |
| App FRD | `Docs/{App}/FRD/{App}-FRD-{NNN}.md` | App별 기능 요구 문서. 코드 상세 없이 목적·흐름·정책·수용 기준·문서 반영 범위 정의 | 콘텐츠 | [_templates/App/FRD/APP-FRD-001-TEMPLATE.md](_templates/App/FRD/APP-FRD-001-TEMPLATE.md) |
| ~~App RFD~~ | ~~`Docs/{App}/RFD/{App}-RFD-{NNN}.md`~~ | **DEPRECATED (v0.7)** — RFD 양식 폐기. 리팩토링 작업은 App TASK 의 `작업 유형 = refactor` 로 처리 | — | — |
| App TASK | `Docs/{App}/TASK/{App}-TASK-{NNN}.md` | App별 AI 실행용 작업 지시서. **휘발성 + self-contained**. 작업 유형 메타 (feature/refactor/maintenance/migration/setup/investigation/etc) 로 모든 코드 작업을 표현. **외부 SSOT 인용 금지 (양방향)**: TASK 는 영구 SSOT 를 마크다운 링크로 인용하지 않으며, 영구 SSOT 도 TASK 를 인용하지 않는다. 영향 SSOT 갱신은 작성 시점에 작성자가 동반 수행하고 §6 에 텍스트로만 명시 | 휘발성 콘텐츠 | [_templates/App/TASK/APP-TASK-001-TEMPLATE.md](_templates/App/TASK/APP-TASK-001-TEMPLATE.md) |
| App ADR | `Docs/{App}/ADR/{App}-ADR-{NNN}.md` | App별 아키텍처 결정 narrative | 콘텐츠 | [_templates/App/ADR/APP-ADR-001-TEMPLATE.md](_templates/App/ADR/APP-ADR-001-TEMPLATE.md) |
| App ADR-CATALOG | `Docs/{App}/{App}-ADR-CATALOG.md` | App별 결정 상태/영향/반영 인덱스 | 인덱스 | [_templates/App/APP-ADR-CATALOG-TEMPLATE.md](_templates/App/APP-ADR-CATALOG-TEMPLATE.md) |

**명칭**: 템플릿 파일명, 결과 파일명, 문서 ID 모두 `ADR` 를 사용한다.

**FRD 작성 원칙**: FRD 에는 코드 경로, 파일명, 클래스명, 메서드명, 구현 방식, 테스트/검증 명령, 설정 키, API 경로·스키마를 쓰지 않는다. FRD 는 기능 요구·흐름·정책·수용 기준 중심.

**TASK 작성·실행 원칙 (v0.7)**:

1. **TASK = 휘발성 + Self-contained 작업 지시서**. 영구 SSOT 가 아니다. 작업 완료 후 TASK 파일은 삭제될 수 있다. AI 가 코드 실행에 필요한 정보 (외부 계약 / 데이터 구조 / 정책 / 코드 변경 단위) 는 TASK 본문의 컨텍스트 임베드 절에 모두 포함한다.
2. **외부 SSOT 인용 금지 (양방향)**: TASK 본문은 영구 SSOT (PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE) 를 마크다운 링크로 인용하지 않는다 (`[FRD-006](...)` 형태 금지). 영향받는 SSOT 는 §6 영향 표에 **이름·요지·갱신 상태만 텍스트로** 명시한다. 역으로 영구 SSOT 도 TASK 를 인용하지 않는다 (휘발성 → 깨진 링크 방지).
3. **영향 SSOT 갱신은 작성 시점 사전 동반**: TASK 작성자는 본 TASK 작성 시점에 영향 영구 SSOT (FRD 본문·FC 행·ADR 신설·ADR-CATALOG 행) 를 직접 갱신한다. TASK §6 에 갱신 상태 = "완료" 로 선언한다.
4. **AI 실행 시 SSOT 자동 수정 금지**: AI 가 TASK 를 입력으로 받아 §8 단계를 코드로 실행할 때는 **코드 변경만** 수행한다. 영구 SSOT 자동 수정 금지 (사전 갱신 전제).
5. **작업 유형 메타**: TASK 의 작업 유형을 `feature / refactor / maintenance / migration / setup / investigation / 기타` 중 하나로 분류한다. **리팩토링도 TASK 양식** (작업 유형 = refactor) 으로 처리 — RFD 양식 폐기.

**RFD 폐기 안내**: 기존 RFD 양식 ([_templates/App/RFD/APP-RFD-001-TEMPLATE.md](_templates/App/RFD/APP-RFD-001-TEMPLATE.md)) 은 v0.7 부터 사용하지 않는다. 폴더 (`Docs/{App}/RFD/`) 가 비어 있으면 그대로 두고, 기존 RFD 본문이 있으면 별도 결정으로 처리 (보존 / 삭제 / TASK 로 흡수).

**부트스트랩 절차**: [`/CLAUDE.md` § 최초 부트스트랩](../CLAUDE.md) 참조.

## 2. 작성 순서

**신규 기능 추가**: `{App}-PRD.md` §3.1·§7 갱신 → `{App}-FC.md` 5축 표 행 추가 → `Docs/{App}/FRD/{App}-FRD-{NNN}.md` 신규 (코드 상세 없이 기능 요구·수용 기준 작성) → 필요 시 ADR 등재 + `{App}-ADR-CATALOG.md` 동기화 → 구현 착수.

**신규 결정 등재**: `Docs/{App}/ADR/{App}-ADR-{NNN}.md` 신규 (narrative) → `{App}-ADR-CATALOG.md` 의 Proposed/Accepted 행 추가 → 영향 PRD/FC/FRD/RFD/TASK 본문에 ADR 인용.

**리팩토링 작업** (v0.7 부터): RFD 양식 폐기. **TASK 양식 + 작업 유형 = refactor** 로 처리. 작성 흐름은 아래 "AI 실행용 작업 지시서 작성" 과 동일.

**AI 실행용 작업 지시서 작성** (TASK — 모든 코드 작업 통합 흐름):
1. **사전: 영향 영구 SSOT 갱신** — 영향받는 FRD 본문·FC 행·ADR 신설·ADR-CATALOG 행 등을 작성자가 먼저 직접 갱신한다. (이 단계가 TASK 작성보다 선행)
2. `Docs/{App}/TASK/{App}-TASK-{NNN}.md` 신규 — 휘발성 + self-contained. 외부 SSOT 인용 금지.
3. §6 영향 SSOT 표에 갱신 완료 상태 텍스트로 선언 (링크 X).
4. §12 컨텍스트 임베드 — AI 가 코드 실행에 필요한 외부 계약·데이터 구조·정책을 본문에 복제·요약 임베드.
5. §8 작업 단계 = AI 가 코드로 실행 가능한 단위로 작성 (영구 SSOT 본문 갱신 단계 포함 X — 이미 사전 완료).
6. AI 에게 TASK 던져 §8 실행. AI 는 코드만 변경.
7. 완료 후 본 TASK 파일은 삭제될 수 있다 (영구 추적은 영구 SSOT 본문·변경이력·ADR 에서 한다).

**아키텍처 룰 변경**: ADR 등재 (배경/결정/결과/대안) → ADR-CATALOG → 솔루션 룰 파일(`DDD_ARCHITECTURE_RULES.md` 등) 본문 갱신.

**신규 App 추가**: `/CLAUDE.md` Backend Services Overview 표 행 추가 (SYSTEM_CODE 확정) → `/CLAUDE.md` 설계 문서 인덱스 표 App 행 복제·추가 → `Docs/{App}/` 폴더 + 하위 `FRD/`·`ADR/`·`RFD/`·`TASK/` 서브폴더 생성 → `_templates/App/` 직접 양식 복사·rename (`APP-PRD-TEMPLATE` → `{App}-PRD.md` 등) → `_templates/App/{ADR,FRD,RFD,TASK}/` 서브폴더 양식은 첫 개별 문서 작성 시 사용.

## 3. 메타 표 공통 패턴

모든 콘텐츠 문서 상단 보유 (라우터 CLAUDE 제외):

| 항목 | 값 |
|---|---|
| 문서 ID | (§5 식별자 규약 참조) |
| 버전 | 0.1 (Draft) 등 |
| 작성 가정 | 작성 시 깔린 가정 한 줄 |
| 관련 문서 | 상위 SSOT 인용 (PRD / ADR-CATALOG 등) |

## 4. 변경 이력 표 공통 패턴

메타 표 직후 신설. 모든 콘텐츠 문서 적용.

```
## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |
```

## 5. 식별자 규약

| 식별자 | 형식 | 예시 |
|---|---|---|
| SOLUTION_CODE | 영문 대문자 (솔루션 이름) | `XLAB` |
| SYSTEM_CODE ≡ APP_CODE ≡ {App} | 영문 대문자 (App 이름) | `LOADER` |
| 솔루션 PRD ID | `{SOLUTION_CODE}-PRD` (NNN 없음 — 단일) | `XLAB-PRD` |
| App PRD ID | `{App}-PRD` | `LOADER-PRD` |
| FC ID | `{App}-FC` | `LOADER-FC` |
| ARCHITECTURE ID | `{App}-ARCHITECTURE` | `LOADER-ARCHITECTURE` |
| FRD ID | `{App}-FRD-{NNN}` (NNN 3자리, 001~099 정식 / 101~ Backlog) | `LOADER-FRD-001` |
| ~~RFD ID~~ | ~~`{App}-RFD-{NNN}`~~ — **DEPRECATED (v0.7)** | — |
| TASK ID | `{App}-TASK-{NNN}` (NNN 3자리) | `LOADER-TASK-001` |
| ADR ID | `{App}-ADR-{NNN}` (NNN 3자리) | `LOADER-ADR-001` |
| ADR-CATALOG ID | `{App}-ADR-CATALOG` | `LOADER-ADR-CATALOG` |
| 수용 기준 | `AC-{NNN}-{NNN}` (FRD 내부 로컬) | `AC-001-001` |
| 테스트 | `TC-{NNN}-{NNN}` | `TC-001-001` |
| 미확인 | `Q-{NNN}-{NNN}` | `Q-001-001` |
| errorCode | SCREAMING_SNAKE | `INVALID_TOKEN` |

SYSTEM_CODE 후보는 [`/CLAUDE.md` Backend Services Overview](../CLAUDE.md) 표를 단일 출처. 신규 App 도입 시 해당 표 행 추가 선행. SOLUTION_CODE 는 `/CLAUDE.md` 제목 line + `Docs/ARCHITECTURE.md` 메타 표가 단일 출처.

## 6. placeholder / 빈칸 룰

- placeholder 형식: `{설명}` 중괄호. 실제 값 채우거나 줄 삭제.
- 솔루션 레벨 placeholder: `{SOLUTION_CODE}`, `{프로젝트명}`.
- App 레벨 placeholder: `{App}` (또는 `{SYSTEM_CODE}` / `{APP_CODE}` — 동의어), `{NNN}` (FRD/ADR/TASK 번호 3자리. RFD 는 v0.7 폐기).
- 빈칸 / "N/A" **금지**. 해당 없으면 **"없음" 명기**.
- 미완성 항목은 "미작성/추후" 명기.
- `_` 또는 `.` 시작 폴더 (예: `_templates/`) 는 템플릿/감사용 — SSOT 아님.

## 7. SSOT 인용 패턴

상호 참조 시 마크다운 링크 + anchor. **영구 SSOT 끼리만 상호 인용. TASK 는 어디서도 인용되지 않고, TASK 본문도 영구 SSOT 를 인용하지 않는다** (v0.7 룰).

### 7.1 App 폴더 내부 상대 경로 (기준: `Docs/{App}/` 내부 파일, 영구 SSOT 간 인용)

- 절: `[PRD §3]({App}-PRD.md#3-범위)`
- 부록: `[PRD 부록]({App}-PRD.md#부록)`
- FRD: `[{App}-FRD-001](FRD/{App}-FRD-001.md)`
- ADR: `[{App}-ADR-001](ADR/{App}-ADR-001.md)`
- ADR-CATALOG: `[ADR-CATALOG]({App}-ADR-CATALOG.md)`
- ~~RFD~~: **DEPRECATED (v0.7)** — RFD 양식 폐기
- ~~TASK~~: **인용 금지 (v0.7)** — TASK 는 휘발성. 영구 SSOT 가 TASK 를 인용하지 않으며, TASK 본문도 영구 SSOT 를 인용하지 않는다. 영향받는 SSOT 는 TASK §6 영향 표에 텍스트로만 명시

### 7.2 솔루션 공통 문서 참조 (기준: `Docs/{App}/` 내부 파일 → 상위)

- 솔루션 ARCHITECTURE: `[ARCHITECTURE](../ARCHITECTURE.md)`
- DDD 룰: `[DDD](../DDD_ARCHITECTURE_RULES.md)`
- DOCUMENT_GUIDE: `[DOCUMENT_GUIDE](../DOCUMENT_GUIDE.md)`
- CLAUDE: `[CLAUDE](../../CLAUDE.md)` (레포 루트)

### 7.3 메타 행 인용 룰

"관련 문서" 메타 행에 부모 SSOT (상위) 인용. 하위 (디테일) 는 본문에서 인용.

## 8. 동기화 부담 위치

| 변경 | 갱신 위치 |
|---|---|
| 신규 ADR | `{App}-ADR-{NNN}.md` + `{App}-ADR-CATALOG.md` + 영향 PRD/FC/FRD 본문 (TASK 인용 X) |
| ~~신규 RFD~~ | **DEPRECATED (v0.7)** — 리팩토링은 신규 TASK 의 작업 유형 = `refactor` 로 처리 |
| 신규 TASK | (사전) 영향 영구 SSOT (PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE) 를 작성자가 직접 갱신 → (후) `Docs/{App}/TASK/{App}-TASK-{NNN}.md` 신규 (self-contained, 외부 SSOT 인용 X). TASK §6 에 갱신 상태 텍스트로 선언. AI 가 §8 실행 시 코드만 변경 |
| 신규 App | `/CLAUDE.md` Backend Services Overview + `/CLAUDE.md` 인덱스 표 + `Docs/{App}/` 전체 신규 (`{App}-PRD.md` / `{App}-FC.md` / `{App}-ARCHITECTURE.md` / `{App}-ADR-CATALOG.md`) |
| 신규 기능 `{NNN}` | `{App}-FC.md` 5축 표 행 + `{App}-FRD-{NNN}.md` 신규 + `{App}-PRD.md` §7 (해당 시) |
| 신규 기능 `{NNN}` (cross-cutting 영향) | 위 + 솔루션 PRD §3.1·§8·§11 + 솔루션 부록 B/D/E (영향 시) |
| 솔루션 PRD ↔ App PRD 동기화 | App PRD §3.1·§7 변경 시 솔루션 PRD §3.1·§8 동기화. App 신규 errorCode/도메인 entity/Contract DTO 발생 시 솔루션 PRD 부록 B/D/E 등재 선행 |
| 아키텍처 룰 변경 | ADR + ADR-CATALOG + 솔루션 룰 파일 본문 |
| 새 룰 파일 추가 | `/CLAUDE.md` 인덱스 행 추가 |
| 신규 솔루션 (레포 초기화) | `/CLAUDE.md` § 최초 부트스트랩 절차 수행 |

## 9. AI 작업 시나리오 요약

- **신규 기능 추가 요청** → §2 의 신규 기능 추가 흐름. FRD 에 코드 상세 없이 기능 요구·흐름·수용 기준 작성.
- **결정 등재 요청** → §2 의 신규 결정 흐름. ADR Proposed → Accepted.
- **리팩토링 요청** → §2 의 "AI 실행용 작업 지시서 작성" 흐름 (TASK 양식 + 작업 유형 = refactor). RFD 양식은 v0.7 폐기.
- **일회성 작업 요청** → §2 의 "AI 실행용 작업 지시서 작성" 흐름 (TASK 양식 + 적절한 작업 유형). 사전에 영향 영구 SSOT 를 작성자가 직접 갱신하고, TASK 는 휘발성 self-contained 작업 지시서로 작성한다.
- **신규 App 추가 요청** → §2 의 신규 App 추가 흐름. `/CLAUDE.md` Backend Services Overview 행 추가가 모든 다른 작업보다 선행.
- **코드 작성 요청** → CLAUDE 인덱스의 룰 파일 (`DDD_ARCHITECTURE_RULES` / `OBJECT_ORIENTED_DESIGN_RULES` / `BEHAVIORAL_GUIDELINES_RULES`) 읽고 4단계 마커 (반드시/허용/금지/절대 금지) 준수. FRD §1·§2·§17·§18 로 기능 의도와 수용 기준을 확인하되, 구현 상세와 검증 명령은 최신 코드/빌드 환경 기준으로 판단한다.
- **신규 솔루션 부트스트랩 요청** → [`/CLAUDE.md` § 최초 부트스트랩](../CLAUDE.md) 절차 수행.
