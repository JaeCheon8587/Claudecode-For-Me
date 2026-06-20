---
name: forge-scope
description: harness_framework forge-scope 경량 TDD phase runner를 사용자 프로젝트에서 실행한다. 플러그인 캐시의 worktree_setup.py를 직접 실행(프로젝트로 복사 안 함)해 init 으로 워크트리·서브모듈 링크·가드레일 복사·.process 스캐폴딩을 셋업한다. 이후 고정 계약-TDD 파이프라인(계약+테스트→구현→빌드/유닛테스트)을 현재 세션이 워크트리 안에서 인라인으로 수행한다 (오케스트레이터·자식 spawn 없음). /claudecode-for-me:forge-scope 로 실행.
argument-hint: "<TASK-doc-path> [--name <slug>] [--force]"
input: TASK 문서 경로 (docs/.templates/App/TASK/APP-TASK-NNN-TEMPLATE.md 형식)
output: .worktree/<slug>/ 워크트리 + feat-<slug> 브랜치 commit (계약+테스트 / 구현 / 빌드·테스트 통과)
requires-user-interaction: true
---

# Forge Scope — Skill (인라인 TDD)

`forge-scope`는 단일 TASK 문서를 **고정 계약-TDD 파이프라인**으로 빠르게 구현하는 경량 runner다.

**역할 분리**: `scripts/worktree_setup.py`는 **셋업·검증·정리만** 한다 — 워크트리 생성, 서브모듈 링크, 가드레일 복사, 미결 항목 검증 게이트, `.process` 스캐폴딩, cancel teardown. **실제 코딩(계약→테스트→구현→빌드/테스트)은 이 세션이 워크트리 안에서 인라인**으로 수행한다. 오케스트레이터·step별 자식 spawn·하드 강제 게이트는 없다.

> **병렬 격리**: 여러 세션을 동시에 켜 병렬 개발할 수 있다. 각 세션은 **자기 워크트리 안에서** 작업하므로 서로 충돌하지 않는다. 작업을 워크트리 상위(메인 repo)에서 하지 않는다.

> **완전 세션 자율**: TDD 순서·단계별 커밋·테스트 통과 여부는 세션이 `forge-scope-build.md`를 따라 self-discipline으로 지킨다. python은 강제하지 않는다 (검증 게이트 1개 제외).

> **빌드 절대 제약**: 빌드/테스트는 솔루션(`*.sln`) 단위 **금지**. 무조건 대상 **프로젝트(.csproj)만** `dotnet build`/`dotnet test`.

---

## 단계 1 — Python 사전 검사

```bash
python --version 2>&1 || py -3 --version 2>&1
```

- 명령이 없거나 3.10 미만이면 **즉시 중단**하고 안내:

```
[forge-scope] Python 3.10 이상이 필요합니다.
설치: Windows https://www.python.org/downloads/ (PATH 추가 체크), macOS/Linux pyenv·brew·패키지 매니저.
설치 후 터미널 재시작하고 다시 시도하세요.
```

- `py -3`로만 가능하면 이후 모든 `python` 호출을 `py -3`로 대체한다.

---

## 단계 2 — 준비 (복사 없음)

**`worktree_setup.py`와 템플릿을 프로젝트로 복사하지 않는다.** 플러그인 캐시에서 직접 실행한다 — helper는 cwd(메인 repo)에서 동작하고 템플릿은 helper 옆(`${CLAUDE_PLUGIN_ROOT}/scripts/forge_templates/`)에서 읽으므로 프로젝트에 forge 도구를 남길 이유가 없다. 앱 repo 히스토리를 오염시키지 않는다.

helper 경로를 변수로 잡는다:

```bash
FORGE="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

**`.gitignore` 확인 (생성물만)**: `.worktree/`·`.process/`(워크트리·상태 생성물)가 `.gitignore`에 있는지 확인한다. 없으면 추가하고 그 `.gitignore` 변경만 commit한다 (dirty 게이트 오탐 방지). forge 도구 자체는 프로젝트에 없으므로 commit 대상이 아니다.

```bash
git add .gitignore && git commit -m "chore: ignore forge-scope worktree/process dirs"
```

> 이미 `.worktree/`·`.process/`가 ignore돼 있으면 이 단계 전체를 생략한다.

---

## 단계 3 — 검증 + 셋업 (worktree_setup.py init)

`$ARGUMENTS` 첫 토큰을 TASK 문서 경로로 해석한다 (앞 `/` 제거). (정리는 이 스킬이 아니라 `/claudecode-for-me:forge-cancel` 커맨드가 담당한다.)

```bash
python "$FORGE" init --doc <TASK-doc-path>
```

- `--name <slug>`: docName/워크트리/브랜치 이름 명시 (기본: doc 파일명 stem).
- `--force`: 메인 repo dirty 검사 우회.

**결과 처리**:

- **exit code 2** (검증 게이트 미통과): stderr에 `§F` 메시지로 미결 항목(원시 템플릿 / §11 미확인 사항 Open / §7 결정 필요 / 미치환 placeholder)이 나온다. 사용자에게 그대로 전달하고 **중단**한다 — 문서를 먼저 완성/확정해야 한다.
- **exit code 0**: stdout 마지막 줄의 JSON 매니페스트를 파싱한다:

```json
{"root":"<abs>","worktree":"<abs>","branch":"feat-<slug>","docName":"<slug>",
 "doc":"<abs>","build_md":"<abs>","progress_md":"<abs>","copied":[...],"skipped":[...]}
```

- 그 외 비0: stderr를 사용자에게 전달하고 중단.

`init`이 수행한 것: `.worktree/<slug>/` 워크트리 + `feat-<slug>` 브랜치 생성, 서브모듈 junction/symlink 링크, 가드레일(`CLAUDE.md`·`.claude/rules/`·`Docs`/`docs`) 워크트리 복사, `.worktree/<slug>/.process/<docName>/`에 build/progress 템플릿 생성(재호출 시 제거 후 재생성).

---

## 단계 4 — 가드레일 read + build.md 작성

1. **가드레일 read (1회)**: `<worktree>/CLAUDE.md`와 TASK 문서(`doc`)를 read한다. 작업 규칙·범위의 ground truth. (가드레일은 워크트리에 복사돼 있다.)
2. **build.md 작성**: TASK 문서의 §8 작업 단계 · §9 완료 기준 · §9.1 단위 테스트 명세 · §12 컨텍스트 임베드를 읽고, `<build_md>`(`.process/<docName>/forge-scope-build.md`)의 고정 3-Step 골격에 **구체 내용을 채운다**:
   - **빌드 타겟(.csproj)**: §9.1 "프로젝트" 칸에서 도출해 입력 절에 명시. (솔루션 금지 — 프로젝트만)
   - Step 1 계약: §12 외부계약/데이터구조 기반 인터페이스·DTO.
   - Step 1 테스트: §9.1 TS 행 기반 단위 테스트(§9 AC 검증).
   - Step 2 구현: §8 작업 단계 기반.

---

## 단계 5 — 인라인 TDD 루프 (핵심)

**모든 작업은 `<worktree>` 안에서** 수행한다 — Edit/Write/`git`/`dotnet`의 cwd는 워크트리. 메인 repo(워크트리 상위) 파일은 read만, 수정 금지. `run_in_background`·`Monitor`·`ScheduleWakeup`를 쓰지 않는다 (foreground 인터랙티브).

`forge-scope-build.md`의 순서대로:

### Step 1 — 계약 + 테스트 (RED)
1. 계약(인터페이스·DTO) 작성.
2. 단위 테스트 작성 — §9 AC를 검증. 구현 없으므로 올바른 이유로 실패해야 함.
3. 커밋: `git add` 후 `git commit -m "test(<slug>): 계약 + RED 테스트"`.
4. `forge-scope-progress.md` Step 1 행을 `done` + commit hash로 갱신.

### Step 2 — 구현 (GREEN)
1. Step 1 테스트를 통과시키는 **최소 구현**. 범위 밖 리팩토링 금지.
2. 커밋: `git commit -m "feat(<slug>): 구현"`.
3. progress.md Step 2 갱신.

### Step 3 — 빌드 + 유닛테스트 통과
1. `dotnet build <타겟>.csproj` (**`*.sln` 금지**).
2. `dotnet test <타겟>.csproj`.
3. 실패 시 통과까지 개선 (테스트 약화·삭제 금지).
4. 커밋: `git commit -m "fix(<slug>): 빌드/테스트 통과"`.
5. progress.md Step 3 갱신.

> **resume**: 같은 세션을 이어갈 때는 `forge-scope-progress.md`를 읽어 미완 Step부터 재개한다. (worktree_setup.py를 같은 doc로 재호출하면 `.process`가 제거 후 재생성되므로 새 시작 — resume는 재호출 없이 세션 내에서 이어가는 것이다.)

---

## 단계 6 — 보고 / 정리

**완료 보고**:
- 워크트리 `.worktree/<slug>` · 브랜치 `feat-<slug>` · 커밋 3개(test/feat/fix).
- 확인: `git diff feat-<slug>` · 머지: `git merge feat-<slug>`.

**정리**: 워크트리·브랜치 제거는 별도 커맨드 `/claudecode-for-me:forge-cancel`을 쓴다 (서브모듈 메인 원본 보존). 이 스킬에서는 정리하지 않는다.

---

## 옵션 참고

| 옵션 | 설명 |
|---|---|
| `init --doc <path>` | 검증 게이트 → 워크트리 + 서브모듈 링크 + 가드레일 복사 + `.process` 스캐폴딩 → JSON 매니페스트. **셋업의 전부.** |
| `--name <slug>` | docName/워크트리/브랜치 이름 명시 (기본: doc 파일명 stem). |
| `--force` | 메인 repo dirty 검사 우회 (init). |
| `--quiet` | 진행 로그 억제, JSON만 출력 (init). |

> **정리는 별도 커맨드**: 워크트리·브랜치 제거는 `/claudecode-for-me:forge-cancel`을 쓴다.

> **검증 게이트(init 내부)**: git repo · 문서 존재 · 미결 항목 없음을 검사한다. 미결 = 원시 템플릿 배너 잔존 / §11 미확인 사항 Open 행 / §7 결정 필요 결정 행 / 미치환 `{...}` placeholder. 하나라도 있으면 exit 2로 중단하고 워크트리를 만들지 않는다.
