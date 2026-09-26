---
name: forge-scope
description: 승인된 Intent 문서(requirement-spec 산출물)를 오케스트레이터 세션(opus-orchestrator / fable-orchestrator, 에이전트 모드)이 워크트리에서 개발한다. worktree_setup.py init 이 승인 게이트·시작 조건 검사·워크트리 생성·상태 전이(approved→in-dev)를 수행하고, 팀장(세션)은 개발 플랜을 세워 웨이브마다 coder RED → coder GREEN → reviewer → 커밋을 돌린 뒤 A-n 완료 조건을 증거로 마감한다. Work Packet·TASK 입력은 v3.58 에서 폐지. /claudecode-for-me:forge-scope <Intent 경로> 로 실행.
---

# Forge Scope — 오케스트레이터 개발 절차

입력은 **승인된 Intent 하나**다. `/forge-scope docs/<App>/INTENT/<ID>.md`

이 스킬은 **오케스트레이터 세션**(opus-orchestrator · fable-orchestrator 를 에이전트 모드로 실행)을 전제로 쓴다. 세션은 팀장이다 — 직접 코드를 쓰거나 빌드·테스트를 돌리지 않는다. 코드는 coder, 판정은 reviewer, 기록은 팀장 ledger. 이 문서의 절차와 오케스트레이터 프로토콜(HARD LIMITS·routing rules)이 겹치면 **프로토콜이 이긴다** — 이 문서는 그 위에 얹는 "개발 일감 순서"다.

**역할 분리**

| 누가 | 무엇을 |
|---|---|
| `scripts/worktree_setup.py` | 승인 게이트 · 시작 조건 · 워크트리/브랜치 · 서브모듈 링크 · 가드레일 복사 · `approved→in-dev` 전이 커밋 · cancel 정리 |
| 팀장(세션) | ledger · 개발 플랜 결정 · 스펙 작성 · 판정 · 커밋 · 보고 (Intent 는 직접 고치지 않는다) |
| scribe | F5 의 Intent 상태 행 `in-dev→in-review` 1줄 |
| coder (ext 기본, native 폴백) | RED 테스트 · GREEN 구현 · VERIFY 실행 |
| reviewer / reviewer-lite | 웨이브 diff 판정 · 마감 브랜치 판정 |
| explorer / analyst | 골격 파악 · 위험 도메인 감사 · 대안 비교 |

**불변 규칙**

- Intent 는 개발 단계에서 **고치지 않는다**(상태 행 제외). 부족하면 멈추고 requirement-spec 으로 되돌린다(F2).
- 모든 작업은 **워크트리 안**. 메인 repo 에서 코딩·커밋하지 않는다. 여러 세션이 각자 워크트리로 병렬 개발할 수 있다.
- 빌드·테스트는 **프로젝트(`.csproj`) 단위**만. `*.sln` 단위 `dotnet build`/`dotnet test` 금지.
- 완료 = 증거. A-n 하나라도 증거가 없으면 done 이 아니다.

---

## F0 — 입력과 ledger

1. `$ARGUMENTS` 첫 인자 = Intent 경로. `--name <slug>` · `--force` 는 F1 에 그대로 넘긴다.
2. Python 3.10+ 확인: `python --version`(없으면 `py -3 --version`). 없으면 중단 + 설치 안내.
3. 태스크 ledger 생성 `.orchestration/ledgers/<yyyymmdd>-<ID>.md`:
   - `status: active`, goal = Intent 제목.
   - 수용 기준 = Intent `A-1..A-n` **원문 그대로** + "대상 test.csproj 전체 green". 개발 중 기준을 바꾸지 않는다.

## F1 — 문지기 · 작업 공간

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py" init --doc <Intent> --quiet [--name <slug>] [--force]
```

- **exit 1** → 작업 공간 상태 문제. stderr 를 그대로 사용자에게 전하고 **중단**, 사용자 결정을 받는다:
  - `메인 repo 작업트리가 dirty` → 사용자가 커밋·stash. `--force` 는 dirty 파일이 이 Intent 와 무관하다고 **사용자가 명시**했을 때만 붙인다(워크트리는 마지막 커밋 사본이라 dirty 변경은 어차피 따라가지 않는다).
  - 브랜치가 다른 워크트리에 붙어 있음 → 그 워크트리를 `/forge-cancel <그 slug>` 로 정리(브랜치는 Handoff 로 정해지므로 `--name` 으로는 피할 수 없다. Intent 는 고치지 않는다).
  - stale 워크트리 → `git worktree prune` 후 재실행.
  - 등록 안 된 `.worktree/<slug>` 디렉터리 → 사용자가 확인 후 수동 삭제하거나 `git worktree prune` 후 재실행.
- **exit 2** → stderr 사유를 그대로 사용자에게 전하고 **중단**. 게이트를 통과시키려고 Intent 를 고치지 않는다. 흔한 사유:
  - `Intent 상태가 'draft'` → requirement-spec Phase 5 에서 승인.
  - `INT_*` FAIL → requirement-spec 으로 돌아가 수정·재검증.
  - `커밋이 하나도 없다` / `마지막 커밋에 없다` → 사용자가 Intent 와 프로젝트 골격(소스·테스트·솔루션)을 커밋. 워크트리는 마지막 커밋의 사본이라 커밋 안 된 파일은 따라오지 않는다. `--force` 로도 우회되지 않는다.
  - `Work Packet·TASK 입력은 … 폐지` → requirement-spec 으로 Intent 작성.
- **exit 0** → stdout 마지막 줄 매니페스트 JSON 을 ledger 에 기록. 쓰는 키:
  - `worktree`(이후 모든 경로의 뿌리) · `branch` · `intent_worktree`(워크트리 안 Intent)
  - `status_committed` — `true` 면 신규 시작(F2 부터). `false` 면 **resume** — Intent 는 이미 `in-dev` 다. `created` 는 워크트리를 이번에 붙였는지일 뿐(브랜치만 남아 있던 경우 `true`)이라 판단에 쓰지 않는다. 태스크 ledger 가 있으면 웨이브 표에서 이어가고, 없으면 F2 부터 다시 세운다(`git -C <worktree> log --oneline` 으로 기존 웨이브 커밋 확인).
  - init 의 `chore(<ID>): 상태 in-dev` 커밋은 스크립트의 결정적 전이라 reviewer 없이 허용되는 **유일한** 커밋이다. 그 밖의 모든 커밋은 reviewer APPROVE 뒤.
  - `acceptance`(A-n 목록) · `handoff`(5행: repo·app / base branch / 브랜치명 / 손대지 말 영역 / 완료 보고 방식)
- 브랜치는 Handoff `브랜치명`(유효한 ref 일 때), 아니면 `intent/<문서 ID>`.

## F2 — 개발 플랜

1. **explorer** 1회: 시작점 = Handoff `repo · app` + 워크트리의 솔루션·프로젝트 골격. 질문 = 기존 구조·테스트 프로젝트·빌드 명령·Intent FR/E/X 가 닿을 파일.
2. **analyst** — 아래 중 하나면 디스패치:
   - 위험 도메인(결제·과금, 인증·인가, 자격증명·비밀, 개인·민감 정보, 스키마·마이그레이션, 암호) → **의무**(audit).
   - 설계 대안 ≥2 → tradeoff.
3. 팀장이 결정하고 ledger 에 쓴다:
   - ① **설계 결정** — 파일·인터페이스·스키마·라이브러리, 기각한 대안과 이유.
   - ② **웨이브 표** — `W | 담당 FR/E/X | 담당 A | TARGET FILES(≤3) | 선행 | RED 필터 | test.csproj`. 공유 계약(타입·인터페이스)은 첫 웨이브.
4. **Intent 부족**(FR 모순, 결정 없이는 스펙을 못 씀, A 가 판정 불가) → **멈춘다.** 사용자에게 부족한 항목을 Intent ID 로 보고하고 requirement-spec 재실행을 안내. 개발 중 임의 결정으로 메우지 않는다.

## F3 — 웨이브 루프

웨이브 하나 = coder 2회 + reviewer 1회 + 커밋 1개.

1. **RED** — coder: 담당 FR/A 를 검증하는 테스트 + 컴파일에 필요한 최소 계약(시그니처·빈 구현)만.
   - VERIFY `dotnet test <test.csproj> --filter <이번 테스트>` — 통과 조건: **exit ≠ 0, 출력에 `Failed` 1개 이상, `error CS` 0개**(컴파일 실패는 RED 가 아니다).
2. **GREEN** — coder: 테스트를 통과시키는 최소 구현. 테스트 파일은 고치지 않는다.
   - VERIFY `dotnet test <test.csproj>` — 통과 조건: exit 0.
3. **스팟체크** — 팀장: `git -C <worktree> diff --stat` 이 TARGET FILES 와 일치, VERIFY 원출력 1줄 grep. init 이 워크트리 `.gitignore` 에 `.worktree/`·`.process/` 를 추가하고 커밋하지 않으므로, **첫 웨이브** diff 에 `.gitignore` 가 보이는 것은 정상 — 그 웨이브 커밋에 함께 넣는다.
4. **review** — 위험 도메인·스펙 밖 설계 판단 = reviewer(opus), 스펙대로 기계적 = reviewer-lite. 스펙에 ledger 경로·담당 FR/A 를 적고 "담당 기준 중 diff 에 대응이 없는 것은?"(UNCOVERED) 을 묻는다.
5. **APPROVE** → 워크트리에서 커밋 `feat(<ID>): W<k> <요약> (FR-…, A-…)`. ledger 에 합성 3줄.
6. REVISE/REJECT 2회 → 사용자 에스컬레이션.

coder 스펙 규칙:
- TARGET FILES = **워크트리 절대경로**. `손대지 말 영역` 은 CONSTRAINTS 에 옮긴다.
- ext 디스패치는 `ext_dispatch.py run --role coder --repo <worktree> --spec … --report …`.
- 같은 워크트리의 coder 는 순차.

## F4 — 통합

1. coder 최종 VERIFY: `dotnet test <test.csproj>`(전체) exit 0.
2. **A-n 워크** — ledger 의 각 A 에 증거 포인터: 웨이브 VERIFY · 테스트명 · reviewer APPROVE. 증거 없는 A 는 미충족.
3. 환경 의존 A(예: Docker·외부 서비스 필요)를 이 환경에서 확인할 수 없으면 **"미충족 + 사유"**. 통과로 세지 않는다.

## F5 — 마감

1. **scribe** 1회(상태 in-dev → in-review): 워크트리 Intent 메타 `| 상태 | in-dev |` → `| 상태 | in-review |` 1줄만(그 밖 무변경). 팀장은 Intent 를 직접 고치지 않는다.
2. reviewer(opus) — 브랜치 전체 diff(`<base branch>...HEAD`) vs Intent: A 커버리지, `손대지 말 영역` 무변경, FR/X 위반 여부.
3. APPROVE → 커밋 `chore(<ID>): 상태 in-review`.
4. Handoff `완료 보고 방식` 대로 보고: A-n 표(충족/미충족 + 증거) · Deviations(Intent 와 다르게 한 것) · 브랜치명.
5. ledger `status: done` + retro 3줄.

머지·푸시는 사용자 지시가 있을 때만. 작업 공간 정리는 `/forge-cancel <slug>`.

---

## 실패 처리

| 상황 | 행동 |
|---|---|
| init exit 1 | 사유 그대로 보고, 중단 — 사용자 결정(커밋·stash·`--force` 허락·`/forge-cancel`) |
| init exit 2 | 사유 그대로 보고, 중단 |
| Intent 부족 발견 | 중단, requirement-spec 으로 되돌림 |
| coder BLOCKED | 스펙 결함 — 빠진 결정을 채워 재디스패치 |
| RED 가 컴파일 실패 | RED 미달 — 계약 보강 재디스패치 |
| reviewer 2회 REVISE | 사용자 에스컬레이션 |
| 환경 의존 A 확인 불가 | 미충족 + 사유, done 불가 |
