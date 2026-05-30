# Claudecode-For-Me

> **Claude Code Plugin** · v2.0.0 · 커스텀 스킬 10종 + 슬래시 커맨드 13종 (외부 도구 `codenavigator` 연동, pre-commit hook 포함)

`/plugin marketplace add` 한 번으로 모든 프로젝트에서 동일한 워크플로(요구사항 정제 → 문서 하네스 → 구현 자동화 → 브랜치 리뷰 → 커밋 → C# 시맨틱 검색)를 슬래시 커맨드로 호출할 수 있게 묶은 Claude Code 플러그인이다.

---

## 1. 플러그인 개요

| 항목 | 값 |
|---|---|
| 이름 | `claudecode-for-me` |
| 버전 | `2.0.0` |
| 매니페스트 | `.claude-plugin/plugin.json` |
| 마켓플레이스 | `.claude-plugin/marketplace.json` |
| 설치 위치 | `~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<version>/` (글로벌) |
| 네임스페이스 | `/claudecode-for-me:<name>` |
| 구성요소 | Skill 10 · Command 13 · Python runner 5 (`scripts/`) |
| 외부 연동 도구 | [`codenavigator`](https://github.com/JaeCheon8587/codenavigator) (PyPI) — codenav-bootstrap / codenav-frontmatter-gen 슬래시가 호출 |

플러그인은 **글로벌 캐시**에 설치되므로 한 번 설치 후 모든 프로젝트의 **새 세션**에서 자동 노출된다. 프로젝트별 재설치 불필요.

---

## 2. 설치

타깃 프로젝트에서 Claude Code 세션 열고:

```text
# 1) 마켓플레이스 등록
/plugin marketplace add JaeCheon8587/Claudecode-For-Me

# 2) 플러그인 설치
/plugin install claudecode-for-me@claudecode-for-me

# 3) ★ Claude Code 세션 종료 후 재시작 ★
#    매니페스트는 세션 시작 시점에만 로드된다 (hot-reload 없음).

# 4) 새 세션에서 슬래시 자동완성 확인
/claudecode-for-me:meta-prompter ...
/claudecode-for-me:forge-scope ...
/claudecode-for-me:branch-review
/claudecode-for-me:codenav-bootstrap
```

CodeNavigator 슬래시 커맨드(`/codenav-bootstrap`, `/codenav-frontmatter-gen`)는 외부 PyPI 패키지 [`codenavigator`](https://github.com/JaeCheon8587/codenavigator)를 호출한다. 한 줄 설치:

```bash
pip install codenavigator
```

이후 어디서든 `codenav` CLI 사용 가능. 업데이트:

```bash
pip install -U codenavigator
```

## 3. 업데이트

```text
/plugin marketplace update claudecode-for-me
/plugin update claudecode-for-me@claudecode-for-me
```

- `plugin.json` / `marketplace.json`의 `version`이 올라가야 클라이언트가 변경을 인식한다.
- **세션 재시작 필수**. 기존 세션은 구버전 매니페스트를 그대로 보유.
- 캐시: `~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<version>/` — 구·신버전 공존 가능, 활성은 최신 1개.

### v2.0.0 — 경로 컨벤션 통일 (Breaking)

전 리소스의 디렉토리 케이싱을 소문자로 통일했다. major 승격 사유:

- **문서 경로**: `Docs/` → `docs/`, `Docs/_templates/` → `docs/.templates/`, 코드 룰은 `docs/.rules/` 하위로 정렬.
- **codenav venv 경로**: `Tools/codenavigator/` → `tools/codenavigator/` (install·bootstrap·launcher·`.gitignore`·검증 전 지점 동기).
- **codenav-install legacy 호환 제거**: 워크스페이스 `Docs/` 폴더 fallback 삭제 — 이제 소문자 `docs/` 만 인식.
- **forge 데이터 계약**: forge index/plan JSON 키 `Docs`/`Docs_scope` → `docs`/`docs_scope`, 경로 prefix 소문자화. 기존 forge 상태 파일은 비호환 → 재부트스트랩 필요.

기존 설치 워크스페이스: codenav 는 재설치 시 `tools/` 신생(Windows case-insensitive FS 는 무영향). forge 진행 중 작업은 phase 재시작 권장.

## 4. 제거

```text
/plugin uninstall claudecode-for-me@claudecode-for-me
/plugin marketplace remove claudecode-for-me
```

---

## 5. 플러그인 구성요소

### Skill 10종

| Skill | 슬래시 커맨드 | 역할 |
|---|---|---|
| `branch-review` | `/claudecode-for-me:branch-review [ref]` | HEAD↔ref diff을 Standards/Spec 2축 병렬 검토 |
| `codenav-frontmatter-gen` | `/claudecode-for-me:codenav-frontmatter-gen [--limit N] [--apply]` | C# 클래스 description 빈칸을 AI로 일괄 채워 `// ---` frontmatter 블록 삽입 |
| `doc-driven-review` | `/claudecode-for-me:doc-driven-review <doc-path>... [--worktree <ref>]` | 첨부 문서 기준 working-tree 변경을 Codex CLI로 검증. Missing/Improve/Overengineered + Conformance(%) 보고. forge-scope linked worktree 지원 |
| `docs-add-frd` | `/claudecode-for-me:docs-add-frd [요청]` | v0.7 per-App 신규 기능 FRD + ADR 생성, PRD/FC/ADR-CATALOG 갱신 |
| `docs-add-task` | `/claudecode-for-me:docs-add-task [요청]` | v0.7 per-App 기존 기능 수정 TASK + ADR 생성, FC/영향 FRD/ADR-CATALOG 갱신 |
| `forge-cancel` | `/claudecode-for-me:forge-cancel <phase>` | forge phase 브랜치·산출물 정리 |
| `forge-full` | `/claudecode-for-me:forge-full <phase>` | 문서 기반 전체 프로젝트 구현 phase runner |
| `forge-scope` | `/claudecode-for-me:forge-scope <prompt>` | 단일 FRD·기능·버그픽스용 경량 phase runner |
| `grill-me` | `/claudecode-for-me:grill-me [주제]` | 1문 1답으로 요구사항 모호점 추적 |
| `meta-prompter` | `/claudecode-for-me:meta-prompter [요청]` | 거친 요청 → 구조화된 메타 프롬프트 |

### Command 13종

| Command | 설명 |
|---|---|
| `branch-review` | branch-review skill 진입 |
| `codenav-bootstrap` | CodeNavigator parser-only 인덱싱 (frontmatter/XML doc만 읽어 SQLite 빌드, AI 호출 없음) |
| `codenav-frontmatter-gen` | codenav-frontmatter-gen skill 진입 (AI가 .cs에 frontmatter 영구 삽입). `--projects` / `--files` / `--staged` 스코프 인자 |
| `codenav-install` | 프로젝트 루트의 `tools/codenavigator/` 폴더에 codenavigator (PyPI) 격리 설치 + `codenav.ps1/codenav.sh` launcher + `.gitignore` 자동 작성 + `docs/codenav-guide.md` 작성 + 루트 `CLAUDE.md` 링크 셋업 |
| `doc-driven-review` | doc-driven-review skill 진입. Codex CLI 위임 read-only 리뷰. `--worktree <branch\|path>` 로 linked worktree 지정 가능 |
| `commit-analysis` | 변경 분석 후 `[ADD]`/`[MOD]`/`[FIX]` 자동 판단 한글 커밋 생성 |
| `docs-add-frd` | docs-add-frd skill 진입 (신규 기능 FRD + ADR) |
| `docs-add-task` | docs-add-task skill 진입 (기존 기능 수정 TASK + ADR) |
| `forge-cancel` | forge-cancel skill 진입 |
| `forge-full` | forge-full skill 진입 |
| `forge-scope` | forge-scope skill 진입 |
| `grill-me` | grill-me skill 진입 |
| `meta-prompter` | meta-prompter skill 진입 |

---

## 6. Skill 상세

### 6.1 branch-review

```
/claudecode-for-me:branch-review main
/claudecode-for-me:branch-review v1.4.0
/claudecode-for-me:branch-review          # ref 생략 시 merge-base 자동
```

- **2축 병렬**: Standards(컨벤션 준수) + Spec(요구사항 충족) 독립 서브에이전트 → masking 방지
- **3-dot diff** (`<ref>...HEAD`) — 내 변경만, ref 진행분 노이즈 제거
- **심각도 4단**: CRITICAL / MAJOR / MINOR / NIT (NIT 기본 억제)
- **TYPE**: Standards = VIOLATION/JUDGMENT, Spec = MISSING/PARTIAL/SCOPE-CREEP/FLAW
- **Diff 분기**: ≤50라인 인라인, 51~2000 표준, 초과 시 디렉토리 청크 분할
- **Spec 5층 fallback**: 이슈본문 → docs/specs → PR description → 커밋 메시지 → 부재
- **다언어**: TS/JS · Python · Go · Rust · Java/Kotlin · C#/.NET · Ruby · Swift
- **충돌**: 축간 모순 finding을 별도 "Conflicts" 섹션
- **Recommendation**: SHIP / FIX-MINOR-THEN-SHIP / FIX-CRITICAL-FIRST / BLOCK-SPEC-MISMATCH / RESOLVE-CONFLICTS / RECONFIRM-INTENT

### 6.2 codenav-bootstrap / codenav-frontmatter-gen (CodeNavigator 워크플로)

CodeNavigator는 AI 코딩 에이전트용 C# 클래스 시맨틱 인덱스. 2단계 분리:

```
# 1) AI가 description 빈 클래스에 frontmatter 영구 삽입 (.cs 파일 변경)
/claudecode-for-me:codenav-frontmatter-gen --limit 30 --apply

# 2) parser-only 인덱싱 (frontmatter + XML doc 추출 → SQLite, AI 호출 없음)
/claudecode-for-me:codenav-bootstrap [repo-root] [scan-path]
```

`codenav-frontmatter-gen` 특성:
- **dry-run 기본** — `--apply` 없이는 .cs 파일 무변경. 미리보기 후 적용.
- **git clean 강제** — uncommitted change 있으면 거부 (`--allow-dirty` 우회).
- **배치 제한** — `--limit N` (기본 50, `0` = 무제한).
- **idempotent** — 이미 XML doc 또는 frontmatter 있는 클래스는 자동 스킵.
- **삽입 형식**:
  ```csharp
  // ---
  // description: 한 줄 요약
  // tags: [tag1, tag2, ...]
  // ---
  public class Foo { }
  ```

`codenav-bootstrap` 특성:
- `codenav reindex --full --no-ai` 호출 → parser_cs가 frontmatter/XML doc만 읽음.
- `claude` CLI 부재해도 안전 (AI 호출 0).
- description 빈 클래스도 `stale=0` 으로 저장.
- 두 번째 인자로 `scan-path` 지정 시 해당 경로만 인덱싱.

CLI 직접:
```bash
pip install codenavigator   # 1회

# 1단계 (.cs 변경)
codenav --root <repo> frontmatter gen --limit 50 --apply

# 2단계 (SQLite 빌드)
codenav --root <repo> reindex --full --no-ai

# 검색
codenav --root <repo> search "키워드" --limit 30

# 대시보드 UI
codenav --root <repo> ui --port 9876
```

상세는 [codenavigator README](https://github.com/JaeCheon8587/codenavigator#readme) 및 [frontmatter 규약](https://github.com/JaeCheon8587/codenavigator/blob/main/docs/frontmatter.md) 참조.

### 6.3 docs-add-frd / docs-add-task (v0.7 per-App SSOT)

```
/claudecode-for-me:docs-add-frd 주문 검색 기능 추가
/claudecode-for-me:docs-add-task 주문 검색에 cursor 페이지네이션 추가
```

- **v0.7 per-App 전용** — `docs/.templates/App/` 양식 (20 section FRD, 5 표 FC, ADR/ADR-CATALOG/TASK)
- **In-place 수정** — source repo 직접 쓰기. preview 없음.
- **ADR 항상 강제** — FRD 또는 TASK 1개 = ADR 1개 동반 (결정 없으면 placeholder 자동)
- **/docs-add-frd**: 신규 기능 — FRD + ADR 생성, App-PRD §3.1·§7 갱신, FC 5표 행 추가, ADR-CATALOG Proposed +1
- **/docs-add-task**: 기존 기능 수정/refactor — TASK + ADR 생성, AI 가 FC 보고 영향 FRD 다수 자동 식별, 영향 FRD 변경 이력 + section 갱신, FC 상태 갱신, ADR-CATALOG Proposed +1
- **TASK 양방향 인용 금지** (v0.7) — TASK 본문 ↔ 영구 SSOT 마크다운 링크 X
- **자기 검증** — 쓰기 후 `python scripts/docs_helpers.py check --repo .` 자동
- Python helper (read-only): `python scripts/docs_helpers.py {list-apps|next-id|parse-fc|parse-frd|git-user|check}`

### 6.4 forge-full / forge-scope / forge-cancel (harness_framework 임베디드)

#### 전제 조건

| 조건 | 필수 | 비고 |
|---|---|---|
| Python 3.10+ (`python` 또는 `py -3`) | **필수** | 미설치 시 즉시 가이드 출력 후 중단 |
| `claude` CLI PATH | **필수** | child claude spawn |
| git repository | 권장 | 없으면 경고, 브랜치 자동화 실패 가능 |
| `FORGE_TRUST=1` 또는 `--trust` | **필수** | 미설정 시 child claude 즉시 종료 |

#### 환경변수

| 변수 | 설명 |
|---|---|
| `FORGE_TRUST` | `1`/`true`/`yes` — `--trust` 동일 |
| `FORGE_CLAUDE_TIMEOUT` | step 최대 시간(초). 기본 1800 |
| `ANTHROPIC_API_KEY` | `--bare` child 모드 사용 시 필수 |

#### 첫 호출 시 자동 부트스트랩

사용자 프로젝트 cwd에 **없는 것만** 복사(덮어쓰기 없음):

```
./scripts/forge_full.py
./scripts/forge_scope.py
./scripts/forge_cancel.py
./CLAUDE.md
./PHASE_SCHEMA.md
./FORGE_SCOPE.md
./docs/.templates/   (8 템플릿)
```

#### 사용 예시

```bash
# FRD 단건 구현 (권장 — splitter 우회, 토큰 절감)
/claudecode-for-me:forge-scope /docs/FRD/FRD-F003.md FRD-F003 주문 상태 API 구현

# 자유 텍스트 prompt (phase-dir 자동 도출, 확인 1회)
/claudecode-for-me:forge-scope 로그인 기능에 소셜 로그인 옵션 추가

# 전체 프로젝트 구현
/claudecode-for-me:forge-full mvp-v2 --prompt="MVP v2 전체 구현" --docs-mode=recursive --trust

# plan 미리보기 (파일·브랜치 생성 없음)
/claudecode-for-me:forge-full order-flow --plan-only --prompt="주문 흐름" --doc=docs/FRD/FRD-F009.md --trust

# 취소
/claudecode-for-me:forge-cancel login-feature --dry-run
/claudecode-for-me:forge-cancel login-feature --kind scoped
```

#### forge-scope 인자 모드

- **Mode 1 (prompt-only)**: 일반 텍스트 → phase-dir 자동 도출 + 확인 1회
- **Mode 2 (doc + prompt)**: 첫 토큰이 `docs/...md` / `/docs/...md`(대소문자 무시) → `--doc` 분리
- FRD(`docs/FRD/` 하위) → `--preset=frd-implementation --compact-docs` 자동
- 일반 문서 → `--single-step --compact-docs` 자동

#### forge-full 주요 옵션

| 옵션 | 설명 |
|---|---|
| `--prompt` | plan 생성 입력 (반복 가능) |
| `--doc` | guardrail 문서 (`docs/` 하위 `.md`, 반복 가능) |
| `--docs-mode=root\|recursive\|explicit` | 문서 인입 정책 |
| `--trust` | child claude 권한 (`FORGE_TRUST=1` 동일) |
| `--yes` | plan 자동 승인 |
| `--quiet` | 진행 표시기 억제 (Claude Code spawn 권장) |
| `--plan-only` | plan 생성·출력만 |
| `--preset=auto\|contract-tdd` | 기본 splitter / contract→red→green→regression 4-step |
| `--sln=<path>` | contract-tdd 가 사용할 .sln 경로. 미지정 시 `Src/*.sln` auto-detect (다수 시 에러) |
| `--compact-docs` | guardrail 문서 핵심 섹션 압축 주입 |

#### 한계

- `--preset=contract-tdd`는 .sln 필요. `--sln=<path>` 명시 또는 `Src/*.sln` / `Src/*/*.sln` 단일 자동 감지. 다수 sln 있으면 명시 강제.
- step timestamp **KST(UTC+9) 고정**.
- step.md 5개 헤딩 **한국어 고정**.

#### .gitignore 권장

```gitignore
phases/
```

### 6.5 grill-me

```
/claudecode-for-me:grill-me 알림 시스템 설계
```

- **1문 1답** (`AskUserQuestion`)으로 모호점 추적
- 각 질문 = 추천 2개(`(Recommended)`) + auto-`Other`
- 탐색 영역: Purpose / Scope / Success Criteria / Assumptions / Key Decisions / Constraints / Dependencies / Stakeholders / Failure Modes / Alternatives / Priorities / Execution
- **논리 모순 시 명시 지적**, 해소될 때까지 해당 가지 잔류
- 3~4 교환마다 영역별 완료 트래커
- 종료 시 Requirements Summary (영역별 + Key Decisions Q&A + Open Items + Next Steps) 후 확정 리뷰

### 6.6 meta-prompter

```
/claudecode-for-me:meta-prompter ApiGateway에 health check 엔드포인트 추가
```

- **정제기**: 단순 포매터 X — 모호 표현 challenge / 가정 표면화 / 모순 지적
- **작업 유형 자동 분류**: 기능 개발 / 리팩토링 / 문서화 / 분석 (혼합 시 주·보조 표기)
- **유형별 템플릿**: 베이스 12 항목 + 유형별 추가, 근거 있는 것만 채움 (빈 placeholder 금지)
- **필수 누락 시** 한 번에 묶어 질문(≤3개), 그 외는 합리 가정 + 메타 헤더 `추가한 가정 N개` 카운트
- **채팅 출력 전용**: 마크다운 코드블록 1개로 wrap, `.md` 저장 안 함
- 개조식 종결 강제, 출력 끝 `[에이전트 행동 규칙]` 4문구 자동 부착

### 6.7 commit-analysis

```
/claudecode-for-me:commit-analysis
```

- 구분자 자동: `[ADD]` 추가 / `[MOD]` 수정 / `[FIX]` 버그
- `.md` 자동 제외 (`git add --all` 후 `git reset -- "*.md"`)
- Co-Authored-By / "Generated with Claude Code" 문구 제외
- 한글 커밋 메시지

### 6.8 doc-driven-review

```
/claudecode-for-me:doc-driven-review docs/spec-feature.md
/claudecode-for-me:doc-driven-review docs/spec.md --wait --scope working-tree
/claudecode-for-me:doc-driven-review docs/spec.md --worktree feat-cn-foo
/claudecode-for-me:doc-driven-review docs/spec.md --worktree .worktrees/cn-foo --background
```

- **Codex CLI 위임** — 첨부 문서 기준 working-tree + untracked 변경을 codex가 리뷰. read-only.
- **산출**: Missing / Improve / Overengineered + **Conformance (0-100%)** 점수.
- **strict 상태 판정**: ✓ 모든 시그니처/literal 일치 · ⚠ 외형 맞지만 일부 누락 · ✗ literal 부재 또는 완전 부재.
- **Cross-file ripple**: public API 변경 시 patch + UNCHANGED CONTEXT(caller auto-detect) 모두 참조.
- **Weighted Conformance**: Critical=4 / Major=2 / Minor=1, ✓=full ⚠=0.5× ✗=0. `pct = round(100 × passed / total)`.
- **워크트리 지정**: `--worktree <branch|path>` — forge-scope linked worktree 또는 임의 경로 직접 리뷰. `--repo-root` 와 mutex.
- **scope**: `working-tree` (변경) / `branch` (HEAD↔base diff) / `auto` (변경 있으면 working-tree).
- **결과 파일**: `<repo>/.review/<doc-stem>-review.md`.
- **모드**: `--wait` (foreground) / `--background` (PID + log 출력). 미지정 시 변경 규모로 자동 추천.
- **dry-run**: `--dry-run`으로 codex 호출 없이 prompt만 stdout. `--keep-patch`로 디버깅용 patch 보존.

#### 한계

- Codex CLI 필수. 미설치 시 exit 2. `/codex:setup` 안내.
- patch + background log는 main repo `.git/info/` 공유 (파일명 unique로 동시 실행 안전).
- submodule / multi-repo 미지원.

---

## 7. 외부 연동 도구: codenavigator

C# 코드베이스 시맨틱 인덱스 + AI 자동 description 생성 도구. **별도 PyPI 패키지로 분리** (v1.16.0 부터). 본 플러그인은 슬래시 커맨드(`codenav-bootstrap`, `codenav-frontmatter-gen`)로 도구를 호출할 뿐, 코드는 동행하지 않음.

| 항목 | 값 |
|---|---|
| GitHub | [`JaeCheon8587/codenavigator`](https://github.com/JaeCheon8587/codenavigator) |
| PyPI | [`codenavigator`](https://pypi.org/project/codenavigator/) |
| 설치 | `pip install codenavigator` |
| CLI | `codenav` |
| DB | `<repo-root>/.codenav/index.sqlite` |

### 워크플로 (3단계)

```bash
pip install codenavigator   # 1회

cd <repo-root>

# 1. AI가 description 빈 클래스에 frontmatter 영구 삽입
codenav frontmatter gen --limit 30 --apply

# 2. parser가 frontmatter+XML doc 추출 → SQLite (AI 호출 없음)
codenav reindex --full --no-ai

# 3. 검색
codenav search "은행 계좌"
```

자세한 사용법·옵션은 [codenavigator README](https://github.com/JaeCheon8587/codenavigator#readme) 참조.

### Pre-commit hook (frontmatter 정합성)

codenavigator v1.0.5+ 는 git pre-commit hook 설치 CLI 제공. **AI 호출 없는 정적 검증** — staged `.cs` 의 frontmatter 누락/깨짐 잡음. 1초 미만.

```powershell
# tools/codenavigator/ venv 또는 글로벌 codenav 설치 후
.\codenav.ps1 --root . frontmatter install-hook              # 설치
.\codenav.ps1 --root . frontmatter install-hook --uninstall  # 제거
.\codenav.ps1 --root . frontmatter install-hook --force      # 덮어쓰기
```

hook 동작 (commit 마다 자동):
- staged `.cs` 추출 후 클래스 검사.
- **WARN** (commit 통과): frontmatter / XML doc 둘 다 없는 클래스.
- **FAIL** (commit 차단): 빈 `description:`, 잘못된 `tags:`, 닫는 `// ---` 누락, frontmatter block 안에 `description:` 라인 자체 없음.
- bypass: `git commit --no-verify`.

설치 결과:
- `.git/hooks/pre-commit` 생성/갱신. sentinel marker (`# codenav-frontmatter-hook-start`/`-end`) 로 멱등성 보장.
- 기존 hook 내용 있으면 append. 다른 도구의 hook 과 공존 가능.
- launcher `./codenav.ps1` 우선 탐지 → PATH `codenav` fallback → 둘 다 없으면 skip (commit 안 막음).

#### AI 자동 채움 옵트인

기본은 **검증만**. AI 가 commit 시점에 frontmatter 자동 채움까지 원하면:

```powershell
git config codenav.autofill true        # 영구
# 또는
$env:CODENAV_HOOK_AUTOFILL = "1"        # 현 세션
```

활성 시 hook 흐름:
1. `frontmatter check --staged` (FAIL 있으면 차단).
2. `frontmatter gen --staged --apply` (Claude CLI 호출, 빈 description 채움).
3. 수정된 `.cs` 자동 `git add`.
4. commit 진행.

비용 주의:
- commit 마다 Claude CLI 호출 → 5–30s + 토큰 비용.
- 자동 채워진 description 검토 없이 git history 에 박힘.
- claude CLI 부재 시 그냥 통과 (warning, commit 안 막음).

끄기:
```powershell
git config --unset codenav.autofill
Remove-Item env:CODENAV_HOOK_AUTOFILL
```

#### 수동 호출 (hook 외)

```powershell
# 정합성 검사만
.\codenav.ps1 --root . frontmatter check --staged             # staged 만
.\codenav.ps1 --root . frontmatter check --files Foo.cs Bar.cs
.\codenav.ps1 --root . frontmatter check --staged --strict    # WARN 도 exit 1

# AI 채움 (수동)
.\codenav.ps1 --root . frontmatter gen --staged --apply       # staged 빈 클래스 채움
.\codenav.ps1 --root . frontmatter gen --files Foo.cs --apply # 명시 파일만
```

---

## 8. 프로젝트 구조

```
Claudecode-For-Me/
├── .claude-plugin/
│   ├── plugin.json              # 매니페스트 (name·version·author)
│   └── marketplace.json         # 마켓플레이스 등록 정보
├── skills/                      # Claude Code 스킬 (자연어 트리거)
│   ├── branch-review/
│   ├── codenav-frontmatter-gen/
│   ├── doc-driven-review/
│   ├── docs-add-frd/
│   ├── docs-add-task/
│   ├── forge-cancel/
│   ├── forge-full/
│   ├── forge-scope/
│   ├── grill-me/
│   └── meta-prompter/
├── commands/                    # 슬래시 커맨드 (명시 호출)
│   ├── codenav-templates/       # /codenav-install 이 워크스페이스로 복사하는 자산
│   │   ├── CODENAV-GUIDE-TEMPLATE.md
│   │   └── codenav-prefer.ps1
│   ├── branch-review.md
│   ├── codenav-bootstrap.md
│   ├── codenav-frontmatter-gen.md
│   ├── codenav-install.md
│   ├── commit-analysis.md
│   ├── doc-driven-review.md
│   ├── docs-add-frd.md
│   ├── docs-add-task.md
│   ├── forge-cancel.md
│   ├── forge-full.md
│   ├── forge-scope.md
│   ├── grill-me.md
│   └── meta-prompter.md
├── docs/                       # v0.7 문서 시스템 자산
│   └── .templates/             # PRD/FC/FRD/ADR/ARCHITECTURE/CLAUDE/README 양식 + App/ + .rules/ (코드 룰 3종)
├── scripts/                     # Python 헬퍼·러너
│   ├── doc_driven_review.py
│   ├── docs_helpers.py
│   ├── forge_full.py
│   ├── forge_scope.py
│   ├── forge_cancel.py
│   └── forge_templates/         # forge 부트스트랩 리소스
├── tests/                       # pytest 스위트 (forge·docs·doc-driven-review)
├── samples/                     # (gitignored) 로컬 C# 테스트 픽스처 — 미커밋
├── .gitattributes
├── .gitignore
└── README.md
```

---

## 9. 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| install 직후 슬래시 자동완성에 안 보임 | 매니페스트는 세션 시작 시 1회 로드 | 세션 종료 → 재시작 |
| update 후 신규 스킬 호출 불가 | 동일 — 캐시는 갱신됐으나 세션은 구버전 보유 | 세션 재시작 |
| `/claudecode-for-me:forge-*` 실행 즉시 종료 | `FORGE_TRUST` 미설정 | `FORGE_TRUST=1` 또는 `--trust` |
| `docs-add-frd` / `docs-add-task` "App 0건" | `/CLAUDE.md` Backend Services Overview 표 + `docs/<App>/` 부재 | App 행 추가 + 폴더 부트스트랩 |
| `codenav frontmatter gen` 결과 `generated=0` | `claude` CLI 부재 또는 stdout JSON 키 mismatch | `where claude` 확인. v1.15.0+ 는 `result`/`response` 둘 다 처리 |
| `codenav frontmatter gen` "git working tree is dirty" 거부 | 안전장치 | commit/stash 또는 `--allow-dirty` |
| `codenav ui --port 8765` 실행 시 `WinError 10013` | Windows excluded port range (8601-8900 등) | 다른 포트 사용 (예: `--port 9876`). `netsh interface ipv4 show excludedportrange protocol=tcp` 로 확인 |
| `codenav reindex` 후 description 절반 빔 | XML doc/frontmatter 양쪽 모두 없는 클래스 | `/codenav-frontmatter-gen --apply` 로 AI 자동 채움 |
| `codenav search` "No results" 인데 항목 존재 | 과거 AI 실패로 `stale=1` 마킹 + 검색 필터 | v1.15.0+ 는 description 있으면 stale도 노출. `reindex --no-ai` 로 stale 해소 |
| `codenav frontmatter gen --files` 매칭 안 됨 | `--root` 와 `--files` 경로 중첩 | `--files` 는 `--root` 기준 상대경로 또는 절대경로 |
| pre-commit hook 이 commit 안 막음 | codenav CLI 부재 → hook 자동 skip 안전장치 | `tools/codenavigator/` venv 또는 글로벌 `pip install codenavigator` |
| pre-commit hook 매 commit `[FAIL]` | staged `.cs` 의 frontmatter 깨짐 (빈 description, 잘못된 tags, 닫는 `---` 누락) | `codenav frontmatter check --staged` 로 디버그 후 수정. 우회는 `--no-verify` |
| `git config codenav.autofill true` 했는데 자동 채움 안 됨 | claude CLI PATH 부재 또는 인덱스 stale | `where claude` 확인. autofill 은 안전상 실패 시 통과 (commit 진행) |

---

## 10. 라이선스

MIT
