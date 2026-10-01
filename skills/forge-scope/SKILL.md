---
name: forge-scope
description: /forge-init 이 만들어 둔 워크트리 안에서 오케스트레이터 세션(opus-orchestrator / fable-orchestrator, 에이전트 모드)이 승인된 Intent 를 개발한다. 입력은 forge-init 매니페스트(.process/forge/handoff.json)이고, 팀장(세션)은 개발 플랜을 세워 슬라이스마다 coder RED → coder GREEN → reviewer → 커밋을 돌린 뒤 A-n 완료 조건을 증거로 마감한다. 워크트리를 직접 만들지 않는다 — 환경 구성은 /forge-init. Work Packet·TASK 입력은 v3.58 에서 폐지.
---

# Forge Scope — 오케스트레이터 개발 절차

입력은 **`/forge-init` 매니페스트 하나**다. `/forge-scope .process/forge/handoff.json`

이 스킬은 **오케스트레이터 세션**(opus-orchestrator · fable-orchestrator 를 에이전트 모드로 실행)을 전제로 쓴다. 세션은 팀장이다 — 직접 코드를 쓰거나 빌드·테스트를 돌리지 않는다. 코드는 coder, 판정은 reviewer, 기록은 팀장 ledger. 이 문서의 절차와 오케스트레이터 프로토콜(HARD LIMITS·routing rules)이 겹치면 **프로토콜이 이긴다** — 이 문서는 그 위에 얹는 "개발 일감 순서"다.

**역할 분리**

| 누가 | 무엇을 |
|---|---|
| `/forge-init` (이 스킬 **이전**, 스펙 세션) | 승인 커밋 게이트 · base 선택 · 워크트리/브랜치 · 서브모듈 링크 · 가드레일 복사 · `approved→in-dev` 전이 커밋 · 매니페스트 기록 |
| 팀장(세션) | ledger · 개발 플랜 결정 · 스펙 작성 · 판정 · 커밋 · 보고 (Intent 는 직접 고치지 않는다) |
| scribe | F5 의 Intent 상태 행 `in-dev→in-review` 1줄 |
| coder | RED 테스트 · GREEN 구현 · VERIFY 실행 |
| reviewer / reviewer-lite | 슬라이스 diff 판정 · 마감 브랜치 판정 |
| explorer / analyst | 골격 파악 · 위험 도메인 감사 · 대안 비교 |

**불변 규칙**

- Intent 는 개발 단계에서 **고치지 않는다**(상태 행 제외). 부족하면 멈추고 requirement-spec 으로 되돌린다(F0·F2).
- 모든 작업은 **워크트리 안**. 이 세션의 cwd 가 곧 워크트리다 — 메인 repo 로 나가서 코딩·커밋하지 않는다. 여러 세션이 각자 워크트리로 병렬 개발할 수 있다.
- **워크트리를 만들지 않는다.** `worktree_setup.py init` 을 호출하지 않는다 — 워크트리 안에서 부르면 워크트리 속에 워크트리가 생긴다. 없으면 `/forge-init` 으로 되돌린다.
- 빌드·테스트는 **프로젝트(`.csproj`) 단위**만. `*.sln` 단위 `dotnet build`/`dotnet test` 금지.
- 완료 = 증거. A-n 하나라도 증거가 없으면 done 이 아니다.

---

## F0 — 입력 · 진입 가드 · ledger

**입력은 `/forge-init` 이 만든 매니페스트다.** `/forge-scope .process/forge/handoff.json`

이 스킬은 **워크트리를 만들지 않는다.** 세션의 cwd 는 프로세스 시작 시점에 고정되므로, 워크트리 안에서 개발하려면 그 전에 워크트리가 있어야 한다. 그 일은 `/forge-init` 이 스펙 세션에서 미리 해둔다.

1. **진입 가드** — 워크트리 안인지 확인한다:
   ```bash
   git rev-parse --git-common-dir
   ```
   `.git` 이면 메인 repo 다 → **중단**하고 `/forge-init <Intent 경로>` 를 안내한다. 절대경로(다른 위치의 `.git`)면 linked worktree 안이다 → 계속.
2. **매니페스트 로드** — `$ARGUMENTS` 가 가리키는 JSON, 없으면 `<cwd>/.process/forge/handoff.json`. 둘 다 없으면 **중단**하고 `/forge-init` 을 안내한다. 매니페스트 없이 Intent 경로만으로 시작하지 않는다 — 브랜치·`base_commit` 을 추측하게 된다.
   쓰는 키:
   - `worktree`(이후 모든 경로의 뿌리) · `branch` · `intent_worktree`(워크트리 안 Intent)
   - `base` · `base_commit`(마감 diff 기준 sha) · `base_applied` — `base_applied: false` 면 브랜치가 이미 있어 분기점이 적용되지 않은 것이므로 **한 줄 보고**하고 진행한다.
   - `status_committed` — `true` 면 신규 시작, `false` 면 **resume**(Intent 가 이미 `in-dev`). ledger 가 있으면 슬라이스 표에서 이어가고, 없으면 F2 부터 다시 세운다(`git log --oneline` 으로 기존 슬라이스 커밋 확인).
   - `acceptance`(A-n 목록) · `handoff`(5행: repo·app / base branch / 브랜치명 / 손대지 말 영역 / 완료 보고 방식)
   - `submodule_log` — 비어 있지 않으면 사용자에게 보고한다.
3. Python 3.10+ 확인: `python --version`(없으면 `py -3 --version`). 없으면 중단 + 설치 안내.
4. 태스크 ledger 생성 `<worktree>/.orchestration/ledgers/<yyyymmdd>-<ID>.md`:
   - `status: active`, goal = Intent 제목.
   - 수용 기준 = 매니페스트 `acceptance` 의 `A-1..A-n` **원문 그대로** + "대상 test.csproj 전체 green". 개발 중 기준을 바꾸지 않는다.
   - ledger 는 워크트리 안에 둔다 — `.orchestration/` 은 gitignore 라 체크아웃되지 않으므로 이 세션이 만든다. `/forge-cancel` 과 함께 사라지므로, 남겨야 할 결론은 F5 에서 별도 파일로 뽑는다.

`/forge-init` 의 `chore(<ID>): 상태 in-dev` 커밋은 스크립트의 결정적 전이다. 이 세션이 만드는 **모든** 커밋은 reviewer APPROVE 뒤에 온다.

Intent 가 부족하면(FR 모순, 결정 없이는 스펙을 못 씀, A 가 판정 불가) **멈춘다.** 부족한 항목을 Intent ID 로 보고하고 requirement-spec 재실행을 안내한다.

## F2 — 개발 플랜

1. **explorer** 1회: 시작점 = Handoff `repo · app` + 워크트리의 솔루션·프로젝트 골격. 질문 = 기존 구조·테스트 프로젝트·빌드 명령·Intent FR/E/X 가 닿을 파일.
2. **analyst** — 아래 중 하나면 디스패치:
   - 위험 도메인(결제·과금, 인증·인가, 자격증명·비밀, 개인·민감 정보, 스키마·마이그레이션, 암호) → **의무**(audit).
   - 설계 대안 ≥2 → tradeoff.
3. 팀장이 결정하고 ledger 에 쓴다:
   - ① **설계 결정** — 파일·인터페이스·스키마·라이브러리, 기각한 대안과 이유.
   - ② **슬라이스 표** — `S | 담당 FR/E/X | 담당 A | TARGET FILES(≤3) | 선행 | RED 필터 | test.csproj`. 공유 계약(타입·인터페이스)은 첫 슬라이스.
4. **Intent 부족**(FR 모순, 결정 없이는 스펙을 못 씀, A 가 판정 불가) → **멈춘다.** 사용자에게 부족한 항목을 Intent ID 로 보고하고 requirement-spec 재실행을 안내. 개발 중 임의 결정으로 메우지 않는다.

## F3 — 슬라이스 루프

슬라이스 하나 = coder 2회 + reviewer 1회 + 커밋 1개.

1. **RED** — coder: 담당 FR/A 를 검증하는 테스트 + 컴파일에 필요한 최소 계약(시그니처·빈 구현)만.
   - VERIFY `dotnet test <test.csproj> --filter <이번 테스트>` — 통과 조건: **exit ≠ 0, 출력에 `Failed` 1개 이상, `error CS` 0개**(컴파일 실패는 RED 가 아니다).
2. **GREEN** — coder: 테스트를 통과시키는 최소 구현. 테스트 파일은 고치지 않는다.
   - VERIFY `dotnet test <test.csproj>` — 통과 조건: exit 0.
3. **스팟체크** — 팀장: `git -C <worktree> diff --stat` 이 TARGET FILES 와 일치, VERIFY 원출력 1줄 grep. `/forge-init` 이 워크트리 `.gitignore` 에 `.worktree/`·`.process/` 를 추가하고 커밋하지 않으므로, **첫 슬라이스** diff 에 `.gitignore` 가 보이는 것은 정상 — 그 슬라이스 커밋에 함께 넣는다.
4. **review** — 위험 도메인·스펙 밖 설계 판단 = reviewer(opus), 스펙대로 기계적 = reviewer-lite. 스펙에 ledger 경로·담당 FR/A 를 적고 "담당 기준 중 diff 에 대응이 없는 것은?"(UNCOVERED) 을 묻는다.
5. **APPROVE** → 워크트리에서 커밋 `feat(<ID>): S<k> <요약> (FR-…, A-…)`. ledger 에 합성 3줄.
6. REVISE/REJECT 2회 → 사용자 에스컬레이션.

coder 스펙 규칙:
- TARGET FILES = **워크트리 절대경로**. `손대지 말 영역` 은 CONSTRAINTS 에 옮긴다.
- 같은 워크트리의 coder 는 순차.

## F4 — 통합

1. coder 최종 VERIFY: `dotnet test <test.csproj>`(전체) exit 0.
2. **A-n 워크** — ledger 의 각 A 에 증거 포인터: 슬라이스 VERIFY · 테스트명 · reviewer APPROVE. 증거 없는 A 는 미충족.
3. 환경 의존 A(예: Docker·외부 서비스 필요)를 이 환경에서 확인할 수 없으면 **"미충족 + 사유"**. 통과로 세지 않는다.

## F5 — 마감

1. **scribe** 1회(상태 in-dev → in-review): 워크트리 Intent 메타 `| 상태 | in-dev |` → `| 상태 | in-review |` 1줄만(그 밖 무변경). 팀장은 Intent 를 직접 고치지 않는다.
2. reviewer(opus) — 브랜치 전체 diff(`git -C <worktree> diff <base_commit>...HEAD`, 매니페스트의 `base_commit`. 없으면 `base`, 그것도 없으면 Handoff `base branch`) vs Intent: A 커버리지, `손대지 말 영역` 무변경, FR/X 위반 여부. sha 를 우선 쓰는 이유 — base 브랜치가 개발 중 앞으로 나가도 비교 범위가 흔들리지 않는다.
3. **카탈로그 재생성**: `python "${CLAUDE_PLUGIN_ROOT}/scripts/docs_helpers.py" intent-catalog --repo <worktree> --app <App> --write`. 카탈로그는 INTENT/ 에서 파생하는 인덱스라 상태 전이 직후 다시 써야 한다 — 손으로 고치지 않는다.
4. APPROVE → 커밋 `chore(<ID>): 상태 in-review` (Intent + `<App>-INT-CATALOG.md` 2 파일).
5. **완료 기록 파일** — 마감 보고를 `<worktree>/.review/forge-<ID>.md` 로 남긴다: A-n 표(충족/미충족 + 증거) · Deviations(Intent 와 다르게 한 것) · 브랜치명 · `base_commit`. ledger 와 `.review/` 는 gitignore 라 `/forge-cancel` 과 함께 사라지므로, **워크트리를 지우기 전에 메인 repo 로 복사**하라고 안내한다.
6. Handoff `완료 보고 방식` 대로 사용자에게 보고한다(5 의 내용 + 파일 경로).
7. ledger `status: done` + retro 3줄.

**다음 단계 안내만 한다 — 실행하지 않는다.** 이 워크트리에서 `/branch-review <base_commit>` (매니페스트의 `base_commit`). branch-review 는 cwd 의 HEAD 를 기준으로 slug 를 잡으므로 이 워크트리 안에서 돌려야 맞다. 기준점을 생략하면 `origin/main` 과의 merge-base 를 추정하므로, base 가 main 이 아니면 어긋난다.

머지·푸시는 사용자 지시가 있을 때만. 작업 공간 정리는 `/forge-cancel <slug>` — **메인 repo 에서** 실행한다.

---

## 실패 처리

| 상황 | 행동 |
|---|---|
| cwd 가 메인 repo (`--git-common-dir` 이 `.git`) | 중단, `/forge-init <Intent 경로>` 안내 — 워크트리를 여기서 만들지 않는다 |
| 매니페스트 없음 | 중단, `/forge-init` 안내 — Intent 경로만으로 시작하지 않는다 |
| Intent 부족 발견 | 중단, requirement-spec 으로 되돌림 |
| coder BLOCKED | 스펙 결함 — 빠진 결정을 채워 재디스패치 |
| RED 가 컴파일 실패 | RED 미달 — 계약 보강 재디스패치 |
| reviewer 2회 REVISE | 사용자 에스컬레이션 |
| 환경 의존 A 확인 불가 | 미충족 + 사유, done 불가 |
