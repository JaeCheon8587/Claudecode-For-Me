# {App}-INT-{NNN} — {제목}

> ⚠ **TEMPLATE** — 본 파일은 Intent 문서 템플릿이다. 복사한 뒤 모든 `{...}` placeholder 를 실제 값으로 채우거나 해당 줄을 삭제하고, **이 경고 블록을 삭제**한다. 결과 파일명과 문서 ID 는 `{App}-INT-{NNN}` 형식을 사용한다 (`NNN` = 3자리 0패딩).
>
> **Intent 는 작업 단위 계약**: Part 1 은 무엇을·왜(기능 명세), Part 2 는 Part 1 에서 파생한 작업 지시다. 큰 기능은 여러 Intent 로 나누고 메타 표 "관련 Intent" 에 서로의 ID 를 남긴다. **클래스명·파일명·구현 방법은 Part 1·Part 2 어디에도 쓰지 않는다** — 개발 세션 몫이다.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-INT-{NNN} |
| 유형 | 기능개발 \| 리팩토링 |
| 상태 | draft |
| 작성 | {작성자} · {YYYY-MM-DD} |
| 승인 | pending |
| 관련 Intent | none |

<!-- 유형: 기능개발 · 리팩토링 중 하나만 남긴다. 상태 허용값: draft | approved | in-dev | in-review | done. 승인: approved 시 `{승인자} · {YYYY-MM-DD}`. 관련 Intent: 큰 기능을 여러 Intent 로 나눴을 때 해당 ID 를 나열, 없으면 none. -->

## Part 1 — 기능 명세

### Problem
<!-- 지금 무엇이 문제인가, 이것이 없으면 무슨 일이 생기는가. -->
{문제}

### Outcome
<!-- 이 Intent 가 끝났을 때 사용자·시스템이 얻는 결과. -->
{결과}

- Out of scope: {이번 Intent 에서 다루지 않는 범위}

### Affected
<!-- 영향 받는 대상 — 앱·사용자·기능 영역 (파일·클래스 아님). -->
{영향 범위}

### Constraints
<!-- 지켜야 할 제약 — 호환성·성능·일정·정책 등. -->
- {제약}

### Decisions
<!-- 되돌리기 어려운 결정과 근거·기각 대안. ADR 은 별도 파일 없이 이 섹션에 남긴다. -->
- D1. {결정} — 근거: {근거} — 기각 대안: {기각한 대안}

### Open questions
<!-- 아직 답이 없는 질문. 없으면 none. -->
none

---

<!-- 이 선 아래는 작업 지시. 클래스·파일·구현 방법은 쓰지 않는다 — 개발 세션 몫. -->

## Part 2 — 작업 지시

### Functional requirements
<!-- 테스트 가능한 문장으로 쓴 기능 요구. Part 1 의 Outcome·Decisions·Constraints 에서 추적 가능해야 한다. -->
- FR-1. {테스트 가능한 요구 문장}

### Edge cases
<!-- 각 FR 의 경계 상황과 기대 동작. 없으면 none. -->
- E-1. {상황} → {기대 동작}

### Error cases
<!-- 각 FR 의 오류 상황과 기대 동작. 없으면 none. -->
- X-1. {오류 상황} → {기대 동작}

### Acceptance
<!-- 기능개발: `- [ ] {완료 조건}` 체크리스트. 리팩토링: `- {보존해야 할 동작}` 목록. -->
- [ ] {완료 조건}

### Verification
<!-- 완료를 확인하는 **방법**. 실행 명령은 쓰지 않는다. -->
- {확인 방법}

### Risks
<!-- 이 작업이 깨뜨릴 수 있는 것과 대비. -->
- {리스크}

### Handoff
<!-- 개발 세션이 착수에 필요한 값. 모르는 값은 pending 으로 둔다. -->
| 항목 | 값 |
|---|---|
| repo · app | pending |
| base branch | pending |
| 브랜치명 | intent/{App}-INT-{NNN} |
| 손대지 말 영역 | pending |
| 완료 보고 방식 | pending |

<!-- 작성 규칙
1. 클래스명·파일명·구현 방법은 어느 Part 에도 쓰지 않는다.
2. FR 은 테스트 가능한 문장으로 쓴다.
3. Part 2 의 모든 항목은 Part 1(Outcome·Decisions·Constraints)에 근거가 있어야 한다.
4. `상태: approved` 는 Open questions 가 `none` 이고 Handoff 에 `pending` 이 없을 때만 가능하다. -->
