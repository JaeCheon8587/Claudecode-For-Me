# Branch Review — 최종 보고 템플릿

Step 6(종합 보고 및 영속화)이 소비하는 출력 스켈레톤. SKILL.md에 하드코딩하지 않고 여기서 단일 관리한다.
메인 에이전트는 이 파일을 Read → 아래 스켈레톤에 값을 채워 사용자에게 노출하고 `.review/branch-review-<slug>.md`에 그대로 Write한다.

---

## 0. finding 1줄 포맷 — finder 템플릿이 단일 출처

각 축의 finding 라인 포맷·SEVERITY·TYPE 정의는 **이 파일에 재기술하지 않는다**. 아래 finder 템플릿이 유일한 출처다 (drift 방지):

| 축 | 포맷 출처 |
|---|---|
| bugs | `templates/bugs-finder.md` (§Finding 포맷) |
| style | `templates/style-finder.md` |
| spec | `templates/spec-finder.md` |
| perf | `templates/perf-finder.md` |

**verbatim 원칙**: 4개 finder 출력은 재정렬·재작성 없이 그대로 노출한다. 메인 에이전트가 finding 문구를 손대면 편향 유입 — 금지.

---

## 1. 모드 선택 — 기본 vs 요약우선

| 모드 | 트리거 | 배치 |
|---|---|---|
| **기본** | 인라인/표준 모드 (단일 청크) | verbatim 먼저 → Summary/Recommendation 나중 |
| **요약우선(summary-first)** | 청크 분할 모드 **또는** 사용자가 "요약우선"·"결정만 먼저" 요청 | Summary/Recommendation 먼저 → verbatim 상세는 하단 |

두 모드 공통: 최상단 **BLUF 1줄**(결정 라벨 + 카운트)은 항상 맨 위. 대형 diff에서 결정을 찾으러 스크롤하는 비용을 없앤다.

---

## 2. 스켈레톤 — 기본 모드

```
## Branch Review: <브랜치명 또는 ref>

→ <RECOMMENDATION-LABEL> — <1줄 근거>
  (CRITICAL <n> · MAJOR <m> · Conflicts <k> · Intent mismatch <i>)

기준점: <ref> (merge-base = <sha>)
변경 규모: <N files, L lines (+a/-d), 제외 후>
Spec source: <라벨> [<HIGH|MEDIUM|LOW|FALLBACK|NONE>]
Standards source: <라벨> [<STRONG|WEAK|NONE>]
Intent: "<커밋 의도 요약>"

---

## bugs (verbatim)
<finder 원문 그대로 + Tests 한 줄>

---

## style (verbatim)
<finder 원문 그대로>

---

## spec (verbatim)
<finder 원문 그대로>

---

## perf (verbatim)
<finder 원문 그대로. 없으면 "없음.">

---

## Conflicts
<Step 5-2 결과. 없으면 "없음.">

## Cross-axis 중복        ← 2축 이상 겹친 그룹이 있을 때만. 없으면 섹션 자체 생략
[axis+axis] <path>:<line 또는 symbol> | max=<SEVERITY>
  <axis1>: <원문 1줄 요약>
  <axis2>: <원문 1줄 요약>

## Cross-chunk 검증 결과   ← 청크 모드 + REFUTED 있을 때만 (Step 5-0)
~~<원문>~~ — REFUTED, 근거: <파일:경로>

---

<§4 Summary>

<§5 Recommendation>

---
저장됨: .review/branch-review-<slug>.md
```

---

## 3. 스켈레톤 — 요약우선 모드 (청크/대형)

BLUF·메타 다음에 **Summary/Recommendation을 먼저**, verbatim 4축을 그 아래 상세 근거로 둔다. 나머지 규칙 동일.

```
## Branch Review: <...>

→ <RECOMMENDATION-LABEL> — <1줄 근거>
  (CRITICAL <n> · MAJOR <m> · Conflicts <k> · Intent mismatch <i>)

<메타 5줄: 기준점/변경규모/Spec/Standards/Intent>

⚠ 청크 분할 리뷰 (<N>청크 × 4 finder) — 청크간 ripple 미검출.

---

<§4 Summary>

<§5 Recommendation>

## Conflicts
## Cross-axis 중복 (있을 때만)
## Cross-chunk 검증 결과 (있을 때만)

---
## 상세 (verbatim)

### bugs
### style
### spec
### perf

---
저장됨: .review/branch-review-<slug>.md
```

---

## 4. Summary 포맷

**CRITICAL 전건 열거는 이 섹션 1곳에서만 한다** (BLUF는 카운트, Recommendation은 참조 — 열거 중복 제거).

```
## Summary
- bugs:  <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed)
- style: <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed) | Standards source: <STRONG|WEAK|NONE>
- spec:  <N> findings (Missing: A, Partial: B, Scope-creep: C, Flaw: D) | Spec source: <라벨 + 신뢰도>
- perf:  <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed)
- Conflicts: <N>
- Tests: <added | partial | missing | n/a>
- Intent mismatches: <N>
[청크 모드였다면]        ⚠ 청크 분할 리뷰 — 청크간 ripple(교차 영향) 미검출.
[spec FALLBACK/NONE]     ⚠ spec 근거 빈약 — MISSING/PARTIAL 보수적 자제됨, bugs/perf에 상대적으로 더 의존할 것.
[standards NONE]         ⚠ style 근거 문서·lint 설정 전무 — 주변 코드 대비 명백 일탈만 보고됨.
[CRITICAL ≥ 1 이면 필수]
  CRITICAL 목록 (축 무관 전건):
  - <axis> <path>:<line> — <한줄 요약>
  - ...
```

**CRITICAL 목록이 필수인 이유**: Recommendation precedence는 최우선 규칙 1개만 라벨화 → 한 축 CRITICAL이 `FIX-CRITICAL-FIRST`를 띄우면 다른 축 CRITICAL이 라벨 하나에 가려진다. 여기 전건 나열로 방지. **BLUF·Recommendation은 이 목록을 다시 열거하지 않고 "Summary 참조"로 가리킨다.**

---

## 5. Recommendation — precedence 규칙

복수 조건 동시 성립 시 **번호가 빠른 규칙 1개만** 채택. 채택된 라벨이 곧 BLUF의 `<RECOMMENDATION-LABEL>`.

```
1. 임의 축(bugs/style/spec/perf)에 CRITICAL ≥ 1     → FIX-CRITICAL-FIRST (머지 보류)
2. Conflicts ≥ 1                                     → RESOLVE-CONFLICTS (의도 재확인 필요)
3. Intent mismatch ≥ 1                               → RECONFIRM-INTENT (작성자 의도 확인 필요)
4. spec MISSING/PARTIAL ≥ 2 (등급 HIGH 또는 MEDIUM)  → BLOCK-SPEC-MISMATCH (재작업 필요)
5. 임의 축에 MAJOR ≥ 1                                → FIX-MAJOR-THEN-SHIP (수정 후 머지)
6. (위 전부 미해당)                                   → SHIP (머지 가능)
```

출력:
```
## Recommendation
<LABEL>: <1줄 근거>. <전체 CRITICAL/MAJOR 목록은 Summary 참조>.
```

**부연설명 (조건부 필수)**: 채택 규칙이 1~4번(5번보다 먼저 매치)이면서 4축 MAJOR 총합 ≥ 2면 아래 1줄 필수 —
`참고: 채택 규칙(<번호>)이 MAJOR <N>건보다 우선순위가 높아 라벨을 차지함 — Summary 참조.`

---

## 6. 출력 변형

| 옵션 | 트리거 | 동작 |
|---|---|---|
| 기본 | (없음) | §2 스켈레톤, NIT 억제 (대표 2건) |
| 요약우선 | 청크 모드 자동 / "결정만 먼저" | §3 스켈레톤 |
| compact / 1줄 / 짧게 | 사용자 요청 | finding마다 1줄, 섹션 헤더 최소화, verbatim 생략하고 축 라벨만 |
| verbose / 전체 / NIT 포함 | 사용자 요청 | NIT 펼침 + JUDGMENT 별도 섹션 |

**Compact 예시**:
```
→ FIX-CRITICAL-FIRST (CRITICAL 1 · MAJOR 2)
[CRITICAL][bugs][BOUNDARY] src/auth.ts:42 토큰 만료 `<` 사용. Fix: `<=`.
[MAJOR][spec][PARTIAL] PRD §3.2 리프레시 grace period 누락. Fix: 5분 window 추가.
[MAJOR][perf][N+1] src/orders.ts:60 루프당 DB 호출. Fix: 배치 조회.
[MINOR][style][JUDGMENT] src/utils.ts:88 export 불필요.
```

---

## 7. 예시 (기본 모드, 전체)

```
## Branch Review: feature/auth-refactor

→ FIX-CRITICAL-FIRST — 토큰 만료 비교 버그, 보안 영향. 머지 전 수정 필수.
  (CRITICAL 1 · MAJOR 2 · Conflicts 0 · Intent mismatch 0)

기준점: origin/main (merge-base = abc1234)
변경 규모: 12 files, 487 lines (+312/-175), 제외 후
Spec source: GitHub issue #234 [HIGH]
Standards source: CLAUDE.md + eslint.config.js [STRONG]
Intent: "Add JWT refresh rotation per security audit Q1"

---

## bugs (verbatim)

src/auth/middleware.ts:42 | CRITICAL | BOUNDARY | 토큰 만료 비교에 `<` 사용 — 경계 시각 통과. Fix: `<=`.
src/auth/refresh.ts:88 | MAJOR | LOGIC | async 함수 try/catch 누락. Fix: try/catch 감싸기 + logger.error.

Tests: added (src/auth/__tests__/refresh.test.ts)

---

## style (verbatim)

src/utils/jwt.ts:15 | MINOR | JUDGMENT | private 함수 export. 레포 패턴 위반. Rule: "N/A (관례)". Fix: export 제거.

---

## spec (verbatim)

§3.2 리프레시 토큰 회전 | MAJOR | PARTIAL | 회전 구현됐으나 "직전 토큰 5분 grace period" 누락. Spec: "회전 후 직전 토큰은 5분간 유효해야 한다". Fix: refresh.ts grace window 추가.
src/utils/logger.ts | MINOR | SCOPE-CREEP | 이슈 #234 범위 밖. Spec: 로깅 변경 요구 없음. Fix: 별도 PR 분리.

---

## perf (verbatim)
없음.

---

## Conflicts
없음.

---

## Summary
- bugs:  2 findings (Critical: 1, Major: 1, Minor: 0, Nit: 0)
- style: 1 findings (Critical: 0, Major: 0, Minor: 1, Nit: 0) | Standards source: STRONG
- spec:  2 findings (Missing: 0, Partial: 1, Scope-creep: 1, Flaw: 0) | Spec source: issue #234 [HIGH]
- perf:  0 findings
- Conflicts: 0
- Tests: added
- Intent mismatches: 0
  CRITICAL 목록 (축 무관 전건):
  - bugs src/auth/middleware.ts:42 — 토큰 만료 비교 `<` 사용

## Recommendation
FIX-CRITICAL-FIRST: 토큰 만료 비교 버그, 보안 영향. 머지 전 수정 필수. 전체 CRITICAL/MAJOR는 Summary 참조.
참고: 채택 규칙(1)이 MAJOR 2건보다 우선순위가 높아 라벨을 차지함 — Summary 참조.

---
저장됨: .review/branch-review-abc1234.md
```
