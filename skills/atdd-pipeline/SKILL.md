---
name: atdd-pipeline
description: ATDD 전체 파이프라인 오케스트레이터. FRD 생성(Phase 1) → 설계+테스트 코드(Phase 2) → 구현(Phase 3)을 순차 체이닝한다. 각 Phase의 산출물 존재 여부로 재개 지점을 판별하므로, 중간에 중단되어도 완료된 Phase는 스킵하고 이어서 진행한다. /atdd-pipeline으로 실행.
argument-hint: "[기능 요구사항서 경로 또는 내용]"
input: 기능 요구사항서 (텍스트 또는 파일 경로)
output: .atdd/frd_{기능명}.md, 테스트 코드, 프로덕션 코드, .atdd/impl_{기능명}.md
requires-user-interaction: true
---

# ATDD Pipeline — 오케스트레이터

ATDD 개발 파이프라인의 전체 흐름을 관리한다. 직접 설계나 구현을 수행하지 않고, 각 Phase 스킬에 위임한다.

## 핵심 원칙

- **파일 기반 계약**: Phase 간 데이터 전달은 `.atdd/` 폴더의 파일과 소스 코드로만 이루어진다. 컨텍스트 변수나 메모리에 의존하지 않는다.
- **재개 가능**: 산출물 존재 여부로 완료를 판별한다. 이미 완료된 Phase는 스킵한다.
- **Phase 1은 메인 에이전트**: 유저와 대화가 필요하므로 서브 에이전트에 위임하지 않는다.
- **Phase 2~3은 서브 에이전트**: 유저 대화 없이 자율적으로 수행한다. Phase 2(설계+테스트 코드)와 Phase 3(구현)은 별도 서브 에이전트로 분리하여 ATDD의 Red→Green 순서를 구조적으로 강제한다.

## 산출물 컨벤션

| Phase | 파일명 패턴 | 설명 |
|-------|------------|------|
| Phase 1 (Q&A 임시) | `frd_{기능명}_temp.md` | 진행 중 실시간 Q&A 기록 |
| Phase 1 (FRD) | `frd_{기능명}.md` | 완성된 기능 요구사항서 |
| Phase 2 | 테스트 코드 파일 | 테스트 프로젝트에 생성 |
| Phase 3 (보고서) | `impl_{기능명}.md` | 구현 완료 보고서 |

`{기능명}`은 Phase 1에서 결정되며, 모든 Phase에서 동일하게 사용한다.

---

## Phase 0: 초기화

1. `$ARGUMENTS`를 파싱한다:
   - 파일 경로가 주어졌으면 → FRD 또는 요구사항서 파일 경로로 사용
   - 텍스트가 주어졌으면 → 기능 요구사항서 내용으로 사용
   - 인자가 없으면 → Phase 1에서 유저에게 요청

2. `.atdd/` 폴더를 확인하여 이미 완료된 Phase를 판별한다:

   ```
   frd_{기능명}.md 존재?        → Phase 1 완료
   테스트 코드 파일 존재?       → Phase 2 완료
   impl_{기능명}.md 존재?       → Phase 3 완료
   ```

3. **기존 산출물이 하나라도 존재하면**, `AskUserQuestion`으로 유저에게 묻는다:

   ```
   AskUserQuestion:
   - question: "기존 산출물이 발견되었습니다. 어떻게 진행할까요?"
   - options:
     - "이어서 진행 (완료된 Phase 스킵)" (Recommended)
     - "처음부터 시작 (기존 산출물 전부 삭제)"
   ```

   - **이어서 진행** → 기존 산출물을 유지하고, 미완료 Phase부터 재개한다.
   - **처음부터 시작** → `.atdd/` 폴더 내 해당 기능명의 산출물(`frd_`, `impl_`, `frd_*_temp`)을 모두 삭제한 뒤 Phase 1부터 시작한다.

4. 이미 FRD 파일이 존재하고 이어서 진행하는 경우, 기능명을 파일명에서 추출한다.
5. 현재 상태를 유저에게 보고한다:

   ```
   [ATDD Pipeline] 상태 확인
   - Phase 1 (FRD): {완료 ✓ / 미완료}
   - Phase 2 (설계+테스트 코드): {완료 ✓ / 미완료}
   - Phase 3 (구현): {완료 ✓ / 미완료}
   → Phase {N}부터 시작합니다.
   ```

---

## Phase 1: FRD 생성 (메인 에이전트)

### 완료 조건
`.atdd/frd_{기능명}.md` 존재

### 이미 완료된 경우
스킵하고 Phase 2로 진행한다.

### 미완료인 경우

`agents/engineering/engineering-tech-lead.md` 파일을 읽고 Tech Lead 페르소나를 내재화한 뒤, `skills/atdd-flow/SKILL.md`의 지침을 **메인 에이전트에서 직접** 수행한다.

Phase 1은 유저와의 소크라틱 대화가 핵심이므로 서브 에이전트에 위임하지 않는다. Tech Lead가 직접 요구사항을 정제한다. atdd-flow 스킬의 Phase 0~6을 그대로 따른다.

FRD가 생성되면 (`[ATDD-FLOW COMPLETE]` 신호 확인) Phase 2로 진행한다. Phase 1이 완료되기 전까지 **절대로** Phase 2로 넘어가지 않는다.

---

## Phase 2: 설계 + 테스트 코드 작성 (서브 에이전트)

### 선행 조건
`.atdd/frd_{기능명}.md` 존재

### 완료 조건
테스트 프로젝트에 실행 가능한 테스트 코드 파일이 생성됨

### 이미 완료된 경우
테스트 코드가 이미 존재하면 스킵하고 Phase 3으로 진행한다.

### 미완료인 경우

**Agent 도구**를 사용하여 서브 에이전트를 호출한다. 서브 에이전트에게 아래 지시를 전달한다:

```
다음 두 파일을 순서대로 읽고, 해당 페르소나와 스킬 지침에 따라 수행하라:

1. agents/engineering/engineering-backend-architect.md — Backend Architect 페르소나를 내재화하라.
2. skills/atdd-design/SKILL.md — 이 스킬의 지침을 수행하라.

인자: .atdd/frd_{기능명}.md
```

이 서브 에이전트는 **내부적으로 설계를 수행한 뒤 바로 테스트 코드를 작성한다.** 중간 산출물(설계서, 테스트 명세) 파일을 생성하지 않는다. 프로덕션 코드도 작성하지 않는다 — ATDD의 Red 단계다.

서브 에이전트의 완료를 기다린다. `[ATDD-DESIGN COMPLETE]` 신호를 확인한다.

---

## Phase 3: 구현 코드 작성 (서브 에이전트)

### 선행 조건
Phase 2에서 테스트 코드가 생성되어 있어야 한다.

### 완료 조건
`.atdd/impl_{기능명}.md` 존재

### 이미 완료된 경우
스킵하고 Phase 4로 진행한다.

### 미완료인 경우

**Agent 도구**를 사용하여 서브 에이전트를 호출한다. 서브 에이전트에게 아래 지시를 전달한다:

```
다음 두 파일을 순서대로 읽고, 해당 페르소나와 스킬 지침에 따라 수행하라:

1. agents/engineering/engineering-backend-architect.md — Backend Architect 페르소나를 내재화하라.
2. skills/atdd-implement/SKILL.md — 이 스킬의 지침을 수행하라.

인자: {기능명}
```

이 서브 에이전트는 **Phase 2에서 작성된 테스트를 통과시키는 프로덕션 코드를 작성한다.** 테스트 코드는 이미 존재하므로 수정하지 않는다. FRD와 테스트 코드만 참조한다.

서브 에이전트의 완료를 기다린다. `[ATDD-IMPLEMENT COMPLETE]` 신호를 확인한다.

---

## Phase 4: 완료

모든 Phase가 완료되면 산출물을 보고한다:

```
[ATDD Pipeline 완료]

산출물:
1. FRD:        .atdd/frd_{기능명}.md
2. 테스트 코드: {Phase 2에서 생성된 테스트 파일 목록}
3. 구현 코드:  {Phase 3에서 생성된 파일 목록 — impl 보고서에서 추출}
4. 구현 보고서: .atdd/impl_{기능명}.md
```

---

## 에이전트 페르소나 배정

| Phase | 에이전트 | 스킬 | 실행 위치 | 근거 |
|-------|---------|------|----------|------|
| Phase 1 (FRD) | Tech Lead | atdd-flow | 메인 에이전트 | 유저와 직접 대화하며 요구사항 정제 |
| Phase 2 (설계+테스트 코드) | Backend Architect | atdd-design | 서브 에이전트 | 코드 탐색 → 내부 설계 → 테스트 코드 작성을 한 번에 수행 |
| Phase 3 (구현) | Backend Architect | atdd-implement | 서브 에이전트 | FRD + 테스트 코드를 참조하여 프로덕션 코드 구현 |

---

## 에러 처리

- 서브 에이전트가 실패하면 에러 내용을 유저에게 보고하고, 해당 Phase를 재시도할지 묻는다.
- 선행 조건 파일이 없으면 이전 Phase부터 실행해야 함을 안내한다.
- `.atdd/` 폴더가 없으면 자동 생성한다.

---

## Tone & Style

- 한국어를 기본 언어로 사용한다.
- 오케스트레이터는 간결하게 상태를 보고한다 — 각 Phase의 세부 내용은 해당 스킬이 처리한다.
- Phase 전환 시 현재 진행 상황을 한 줄로 안내한다.
