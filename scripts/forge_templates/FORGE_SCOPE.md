# FORGE_SCOPE — `scripts/forge_scope.py` 레퍼런스

> 본 문서는 `scripts/forge_scope.py`의 동작과 모든 CLI 플래그를 정리한 운영 레퍼런스이다. 자동화 도구 본체는 `scripts/forge_scope.py`이며, 사용자 대면 스킬 명세는 `.claude/commands/forge-scope.md`에 있다.

---

## 1. 개요

`forge_scope.py`는 **scoped phase runner**다. 사용자가 제시한 짧은 prompt 또는 단일 문서를 입력으로 받아 작은 단위 기능을 빠르게 처리한다. `forge_full.py`(전 docs 자동 인입)의 경량 변종으로, `index.json`의 `docs_scope` 화이트리스트에 명시된 문서만 가드레일로 결합한다.

작업은 **phase**(=하나의 작업 단위) 단위로 진행된다. 한 phase는 N개의 **step**으로 쪼개지며, 각 step은 Claude를 1회 호출해 코드 작성·테스트·커밋까지 자율 수행한다. 첫 실행 시에는 step 분해(plan)부터 결정하고, 두 번째 실행부터는 기존 plan을 이어서 돈다.

### 1.1 처리 흐름

1. **plan 생성** (최초 1회)
   - `auto` preset → Claude **splitter**가 `--prompt`/`--doc`을 받아 strict-JSON plan을 생성하고 사용자 승인을 받음.
   - `frd-implementation`/`contract-tdd` preset 또는 `--single-step` → splitter 호출 없이 **deterministic plan**을 로컬에서 생성(토큰 0).
2. **plan 검증** — 5개 H2 헤딩 강제(`## 읽어야 할 파일`, `## 작업`, `## Acceptance Criteria`, `## 검증 절차`, `## 금지사항`), kebab-case name, step 인덱스 0..N-1 연속 등.
3. **파일 emit** — `phases/scoped/<phase-dir>/index.json` + `step{N}.md` 일괄 기록.
4. **워크트리 준비** — `.worktrees/<phase-dir>/`에 git worktree를 생성하고 `feat-<phase-dir>` 브랜치에 attach. 메인 repo 작업 트리는 영향 없음. 이미 등록된 워크트리는 그대로 재사용. 정리는 사용자가 `forge_cancel.py` 또는 `git worktree remove`로 명시적 수행.
5. **step 순회 실행** — 각 step에 대해 Claude를 호출, 최대 3회 재시도, status 전이(pending → completed | error | blocked), 2단계 커밋(`feat(<phase>): step N — <name>` + `chore(<phase>): step N output`).
6. **finalize** — 전체 step 완료 시 `chore(<phase>): mark phase completed` 커밋, 옵션 시 `git push -u origin feat-<phase>`.

### 1.2 가드레일 주입 모델

매 step 호출 시 prompt 컨텍스트:
- `CLAUDE.md` (항상)
- `docs_scope`에 명시된 문서만 (whitelist)
- `--compact-docs` 사용 시 FRD류 문서는 핵심 H2 섹션(§1·§4·§5·§7·§8·§9·§12·§14·§17)만 추출
- 이전 step의 `summary` (있으면) — 직렬 컨텍스트 누적
- 첫 호출에서만 작업 규칙·재시도 규약 전체 주입(이후는 동일 세션 `-r`로 cache_read 적중)

### 1.3 토큰 절감 메커니즘

| 메커니즘 | 트리거 | 효과 |
|---|---|---|
| splitter 우회 | `--preset=frd-implementation` / `--preset=contract-tdd` / `--single-step` | plan 생성용 Claude 호출 0건 |
| compact docs | `--compact-docs` (또는 위 preset 자동 활성화) | FRD 전문 대신 핵심 H2만 주입 |
| step 모델 다운그레이드 | `--step-model=claude-haiku-4-5-20251001` | step 실행 단가 절감 |
| 세션 공유 | 자동 (phase UUID) | step 0 첫 호출의 가드레일이 step 1+에서 cache_read 적중 |
| stdout 압축 | `--quiet` | 부모 Claude Code 세션에 진행 표시기/usage 표가 누적되지 않음 |
| `--bare` | 자동 (`ANTHROPIC_API_KEY`가 있을 때만) | 자식 claude에서 CLAUDE.md/hooks/plugins 자동 로딩 스킵 |

---

## 2. CLI 플래그 전체 목록

호출 형식:

```bash
python scripts/forge_scope.py <phase_dir> [options]
```

### 2.1 필수 인자

| 인자 | 타입 | 설명 |
|---|---|---|
| `phase_dir` | positional | Phase 디렉토리 이름. kebab-case 권장 (예: `login-feature`, `frd-f009-order-integrity`). 실제 경로는 `phases/scoped/<phase_dir>/`. |

### 2.2 입력 (plan 생성 재료)

| 플래그 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--prompt` | str (반복) | `None` | 자유 텍스트 요구사항. 반복 지정 가능. 첫 실행 시 `--doc`과 함께 사용. 기존 plan이 있으면 무시되고 경고. |
| `--doc` | str (반복) | `None` | 첨부 문서 경로. `docs/` 하위 `.md` 만 허용. 반복 지정 가능. leading slash(`/docs/...`)는 자동 정규화. 중복 자동 dedupe. `--preset=frd-implementation`/`contract-tdd`는 정확히 1개 강제. |

### 2.3 plan 생성 모드

| 플래그 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--preset` | choice | `auto` | 초기 step 생성 방식. 값: `auto` / `frd-implementation` / `contract-tdd`. 자세한 의미는 §3. |
| `--single-step` | bool | `false` | splitter 호출 없이 고정 단일 step plan 생성. `--preset=auto`와 함께 쓰면 deterministic single-step. `contract-tdd`와 함께 쓰면 의미 라벨로만 작용(실제 dispatch는 contract-tdd 우선, 4-step 생성). |
| `--compact-docs` | bool | `false` | `docs_scope` 문서를 핵심 H2 섹션만 압축해 가드레일에 주입. `--preset=frd-implementation`/`contract-tdd`/`--single-step` 사용 시 자동 활성화. |

### 2.4 비대화 / 자동화

| 플래그 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--yes` | bool | `false` | plan 사용자 확인(`[y/N]`) 자동 승인. CI/비대화 환경 또는 Claude Code spawn 시 필수. |
| `--trust` | bool | `false` | Claude 자식 프로세스에 `--dangerously-skip-permissions` 부착 옵트인. 환경변수 `FORGE_TRUST=1`(또는 `true`/`yes`)로도 옵트인 가능. **둘 중 하나가 없으면 즉시 EXIT_ERR.** |

### 2.5 비용/토큰 절감

| 플래그 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--quiet` | bool | `false` | 부모 세션 stdout 누적 차단. 진행 표시기·헤더·step별 usage·plan 표 출력을 억제하고 phase 완료 한 줄 + 에러만 출력. **Claude Code 부모 세션에서 spawn할 때 필수.** |
| `--step-model` | str | `claude-opus-4-8` | splitter·step·commit-msg 실행에 사용할 Claude 모델 이름. 더 싸게 돌리려면 `claude-sonnet-4-6`/`claude-haiku-4-5-20251001`. |
| `--step-effort` | str | `high` | Claude `--effort` 레벨 (`low`/`medium`/`high`/`xhigh`/`max`). 지능↔토큰 트레이드오프 다이얼. |
| `--compact-docs` | bool | (자동) | §2.3 참고. 토큰 절감 항목으로도 분류. |

### 2.6 git 부수 동작

| 플래그 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--push` | bool | `false` | phase 완료 후 `git push -u origin feat-<phase>` 자동 실행. |
| `--force` | bool | `false` | 워크트리 dirty tree(commit 안 된 변경) 검사 우회. 재실행 시 워크트리 내 수동 변경을 step commit이 흡수하도록 허용. 작업 손실 위험이 있으므로 신중히. |

### 2.7 운영/디버깅

| 플래그 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--strict` | bool | `false` | 가드레일 문서에 `{placeholder}` 패턴이 남아 있으면 실패. 문서 미완성 상태로 자동 진행을 막고 싶을 때. |
| `--verbose` | bool | `false` | DEBUG 레벨 로그를 stderr로 출력. 본 옵션은 `--quiet`과 직교(quiet은 stdout만 억제, verbose는 stderr만 늘림). |

---

## 3. preset 동작 상세

### 3.1 `--preset=auto` (기본값)

- Claude **splitter**가 `--prompt`/`--doc`을 strict-JSON plan으로 변환.
- step 수는 splitter가 자율 결정(상한 30).
- plan 콘솔 미리보기 후 `[y/N]` 승인 대기. `--yes`로 자동 승인 가능.
- 문서 변경 큰 작업, 여러 레이어/모듈을 횡단하는 작업에 적합.
- 토큰 비용: splitter 호출 1회 + step 실행 N회.

### 3.2 `--preset=frd-implementation`

- splitter 호출 **없이** deterministic single-step plan 생성.
- `--doc=docs/FRD/<FRD-ID>.md` **정확히 1개** 강제. 0개·2개 이상이면 EXIT_ERR.
- step 1개. body는 5개 H2를 갖춘 기본 구현 지시문(범위 밖 리팩터링 금지, FRD/prompt 밖 기능 추가 금지 등).
- `--compact-docs` 자동 활성화.
- 사용처: FRD 1개 구현 토큰 테스트, scope가 명확한 단일 기능 구현.

### 3.3 `--preset=contract-tdd`

- splitter 호출 **없이** deterministic 4-step plan 생성.
- `--doc=docs/FRD/<FRD-ID>.md` **정확히 1개** 강제. 0개·2개 이상이면 EXIT_ERR.
- step 구조:

| step | name | 역할 |
|---|---|---|
| 0 | `contract-skeleton` | interface/DTO/enum/route skeleton/`NotImplementedException` placeholder. 비즈니스 로직 금지. |
| 1 | `red-tests` | FRD 요구사항 검증 단위/통합 테스트 추가. **의도한 이유로 실패해야 함.** 컴파일 실패는 불허. |
| 2 | `green-implementation` | step1 테스트를 통과시키는 최소 제품 코드. 테스트 삭제/완화/skip/ignore 금지. |
| 3 | `refactor-and-regression` | 정리 + 전체 회귀(`dotnet test ... --no-restore` filter 없음) + `git diff --check`. |

- AC 의 솔루션 경로는 우선순위 순으로: `--sln=<path>` CLI → `FORGE_DEFAULT_SLN` 환경변수 → `forge-scope.json`의 `default_sln` 키 → `Src/*.sln` (1단계) / `Src/*/*.sln` (2단계) auto-detect. 다수 sln 발견 시 위 설정 채널 중 하나를 써야 함(후보 목록 출력). red/green step 의 test 명령에는 placeholder `<feature-specific-filter>`가 박혀 있으며, 구현 에이전트가 step 실행 시 채운다.
- `--compact-docs` 자동 활성화.
- `--single-step`과 함께 써도 충돌 없음(의미상 "본 개발 1 step + TDD wrap 3 step"으로 해석, 실제 dispatch는 contract-tdd 우선 → 4-step).
- 사용처: 계약 → 실패 테스트 → 구현 → 회귀 순서를 하네스 차원에서 강제하고 싶은 모든 FRD/API 작업.

---

## 4. 환경변수

| 변수 | 효과 |
|---|---|
| `FORGE_TRUST` | `1` / `true` / `yes` 중 하나 → `--trust`와 동일 효과. |
| `FORGE_DEFAULT_SLN` | `Src/` 하위에 sln이 여러 개일 때 기본값 지정 (repo root 기준 상대경로). 예: `Src/MyProject/My.sln`. `--sln` CLI보다 우선도 낮음. `forge-scope.json`의 `default_sln`보다 우선도 높음. |
| `ANTHROPIC_API_KEY` | 설정 시 자식 claude 호출에 `--bare` 부착 가능(CLAUDE.md/hooks/plugins 자동 로딩 스킵). |
| `CLAUDECODE` / `CLAUDE_CODE_ENTRYPOINT` / `CLAUDE_CODE_SSE_PORT` / `CLAUDE_PROJECT_DIR` / `AI_AGENT=claude-code*` | 부모가 Claude Code임을 감지. 자식에서 `--dangerously-skip-permissions` 자동 제거(상위 권한 컨텍스트 상속). |

## 4.1 forge-scope.json (프로젝트 설정 파일)

consumer repo root에 `forge-scope.json`을 두면 런타임 설정을 커밋으로 공유할 수 있다.

```json
{
  "default_sln": "Src/MyProject/My.sln"
}
```

| 키 | 타입 | 설명 |
|---|---|---|
| `default_sln` | string | sln 자동 탐지 다수 결과 시 사용할 경로 (repo root 기준 상대경로). `FORGE_DEFAULT_SLN` env보다 우선도 낮음. `--sln` CLI보다 우선도 낮음. |

파싱 실패(JSON 오류, 파일 손상)는 경고 로그만 출력하고 무시한다.

---

## 5. 종료 코드

| 코드 | 상수 | 의미 |
|---|---|---|
| `0` | `EXIT_OK` | 성공. |
| `1` | `EXIT_ERR` | 일반 오류(검증 실패·plan 거부·재시도 한도 초과 등). |
| `2` | `EXIT_BLOCKED` | step이 `blocked` 상태 진입(사용자 개입 필요). |
| `130` | `EXIT_KBI` | KeyboardInterrupt(Ctrl-C 또는 SIGTERM). 진행 중인 step은 `interrupted`로 마크. |

---

## 6. 권장 호출 패턴

### 6.1 FRD 1개 단순 구현 (가장 싼 토큰)

```bash
python scripts/forge_scope.py <phase-dir> \
  --preset=frd-implementation \
  --doc=docs/FRD/<FRD-ID>.md \
  --prompt="<FRD 구현만 수행. 범위 밖 리팩터링/문서 수정 금지>" \
  --compact-docs --quiet --yes --trust
```

### 6.2 FRD를 TDD 흐름으로 구현 (계약→red→green→회귀)

```bash
python scripts/forge_scope.py <phase-dir> \
  --preset=contract-tdd \
  --doc=docs/FRD/<FRD-ID>.md \
  --prompt="<FRD 구현. 본 개발 1 step + TDD wrap 3 step>" \
  --single-step \
  --compact-docs --quiet --yes --trust
```

(여기서 `--single-step`은 의미 라벨, 실제로는 contract-tdd가 4-step을 만든다. 생략해도 동일.)

비용을 더 줄이려면 `--step-model=claude-haiku-4-5-20251001` 추가.

### 6.3 일반 단일 작업 (FRD 아님, splitter 우회)

```bash
python scripts/forge_scope.py <phase-dir> \
  --single-step --compact-docs \
  [--doc=docs/<...>.md] \
  --prompt="<작업 범위>" \
  --quiet --yes --trust
```

### 6.4 Auto-splitter (여러 레이어/모듈로 분해 필수일 때만)

```bash
python scripts/forge_scope.py <phase-dir> \
  --compact-docs \
  --prompt="<사용자 prompt>" \
  [--doc=docs/<...>.md] \
  --quiet --yes --trust
```

### 6.5 Claude Code 부모 세션에서 spawn할 때

`Bash(run_in_background=true)`로 한 번 호출하고 즉시 turn 종료. **`--quiet --yes` 필수.** Monitor / ScheduleWakeup / 자발적 진행 확인용 read 금지(메인 세션 토큰 30% 소모 사례 있음).

---

## 7. 에러 복구

| 상태 | 회복 절차 |
|---|---|
| `error` | `phases/scoped/<phase-dir>/index.json`에서 해당 step의 `status`를 `pending`으로, `error_message`를 삭제 → 재실행. |
| `blocked` | `blocked_reason` 해결 후 위와 동일. |
| `interrupted` | 위와 동일. |
| 부분 상태(index.json 부재 + step 파일만 존재) | `phases/scoped/<phase-dir>/`를 비우고 `--prompt`/`--doc`과 함께 재실행, 또는 `index.json`을 직접 작성한 뒤 재실행. |

splitter를 다시 돌리고 싶으면 `phases/scoped/<phase-dir>/`를 통째로 제거하고 재실행한다.

---

## 8. 절대 변경 금지

`forge_scope.py` 실행 중 다음은 수정·삭제하지 않는다.

- `docs/**` (사용자가 명시적으로 doc 편집을 지시한 경우 제외)
- `CLAUDE.md`, `MEMORY.md`
- `scripts/forge_full.py`, `.claude/commands/forge-full.md`
- `phases/full/**` (full 흐름 산출물 — `forge-scope`는 절대 읽지·쓰지 않음)
- `PHASE_SCHEMA.md`

---

## 9. 관련 파일

| 경로 | 역할 |
|---|---|
| `scripts/forge_scope.py` | 본체 실행기. |
| `scripts/test_forge_scope.py` | 단위 테스트(91개). |
| `.claude/commands/forge-scope.md` | 사용자 대면 슬래시 커맨드 명세(스킬). |
| `PHASE_SCHEMA.md` | phase 디렉토리 스키마(공용). |
| `phases/scoped/index.json` | 모든 scoped phase의 top-level 상태 인덱스. |
| `phases/scoped/<phase-dir>/index.json` | 해당 phase의 plan + step 상태. |
| `phases/scoped/<phase-dir>/step{N}.md` | step별 작업 지시문(5개 H2 헤딩 필수). |
| `phases/scoped/<phase-dir>/step{N}-output.json` | step 실행 결과(stdout/stderr/usage). |
