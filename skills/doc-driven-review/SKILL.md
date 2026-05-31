---
name: doc-driven-review
description: 첨부 문서가 현재 코드 변경점(working-tree + untracked)에 반영됐는지 Codex 위임으로 검증. 누락/개선/오버엔지니어링/일치도(%) 보고. "문서 기준 리뷰", "spec 반영 확인", "이 문서대로 만들었는지 codex로 확인", "doc-driven-review", "DDR" 요청 시 트리거.
argument-hint: "<doc-path> [추가 doc-path...] [--wait|--background] [--scope working-tree|branch] [--commit <ref>] [--base <ref>] [--model <name>] [--effort <level>]"
---

# Doc-Driven Review

첨부 문서를 기준으로 현재 변경점(working-tree + untracked)을 Codex가 검증한다.
산출물: **Missing** / **Improve** / **Overengineered** + **Conformance(%)**.

## 실행 환경

- **Codex CLI 필요** — `codex --version` 동작해야 함. 없으면 Step 5에서 `/codex:setup` 안내.
- Git 레포 안에서만 동작.
- Python 3.9+ — forge-* 스킬과 동일 의존.

---

## Process

### Step 1 — 인자 트리아지

`$ARGUMENTS`에서 분리:

- **doc 경로**: `--`로 시작 안 하는 토큰 (보통 `.md` / `.txt` / `.rst` / `.adoc` 확장자)
- **flags**: `--wait`, `--background`, `--scope <kind>`, `--commit <ref>`, `--base <ref>`, `--model <name>`, `--effort <level>`, `--dry-run`, `--keep-patch`, `--verbose`

doc 경로 0개 → 아래 안내 후 종료:
```
문서 경로 필수. 예: /claudecode-for-me:doc-driven-review docs/feature.md
```

### Step 2 — Doc 미리 검증

각 doc 경로에 대해 `Read` 호출:
- 파일 없음 → `"오류: 문서 파일 없음: <path>"` 보고 후 종료.
- 합산 200KB 초과 시 경고 + `AskUserQuestion` ("진행" / "중단") — `DocTooBigError`는 Python이 처리하지만 사전에 경고.

### Step 3 — 실행 모드 결정

> `--commit <ref>` 가 있으면 scope 결정(working-tree/branch)을 건너뛰고 그 커밋 diff 를 대상으로 한다 (`--scope`/`--base` 무시). no-worktree forge 처럼 변경이 이미 커밋된 경우 `feat` 커밋 sha 를 지목해 그 노드만 doc 과 대조.

인자에 `--wait` → **foreground** (Python에 flag 미전달).
인자에 `--background` → **background** (`--background` Python에 전달).
둘 다 미명시:
- `git diff --shortstat` + `git diff --shortstat --cached` 측정.
- `git status --short --untracked-files=all` 라인 수 확인.
- 합산 변경 라인 **>500** 또는 변경 파일 **>10** → background Recommended.
- 그 외 → foreground Recommended.
- `AskUserQuestion` 1회 ("Wait for results" / "Run in background"). 두 옵션만.

### Step 4 — Python 스크립트 호출

```bash
python scripts/doc_driven_review.py \
  --docs <p1> [<p2>...] \
  [--scope <kind>] \
  [--base <ref>] \
  [--model <name>] \
  [--effort <level>] \
  [--background]
```

- `--wait` (또는 결정 후 foreground): `Bash` 일반 호출.
- `--background` (또는 결정 후 background): 스크립트가 자기 자신을 **foreground로 detached 재실행**한다 (child가 codex→스키마검증→인용검증→`.review/` 저장 전 과정 수행). `Bash` 일반 호출로 충분 — 스크립트가 즉시 PID+Log 경로를 출력하고 반환한다. 사용자에게 안내:
  ```
  Codex 리뷰가 백그라운드에서 시작됐습니다.
  완료 후 처리된 리뷰(스키마검증·Conformance·인용검증 포함)가 Log 경로와 .review/ 에 저장됩니다.
  ```

### Step 5 — 출력 처리

Python 스크립트 종료 코드별 대응:

| exit code | 처리 |
|---|---|
| **0** | stdout verbatim 노출. `[doc-driven-review] OUTPUT-SCHEMA-VIOLATION:` 라인 있으면 그대로 노출 (가공 금지). |
| **2** | `"Codex CLI 미설치. \`/codex:setup\`을 먼저 실행하세요."` |
| **3** | `"리뷰할 변경 없음. working-tree와 branch 모두 비어있습니다."` |
| **4** | `"첨부 문서 합계 200KB 초과. 더 작은 문서로 분할하거나 한 번에 하나씩 사용하세요."` |
| **5** | `"\`--base <ref>\` 존재하지 않습니다. ref 확인 또는 --base 미지정으로 재시도하세요."` |
| **6** | `"--worktree 해석 실패. branch명 또는 유효 경로인지 확인. \`git worktree list\` 로 등록 워크트리 확인하세요."` |
| **1** | stderr 그대로 노출 + `"스크립트 실행 오류. \`--verbose\` 옵션 추가 후 재시도하면 상세 로그를 확인할 수 있습니다."` |
| **130** | `"사용자 중단."` |

---

## 트리거 문구 예시

- `"이 문서대로 만들었는지 codex로 확인"`
- `"spec 반영됐는지 검토해줘"`
- `"docs/feature.md 기준으로 변경점 리뷰"`
- `"문서 기준 리뷰"`
- `"doc-driven-review docs/design.md"`
- `"DDR docs/x.md --wait"`
- `"doc-driven-review docs/spec.md --worktree feat-foo"`
- `"forge-scope 워크트리 spec 반영 확인"`

---

## 옵션 요약

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--wait` | — | 결과 기다림 (foreground) |
| `--background` | — | 백그라운드 실행 |
| `--scope auto\|working-tree\|branch` | `auto` | 리뷰 범위 |
| `--worktree <branch\|path>` | — | 대상 워크트리 지정. branch명 또는 경로. linked worktree(forge-scope) 사용 시 권장. `--repo-root` 와 mutex |
| `--base <ref>` | 자동 추정 | branch scope 기준점 |
| `--commit <ref>` | — | 특정 커밋(또는 `A..B` 범위) 지목. 그 변경분만 doc 대조. working-tree/branch·`--base` 우회. no-worktree forge 산출(현재 브랜치 커밋) 검토에 유용 |
| `--model <name>` | 기본 | codex 모델 선택 |
| `--effort minimal\|low\|medium\|high\|xhigh` | 기본 | codex 추론 수준 |
| `--dry-run` | — | Codex 미호출, 생성 프롬프트만 출력 |
| `--keep-patch` | — | .patch 파일 보존 (디버깅) |
| `--verbose` | — | 상세 로그 |
| `--no-auto-context` | — | Caller 자동 탐지 비활성. cross-file ripple 분석 약화 |

---

## 출력 형식 (Codex 산출물 — v1.2)

```markdown
# Code Review: <doc-stem>

## Summary
- **무엇을 하는 코드인지**: 2-3줄
- **핵심 문제**: 2-3줄
- **핵심 장점**: 1-2줄 (없으면 `- (none)`)

## Severity 기준
- **Critical** / **Major** / **Minor** / **Suggestion** 정의 포함

## Requirements Coverage
| § | 요구사항 | 상태 | 코드 위치 | 비고 |
|---|---|---|---|---|
| 1 | ... | ✓/⚠/✗ | file:line | ... |

## Top Priorities
1. [SEVERITY] 제목 — 영향도 (최대 5개)

## Review Comments

### 1. [SEVERITY] 제목

**Location** / **Issue** / **Why it matters** / **Suggestion** / **Example** (코드 블록)

(severity 내림차순. 최대 20개)

## Overengineered (문서 범위 밖)
| 항목 | 코드 위치 | 설명 |

## Conformance
Counts: Critical: <N>, Major: <M>, Minor: <K>, Suggestion: <S>
<2-3줄 rationale>

Conformance: <0-100>%
```

- `SEVERITY`: `CRITICAL` | `MAJOR` | `MINOR` | `SUGGESTION`
- Requirements Coverage 상태: `✓` 충족 / `⚠` 부분 / `✗` 미구현
- Overengineered 없으면 `- (none)` 한 줄
- Example: 반드시 fenced 코드 블록 + 언어 힌트

### v1.2.1 강화 규칙 (Codex가 따라야 할 추가 제약)

- **Exact-string fidelity**: 문서 명시 literal(예외 메시지, 출력 포맷, 타입명, namespace)은 Issue + Example에 verbatim 인용. paraphrase/번역 금지.
- **Cross-file ripple**: public API 변경(namespace 이동/시그니처/타입명/멤버 추가삭제) 시 patch 내 모든 caller `file:line` 나열. patch에 caller 없으면 `No callers in patch` 명시.
- **Compilable Example**: Example 코드는 standalone 컴파일 가능해야 함 — `using`/`import`/`#include` 포함 + 최소 클래스/함수 wrapper.
- **비고 column (Requirements Coverage)**: ⚠/✗ 행은 (a) 위반 doc clause + (b) 누락/잘못된 literal을 ≤120자로 인용. ✓ 행은 ≤40자 sanity note.
- **Conformance 가중치 산식**: Critical=4 / Major=2 / Minor=1. ✓=full, ⚠=0.5×, ✗=0. `pct = round(100 × passed / total)`. Rationale에 산식 표시 의무.

### v1.2.2 강화 규칙

- **상태 기호 판정 기준 (엄격)**:
  - `✓` 모든 시그니처/literal/타입/예외 일치
  - `⚠` 외형은 맞지만 일부 로직 누락 — **literal 누락 시 ✗**
  - `✗` 완전 부재, 정반대 동작, literal 부재
  - 의심 시 더 엄격한 쪽 선택.
- **연관 요구 통합**: 같은 메서드/심볼의 sub-요구는 한 Requirements Coverage 행으로 묶기. 상태는 가장 나쁜 것 우선. weight 이중 가중 방지.
- **Overengineered 범위 제한**: 빌드(`*.csproj`, `package.json`...), VCS 설정(`.gitignore`, `.editorconfig`), CI(`.github/`), IDE(`.vscode/`)는 Overengineered 분류 제외. 신규 public API surface만 해당.
- **Caller auto-detect (`# UNCHANGED CONTEXT` 섹션)**:
  - changed 파일에서 식별자(클래스/네임스페이스/메서드명) 추출
  - `git grep --fixed-strings`로 unchanged 호출자 검색
  - 최대 10 파일 / 100KB / 단일 파일 20KB head 까지 프롬프트 주입
  - `--no-auto-context`로 비활성
  - Cross-file ripple 분석 시 patch + UNCHANGED CONTEXT 모두 참조

### 인용 검증 (Python 후처리)

- Codex 출력의 인용 `file:line` (Requirements Coverage 코드 위치 + Review Comments Location)을 **Python이 repo에 대조**한다.
- 파일 부재 또는 라인 범위 초과 시 출력·`.review/` 에 `[doc-driven-review] CITATION-CHECK: N건 미검증 — …` 라인 추가 (advisory, exit code 불변).
- `MISSING`/`No callers` 등 비-경로 표기는 자동 제외. 정적 검증(파일 존재 + 라인 수)만 — 의미적 정확성은 보장 안 함.
- background 모드도 동일 후처리 거침(fg와 동등).

---

## 한계

- **Codex CLI 의존** — 미설치 시 exit 2.
- **출력 schema soft enforce** — 프롬프트 엄격화 + Python validator. Codex가 schema 위반하면 verbatim + `[OUTPUT-SCHEMA-VIOLATION: ...]` 라인 추가 (재호출은 사용자 판단).
- **인용 검증은 정적** — 파일 존재 + 라인 수만 확인. 인용이 의미적으로 옳은지(해당 라인이 실제 그 코드인지)는 미보장.
- **50,000라인 초과 경고** — 단일 청크 + 경고 출력. 분석 정확도 낮을 수 있음.
- **background = detached foreground** — fg와 동일 산출(스키마검증·`.review/`·Conformance·인용검증). 부모는 PID+log 즉시 반환. 오래된 bg 로그·stale patch 는 7일 경과 시 자동 정리. `/codex:status` 비호환 — 자체 PID + log 파일 추적.
- **read-only** — 자동 수정 안 함.
- **단일 레포만** — submodule / multi-repo 미지원.
