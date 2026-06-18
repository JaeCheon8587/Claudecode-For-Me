---
name: forge-scope
description: harness_framework forge-scope 경량 phase runner를 사용자 프로젝트에서 실행한다. 첫 호출 시 scripts/forge_*.py、CLAUDE.md、PHASE_SCHEMA.md、FORGE_SCOPE.md、docs/.templates/ 를 자동 부트스트랩한 뒤 forge_scope.py를 실행한다. 인라인 모드 — scaffold(워크트리·plan·warmup)는 python이 결정적으로 강제하고 step 코딩은 현재 세션이 직접 수행한다(자식 claude spawn 없음). /claudecode-for-me:forge-scope 로 실행.
argument-hint: "<prompt> 또는 <doc-path> <prompt> 또는 tdd <doc-path> <prompt> 또는 <phase-dir> [--no-worktree] [--test-target=<csproj>] [options]"
input: 자유 텍스트 prompt 또는 doc-path + prompt + 선택적 CLI 옵션
output: phases/scoped/<phase-dir>/index.json + step{N}.md + 워크트리 feat-<phase-dir> 브랜치 commit
requires-user-interaction: true
---

# Forge Scope — Skill (인라인 실행)

`forge-scope`는 작은 범위(단일 FRD, 단일 기능, 버그픽스)를 빠르게 처리하는 경량 scoped phase runner다.

**인라인 실행 모델**: `scripts/forge_scope.py`가 **결정적 골격**(워크트리 격리·step plan·warmup·step별 atomic commit·index 상태)을 강제하고, **step 코딩은 이 세션(부모 Claude Code 세션)이 직접 인라인으로 수행**한다. 과거처럼 step마다 `claude` 자식 프로세스를 spawn하지 않으므로 **프로세스 콜드스타트가 사라져 간단 작업이 빠르다**.

> **역할 분리**: 무거운/장기 멀티 phase 작업은 `forge-full`(자식 프로세스 + 백그라운드)을 쓴다. `forge-scope`는 경량·인라인·foreground 전용이다. 큰 작업으로 세션 컨텍스트가 오염될 것 같으면 forge-full로 라우팅하라.

> **자식 spawn 여부**: deterministic preset(`frd-implementation`/`contract-tdd`/`single-step`)은 scaffold가 AI 0콜(콜드스타트 0)이다. `--preset=auto`만 scaffold 단계에서 splitter 자식 1콜을 쓴다 — 인라인은 deterministic preset을 권장한다.

---

## 단계 1 — Python 사전 검사

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 명령이 없거나 버전이 3.10 미만이면 **즉시 중단**하고 안내:

```
[forge-scope] Python 3.10 이상이 필요합니다.
설치 방법:
  - Windows: https://www.python.org/downloads/  (PATH 추가 체크 필수)
  - macOS/Linux: pyenv, brew, 또는 패키지 매니저 사용
설치 후 터미널을 재시작하고 다시 시도하세요.
```

- Python이 `py -3`로만 가능하면 이후 모든 `python` 호출을 `py -3`로 대체한다.

---

## 단계 2 — 부트스트랩 (idempotent)

cwd에 아래 파일·디렉토리가 없으면 플러그인 내장 템플릿에서 복사한다. **기존 파일은 절대 덮어쓰지 않는다** — 존재 시 skip 후 알린다. 플러그인 경로는 `${CLAUDE_PLUGIN_ROOT}`로 얻는다.

| 복사 원본 (`${CLAUDE_PLUGIN_ROOT}/…`) | 복사 대상 (cwd 기준) |
|---|---|
| `scripts/forge_full.py` | `./scripts/forge_full.py` |
| `scripts/forge_scope.py` | `./scripts/forge_scope.py` |
| `scripts/forge_cancel.py` | `./scripts/forge_cancel.py` |
| `scripts/forge_templates/CLAUDE.md` | `./CLAUDE.md` |
| `scripts/forge_templates/PHASE_SCHEMA.md` | `./PHASE_SCHEMA.md` |
| `scripts/forge_templates/FORGE_SCOPE.md` | `./FORGE_SCOPE.md` |
| `scripts/forge_templates/docs/.templates/*` | `./docs/.templates/` (각 파일) |

`./scripts/`, `./docs/.templates/`가 없으면 먼저 생성한다. 완료 후 복사·skip 목록을 한 번 출력한다.

> 이미 부트스트랩된 프로젝트라도 forge_scope.py가 갱신되었으면 최신본으로 교체한다(인라인 플래그 `--scaffold-only`/`--record-step`/`--finalize` 필요).

### 단계 2b — 부트스트랩 산출물 commit (필수)

신규 파일이 복사되었다면 **워크트리 생성 전에 메인 repo에 commit**한다. 워크트리는 현재 HEAD 기준 생성되므로 untracked 부트스트랩 파일은 워크트리에 없어 scaffold가 실패한다.

```bash
git add scripts/forge_full.py scripts/forge_scope.py scripts/forge_cancel.py \
        CLAUDE.md PHASE_SCHEMA.md FORGE_SCOPE.md docs/.templates/ .gitignore
git commit -m "chore: bootstrap forge-scope"
```

복사된 파일이 0개면 생략. `.gitignore`에 `.worktrees/`가 포함되는지 확인한다(메인 repo dirty 오탐 방지).

---

## 단계 3 — Git repo 확인 + 워크트리 동작

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

실패(git repo 아님)면 경고만 하고 계속 진행한다:

```
[forge-scope] 현재 디렉토리가 git repository가 아닙니다.
forge_scope.py는 git worktree 기반으로 동작합니다.
'git init && git commit -m "init"' 으로 초기화 후 다시 시도하세요.
```

### 워크트리 동작 요약

`forge_scope.py --scaffold-only`는 phase 시작 시 메인 repo 안 `.worktrees/<phase-dir>/`에 git worktree를 생성하고 branch `feat-<phase-dir>`에 attach한다. 다음이 모두 워크트리 안에서 발생한다:

- `phases/scoped/<phase-dir>/index.json` 및 `step{N}.md`
- step 코딩으로 작성·수정되는 코드
- 모든 `git commit`

**인라인 실행에서 이 세션은 워크트리 디렉토리 안에서 작업한다.** scaffold가 stdout으로 워크트리 절대경로를 넘겨주며, 이후 모든 Read/Edit/Write/Bash(cwd)는 **그 워크트리 절대경로 하위에서만** 수행한다. 메인 repo 작업 트리는 건드리지 않는다(record-step이 누수를 탐지해 abort한다 — 단계 5 참고).

> **서브모듈**: 워크트리 서브모듈은 메인 repo 서브모듈을 junction(Windows)/symlink(Unix)로 링크해 가져온다(오프라인 동작). `submodule.<name>.ignore=all`로 status/commit에서 무시. 메인 미populate면 skip. 정리는 `forge_cancel.py`가 링크를 먼저 제거.

워크트리는 phase 완료 후에도 유지된다. 정리:

```bash
python scripts/forge_cancel.py <phase-dir> --yes   # 워크트리 + 브랜치 제거
```

### no-worktree 모드 (--no-worktree)

`--no-worktree`면 워크트리·`feat-` 브랜치 없이 **현재 브랜치에서 직접** 실행한다(격리 없음). 이 경우 인라인 세션은 메인 repo에서 직접 코딩하며, record-step의 메인-repo 누수 가드는 비활성(ROOT==worktree)이고 워크트리 무변경 가드만 적용된다. 시작 시 작업 트리 dirty면 중단(`--force` 우회).

---

## 단계 4 — 인자 파싱

`$ARGUMENTS`를 아래 모드로 해석한다.

> **in-place 직교 옵션**: 사용자가 *워크트리 없이/현재 트리/in-place/직접* 의도를 표현하면 실행 명령 끝에 `--no-worktree`를 첨가한다. preset·`--single-step`과 직교한다.

> **테스트 스코프 자동 판단**: 작업 문서(TASK/FRD/prompt)에서 대상 App·기능을 읽어 검증 테스트 프로젝트(.csproj)를 추론하고 `--test-target=<csproj>`(repo root 상대경로)를 첨가한다. 풀 솔루션 빌드를 피해 빠르게 검증한다. 확신 없으면 생략.

> **인자 충돌 경고 금지 (precedence, NOT conflict)**: 아래를 충돌로 보고하지 말 것 — `forge_scope.py`가 정의된 우선순위로 정상 처리한다.
> - `--single-step` + `--preset=contract-tdd` 동시 지정은 에러 아님. contract-tdd가 이긴다(deterministic 4-step).
> - preset 우선순위: `--preset=<X>` 명시 > `--single-step` > 기본(auto).
> - `--doc`은 FRD 전용이 아니다 — TASK·일반 문서·FRD 모두 가능.

### Mode 1 — prompt-only
일반 텍스트로 시작하면:
1. `<phase-dir>`을 prompt 핵심 의도 1~3단어 kebab-case로 도출(예 `login-feature`).
2. 사용자에게 slug 한 번 확인. 다른 이름 원하면 따른다.
3. **deterministic single-step**으로 실행한다(인라인 권장):
   ```bash
   python ./scripts/forge_scope.py <phase-dir> --single-step \
     --prompt="<전체 $ARGUMENTS>" --scaffold-only --trust --yes --quiet
   ```

### Mode 2c — TDD (contract-tdd preset)
`$ARGUMENTS` 첫 토큰이 `tdd`면:
1. `tdd` 소비, 두 번째 토큰을 `docs/...md` doc-path로 해석(앞 `/` 제거, `docs/` prefix 강제).
2. 나머지 텍스트를 `--prompt` 값으로.
3. doc-path 부재/형식 위반 시 1회 안내 후 중단:
   ```
   [forge-scope] tdd 모드는 docs/FRD/<FRD-ID>.md 경로 1개가 필요합니다.
   예: /forge-scope tdd docs/FRD/F003.md 로그인 인증
   ```
4. `<phase-dir>`은 FRD ID 또는 파일명 stem으로 도출(예 `tdd-frd-f003`).
5. scaffold 실행:
   ```bash
   python ./scripts/forge_scope.py <phase-dir> --preset=contract-tdd --compact-docs \
     --doc=<정규화된 doc 경로> --prompt="<나머지 텍스트>" --scaffold-only --trust --yes --quiet
   ```

### Mode 2 — doc + prompt
첫 토큰이 `/docs/...md` 또는 `docs/...md`면:
- 앞 `/` 제거, prefix `docs/` 정규화. 나머지 텍스트를 `--prompt`로.

FRD 파일(`docs/FRD/` 하위) — **frd-implementation (single-step)**:
```bash
python ./scripts/forge_scope.py <phase-dir> --preset=frd-implementation --compact-docs \
  --doc=<정규화된 doc 경로> --prompt="<나머지 텍스트>" --scaffold-only --trust --yes --quiet
```
> FRD를 TDD 흐름으로 처리하려면 `tdd` 토큰을 앞에 붙인다(Mode 2c).

일반 문서:
```bash
python ./scripts/forge_scope.py <phase-dir> --single-step --compact-docs \
  --doc=<정규화된 doc 경로> --prompt="<나머지 텍스트>" --scaffold-only --trust --yes --quiet
```

---

## 단계 5 — 인라인 실행 루프 (핵심)

scaffold → 가드레일 read → step 루프(코딩·AC·record) → finalize 순으로 **이 세션이 직접** 수행한다. **`run_in_background`·`Monitor`·`ScheduleWakeup`를 쓰지 않는다** — 인라인은 foreground 인터랙티브 작업이다.

### 5-1. Scaffold
단계 4의 `--scaffold-only` 명령을 **foreground**로 실행한다. stdout 마지막 줄의 JSON 매니페스트를 파싱한다:

```json
{
  "worktree": "<절대경로>", "phase_dir": "<절대경로>", "phase": "<name>",
  "docs_scope": ["docs/..."], "no_worktree": false,
  "root_dirty_baseline": [...],
  "steps": [{"step":0,"name":"...","status":"pending","step_file":"<절대경로>"}, ...]
}
```

- exit code 2(EXIT_BLOCKED) + stderr에 `§F` 메시지면 **FRD 미결 항목 복구**(아래 절)로 분기한다.
- 비정상 종료면 stderr를 사용자에게 전달하고 중단한다.

### 5-2. 가드레일 read (1회)
`<worktree>/CLAUDE.md`와 `docs_scope`의 각 문서를 **1회 read**한다. 이것이 작업 규칙·범위의 ground truth다.

### 5-3. Step 루프 (번호 오름차순, 순서 엄수)
`steps`의 `pending` step을 **번호 오름차순으로 하나씩** 처리한다. step N record가 `completed`되기 전에 step N+1을 시작하지 않는다(TDD red→green 순서 보존).

각 step:
1. `step_file`(절대경로) Read — 작업 내용·`## Acceptance Criteria` bash·금지사항 확인.
2. **코딩**: 요구사항만 구현. **모든 Edit/Write/Read는 `worktree` 절대경로 하위에서만.** 메인 repo 파일 수정 금지.
3. **AC 실행**: step 파일의 Acceptance Criteria bash를 `cwd=<worktree>`로 실행. 통과해야 완료.
4. **status 기록**: `<phase_dir>/step{N}-status.json`에 한 객체로 작성:
   - 성공 → `{"status":"completed","summary":"<핵심 파일·검증결과 200자 이내>"}`
   - 실패(여러 번 고쳐도 AC 불통) → `{"status":"error","error_message":"<원인>"}`
   - 사용자 개입 필요 → `{"status":"blocked","blocked_reason":"<이유>"}`
   - **index.json은 직접 수정하지 않는다 — forge가 소유·관리한다.**
5. **record**: 
   ```bash
   python ./scripts/forge_scope.py <phase-dir> --record-step=N --trust --yes --quiet
   ```
   stdout result JSON의 `result`에 따라:
   - `completed` → 다음 step으로.
   - `retry` → **같은 step을 재작업**(2번부터). 누적 시도는 `--max-attempts`(기본 3)로 제한 — `attempts`/`max` 필드 확인.
   - `error` → 중단. `message` 보고(메인 repo 누수면 워크트리로 작업 이동 후 재시도, 최대 시도 초과면 원인 분석).
   - `blocked` → 중단. 사용자에게 `message`(blocked 사유) 보고.

> **시도 상한(필수)**: step당 인라인 재작업은 `--max-attempts`회를 넘기지 않는다. record-step이 카운터로 강제 종료하지만, 세션도 동일 cap을 지켜 무한 루프를 만들지 않는다.

### 5-4. Finalize
모든 step이 `completed`되면:
```bash
python ./scripts/forge_scope.py <phase-dir> --finalize --trust --yes --quiet
```
result가 `finalized`면 완료. `error`(미완 step)면 해당 step을 마저 처리한다.

### 5-5. 보고
- **워크트리 모드(기본)**: 워크트리 `.worktrees/<phase-dir>/` · 브랜치 `feat-<phase-dir>`. 결과 확인·머지는 `git diff feat-<phase-dir>` / `git merge feat-<phase-dir>`.
- **no-worktree 모드**: 현재 브랜치에 직접 commit. `--push`는 현재 브랜치 push.

---

## FRD 미결 항목 복구 (EXIT_BLOCKED(2) 수신 시)

scaffold가 exit code 2 + stderr `§F` 메시지를 출력하면 `FORGE_SCOPE.md §7` 복구 절차를 따른다: 미결 항목 추출 → 사용자 결정 1회 → docs+코드 변경 → commit → 동일 명령 재실행.

---

## 옵션 참고

| 옵션 | 설명 |
|---|---|
| `--scaffold-only` | 워크트리·plan·warmup·가드레일까지만 하고 step 매니페스트(JSON)를 출력 후 종료. **인라인 실행의 1단계.** |
| `--record-step=N` | 인라인 세션이 끝낸 step N 수확: 사후가드(메인repo 누수·워크트리 무변경) → counter → TDD 순서 gate → status ingest → 2단계 commit. result JSON 출력. |
| `--finalize` | phase 마감(finalize+top index+옵션 push). 전 step 완료 후 1회. |
| `--max-attempts` | record-step 하드 백스톱(기본 3). step당 record 누적이 도달하고도 미완이면 강제 error. |
| `--preset=frd-implementation` | FRD 단건 구현. deterministic single step(콜드스타트 0). FRD 권장. |
| `--preset=contract-tdd` | 문서 1개로 contract/red/green/regression 4-step. deterministic. sln 우선순위: `--sln` > `FORGE_DEFAULT_SLN` > `forge-scope.json` `default_sln` > auto-detect. 단축형 `/forge-scope tdd <doc> <prompt>`. |
| `--preset=auto` | auto-splitter(scaffold 단계 splitter 자식 1콜). 여러 레이어 분해가 꼭 필요할 때만. |
| `--single-step` | 일반 단일 작업 deterministic single step. |
| `--sln=<path>` | contract-tdd용 .sln(repo root 기준). 미지정 시 auto-detect. |
| `--test-target` | 검증 대상 테스트 `.csproj`(repo root 상대경로). 풀 솔루션 빌드 회피. parent AI가 작업 문서 보고 추론. |
| `--compact-docs` | 가드레일 문서 핵심 섹션만 압축 주입. |
| `--no-worktree` | 워크트리·`feat-` 브랜치 미생성, 현재 브랜치 직접 실행(격리 없음). |
| `--force` | dirty 검사 우회. |
| `--push` | 완료 후 원격 push. |
| `--timings` | 구간별 wall-clock 상세 출력(미지정이어도 `[timings]` 요약 1줄은 항상 stderr). |
| `--yes` / `--quiet` | 자동 승인 / 진행 표시 억제. 인라인 호출에 항상 포함. |

> **빌드 스코프**: 검증은 풀 솔루션 `dotnet build` 대신 대상 테스트 프로젝트만 `dotnet test`로 좁힌다. 타깃 우선순위: `--test-target` CLI > `forge-scope.json` `test_target` > 자동 감지 > 전체 sln. scaffold의 warmup `dotnet restore`도 같은 타깃으로 좁힌다(contract-tdd는 회귀 때문에 풀 sln 유지).

> **하위호환(부품 보존)**: `forge_scope.py`의 `ClaudeInvoker`·`DEFAULT_CHILD_TOOLS`·`StepExecutor`·`StepSplitter`는 그대로 유지된다(`ddr_loop.py`가 import). `--preset=auto` scaffold의 splitter, 그리고 `forge-full`이 자식 claude를 계속 사용한다.
