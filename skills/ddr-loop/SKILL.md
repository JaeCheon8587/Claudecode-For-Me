---
name: ddr-loop
description: harness_framework ddr-loop. forge 워크트리 브랜치의 변경점을 Intent(또는 명시 docs)와 doc-driven-review(codex)로 대조해 일치율(Conformance%)을 매기고, 미달 항목을 현재 세션이 워크트리 안에서 인라인 수정·재검한다. --docs 생략 시 forge-init 매니페스트의 Intent를 비교 문서로 쓴다. 최대 3회 반복, 일치율 99% 도달 시 정지. reviewer=codex / fixer=세션(자식 spawn 없음). 빌드는 대상 프로젝트(.csproj)만, 솔루션(*.sln) 금지. /claudecode-for-me:ddr-loop 로 실행.
---

# DDR-Loop — Skill (인라인 수렴 루프)

`ddr-loop`은 `/forge-init`이 만들고 forge-scope가 구현한 워크트리 브랜치를 **문서(docs) 기준으로 수렴**시키는 루프다. `--docs` 생략 시 forge-init 매니페스트의 Intent(워크트리 안 사본 `intent_worktree`)를 비교 문서로 쓴다. `--docs <doc...>`를 주면 명시 docs override로 동작한다. codex(`doc_driven_review.py`)가 브랜치 변경점을 docs와 대조해 **일치율(Conformance %)**을 매기고, **현재 세션**이 미달 항목을 워크트리 안에서 인라인 수정한 뒤 재검한다. **최대 3회**, **일치율 ≥ 99%** 도달 시 정지.

**역할 분리**: `ddr_loop.py`는 **셋업·검증만**(워크트리·docs 확인, build/progress 스캐폴딩). 리뷰는 `doc_driven_review.py`(codex). 수정·빌드·커밋은 이 세션이 워크트리 안에서 인라인. 자식 claude spawn 없음.

> **빌드 절대 제약**: 빌드/테스트는 솔루션(`*.sln`) **금지**. 무조건 대상 **프로젝트(.csproj)만**.
> **문서 자동수정 금지**: 일치율을 올리려 비교 문서(Intent 등)를 고치지 않는다. docs는 정답, 코드를 docs에 맞춘다.

---

## 단계 1 — 사전 검사 (Python + codex)

```bash
python --version 2>&1 || py -3 --version 2>&1
```
- 없거나 3.10 미만이면 즉시 중단 + 설치 안내(`py -3`만 되면 이후 `python`을 `py -3`로 대체).
- **codex 의존**: 리뷰는 codex CLI를 쓴다(doc-driven-review 경유). 단계 5 첫 review가 exit 2면 codex 미설치 → `/codex:setup` 안내 후 중단(루프 진입 안 함).

## 단계 2 — 준비 (복사 없음)

플러그인 캐시에서 직접 실행한다(프로젝트로 복사 안 함). 변수:
```bash
DDR="${CLAUDE_PLUGIN_ROOT}/scripts/ddr_loop.py"
REVIEW="${CLAUDE_PLUGIN_ROOT}/scripts/doc_driven_review.py"
WT="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```
`.worktree/`·`.process/`가 `.gitignore`에 있는지 확인(forge-init이 이미 처리). 없으면 추가하고 그 `.gitignore` 변경만 commit.

## 단계 3 — slug 결정 + init

`$ARGUMENTS` 파싱:
- 첫 토큰이 `--`로 시작하지 않으면 **slug**(positional). `--docs` 뒤 토큰들(다음 `--`flag 전까지)은 **명시 비교 문서 경로**. 생략하면 forge-init 매니페스트의 Intent를 쓴다. `--base`/`--model`/`--effort`는 1토큰 옵션.
- **slug 없음** → `python "$WT" list` → 마지막 줄 JSON 배열 파싱. `"source": "manifest"` 항목만 후보다 — `"scan"` 항목은 매니페스트가 없어 init 이 exit 2 로 막는다(먼저 /forge-init). 후보가 없으면 "forge 워크트리 없음 — 먼저 /forge-init 실행" 보고 후 중단. 아니면 표로 보여주고 `AskUserQuestion`으로 1개 선택.
- **`--docs` 없음** → 메인 repo `.process/forge/<slug>.json`(forge-init 매니페스트)의 `intent_worktree`(없으면 `intent`)를 비교 문서로 쓴다. 매니페스트에 Intent 경로가 없거나 파일이 없으면 `--docs <doc...>` 필요 메시지로 중단.
- **매니페스트 없음** → init 이 exit 2 로 중단한다(`--docs` 를 줘도 마찬가지 — 브랜치를 매니페스트에서 읽는다). 먼저 `/forge-init`.
- **`--base` 없음** → 매니페스트의 `base_commit`(forge-init 이 분기한 시점 sha)을 쓴다.

```bash
python "$DDR" init --slug <slug> [--docs <doc...>] [--base <ref>]
```
**결과 처리**:
- **exit 2**: stderr(워크트리 없음 / docs 없음)를 그대로 사용자에게 전달하고 중단. **세션은 docs를 만들거나 수정하지 않는다.**
- **exit 0**: stdout 마지막 줄 manifest JSON 파싱:
  ```json
  {"root":"<abs>","worktree":"<abs>","branch":"<매니페스트 branch — 기본 intent/<문서 ID>>","docName":"<slug>",
   "docs":["<abs>",...],"docs_source":"auto-intent|explicit","intent":"<abs-or-null>",
   "base":"<ref|null>","build_md":"<abs>","progress_md":"<abs>"}
  ```
  `init`이 한 것: `.process/<docName>/ddr-loop-build.md`·`ddr-loop-progress.md` 생성/덮어쓰기(**다른 산출물 보존**), 워크트리 `.gitignore`에 `.review/`·`.claude/doc-driven-review-logs/` 추가.

## 단계 4 — build.md 작성

1. **read(1회)**: `<worktree>/CLAUDE.md` + manifest `docs` 전부. 자동 source면 docs는 Intent 1개다. 작업 규칙·정답의 ground truth.
2. **build.md 채움**(`<build_md>`):
   - **입력 source**: `docs_source`, `intent` 확인.
   - **빌드 타겟(.csproj)**: Intent Handoff 의 `repo · app` 과 워크트리 구조에서 도출하거나 사용자 지정. (솔루션 금지 — 프로젝트만.)
   - **base ref(vs)**: manifest.base(기본 = forge-init 의 `base_commit`). null 이면 `git -C <worktree> merge-base <manifest.branch> <develop|main>` 으로 분기점을 확인하거나 모브랜치명(예: `develop`).

## 단계 5 — 인라인 수렴 루프 (핵심)

**모든 작업은 `<worktree>` 안에서** — Edit/Write/`git`/`dotnet` cwd는 워크트리. 메인 repo(워크트리 상위)는 read만, 수정 금지. `run_in_background`·`Monitor`·`ScheduleWakeup` 미사용(foreground). 시작 전 `progress.md`를 읽어 미완 회차부터 재개.

`iter`를 1부터 최대 3까지:

### ① 검증 (codex)
```bash
python "$REVIEW" --docs <manifest.docs...> --worktree <manifest.branch> --scope branch [--base <ref>] [--model <m>] [--effort <e>]
```
- **exit 2** → codex 미설치 → 안내 후 중단.
- **exit 3** → 변경 없음(브랜치에 커밋된 diff 없음 — forge-scope 미실행?) → 보고 후 중단.
- **exit 5/6** → base/worktree 해석 실패 → stderr 보고 후 중단.
- **exit 0** → stdout **마지막 비공백 줄** `^Conformance:\s*(\d{1,3})%$`에서 N 추출. 상세 findings는 stdout의 `## Top Priorities`·`## Review Comments`·`## Overengineered` 또는 `<worktree>/.review/<doc-stem>-review.md`.

### ② 기록
`progress.md` iter 행: 일치율 N%, 주요 findings 요약(TP 건수·핵심), 상태 `doing`. 로그 1줄 추가.

### ③ 판정
- **N ≥ 99** → 수렴. 루프 종료(수정·커밋 불요). 행 상태 `done`.
- **iter == 3** → cap 종료(미수렴). 남은 Top Priorities 보존.
- 그 외 → ④로.

### ④ 수정 (세션 인라인)
codex 리뷰의 `Top Priorities` → `Review Comments`([CRITICAL]>[MAJOR]>[MINOR]) → `Overengineered` 순으로 워크트리 안에서 인라인 수정. 코드를 docs 요구에 맞춘다. **docs(Intent 등)·테스트 약화·`.review/` 편집 금지.**

### ⑤ 빌드 + 유닛테스트 (타겟 프로젝트만)
```bash
dotnet build <타겟>.csproj     # *.sln 금지
dotnet test  <타겟>.csproj
```
실패 시 통과까지 개선(테스트 약화·삭제 금지).

### ⑥ 커밋
```bash
git add <변경 소스/테스트>      # .review/ 등 산출물 제외
git commit -m "fix(ddr-<slug>): iter N 일치율 N%"
```
`progress.md` 조치·커밋 hash·상태 `done` 갱신. → 다음 iter ①(새 커밋 누적분 반영 → 일치율 상승).

## 단계 6 — 보고 / 정리

- **Trajectory**: `62% → 88% → 99% ✅` 또는 `… ⛔ cap`.
- **최종**: 수렴 ✅ N% / cap ⛔ N% — cap이면 남은 Top Priorities 인용.
- **커밋**: 회차별 `fix(ddr-<slug>)` 목록. 확인 `git diff <base>..<manifest.branch>` (`<base>` = manifest.base, null 이면 단계 4 에서 확인한 merge-base) / 머지 `git merge <manifest.branch>`.
- **정리**: 워크트리·브랜치 제거는 `/claudecode-for-me:forge-cancel`(서브모듈 메인 원본 보존). 이 스킬은 정리하지 않는다.

> **resume**: 같은 세션 이어갈 때 `progress.md`로 미완 회차부터. `ddr_loop.py init` 재호출 시 ddr 문서 2개만 새로 덮어써지고 커밋·다른 산출물은 불변(루프 상태 리셋).

## 옵션 참고

| 인자 | 설명 |
|---|---|
| `<slug>` | forge 워크트리 slug. 생략 시 `worktree_setup.py list`→선택 |
| `--docs <doc...>` | 선택. 비교 문서 1개 이상 명시 override. 생략 시 forge-init 매니페스트의 Intent |
| `--base <ref>` | branch scope 기준 ref (기본: forge-init 매니페스트의 `base_commit`) |
| `--model` / `--effort` | codex 모델·reasoning effort passthrough |

> 고정값: 최대 3회 / 일치율 99% (forge-scope "고정 파이프라인" 철학). 변경은 build.md 수동 편집.
