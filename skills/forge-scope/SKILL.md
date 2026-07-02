---
name: forge-scope
description: harness_framework forge-scope 경량 TDD workflow를 사용자 프로젝트에서 실행한다. Work Packet을 우선 입력으로 받아 Ready gate, 연결 TASK, Required SSOT Execution Matrix, Implementation Output Contract를 소비해 워크트리에서 구현한다. legacy TASK 직접 입력도 호환 지원한다. 플러그인 캐시의 worktree_setup.py helper를 직접 실행(프로젝트로 복사 안 함)해 init 으로 워크트리·서브모듈 링크·가드레일 복사·.process 스캐폴딩을 셋업한다. 이후 고정 계약-TDD 파이프라인(계약+테스트→구현→빌드/유닛테스트)을 현재 세션이 워크트리 안에서 인라인으로 수행한다 (오케스트레이터·자식 spawn 없음). /claudecode-for-me:forge-scope 로 실행.
---

# Forge Scope — Skill (인라인 TDD)

`forge-scope`는 Work Packet을 **고정 계약-TDD 파이프라인**으로 구현하는 경량 workflow다. 권장 경로는 `/forge-scope <WORK_PACKET>`이다. `/forge-scope <TASK>`는 legacy 호환 경로이며 TASK gate만 적용되고 Work Packet 기반 Required SSOT gate와 output contract 자동 추적은 없다.

**역할 분리**: `scripts/worktree_setup.py`는 **셋업·검증·정리만** 한다 — Work Packet/TASK gate, 워크트리 생성, 서브모듈 링크, 가드레일 복사, `.process` 스캐폴딩, cancel teardown. **실제 코딩(계약→테스트→구현→빌드/테스트)은 이 세션이 워크트리 안에서 인라인**으로 수행한다. 오케스트레이터·step별 자식 spawn·하드 강제 게이트는 없다.

> **병렬 격리**: 여러 세션을 동시에 켜 병렬 개발할 수 있다. 각 세션은 **자기 워크트리 안에서** 작업하므로 서로 충돌하지 않는다. 작업을 워크트리 상위(메인 repo)에서 하지 않는다.

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

**`worktree_setup.py`와 템플릿을 프로젝트로 복사하지 않는다.** 플러그인 캐시에서 직접 실행한다. helper는 cwd(메인 repo)에서 동작하고 템플릿은 helper 옆(`${CLAUDE_PLUGIN_ROOT}/scripts/forge_templates/`)에서 읽는다.

helper 경로를 변수로 잡는다:

```bash
FORGE="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

**`.gitignore` 확인 (생성물만)**: `.worktree/`·`.process/`가 `.gitignore`에 있는지 확인한다. 없으면 추가하고 그 `.gitignore` 변경만 commit한다.

```bash
git add .gitignore && git commit -m "chore: ignore forge-scope worktree/process dirs"
```

이미 `.worktree/`·`.process/`가 ignore돼 있으면 이 단계 전체를 생략한다.

---

## 단계 3 — 검증 + 셋업 (worktree_setup.py init)

`$ARGUMENTS` 첫 토큰을 Work Packet 또는 TASK 문서 경로로 해석한다 (앞 `/` 제거). 권장 입력은 Work Packet이다.

```bash
python "$FORGE" init --doc <WORK_PACKET-or-TASK-doc-path>
```

- `--name <slug>`: docName/워크트리/브랜치 이름 명시 (기본: doc 파일명 stem).
- `--force`: 메인 repo dirty 검사 우회.

**Work Packet 입력 판별**: `WORK_PACKET` 경로, `-WP-` 문서 ID, 또는 `연결 TASK` 메타 행이 있으면 Work Packet으로 취급한다.

**Work Packet 실행 게이트**:
- `Execution Gate` 섹션이 있어야 한다.
- 상태는 정확히 `Ready`여야 한다. `Draft = do not implement` 이며 워크트리 생성 전 하드 중단한다.
- `Blocking / Open Questions`는 `none`이어야 한다.
- 연결 TASK 링크가 있어야 하고 파일이 존재해야 한다.
- `Required SSOT Execution Matrix`의 `Priority = Required` 행은 `Document` 링크가 있어야 하고 파일이 존재해야 한다.

**TASK legacy 입력 게이트**:
- 기존 TASK gate를 그대로 적용한다.
- 미결 = 원시 템플릿 배너 / §11 미확인 사항 Open / §7 결정 필요 / 미치환 placeholder.
- TASK 직접 입력은 Work Packet §5/§6, Required SSOT Execution Matrix, Implementation Output Contract를 제공하지 않으므로 구현자가 TASK 문서만 기준으로 좁게 진행한다.

**결과 처리**:

- **exit code 2**: stderr의 `§F` 메시지를 사용자에게 그대로 전달하고 중단한다. 문서를 먼저 완성/확정해야 한다. **세션은 Work Packet, TASK, SSOT 문서를 gate 통과 목적으로 직접 수정하지 않는다.**
- **exit code 0**: stdout 마지막 줄의 JSON 매니페스트를 파싱한다:

```json
{"root":"<abs>","worktree":"<abs>","branch":"feat-<slug>","docName":"<slug>",
 "doc":"<abs>","input_kind":"WORK_PACKET","work_packet":"<abs-or-null>",
 "task_doc":"<abs-or-null>","build_md":"<abs>","progress_md":"<abs>",
 "copied":[...],"skipped":[...]}
```

- 그 외 비0: stderr를 사용자에게 전달하고 중단.

---

## 단계 4 — 가드레일 read + build.md 작성

1. **가드레일 read (1회)**: `<worktree>/CLAUDE.md`를 read한다.
2. **입력 문서 read**:
   - Work Packet 입력이면 `work_packet`, 연결 `task_doc`, Work Packet §4 `Required SSOT Execution Matrix`의 Required 링크 파일만 read한다.
   - TASK legacy 입력이면 `doc`만 read한다.
3. **build.md 작성**: `<build_md>`(`.process/<docName>/forge-scope-build.md`)의 고정 3-Step 골격에 구체 내용을 채운다.
   - 입력: Work Packet, 연결 TASK, Required SSOT Execution Matrix, 빌드 타겟(.csproj).
   - 구현 범위: Work Packet §5 실행 규칙, §6 실행 경계, TASK §8 작업 단계, TASK §9 완료 기준, Required SSOT read range.
   - 검증: Work Packet §8 검증 입력 + TASK §9.1/§9.2/§9.3.
   - 빌드 타겟(.csproj): Work Packet §8 또는 TASK §9.1 "프로젝트" 칸에서 도출해 입력 절에 명시. 솔루션 금지.

Work Packet에 없는 문서를 넓게 탐색하지 않는다. 단, 컴파일/테스트 오류 해결에 필요한 직접 관련 코드 탐색은 허용한다.

---

## 단계 5 — 인라인 TDD 루프 (핵심)

**모든 작업은 `<worktree>` 안에서** 수행한다 — Edit/Write/`git`/`dotnet`의 cwd는 워크트리. 메인 repo(워크트리 상위) 파일은 read만, 수정 금지. `run_in_background`·`Monitor`·`ScheduleWakeup`를 쓰지 않는다.

`forge-scope-build.md`의 순서대로:

### Step 1 — 계약 + 테스트 (RED)
1. Work Packet §5/§6, TASK §12, Required SSOT 기반 계약(인터페이스·DTO) 작성.
2. 단위 테스트 작성 — Work Packet §8 + TASK §9 AC를 검증. 구현 없으므로 올바른 이유로 실패해야 함.
3. 커밋: `git add` 후 `git commit -m "test(<slug>): 계약 + RED 테스트"`.
4. `forge-scope-progress.md` Step 1 행을 `done` + commit hash로 갱신.

### Step 2 — 구현 (GREEN)
1. Step 1 테스트를 통과시키는 **최소 구현**. Work Packet §6 금지사항과 TASK §4 비목표 밖 리팩토링 금지.
2. 커밋: `git commit -m "feat(<slug>): 구현"`.
3. progress.md Step 2 갱신.

### Step 3 — 빌드 + 유닛테스트 통과
1. `dotnet build <타겟>.csproj` (**`*.sln` 금지**).
2. `dotnet test <타겟>.csproj`.
3. 실패 시 통과까지 개선 (테스트 약화·삭제 금지).
4. 커밋: `git commit -m "fix(<slug>): 빌드/테스트 통과"`.
5. progress.md Step 3 갱신.

> **resume**: 같은 세션을 이어갈 때는 `forge-scope-progress.md`를 읽어 미완 Step부터 재개한다. `worktree_setup.py`를 같은 doc로 재호출하면 `.process`가 제거 후 재생성되므로 새 시작이다.

---

## 단계 6 — 보고 / 정리

Work Packet 입력이면 완료 보고는 반드시 Work Packet §10 `Implementation Output Contract` 필드로 고정한다.

```
Changed files
- <path>: <요약>

Scope match
- <TASK + Required SSOT Execution Matrix 대비 일치 여부>

Tests run
- <command>: <result>

Not run
- <미실행 검증과 사유 또는 none>

Deviations
- <TASK/SSOT/Work Packet 대비 이탈, 추가 판단, 후속 조치 또는 none>
```

TASK legacy 입력이면 위 형식을 사용하되 `Scope match`에는 TASK 기준으로만 판단했음을 명시한다.

**정리**: 워크트리·브랜치 제거는 별도 커맨드 `/claudecode-for-me:forge-cancel`을 쓴다. 이 스킬에서는 정리하지 않는다.

---

## 옵션 참고

| 옵션 | 설명 |
|---|---|
| `init --doc <path>` | Work Packet/TASK 검증 게이트 → 워크트리 + 서브모듈 링크 + 가드레일 복사 + `.process` 스캐폴딩 → JSON 매니페스트. |
| `--name <slug>` | docName/워크트리/브랜치 이름 명시 (기본: doc 파일명 stem). |
| `--force` | 메인 repo dirty 검사 우회 (init). |
| `--quiet` | 진행 로그 억제, JSON만 출력 (init). |

> **정리는 별도 커맨드**: 워크트리·브랜치 제거는 `/claudecode-for-me:forge-cancel`을 쓴다.
