---
name: ddr-loop
description: doc-driven-review(DDR) 검증 ↔ fix(claude) 수렴 루프를 사용자 프로젝트에서 실행한다. forge가 만든 worktree나 현재 브랜치 변경에 대해 DDR(Codex)로 conformance를 채점하고, 임계 미달이면 그 리포트로 claude가 코드를 고친 뒤 재검증 — 임계(기본 99%) 또는 최대 반복(기본 3) cap까지 반복한다. DDR 단독은 1회 검증으로 끝나지만 ddr-loop는 목표 conformance까지 수렴시킨다. 첫 호출 시 scripts/ddr_loop.py + 의존 스크립트(doc_driven_review.py, forge_scope.py)를 자동 부트스트랩한 뒤 ddr_loop.py를 실행한다. "DDR 루프", "검증하고 고치고 반복", "conformance 99%까지", "ddr-loop" 요청 시 트리거. /claudecode-for-me:ddr-loop 로 실행.
argument-hint: "<doc-path...> [--worktree <branch>|--commit <ref>] [--scope auto|working-tree|branch] [--max-iter N] [--threshold P] [--commit-each]"
input: 문서 경로 1개 이상 + 선택적 스코프/루프 CLI 옵션
output: 수렴 리포트(conformance 궤적) + .review/<doc-stem>-review.md (최종 라운드)
requires-user-interaction: true
---

# DDR Loop — Skill

`ddr-loop`은 `scripts/ddr_loop.py`를 통해 **검증↔개선 수렴 루프**를 관장한다.
`doc-driven-review`(DDR)는 설계상 read-only 검증기라 "검증 땡, 끝"이다 — 스스로 코드를
고치지 못한다. `ddr-loop`은 그 위에 루프를 씌운다:

```
DDR(Codex 검증) → conformance < 임계? → fix(claude 수정) → 재검증 → … → 임계 도달 or cap
```

핵심 분리: **검증자=Codex(DDR), 수정자=Claude.** 한 모델이 짠 코드를 같은 모델이
채점하는 self-grading 마스킹을 피한다. forge·DDR 원본 스크립트는 건드리지 않고 재사용만 한다.
직접 코드 작성·검증을 수행하지 않고, 부트스트랩 검사 → Python 검사 → 인자 파싱 → 스크립트 실행 순으로 위임한다.

> **재귀 호출 경고**: `ddr_loop.py`는 내부적으로 `codex`(검증)와 `claude`(수정) CLI를
> subprocess로 spawn한다. 플러그인 명령 자체도 Claude Code 세션에서 실행되므로 중첩 호출이
> 발생한다. 이는 의도된 동작이며 무한 재귀가 아니다. `--trust` 없이 실행하면 fix용 child
> claude가 권한이 없어 파일을 수정하지 못한다(검증만 반복됨).

---

## 단계 1 — Python 사전 검사

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 명령이 없거나 버전이 3.10 미만이면 **즉시 중단**하고 사용자에게 출력한다:

```
[ddr-loop] Python 3.10 이상이 필요합니다.
설치 방법:
  - Windows: https://www.python.org/downloads/  (PATH 추가 체크 필수)
  - macOS/Linux: pyenv, brew, 또는 패키지 매니저 사용
설치 후 터미널을 재시작하고 다시 시도하세요.
```

- Python이 `py -3`로만 가능한 경우, 이후 모든 `python` 호출을 `py -3`로 대체한다.

> **codex/claude CLI 의존**: `ddr_loop.py`는 검증에 `codex`, 수정에 `claude` CLI를 호출한다.
> codex 미설치면 DDR이 exit 2를 반환하고 루프가 즉시 중단된다(`npm install -g @openai/codex` 또는 `/codex:setup`).

---

## 단계 2 — 부트스트랩 (idempotent)

사용자 cwd에 아래 파일이 없으면 플러그인 내장 스크립트에서 복사한다.
**기존 파일은 절대 덮어쓰지 않는다** — 존재 시 skip 후 사용자에게 알린다.

플러그인 경로는 `${CLAUDE_PLUGIN_ROOT}` 환경변수로 얻는다 (Claude Code가 자동 주입).

| 복사 원본 (`${CLAUDE_PLUGIN_ROOT}/…`) | 복사 대상 (cwd 기준) | 비고 |
|---|---|---|
| `scripts/ddr_loop.py` | `./scripts/ddr_loop.py` | 핵심 오케스트레이터 |
| `scripts/doc_driven_review.py` | `./scripts/doc_driven_review.py` | 검증자 (ddr_loop이 subprocess 호출) |
| `scripts/forge_scope.py` | `./scripts/forge_scope.py` | `ClaudeInvoker` 제공 (ddr_loop이 import) |

`./scripts/` 디렉토리가 없으면 먼저 생성한다.
`ddr_loop.py`는 같은 `./scripts/` 안의 `forge_scope.py`를 import하고 `doc_driven_review.py`를
subprocess로 호출하므로 **세 파일 모두 존재해야** 한다. 이미 `forge-scope`/`doc-driven-review`
스킬을 쓴 프로젝트라면 의존 2개는 이미 존재하여 skip된다.

부트스트랩 완료 후 복사된 파일 목록과 skip된 파일 목록을 사용자에게 한 번 출력한다.

> **commit 불필요**: `ddr-loop`은 워크트리를 새로 만들지 않고 기존 변경/워크트리 위에서 동작한다.
> 부트스트랩 신규 파일은 메인 repo의 untracked 상태로 두어도 무방하다(루프 동작에 영향 없음).
> 단, `--commit-each` 사용 시 타깃 디렉토리의 모든 변경이 라운드 커밋에 흡수되므로,
> 부트스트랩 파일이 타깃에 섞이지 않도록 worktree 모드를 권장한다.

---

## 단계 3 — Git repo 확인

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

실패(git repo 아님)이면 중단한다 — `ddr_loop.py`는 git 변경(working-tree/branch/commit)을
DDR로 검증하므로 git 없이는 동작 불가능하다.

---

## 단계 4 — 인자 파싱

`$ARGUMENTS`를 다음과 같이 해석한다.

1. **문서 경로 추출** (필수): `docs/...md` / `/docs/...md` 형식 토큰을 1개 이상 모아 `--docs`로 넘긴다.
   앞 `/`를 제거하고 `docs/` prefix로 정규화한다. 문서가 0개이면 1회 안내 후 중단:
   ```
   [ddr-loop] 검증할 문서 경로가 1개 이상 필요합니다.
   예: /ddr-loop docs/FRD/F003.md --worktree feat-login-feature
   ```

2. **타깃 스코프**:
   - 사용자가 워크트리/브랜치명을 지목하거나 forge-scope phase를 이어받는 맥락이면 `--worktree <branch|path>`.
   - 특정 커밋(예: forge no-worktree feat 커밋)을 지목하면 `--commit <ref>`.
   - 아무 것도 없으면 생략 → 현재 브랜치 working-tree 대상(`--scope auto`).

3. **루프 파라미터**: 사용자가 횟수/임계를 말하면 `--max-iter N` / `--threshold P`로 넘긴다(기본 3 / 99).
   라운드별 커밋을 원하면 `--commit-each`.

4. **권한**: 자동 수정을 위해 항상 `--trust --quiet`를 첨가한다.

실행 예:
```bash
python ./scripts/ddr_loop.py --docs docs/FRD/F003.md \
  --worktree feat-login-feature --threshold 99 --max-iter 3 \
  --trust --quiet
```

---

## 단계 5 — 환경변수 및 실행

### 환경변수 상속

| 변수 | 설명 |
|---|---|
| `FORGE_TRUST` | `1`/`true`/`yes` 설정 시 `--trust`와 동일 효과 (fix child claude 권한) |
| `FORGE_CLAUDE_TIMEOUT` | fix claude 라운드 최대 시간(초). 기본 1800. |
| `ANTHROPIC_API_KEY` | API 키. |

### 실행 패턴

`ddr-loop`은 라운드마다 codex 검증 + claude 수정이 돌아 수 분~수십 분 소요될 수 있으므로
**`run_in_background=true`**로 호출하고 즉시 turn을 종료한다.
완료 알림이 도착하면 종료 리포트(conformance 궤적)와 `.review/<doc-stem>-review.md`를 1회 read하여
사용자에게 보고한다.

**필수 금지** (부모 세션 토큰 절감):
- `Monitor` 사용 금지
- `ScheduleWakeup`(/loop) 사용 금지
- 진행 확인을 위한 자발적 `git log` / `tail` / review 파일 read 금지 (완료 알림 전)
- `--quiet` 생략 금지

### 종료 보고 시 명시할 것

- **수렴 여부**: exit 0 = 임계 도달, exit 7 = cap 도달·임계 미달.
- **conformance 궤적** (예: `62% → 79% → 90% → 96%`).
- **변경 위치**: worktree 모드면 `.worktrees/<phase>/` (메인 트리 불변), 현재 브랜치 모드면 working-tree.
- **커밋 상태**: 기본은 미커밋 누적 → 사용자가 `commit-analysis`/머지로 마무리. `--commit-each`면 라운드별 `fix: ddr-loop iter N` 커밋.
- cap 미달이면 리포트의 **남은 우선순위 findings** 그대로 전달.

---

## 옵션 참고

| 옵션 | 설명 |
|---|---|
| `--docs <p...>` | 필수. 검증할 문서 1개 이상. DDR에 그대로 통과. |
| `--worktree <branch\|path>` | 대상 워크트리. fix가 이 워크트리 안에서 수행됨. `--commit`과 mutex. |
| `--commit <ref>` | 커밋 노드 검증. fix cwd = repo root. `--worktree`와 mutex. |
| `--scope auto\|working-tree\|branch` | 기본 auto. `auto`는 미커밋/커밋 양쪽을 자동 처리(권장). |
| `--base <ref>` | branch scope 기준점. 기본 origin/main merge-base. |
| `--max-iter <N>` | 최대 반복 cap. 기본 3. |
| `--threshold <pct>` | 목표 conformance %. 기본 99. 도달 시 즉시 종료. |
| `--commit-each` | 라운드별 fix를 타깃에 커밋. 기본 off(미커밋 누적). |
| `--model` / `--effort` | codex(DDR) 통과. |
| `--fix-model` | fix용 claude 모델. 기본 `claude-sonnet-4-6` (최신 Sonnet). |
| `--fix-effort` | fix claude `--effort` (`low\|medium\|high\|xhigh\|max`). 기본 `high`. |
| `--trust` | fix claude에 `--dangerously-skip-permissions` 부여. Claude Code spawn 시 항상 포함. |
| `--quiet` | 진행 로그 억제. Claude Code spawn 시 항상 포함. |
| `--dry-run` | DDR 1회만 돌리고 fix 없이 conformance 출력. |

> **scope ↔ commit-each**: `auto`(기본)는 미커밋이면 working-tree, 깨끗하면 branch를 골라
> 두 모드 모두 자동 처리한다. 명시적으로 `--scope working-tree` + `--commit-each`(커밋 후 트리가 비어
> 다음 라운드가 변경을 못 봄) 또는 `--scope branch` + 미커밋(fix가 branch diff에 안 나타남) 조합은
> 스크립트가 경고를 출력한다 — 가급적 `auto`를 쓴다.

---

## 한계

- **codex/claude CLI 필수** — 둘 중 하나라도 없으면 루프 불가(codex 미설치 시 exit 2).
- **수렴 보장 없음** — 해소 불가 항목이 있으면 cap까지 돌고 exit 7. 정체(매 라운드 동일 conformance) 조기중단은 없고 cap이 backstop.
- **단일 repo** — cross-repo 검증/수정은 미지원.
- **read-only 영역 보호는 프롬프트 의존** — fix claude에게 `.review/` 수정 금지를 지시하나 강제는 아님.
