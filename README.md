# Claudecode-For-Me

> **Claude Code Plugin** · v3.7.0 · 커스텀 스킬 13종 + 슬래시 커맨드 17종 (외부 도구 `codenavigator` 연동, pre-commit hook 포함)

`/plugin marketplace add` 한 번으로 모든 프로젝트에서 동일한 워크플로(요구사항 정제 → 문서 하네스 → 구현 자동화 → 문서 기준 수렴 검증 → 브랜치 리뷰 → 커밋 → C# 시맨틱 검색)를 슬래시 커맨드로 호출할 수 있게 묶은 Claude Code 플러그인이다.

---

## 1. 플러그인 개요

| 항목 | 값 |
|---|---|
| 이름 | `claudecode-for-me` |
| 버전 | `3.7.0` |
| 매니페스트 | `.claude-plugin/plugin.json` |
| 마켓플레이스 | `.claude-plugin/marketplace.json` |
| 설치 위치 | `~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<version>/` (글로벌) |
| 네임스페이스 | `/claudecode-for-me:<name>` |
| 구성요소 | Skill 13 · Command 17 · Python helper 6 (`scripts/`) |
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

### v3.8.0 — 구조 검증 서브에이전트 Sonnet 다운시프트

read-only 서브에이전트 중 **구조 검증·체크리스트·규칙 대조** 성격의 작업을 `model: "sonnet"`으로 내려 비용·지연을 줄였다. 대상: `work-packet-write`·`task-write` Phase 5 auditor, `ssot-write` Phase 5 consistency auditor, `branch-review` **style** finder. 정확성·보안 추론(`branch-review` bugs finder)과 아키텍처 영향 판단(`ssot-write` Phase 3 impact auditor)은 미탐·오판 비용이 커 세션 모델(Opus)을 그대로 유지한다. Task/Agent 도구는 per-call `effort`를 지원하지 않으므로 effort는 세션 값을 상속한다 — 최고 effort가 필요하면 해당 스킬을 high/max effort 세션에서 실행한다. `subagent_type`(예: `general-purpose`)은 그대로 두고 model 오버라이드만 추가하므로 기존 동작과 backward-compatible.

### v3.7.0 — branch-review 4 finder 재설계 + 영속화(.process/.review) + 실전 dogfood 하드닝

`branch-review`를 Standards/Spec 2축에서 **bugs/style/spec/perf 4개 독립 병렬 finder**로 재편하고, ssot-write와 동일한 관례(`templates/` + `.process/<slug>/` build·progress 문서)를 이식했다. 기존 Standards 축 하나가 정확성·컨벤션·성능 3종 판단을 동시에 져 관점이 희석되던 문제를 분해로 해결 — security는 별도 축 없이 bugs finder의 SECURITY-SURFACE 표면검사로 흡수(심층은 `/security-review`), style finder에 Standards 신뢰도 등급(STRONG/WEAK/NONE)을 신설해 Spec 축(HIGH~NONE)과의 비대칭을 해소했다. 4 finder 프롬프트를 SKILL.md 인라인 텍스트에서 `skills/branch-review/templates/*-finder.md` 6개 파일(finder 4종 + build/progress 2종)로 분리. CRITICAL/MAJOR는 400단어 cap 없이 전량 보고, Recommendation은 임의 축 CRITICAL을 최우선으로 하는 6단 precedence 규칙으로 명문화. 신규 Step 0가 `git rev-parse --short HEAD`를 slug로 `.process/branch-review-<slug>/`(build.md+progress.md)를 관리하고, Step 6이 최종 보고 전문을 `.review/branch-review-<slug>.md`에 저장하며 `--resume` 플래그로 중단된 청크 모드 리뷰를 재개한다. spec 문서는 위치 인자와 혼동하지 않도록 `--spec <path>`로 명시한다. read-only 계약은 "소스 파일 미수정"으로 명확화(산출물 쓰기는 계약 밖, doc-driven-review 선례와 동일).

실전 dogfood 테스트(150파일/9천+줄 diff, 청크 모드 36 서브에이전트 실제 발사)로 4건의 구조적 gap을 추가 수정했다. **(1)** 신규 `scripts/branch_review_chunk_plan.py` — Step 2 diff 크기측정·모드판정·청크분할·청크별 patch 생성을 스크립트로 결정화. `git diff --numstat`의 rename 압축표기(`{old => new}`)를 그대로 pathspec에 쓰면 매칭이 조용히 실패하는 버그를 `--no-renames`로 근본 해결(rename은 삭제+추가 별도 라인으로 분리 집계 — `--stat` 대비 파일/라인 수 차이는 정상 동작). 산출물 디렉터리 제외는 top-level `dist/build/out/node_modules`만 적용해 `src/build/*` 같은 소스성 경로 오탐 제외를 피하고, 단일 파일이 청크 라인 cap을 넘는 경우 `Warnings`에 남긴다. **(2)** Step 5에 **"5-0. Cross-chunk 재검증"**(청크 모드 전용, 필수) 신설 — 청크가 서로의 diff를 못 보는 구조적 맹점으로 인한 spec/bugs 오탐(실전에서 CRITICAL 오탐 2건 실측)을 메인 에이전트의 Grep/Read 재확인으로 걸러내고 REFUTED 근거를 투명하게 남긴다(전체 대상 adversarial verify는 여전히 미구현 — Step 4.5 슬롯 참조). **(3)** 청크별 finder raw 출력을 progress.md에 verbatim 인라인하던 스펙을 `.process/branch-review-<slug>/chunk-<id>.log` 개별 파일 저장으로 현실화(대형 diff에서 원본 스펙은 비현실적이었음) — progress.md Log는 경로 참조+요약만 보유. **(4)** 청크 모드 진입 전 "청크 N개 × 4 finder = M개 서브에이전트 발사 예정" 비용 고지를 필수화하고, Step 6-2 Summary에 CRITICAL findings 전체 목록(축 무관)을 필수 추가해 Recommendation의 1등급 라벨 뒤에 다른 축 CRITICAL이 가려지는 정보손실을 보완했다.

### v3.5.0 — docs-add-task 폐지 (task-write/ssot-write/work-packet-write 트리오로 대체)

`docs-add-task`(TASK+FRD+FC+ADR+PRD+ADR-CATALOG 단일 upsert monolith)를 제거했다. `task-write`(TASK 작성) → `ssot-write`(영구 SSOT 갱신) → `work-packet-write`(forge 입력 Work Packet 생성) 트리오가 동일 범위를 책임 분리해 완전 대체하며 forge 입력 단계까지 확장한다. `docs/DEVELOPMENT_PIPELINE.md` step3을 트리오 3단 체인으로 재배선했다. 공유 helper(`docs_helpers.py`·`docs_conformance.py`)는 task-write/ssot-write가 계속 사용하므로 보존.

### v3.4.5 — ddr-loop Work Packet docs 자동 구성

`ddr-loop`가 Work Packet 기반 `forge-scope` 산출물을 직접 소비한다. `--docs`를 생략하면 `.process/<slug>/forge-scope-build.md`의 Work Packet 경로를 읽고, Work Packet + 연결 TASK + `Required SSOT Execution Matrix`의 Required 문서를 `doc-driven-review` 비교 docs로 자동 구성한다. 명시 `--docs <doc...>`는 override로 유지하며, legacy TASK 기반 forge-scope처럼 Work Packet이 없으면 자동 구성을 중단하고 docs 명시를 요구한다.

### v3.4.4 — forge-scope Work Packet gate/output contract 소비

`forge-scope`를 Work Packet 우선 구현 경로로 강화했다. `/forge-scope <WORK_PACKET>` 입력 시 `Ready` 상태만 워크트리를 만들고, `Draft = do not implement`, `Blocking / Open Questions`, 연결 TASK 링크, `Required SSOT Execution Matrix`의 Required 문서 링크/파일 존재를 init 단계에서 차단한다. build 템플릿은 Work Packet + TASK + Required SSOT 입력으로 범위를 채우며, 완료 보고는 `Implementation Output Contract`(`Changed files`, `Scope match`, `Tests run`, `Not run`, `Deviations`) 형식으로 고정한다. `/forge-scope <TASK>` 직접 입력은 legacy 호환으로 유지하되 Work Packet 기반 SSOT gate는 적용되지 않는다.

### v3.4.2 — work-packet-write 실행 gate/output contract 강화

`work-packet-write`의 Work Packet 템플릿에 `Execution Gate`와 `Implementation Output Contract`를 추가했다. `Draft`는 후속 구현 금지 상태로 명확히 쓰고, `Ready`는 blocking 없음·Required SSOT target path 존재·구현 범위 명확 조건을 만족할 때만 허용한다. `CREATE/UPDATE target path` 누락 또는 파일 미존재는 임의 링크 대신 `Draft + Blocking / Open Questions`로 기록하며, Phase 5 auditor는 expected matrix와 observed Work Packet matrix를 동일 컬럼 표로 비교한다.

### v3.4.1 — work-packet-write matrix/auditor contract 강화

`work-packet-write`의 Work Packet 템플릿을 `Required SSOT Execution Matrix` 중심으로 보강하고, `ssot-write`의 `Confirmed SSOT Action Matrix`와 `Source matrix row`를 끝까지 추적하도록 했다. `Blocking / Open Questions`를 별도 섹션으로 분리하고, Phase 5 auditor 입력/출력을 expected/observed/fix 구조로 강화했다.

### v3.4.0 — work-packet-write 추가 (forge 입력 manifest 생성)

`ssot-write` 이후 단계인 `work-packet-write`를 추가했다. 완성된 TASK와 `ssot-write`의 `Confirmed SSOT Action Matrix`를 읽어 `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md` 실행 manifest 하나만 생성한다. Work Packet은 Context Router 역할만 하며 TASK/SSOT 본문을 길게 복제하지 않고, Required SSOT 링크·읽을 범위·실행 경계·검증 입력을 정리한다. `docs_helpers.py next-id`에 `wp`/`work-packet` 번호 산출을 추가하고 read-only Phase 5 auditor 템플릿 및 테스트를 포함했다. 다음 단계는 `forge-scope`.

### v3.3.0 — task-write / ssot-write 분리 파이프라인 추가

`task-write`와 `ssot-write`를 추가해 기존 `docs-add-task`의 대형 문서 upsert 흐름을 두 단계로 분리했다. `task-write`는 요구사항 문서나 자연어 요청에서 TASK 작업 범위 계약만 생성하고 영구 SSOT는 분석·수정하지 않는다. `ssot-write`는 완성된 TASK를 Scope Authority로 삼아 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE를 좁게 갱신하며, read-only impact auditor의 SSOT 종류별 matrix를 Phase 3의 `Confirmed SSOT Action Matrix`로 승격한 뒤 consistency auditor에 전달한다. 관련 커맨드, auditor 템플릿, process build/progress 템플릿, 테스트를 함께 추가했다.

### v3.2.1 — docs-add-task helper 경로 CLAUDE_PLUGIN_ROOT fallback (Phase 13 silent-skip 버그 수정)

`docs-add-task` 만 helper 를 프로젝트-상대(`python scripts/docs_helpers.py`)로 호출해 — forge-scope·ddr-loop·doc-driven-review 가 쓰는 `${CLAUDE_PLUGIN_ROOT}/scripts/` 컨벤션을 벗어나 있었다. v3.0.1 부트스트랩 복사 폐지 이후 소비자 repo 에 스크립트가 없어 두 가지 실패: ① 로컬 사본 없는 repo 는 Phase 0 에서 즉시 file-not-found 하드 실패. ② `docs_conformance.py` 미복사 repo 는 Phase 13 가 file-not-found(python exit 2)를 "codex 미설치"로 **오인해 요구사항 정합 검증을 통째로 silent skip**(검증한 적 없는데 "생략"으로 위장). doc-driven-review 와 동일한 fallback(`[ -f ./scripts/X ] || X="${CLAUDE_PLUGIN_ROOT}/scripts/X"`)을 SKILL 사전 준비 절에 도입하고 Phase 0·2·3·12·13 의 helper 호출 6곳을 `$HELP`/`$CONF` 로 전환. cwd 는 소비자 repo 유지(helper 는 `--repo .` 기반). 로컬 사본도 항상 플러그인 최신본으로 대체돼 stale drift 방지. SKILL·README 만 변경 — 스크립트 코드 무수정.

### v3.2.0 — ddr-loop 재도입 (build-process 인라인 수렴 루프)

문서↔코드 수렴 루프 `ddr-loop`을 forge-scope과 동일한 build-process 방식으로 재도입. forge-scope 워크트리(feat-<slug>) 브랜치의 변경점을 명시 docs와 doc-driven-review(codex)로 대조해 일치율(Conformance%)을 매기고, 미달 항목을 **현재 세션이 워크트리 안에서 인라인 수정**·재검한다. **최대 3회, 일치율 99% 도달 시 정지**. reviewer=codex / fixer=세션(구버전의 ClaudeInvoker 자식 spawn 폐지). 빌드/테스트는 **대상 프로젝트(.csproj)만, 솔루션(*.sln) 금지**. 회차마다 `fix(ddr-<slug>)` 커밋. 신규 얇은 helper `scripts/ddr_loop.py`(init만 — 워크트리·docs 검증 + .process 스캐폴딩, `.process/<docName>/`를 rmtree하지 않아 forge-scope 산출물 보존)·템플릿 `scripts/ddr_templates/ddr-loop-{build,progress}.md`. 리뷰는 기존 `doc_driven_review.py`, slug 선택은 `worktree_setup.py list`, 정리는 `/forge-cancel` 재사용(ddr 전용 cancel 없음).

### v3.1.0 — forge-cancel 커맨드 신설 (워크트리·브랜치 정리, 서브모듈 보존)

워크트리 정리를 forge-scope에서 분리한 독립 커맨드 `/claudecode-for-me:forge-cancel` 신설. `forge-scope`는 개발(create) 전용, 정리는 forge-cancel이 담당. **다중 워크트리 전제** — `/forge-cancel <slug>` 면 그 워크트리+`feat-<slug>` 브랜치 제거, **인자 없으면** forge 워크트리 목록을 제시하고 선택받아 제거. `worktree_setup.py`에 `list` 서브커맨드(`.worktree/*` + `feat-*` 워크트리를 JSON으로 나열) 추가. **서브모듈 메인 원본 절대 보존** — cancel은 워크트리 junction/symlink 링크만 해제(안 하면 `git worktree remove`가 junction 따라 메인 서브모듈을 삭제하는 사고)하고, 기존의 `git submodule deinit`은 제거해 메인 repo 서브모듈 상태를 일절 건드리지 않는다. 커맨드 전용(스킬 없음). forge-scope SKILL에서 cancel 분기 제거 → forge-cancel로 위임.

### v3.0.1 — forge-scope 부트스트랩 폐지 (플러그인 캐시에서 직접 실행)

`worktree_setup.py`·템플릿을 사용자 프로젝트로 **복사하지 않는다**. helper는 cwd(메인 repo)에서 동작하고 템플릿은 helper 옆에서 읽으므로 `${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py`를 직접 실행하면 충분 — 앱 repo 히스토리에 forge 도구를 남기지 않는다. SKILL 단계2(복사+커밋)를 폐지하고, `.gitignore`에 워크트리·상태 생성물(`.worktree/`·`.process/`)만 추가하도록 정리. (구 v3.0.0은 forge 도구 3파일을 프로젝트에 복사·커밋했음.)

### v3.0.0 — forge-scope 전면 재설계 (얇은 worktree_setup helper + 완전 인라인 TDD) · BREAKING

`forge-scope` 를 **고정 계약-TDD 파이프라인 + 완전 세션 자율** 모델로 재설계. 기존 `forge_scope.py`(3408줄, 오케스트레이터·step splitter·`--scaffold-only`/`--record-step`/`--finalize` 상태머신·하드 강제 게이트)를 폐기하고, **얇은 `scripts/worktree_setup.py`** 로 대체한다. `worktree_setup.py` 는 **셋업·검증·정리만** 담당 — 워크트리 생성, 서브모듈 링크, 가드레일 복사, 미결 항목 검증 게이트(1개), `.process` 스캐폴딩, `cancel <slug>` teardown. **실제 코딩(계약→테스트→구현→빌드/유닛테스트)은 호출 세션이 워크트리 안에서 인라인**으로 수행 — step별 자식 `claude` spawn·백그라운드 폴링·python 하드 게이트 제거. TDD 순서·단계별 atomic commit·테스트 통과는 세션이 신규 `scripts/forge_templates/forge-scope-build.md`·`forge-scope-progress.md` 를 따라 self-discipline 으로 지킨다. 빌드/테스트는 솔루션(`*.sln`) 금지, 대상 `.csproj` 단위만.

**BREAKING — 제거**: `forge-full`·`forge-cancel`·`ddr-loop` 의 command·skill·script 전부 삭제 (`forge_full.py`·`forge_cancel.py`·`ddr_loop.py`·구 `forge_scope.py`·`test_forge_scope.py`·`forge_templates/FORGE_SCOPE.md`·`PHASE_SCHEMA.md`, 총 7091 라인 삭제). `forge-cancel` 은 `forge-scope cancel <slug>` 서브커맨드로 흡수. 기존 `forge-full`/`ddr-loop` 워크플로 의존 사용자는 v3.0.0 에서 동작 안 함 — 재설계된 `forge-scope` 로 이전 필요. **세션 재시작 필수** (구버전 매니페스트가 삭제된 스킬을 그대로 보유).

### v2.17.0 — forge-scope 워크트리 복사 폐지 (읽기 ROOT / 쓰기 worktree)

`forge-scope` 인라인 모드에서 워크트리로의 `CLAUDE.md`·`docs/`·`PHASE_SCHEMA.md`·`FORGE_SCOPE.md`·`.claude/rules` **부트스트랩 복사를 통째로 제거**(`_verify_worktree_bootstrap` 삭제). 인라인 전환(v2.16.0) 이후 step 코딩은 호출 세션(cwd=ROOT)이 직접 수행하고, 워크트리는 `ROOT/.worktrees/...`로 ROOT 하위에 중첩돼 있어 가드레일·docs는 **ROOT(source-of-truth)에서 직접 읽으면 충분**하기 때문. 복사가 만들던 문제 3종 제거 — **동시 실행 시 중복 복사**, **docs staleness**(이미 채워진 워크트리 docs 재복사 안 함 → ROOT 수정이 반영 안 되던 것), **읽기 출처 이원화**. `forge_scope.py` 의 docs/CLAUDE.md 읽기 경로 7곳을 `self._cfg.root`(워크트리)→`ROOT`로 전환(`GuardrailLoader`·`ScopeValidator`·`StepSplitter`·`_project_name`·`_check_frd_consistency`). 두 모드 공통 가드 `_verify_root_guardrail`(ROOT에 `CLAUDE.md` 존재만 확인)로 일반화(기존 `_verify_inplace_bootstrap` 대체). scaffold 매니페스트에 `root` 절대경로 필드 추가 — 인라인 세션이 읽기 출처를 명시적으로 받음. 격리는 불변(코드 쓰기는 worktree, 커밋은 feat 브랜치, 누수 가드는 git porcelain 기반이라 read-only는 무영향). **forge-full은 자식 claude(cwd=worktree) 의존이라 복사 유지 — 영향 없음.** SKILL.md §3/§5 와 `FORGE_SCOPE.md` 를 "읽기 ROOT / 쓰기 worktree" 모델로 정합.

### v2.16.0 — forge-scope 인라인 실행 전환 (step 콜드스타트 제거)

`forge-scope` 의 step 실행을 **자식 `claude` 프로세스 spawn → 호출 세션 인라인**으로 전환. 간단 작업이 느린 본체였던 step별 프로세스 콜드스타트(CLI boot·세션 init·툴 등록)·백그라운드 폴링을 제거한다. 워크트리 격리·TDD 4-step·step별 atomic commit·index 상태머신은 **그대로 유지** — python 이 결정적 골격을 강제하고 step 코딩만 세션이 맡는다. `forge_scope.py` 신규 플래그 3종: `--scaffold-only`(워크트리·plan·warmup 까지 + step 매니페스트 JSON 출력 후 종료), `--record-step=N`(사후가드[메인repo 누수·워크트리 무변경]→attempt counter→TDD 순서 gate→status ingest→2단계 commit), `--finalize`(phase 마감). `--max-attempts`(기본 3) 하드 백스톱으로 무한 재작업 차단. 격리는 record-step 사후가드 — 인라인 세션이 메인 repo 에 누수하면 scaffold 시점 `root_dirty_baseline` 대비 탐지해 abort. **하위호환 보존**: `ClaudeInvoker`·`DEFAULT_CHILD_TOOLS`·`StepExecutor`·`StepSplitter` 및 child 실행 경로·`--preset=auto` splitter 는 그대로 유지(`ddr_loop.py`·`forge_full.py` 의존). 큰 작업은 `forge_full.py`(자식+백그라운드)로 라우팅. SKILL.md 는 foreground 인라인 루프(scaffold→가드레일 read→step 코딩·AC·record→finalize)로 재작성, `run_in_background`·Monitor·폴링 지침 제거. `scripts/test_forge_scope.py` 신규(인라인 경로 통합 테스트 10종).

### v2.15.0 — forge-scope 워크트리 부트스트랩에 `.claude/rules` 추가 (룰 본문 누락 수정)

`forge-scope` 가 워크트리 생성 시 main→worktree 로 복사하는 부트스트랩 목록(`_verify_worktree_bootstrap` 의 `_BOOTSTRAP_PATHS`)에 **`.claude/rules` 추가**. 기존엔 `CLAUDE.md` 만 복사돼, `CLAUDE.md` 가 `@.claude/rules/*.md` `@include` 로 룰을 끌어오는 프로젝트에서 **@include 타깃이 워크트리에 없어 룰 본문이 통째로 누락**됐다(GuardrailLoader 는 raw text 주입이라 @include 미전개, child claude 의 native auto-discovery 도 파일 부재로 깨짐 → 인덱스·표 껍데기만 들어감). 이제 `.claude/rules` 가 함께 복사돼 child claude(`--bare` off 환경)가 `@include` 를 native 전개 → IMMUTABLE/GIT_POLICY/DDD 등 규칙이 정상 로드된다. `if not src.exists()` 가드로 rules 디렉토리 없는 프로젝트엔 무영향. 기존 워크트리도 다음 실행 시 dir-skip 가드(`dst 비어있음`)를 통과해 채워진다. `.claude/hooks`·`skills`·`plugins`·codenav 인덱스는 의도적으로 제외(lean 모드가 무력화 + codenav 인덱스는 메인 repo 경로 스냅샷이라 워크트리에선 stale·경로 불일치 위험).

### v2.14.0 — docs-add-task TASK §7/§11 빈 절 생략 (후속 스킬 블로킹 방지)

`docs-add-task` 가 TASK 문서의 **§7 결정 필요 사항·§11 미확인 사항**을 작성할 때, 실제 미해결 항목이 1건 이상일 때만 절(heading+표)을 둔다. 항목 0건이면 **절 전체를 생략**하고 `"없음"` placeholder 행을 남기지 않는다. 기존엔 빈 절에 `"없음"` 행을 남겨 후속 스킬(DDR/branch-review 등)이 미결 항목으로 오인해 블로킹하던 문제를 제거. SKILL Phase 9 룰 + 핵심 원칙 + TASK 템플릿(`APP-TASK-001-TEMPLATE.md` §7/§11) 동기화. `docs_helpers.py check` 는 TASK 섹션 수를 검사하지 않아 절 생략으로 §번호 공백(§6→§8)이 생겨도 PASS — 구조 검증 영향 없음.

### v2.13.0 — docs-add-task 요구사항 정합 자기검증 루프 (codex 99%/3회)

`docs-add-task` 가 설계 문서 작성 후 **codex 로 요구사항서↔생성문서 정합을 자동 채점**하고 수렴시킨다. 기준 = 사용자가 입력한 요구사항서(`.requirements/req-<App>-TASK-<NNN>.md`, 영구 기록·불변), 대상 = 이번 실행 변경 전체(FRD/TASK/ADR/FC/PRD/ADR-CATALOG). codex 가 전용 출력 템플릿(요구 반영 표 ✓/⚠/✗ + 부족 항목·보강 지시 + Conformance%)으로 채점 → 메인 에이전트가 부족분을 설계 문서에 보강 → 재검증, **99% 또는 최대 3회까지 수렴**(미달 시 현재 %·부족 항목 보고). 검증자=codex / 수정자=메인 에이전트(인라인). 신규 `scripts/docs_conformance.py` (doc_driven_review codex 헬퍼 import 재사용, 원본 무수정). codex 미설치·요구사항서 부재 시 graceful skip(본체 작성 결과 유지). step5 `doc-driven-review`(문서↔코드)와 검증 축이 다름 — 본 검증은 요구↔문서.

### v2.12.0 — docs-add-task NEW/CHANGE 모드 폐기 → 문서별 upsert 통합

`docs-add-task` 의 NEW/CHANGE 모드 분기를 폐기하고 **문서별 upsert** 단일 경로로 통합. 영향 자산마다 신설/갱신/생략을 자동 판정 — 신규 기능 FRD 신설 + 기존 영향 FRD 갱신을 **한 작업서 혼합** 가능. ADR 도 upsert(새 결정=신설 / 기존 결정 변경=supersede·in-place / 결정 없음=**생략**)로 "TASK 1개=ADR 1개 항상 강제" 룰 폐기(DOCUMENT_GUIDE "필요 시 ADR" 정렬). FC/PRD/ADR-CATALOG 는 op 따라 행 추가·갱신. TASK 는 항상 생성(휘발성).

### v2.11.0 — ddr-loop·requirement-spec 수렴 루프 기본값 조정 (3회·99%)

`ddr-loop` 기본 `--max-iter` 10→**3**, 기본 `--threshold` 95%→**99%**. `requirement-spec` 의 codex 자기검증을 **1회 반영 → 검증↔보완 수렴 루프(최대 3회·99% 임계)** 로 변경 — 임계 도달 또는 cap 까지 자동 반복(마지막 라운드는 검증만), 종료 후 Phase 5 에서 trajectory·최종 Coverage 를 보고하고 확정/보완 1회를 컨펌받는다. 두 스킬 모두 동일 수렴 구조(검증=codex / 수정=claude).

### v2.10.2 — forge-scope MCP config 정상화 + index.json 상태 갱신 보강

forge-scope child `claude` 호출에 유효한 MCP config 를 전달하고, `index.json` status 업데이트를 robust 하게 처리. (manifest 만 올랐던 누락분 소급 기재.)

### v2.10.1 — forge-scope 인자 우선순위 명문화 (충돌 오인 방지)

`--single-step` + `--preset=contract-tdd` 동시 지정을 parent agent 가 "상호 배타 충돌"로 오인해 경고하던 문제 차단. `forge_scope.py` 는 deterministic precedence(`--preset=<X>` 명시 > `--single-step` 암묵 > auto)로 정상 처리하며, contract-tdd 분기에서 single-step step-cap(=1)은 자동 해제된다. `--doc` 도 FRD 전용이 아님(TASK·일반 문서·FRD 모두 가능)을 SKILL·README 에 명시. 코드 동작 불변 — 문서/가드레일만 보강.

### v2.10.0 — acceptance-design 스킬 추가 + requirement-spec 파이프라인 통합

타겟 문서 기준 **완료조건·엣지케이스·오류케이스·검증방법** 4축을 사용자와 같이 설계하는 스킬 신설. grill-me 질문 루프(1문1답 AskUserQuestion·pushback·모순 지적)를 재사용하되 시작 시 doc를 ground truth로 읽고 질문 범위를 4축으로 고정. 확정 시 `.requirements/{slug}-acceptance.md` 저장.

추가로 `requirement-spec` 메타 스킬에 **Phase 1.5(acceptance-design)** 를 grill-me 다음 단계로 삽입. 파이프라인이 `grill-me → acceptance-design → meta-prompter → 저장 → codex 검증↔보완 수렴 루프(최대 3회·99%)`로 확장됨. meta-prompter 입력과 codex GROUND TRUTH가 정리본 + 4축 설계본 둘 다를 포함해 지시서에 완료조건·검증이 실린다. 세 산출물(`grill-me-{slug}.md`·`{slug}-acceptance.md`·`requirement-{slug}.md`)이 동일 slug 공유.

### v2.9.0 — safe-pull 스킬 추가

`git pull` 안전 게이트 스킬 신설. fetch(비파괴)까지만 먼저 실행해 "지금 → 풀 후" 변경·충돌·사이드이펙트를 브리핑하고, AskUserQuestion 컨펌 뒤에만 pull. 외부 도구 0(순수 git). backward-compatible — 신규 스킬만 추가, 기존 동작 불변.

### v2.8.0 — forge-scope 성능 최적화 (고정 오버헤드 절감)

`forge-scope`/`ddr-loop`의 child `claude` 호출 고정 오버헤드를 깎았다. 모델/effort 기본값(Opus 4.8 + high)·git 커밋 방식은 불변.

- **lean child claude (기본)**: child `claude -p` 에 `--strict-mcp-config`(MCP 0개)·`--disable-slash-commands`·최소 `--tools` 를 **API key 유무와 무관하게** 부착 → 매 호출 MCP 함대·plugin cold-load 세금 제거(OAuth 구독 사용자에 특히 큼). 전체 로드는 `--full-fleet`, 허용 tool은 `--child-tools`. ddr-loop fix 호출에도 적용.
- **AI 커밋 메시지 재작성 기본 OFF**: 옵트인 `--ai-commit-msg`. 단일 step phase에서 매번 붙던 추가 Opus 호출 1회 제거(claude 호출 2→1). 기존 `--no-ai-commit-msg` 는 no-op로 무중단.
- **dotnet warmup restore 스코프 축소**: 풀 sln → AC가 테스트할 그 csproj만 restore(single-step/frd). contract-tdd는 회귀 때문에 풀 sln 유지.
- **`--timings`**: 종료 시 `[timings] worktree=.. warmup=.. step0=..(out=..) commit-msg=.. total=..` 1줄 출력(`--quiet`여도). step `out`(output_tokens) 작은데 elapsed 크면 모델 아닌 .NET 빌드/IO 병목.
- **docs 재복사 스킵**: 워크트리 재실행 시 이미 채워진 docs 디렉토리 재복사 안 함.

backward-compatible — 신규 플래그는 전부 옵트인이고 기본 동작 변경은 commit-msg(기본 OFF)뿐. 데이터 계약·경로 불변이라 재부트스트랩 불필요.

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

### Skill 13종

| Skill | 슬래시 커맨드 | 역할 |
|---|---|---|
| `acceptance-design` | `/claudecode-for-me:acceptance-design <doc-path>` | 타겟 문서를 ground truth로 읽고 완료조건·엣지케이스·오류케이스·검증방법 4축을 1문1답으로 같이 설계. grill-me 질문 루프 재사용. 확정 시 `.requirements/{slug}-acceptance.md` 저장 |
| `branch-review` | `/claudecode-for-me:branch-review [ref] [--spec <path>] [--resume]` | HEAD↔ref diff을 bugs/style/spec/perf 4 dimension 병렬 finder로 검토 |
| `codenav-frontmatter-gen` | `/claudecode-for-me:codenav-frontmatter-gen [--limit N] [--apply]` | C# 클래스 description 빈칸을 AI로 일괄 채워 `// ---` frontmatter 블록 삽입 |
| `doc-driven-review` | `/claudecode-for-me:doc-driven-review <doc-path>... [--worktree <ref>] [--commit <ref>]` | 첨부 문서 기준 working-tree/커밋 변경을 Codex CLI로 검증. Missing/Improve/Overengineered + Conformance(%) + 인용검증 보고. linked worktree·커밋 노드 지목 지원 |
| `ddr-loop` | `/claudecode-for-me:ddr-loop <slug> [--docs <doc>...]` | forge 워크트리 브랜치를 Work Packet/TASK/Required SSOT 또는 명시 docs와 codex로 대조(일치율%), 미달분을 세션이 워크트리 안에서 인라인 수정·재검. `--docs` 생략 시 forge-scope Work Packet에서 자동 구성. 최대 3회·99% 정지. 빌드는 `.csproj`만. 정리는 forge-cancel |
| `forge-scope` | `/claudecode-for-me:forge-scope <WORK_PACKET-or-TASK-doc-path> [--name <slug>] [--force]` | Work Packet을 우선 입력으로 받아 Ready gate, 연결 TASK, Required SSOT Execution Matrix를 소비해 워크트리에서 고정 계약-TDD 파이프라인(계약+테스트→구현→빌드/유닛테스트)으로 구현. TASK 직접 입력은 legacy 호환. 빌드는 `.csproj` 단위만(솔루션 금지). 정리는 `forge-cancel`. |
| `grill-me` | `/claudecode-for-me:grill-me [주제]` | 1문 1답으로 요구사항 모호점 추적 |
| `meta-prompter` | `/claudecode-for-me:meta-prompter [요청]` | 거친 요청 → 구조화된 메타 프롬프트 |
| `requirement-spec` | `/claudecode-for-me:requirement-spec [주제]` | grill-me→acceptance-design→meta-prompter→codex 검증을 자동 체인. 요구사항 도출·완료조건 4축 설계·개발 지시서 `.requirements/requirement-{slug}.md` 산출 후 정리본+설계본 대비 codex 검증↔보완 수렴 루프(최대 3회·99% 임계) |
| `safe-pull` | `/claudecode-for-me:safe-pull [원격/브랜치]` | git pull 전 fetch(비파괴)로 변경·충돌·사이드이펙트 브리핑 후 AskUserQuestion 컨펌 게이트 |
| `ssot-write` | `/claudecode-for-me:ssot-write <TASK-path> [--app <APP>] [--name <slug>] [--resume]` | TASK를 기준으로 PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 영구 SSOT를 갱신. read-only 영향 분석과 수정 후 일관성 감사를 거치며 `.process/<slug>/`에 계획과 진행로그 기록 |
| `task-write` | `/claudecode-for-me:task-write [--app <APP>] [--from <requirements-path>] [요청]` | 요구사항 문서/자연어 요청에서 TASK 작업 범위 계약만 생성. FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 분석·수정 없음 |
| `work-packet-write` | `/claudecode-for-me:work-packet-write <TASK-path> [--app <APP>] [--process <process-dir>] [--name <title>]` | TASK와 Required SSOT Execution Matrix를 연결하는 forge 입력용 Work Packet 생성. TASK/SSOT/코드 수정 없이 실행 규칙·경계·검증 입력만 정리 |

### Command 17종

| Command | 설명 |
|---|---|
| `acceptance-design` | acceptance-design skill 진입. 타겟 doc 기준 4축(완료조건·엣지케이스·오류케이스·검증방법) 설계, `.requirements/{slug}-acceptance.md` 저장 |
| `branch-review` | branch-review skill 진입 |
| `codenav-bootstrap` | CodeNavigator parser-only 인덱싱 (frontmatter/XML doc만 읽어 SQLite 빌드, AI 호출 없음) |
| `codenav-frontmatter-gen` | codenav-frontmatter-gen skill 진입 (AI가 .cs에 frontmatter 영구 삽입). `--projects` / `--files` / `--staged` 스코프 인자 |
| `codenav-install` | 프로젝트 루트의 `tools/codenavigator/` 폴더에 codenavigator (PyPI) 격리 설치 + `codenav.ps1/codenav.sh` launcher + `.gitignore` 자동 작성 + `docs/codenav-guide.md` 작성 + 루트 `CLAUDE.md` 링크 셋업 |
| `doc-driven-review` | doc-driven-review skill 진입. Codex CLI 위임 read-only 리뷰. `--worktree <branch\|path>` linked worktree / `--commit <ref>` 커밋 노드 지목 지원 |
| `ddr-loop` | ddr-loop skill 진입. forge 워크트리 브랜치↔docs 수렴 루프(codex reviewer + 세션 fixer, 최대 3회·99%) |
| `commit-analysis` | 변경 분석 후 `[ADD]`/`[MOD]`/`[FIX]` 자동 판단 한글 커밋 생성 |
| `forge-cancel` | forge-scope 워크트리·`feat-<slug>` 브랜치 제거 (서브모듈 메인 원본 보존). `<slug>` 지정 또는 생략 시 목록에서 선택. 스킬 없이 커맨드 단독 |
| `forge-scope` | forge-scope skill 진입 |
| `grill-me` | grill-me skill 진입 |
| `meta-prompter` | meta-prompter skill 진입 |
| `requirement-spec` | requirement-spec skill 진입. grill-me→acceptance-design→meta-prompter→codex 검증 자동 체인 메타 스킬 |
| `safe-pull` | safe-pull skill 진입. fetch 후 브리핑 → 컨펌 게이트 → pull |
| `ssot-write` | ssot-write skill 진입. TASK 기반으로 영구 SSOT 문서를 갱신하고 read-only auditor로 영향/일관성 감사 |
| `task-write` | task-write skill 진입. TASK 파일만 생성하고 SSOT 문서는 수정하지 않음 |
| `work-packet-write` | work-packet-write skill 진입. TASK와 Required SSOT Execution Matrix를 연결하는 Work Packet만 생성하고 다음 단계를 forge-scope로 넘김 |

---

## 6. Skill 상세

### 6.1 branch-review

```
/claudecode-for-me:branch-review main
/claudecode-for-me:branch-review v1.4.0
/claudecode-for-me:branch-review main --spec docs/Feature/TASK/Feature-TASK-001.md
/claudecode-for-me:branch-review          # ref 생략 시 merge-base 자동
/claudecode-for-me:branch-review --resume # 중단된 리뷰(청크 모드) 재개
```

- **4 dimension 병렬**: bugs(정확성+표면보안) / style(컨벤션) / spec(요구사항) / perf(성능) 독립 서브에이전트 → masking 방지. security는 별도 축 없이 bugs에 표면검사로 흡수(심층은 `/security-review`)
- **3-dot diff** (`<ref>...HEAD`) — 내 변경만, ref 진행분 노이즈 제거
- **심각도 4단**: CRITICAL / MAJOR / MINOR / NIT (NIT 기본 억제, CRITICAL/MAJOR는 무제한 전량 보고. NIT 포함은 리뷰 시작 시 verbose/NIT 포함 요청)
- **TYPE**: bugs = LOGIC/BOUNDARY/NULL/RESOURCE/CONCURRENCY/SECURITY-SURFACE, style = VIOLATION/JUDGMENT, spec = MISSING/PARTIAL/SCOPE-CREEP/FLAW, perf = N+1/COMPLEXITY/ALLOC/BLOCKING/REDUNDANT
- **Diff 분기**: ≤50라인 인라인(4렌즈 1패스), 51~2000 표준(4 서브에이전트), 초과 시 디렉토리 청크 분할(청크당 4 서브에이전트, cross-chunk 교차영향은 미검출 경고). 단일 파일이 청크 cap을 넘으면 `Warnings`에 표시
- **Spec 5층 fallback**: `--spec <path>` → 이슈본문 → docs/specs → PR description → 커밋 메시지 → 부재 (HIGH~NONE 신뢰도 등급)
- **Standards 신뢰도 등급 (신규)**: lint설정+CLAUDE.md/CONTRIBUTING 존재 여부로 STRONG/WEAK/NONE — 규칙 문서 없는 레포에서 style 의견이 과신되는 것 방지
- **Recommendation precedence**: 임의 축 CRITICAL → Conflicts → Intent mismatch → spec MISSING/PARTIAL≥2 → 임의축 MAJOR → SHIP 순으로 상위 1개만 채택
- **templates/**: 4 finder 프롬프트(`bugs/style/spec/perf-finder.md`) + process 문서 2종을 `skills/branch-review/templates/`에서 관리 (ssot-write와 동일 관례)
- **영속화**: `.process/branch-review-<sha>/`(build+progress) + `.review/branch-review-<sha>.md`(최종보고). `--resume`으로 중단된 청크 리뷰 재개(완료 청크는 `chunk-<id>.log` raw 출력으로 재사용)
- **다언어**: TS/JS · Python · Go · Rust · Java/Kotlin · C#/.NET · Ruby · Swift
- **충돌**: 축간 모순 finding을 별도 "Conflicts" 섹션
- **Recommendation**: SHIP / FIX-MAJOR-THEN-SHIP / FIX-CRITICAL-FIRST / BLOCK-SPEC-MISMATCH / RESOLVE-CONFLICTS / RECONFIRM-INTENT

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

### 6.3 task-write / ssot-write (TASK 계약 → 영구 SSOT 반영)

```
/claudecode-for-me:task-write --app Billing --from .requirements/order-refund.md
/claudecode-for-me:ssot-write docs/Billing/TASK/Billing-TASK-014.md --app Billing
/claudecode-for-me:work-packet-write docs/Billing/TASK/Billing-TASK-014.md --app Billing
/claudecode-for-me:ssot-write docs/Billing/TASK/Billing-TASK-014.md --resume
```

- **책임 분리** — `task-write`는 TASK 파일만 생성한다. PRD/FC/FRD/ADR/ADR-CATALOG/ARCHITECTURE 분석·수정·후보 작성은 금지.
- **SSOT 갱신 단계** — `ssot-write`는 완성된 TASK를 Scope Authority로 삼아 영구 SSOT를 좁게 생성·수정한다.
- **read-only auditor 2회** — 영향 분석은 SSOT 종류별 matrix로 판정하고, 수정 후 감사는 확정 matrix 기준으로 expected/observed/fix를 파일별 점검한다.
- **프로세스 기록** — `.process/<TASK-stem>/ssot-write-build.md`에 `Confirmed SSOT Action Matrix`, `ssot-write-progress.md`에 최신 Stage Status와 append-only Log를 남긴다.
- **TASK 인용 금지** — 영구 SSOT 본문과 변경 이력에는 TASK markdown link/TASK ID를 남기지 않는다.
- **실행 manifest** — `work-packet-write`는 TASK와 Required SSOT Execution Matrix를 연결하는 `docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md`만 생성한다.
- **후속 단계** — Work Packet 생성 후 `Next: forge-scope`로 구현 단계에 넘긴다.

### 6.4 forge-scope / forge-cancel (harness_framework 임베디드)

`forge-scope`는 Work Packet을 우선 입력으로 받아 워크트리에서 **고정 계약-TDD 파이프라인**으로 구현한다. python(`worktree_setup.py`)은 **셋업·검증·정리만** 하고, 실제 코딩(계약+테스트→구현→빌드/유닛테스트)은 호출 세션이 워크트리 안에서 인라인으로 수행한다. 빌드/테스트는 **솔루션(`*.sln`) 금지, 대상 `.csproj` 단위만**. TASK 직접 입력은 legacy 호환 경로로 유지된다.

#### 전제 조건

| 조건 | 필수 | 비고 |
|---|---|---|
| Python 3.10+ (`python` 또는 `py -3`) | **필수** | 미설치 시 즉시 가이드 출력 후 중단 |
| git repository | **필수** | 워크트리 기반 동작 |
| Ready Work Packet | **권장 필수** | `Draft = do not implement`. 연결 TASK와 Required SSOT 링크/파일이 없거나 Blocking 이 있으면 exit 2로 중단 |
| 채워진 TASK 문서 | legacy 호환 | TASK 직접 입력 시 미결 항목(§7 결정·§11 미확인)·placeholder·`**TEMPLATE**` 배너 잔존 시 검증 게이트가 exit 2로 중단. Work Packet 기반 SSOT gate는 없음 |

#### 복사 없음 (플러그인 캐시 직접 실행)

`worktree_setup.py`·템플릿을 프로젝트로 복사하지 않는다 — `${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py`를 직접 실행한다. 프로젝트에는 생성물 `.worktree/`·`.process/`만 `.gitignore`에 추가된다(그 `.gitignore` 변경만 commit).

#### 사용 예시

```bash
# Work Packet 기준 구현 (워크트리 .worktree/<slug> + feat-<slug> 브랜치)
/claudecode-for-me:forge-scope docs/Loader/WORK_PACKET/LOADER-WP-007.md

# slug 명시
/claudecode-for-me:forge-scope docs/App/WORK_PACKET/APP-WP-003.md --name order-api

# legacy: TASK 직접 구현 (Work Packet Required SSOT gate 없음)
/claudecode-for-me:forge-scope docs/App/TASK/APP-TASK-003.md

# 워크트리·브랜치 정리 (서브모듈 메인 원본 보존). slug 생략 시 목록에서 선택
/claudecode-for-me:forge-cancel LOADER-TASK-007
/claudecode-for-me:forge-cancel
```

#### 옵션

| 커맨드 | 인자 | 설명 |
|---|---|---|
| `forge-scope` | `<WORK_PACKET-or-TASK-doc-path>` | **필수**. 권장 입력은 Work Packet. TASK 경로는 legacy 호환 |
| | `--name <slug>` | docName·워크트리·브랜치 이름 명시 (기본: 문서 파일명 stem) |
| | `--force` | 메인 repo dirty 검사 우회 |
| `forge-cancel` | `[<slug>]` | 제거할 워크트리 slug. 생략 시 목록에서 선택 |

#### 검증 게이트 (forge-scope init)

git repo·입력 문서 존재·**미결 항목 없음**을 검사한다. Work Packet 입력이면 상태가 `Ready`인지, `Execution Gate`가 있는지, `Blocking / Open Questions`가 `none`인지, 연결 TASK와 Required SSOT 링크 파일이 존재하는지 먼저 검사한다. `Draft` 또는 Required SSOT 누락이면 exit 2로 중단하고 워크트리를 만들지 않는다. TASK legacy 입력은 기존 TASK 미결(=`**TEMPLATE**` 배너 / §11 미확인 사항 Open 행 / §7 결정 필요 행 / 미치환 `{...}` placeholder)을 검사한다.

#### 워크트리 서브모듈

`git submodule update`(네트워크) 대신 **메인 repo 서브모듈을 junction(Windows)/symlink(Unix)로 링크** → 오프라인·내부망 동작. `submodule.<name>.ignore=all`로 커밋/상태 무시. 메인 미populate면 skip. **`forge-cancel`은 워크트리 링크만 해제하고 메인 repo 서브모듈 원본은 절대 건드리지 않는다**(링크 미해제 시 `git worktree remove`가 junction 따라 메인 삭제하는 사고 방지).

#### .gitignore 권장

```gitignore
.worktree/
.process/
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
- 종료 시 **인터뷰 기반 정리본**(배경 / 전개 / 전환 / 결론 + Open Items + 구체화 수준) 후 확정 리뷰
- 확정 시 정리본을 **`.requirements/grill-me-{slug}.md` 자동 저장**(slug=영어 kebab, 동명 시 번호 suffix)
- 산출물은 정리본까지 — **구현 plan·`ExitPlanMode` 미수행**. 다음 단계(meta-prompter 등)는 사용자가 정리본을 받아 진행

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

### 6.7 requirement-spec (메타 스킬 — grill-me→acceptance-design→meta-prompter→codex 파이프라인)

```
/claudecode-for-me:requirement-spec 사칙연산 계산기 개발
```

- **메타 스킬**: grill-me(6.5)·acceptance-design(6.12)·meta-prompter(6.6)를 자동 인라인 체인으로 엮고 codex 자기검증을 붙임. 1회 호출 → 자동 진행(사용자 상호작용은 grill-me 인터뷰 + acceptance-design 인터뷰 + 최종 리뷰만)
- **파이프라인**: `요구사항 도출(grill-me) → 완료조건·엣지·오류·검증 4축 설계(acceptance-design) → 개발 지시서 정제(meta-prompter) → .requirements/requirement-{slug}.md 저장 → codex 검증↔보완 수렴 루프(최대 3회·99% 임계)`
- **Phase 1.5**: acceptance-design의 타겟 doc = grill-me 정리본(`grill-me-{slug}.md`). 설계본 `{slug}-acceptance.md` 산출. meta-prompter 입력·codex GROUND TRUTH가 정리본 + 설계본 둘 다를 포함 → 지시서에 완료조건·검증이 실림
- **slug 일관**: 세 산출물이 동일 slug 공유 — `grill-me-{slug}.md`(정리본) ↔ `{slug}-acceptance.md`(설계본) ↔ `requirement-{slug}.md`(지시서)
- **codex 자기검증**: grill-me 정리본 + acceptance 설계본=GROUND TRUTH 기준 체크리스트 생성 → 지시서 반영도 대조 → `Coverage: N%` + 보완점. 모델 `gpt-5.5`, reasoning effort 레벨 `high` (`-c model_reasoning_effort="high"`)
- **Phase 게이트**: 각 Phase 전이 조건 미충족 시 다음 Phase 진입 금지
- **codex 미설치 시** 검증만 생략(`/codex:setup` 안내), 지시서는 보존
- 산출물은 지시서까지 — **구현 코드 미작성·`ExitPlanMode` 미호출**

### 6.8 commit-analysis

```
/claudecode-for-me:commit-analysis
```

- 구분자 자동: `[ADD]` 추가 / `[MOD]` 수정 / `[FIX]` 버그
- `.md` 자동 제외 (`git add --all` 후 `git reset -- "*.md"`)
- Co-Authored-By / "Generated with Claude Code" 문구 제외
- 한글 커밋 메시지

### 6.9 doc-driven-review

```
/claudecode-for-me:doc-driven-review docs/spec-feature.md
/claudecode-for-me:doc-driven-review docs/spec.md --wait --scope working-tree
/claudecode-for-me:doc-driven-review docs/spec.md --worktree feat-cn-foo
/claudecode-for-me:doc-driven-review docs/spec.md --worktree .worktrees/cn-foo --background
# 특정 커밋(노드) 지목 — no-worktree forge 산출 검토 등
/claudecode-for-me:doc-driven-review docs/TASK.md --commit <feat 커밋 sha>
```

- **Codex CLI 위임** — 첨부 문서 기준 working-tree + untracked 변경을 codex가 리뷰. read-only.
- **산출**: Missing / Improve / Overengineered + **Conformance (0-100%)** 점수.
- **strict 상태 판정**: ✓ 모든 시그니처/literal 일치 · ⚠ 외형 맞지만 일부 누락 · ✗ literal 부재 또는 완전 부재.
- **Cross-file ripple**: public API 변경 시 patch + UNCHANGED CONTEXT(caller auto-detect) 모두 참조.
- **Weighted Conformance**: Critical=4 / Major=2 / Minor=1, ✓=full ⚠=0.5× ✗=0. `pct = round(100 × passed / total)`.
- **커밋 노드 지목**: `--commit <ref>` — 특정 커밋(또는 `A..B` 범위) 변경분만 doc 대조. working-tree/branch·`--base` 우회. no-worktree forge 처럼 변경이 이미 커밋된 경우 그 노드만 검토.
- **워크트리 지정**: `--worktree <branch|path>` — forge-scope linked worktree 또는 임의 경로 직접 리뷰. `--repo-root` 와 mutex.
- **scope**: `working-tree` (변경) / `branch` (HEAD↔base diff) / `auto` (변경 있으면 working-tree).
- **인용 검증**: codex 인용 `file:line` 을 repo에 대조(파일존재+라인수). 미검증 시 `[doc-driven-review] CITATION-CHECK:` 라인 추가(advisory).
- **결과 파일**: `<repo>/.review/<doc-stem>-review.md`.
- **모드**: `--wait` (foreground) / `--background` (PID + log). background는 **detached foreground 재실행** — fg와 동일하게 스키마검증·인용검증·`.review/` 저장까지 수행(비대칭 없음). 오래된 bg 로그·patch 7일 자동 정리.
- **dry-run**: `--dry-run`으로 codex 호출 없이 prompt만 stdout. `--keep-patch`로 디버깅용 patch 보존.

#### 한계

- Codex CLI 필수. 미설치 시 exit 2. `/codex:setup` 안내.
- patch + background log는 main repo `.git/info/` 공유 (파일명 unique로 동시 실행 안전).
- submodule / multi-repo 미지원.

---

### 6.10 safe-pull

```
/claudecode-for-me:safe-pull                  # 현재 브랜치 추적 upstream 자동
/claudecode-for-me:safe-pull origin main      # 명시 원격/브랜치
```

`git pull`은 한 번 실행하면 워킹트리·HEAD·히스토리가 즉시 바뀜. safe-pull은 **비파괴 단계(fetch)까지만 먼저 실행**해 "지금 → 풀 후" 변경을 브리핑하고, 충돌을 실제 머지 없이 예측한 뒤, AskUserQuestion 컨펌을 받은 경우에만 `git pull`을 실행한다.

- **Step 0 안전 게이트** — 비저장소 / detached HEAD / remote 없음 / upstream 없음 / dirty working tree 중 하나라도 걸리면 원인·해결책 설명 후 중단. 자동 보정·자동 stash 안 함.
- **Step 1 fetch** (`--tags --prune`) — 비파괴라 컨펌 전 실행. 새 릴리스 태그·유령 ref 정리 포함.
- **Step 2 브리핑 계산** — ahead/behind, FF가능/diverged/이미최신 판정, 들어올 커밋 로그, 변경 파일 분류(A/M/D/R), 핵심 파일(lock·의존성·CI·스키마) diff 발췌(파일당 ~40줄, 전체 ~200줄 cap).
- **Step 3 충돌 예측** (깃 관점) — FF면 충돌 0 확정. diverged면 `git merge-tree --write-tree`(git 2.38+)로 실제 머지 없이 예측, 미지원 시 양쪽 변경 파일 교집합을 "충돌 가능 후보(확정 아님)"로 표시.
- **Step 4 사이드이펙트** — 머지 커밋 생성 여부, submodule 포인터 변경, 빌드/의존성 재설치 필요, 새 태그(이미 fetch로 반영), 원격 force-push 흔적 경고.
- **Step 5 브리핑 출력** — 고정 한국어 개조식 템플릿(요약 / 들어올 커밋 / 변경 파일 / 새 태그 / diff 발췌 / 충돌 예측 / 사이드이펙트 / 풀 후 상태).
- **Step 6 컨펌** — AskUserQuestion: 진행(merge) / 중단 / rebase로 대신(diverged 한정). `behind==0`이면 컨펌 생략, "풀 불필요" 종료.
- **Step 7 pull** — 진행/rebase 선택 시에만 `git pull`(또는 `--rebase`). 충돌 발생 시 해결 흐름 안내(자동 해결 안 함).
- **외부 도구 0** — 순수 `git`만. PowerShell/Bash 양쪽 동작(`'@{u}'` 작은따옴표 처리).

#### 한계

- 자동 보정 없음 — Step 0 걸리면 사용자가 직접 처리(의도적). 자동 stash 배제(pop 충돌 새 위험 회피).
- 충돌 예측 정밀도는 git 버전 의존 — < 2.38은 교집합 fallback(확정 아님).
- merge 기본(로컬 SHA 보존). rebase는 diverged 한정 옵션.

---

### 6.11 acceptance-design

```
/claudecode-for-me:acceptance-design docs/feature.md
```

타겟 문서(spec/FRD)는 "무엇을 만든다"는 적어도 **완료조건·엣지케이스·오류케이스·검증방법**이 비거나 모호한 경우가 많다. acceptance-design은 그 doc를 ground truth로 읽고 위 4축을 사용자와 같이 설계한다. 질문 방식은 grill-me(6.5)와 동일하되, 시작 시 doc를 읽고 질문 범위를 4축으로 고정한다는 점이 다르다.

- **doc 입력 필수**: `$ARGUMENTS` doc 경로 → `Read` 1회. 경로 없음 "문서 경로 필수" / 파일 없음 "오류: 문서 파일 없음" 종료.
- **4축 고정**: 완료조건(Acceptance Criteria) / 엣지케이스 / 오류케이스 / 검증방법. doc에 명시된 것은 확인, 빈 곳·모호한 곳 우선 질문.
- **1문 1답** (`AskUserQuestion`)으로 추적, 추천 2개(`(Recommended)`) + auto-`Other`. **논리 모순 시 명시 지적**, doc 근거 있으면 인용 후 되묻기.
- 3~4 교환마다 4축 트래커. 종료 시 **4축 설계본**(출처 라인 + 완료조건/엣지/오류/검증 + Open Items + 구체화 수준) 후 확정 리뷰.
- 확정 시 **`.requirements/{slug}-acceptance.md` 자동 저장**(slug=doc stem 영어 kebab, 동명 시 번호 suffix).
- 산출물은 설계본까지 — **구현 plan·`ExitPlanMode` 미수행**. 후속(meta-prompter·forge-scope 등)은 사용자가 설계본을 받아 진행.

---

### 6.12 ddr-loop (문서↔코드 수렴 루프)

```
/claudecode-for-me:ddr-loop LOADER-WP-007    # Work Packet 기반 forge-scope면 docs 자동 구성
/claudecode-for-me:ddr-loop order-api --docs docs/spec.md docs/contract.md --base develop
/claudecode-for-me:ddr-loop                # slug 생략 → forge 워크트리 목록에서 선택
```

forge-scope가 워크트리(feat-<slug>)에 기능을 구현한 뒤, ddr-loop은 그 브랜치 변경점을 **Work Packet/TASK/Required SSOT 또는 명시 문서(docs) 기준으로 수렴**시킨다. forge-scope→ddr-loop이 자연스러운 연계다.

- **build-process 방식** — forge-scope처럼 `.process/<docName>/ddr-loop-build.md`(루프 PLAN)·`ddr-loop-progress.md`(회차·일치율 추적)에 기록하며 진행. `ddr_loop.py init`은 `.process/<docName>/`를 지우지 않아 forge-scope 산출물과 공존.
- **Work Packet 자동 docs** — `--docs`를 생략하면 `.process/<slug>/forge-scope-build.md`의 Work Packet을 읽어 Work Packet + 연결 TASK + Required SSOT 문서를 `doc-driven-review` 입력으로 자동 구성한다. 명시 `--docs`는 override다.
- **reviewer=codex / fixer=세션** — `doc_driven_review.py`(codex)가 `--worktree feat-<slug> --scope branch`로 브랜치 diff↔docs 대조해 `Conformance: N%` 산정. 미달 항목(Top Priorities/Review Comments/Overengineered)을 **현재 세션이 워크트리 안에서 인라인 수정**(자식 spawn 없음).
- **수렴 조건(고정)** — 최대 **3회**, 일치율 **≥ 99%** 도달 시 정지. 회차마다 빌드/테스트(**대상 `.csproj`만, 솔루션 금지**) 통과 후 `fix(ddr-<slug>): iter N 일치율 N%` 커밋.
- **문서 자동수정 금지** — 일치율을 올리려 docs/SSOT를 고치지 않는다. 코드를 docs에 맞춘다.
- **전제** — codex CLI 필수(미설치 시 첫 review exit 2 → 중단), forge 워크트리 존재(없으면 init exit 2). 정리는 `/forge-cancel`(서브모듈 메인 원본 보존).

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
│   ├── acceptance-design/
│   ├── branch-review/
│   ├── codenav-frontmatter-gen/
│   ├── ddr-loop/
│   ├── doc-driven-review/
│   ├── forge-scope/
│   ├── grill-me/
│   ├── meta-prompter/
│   ├── requirement-spec/
│   ├── safe-pull/
│   ├── ssot-write/
│   ├── task-write/
│   └── work-packet-write/
├── commands/                    # 슬래시 커맨드 (명시 호출)
│   ├── codenav-templates/       # /codenav-install 이 워크스페이스로 복사하는 자산
│   │   ├── CODENAV-GUIDE-TEMPLATE.md
│   │   └── codenav-prefer.ps1
│   ├── acceptance-design.md
│   ├── branch-review.md
│   ├── codenav-bootstrap.md
│   ├── codenav-frontmatter-gen.md
│   ├── codenav-install.md
│   ├── commit-analysis.md
│   ├── ddr-loop.md
│   ├── doc-driven-review.md
│   ├── forge-cancel.md
│   ├── forge-scope.md
│   ├── grill-me.md
│   ├── meta-prompter.md
│   ├── requirement-spec.md
│   ├── safe-pull.md
│   ├── ssot-write.md
│   ├── task-write.md
│   └── work-packet-write.md
├── docs/                       # v0.7 문서 시스템 자산
│   └── .templates/             # PRD/FC/FRD/ADR/ARCHITECTURE/CLAUDE/README 양식 + App/ + .rules/ (코드 룰 3종)
├── scripts/                     # Python deterministic helper
│   ├── branch_review_chunk_plan.py  # branch-review diff 크기측정·모드판정·청크분할·patch 생성
│   ├── ddr_loop.py              # ddr-loop 워크트리·docs 검증 + .process 스캐폴딩 (init)
│   ├── doc_driven_review.py
│   ├── docs_conformance.py
│   ├── docs_helpers.py
│   ├── worktree_setup.py        # forge-scope 워크트리 셋업·검증·cancel
│   ├── ddr_templates/           # ddr-loop build/progress 템플릿
│   └── forge_templates/         # forge-scope build/progress 템플릿 + docs/.templates 시드
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
| `forge-scope` 가 워크트리 안 만들고 종료(exit 2) | Work Packet 이 Draft, Blocking 존재, 연결 TASK/Required SSOT 링크 누락, 또는 TASK 문서 미결 항목(§7 결정·§11 미확인·placeholder·`**TEMPLATE**` 배너) | Work Packet을 Ready로 확정하고 Required SSOT 파일을 생성/연결한 뒤 재시도. TASK legacy 입력이면 문서 완성·미결 해소 |
| `ddr-loop` init exit 2 "forge 워크트리 없음" | 해당 slug 워크트리 미생성 | 먼저 `/forge-scope <WORK_PACKET>` 실행, 또는 forge-cancel에 쓴 slug 확인 (`worktree_setup.py list`) |
| `ddr-loop` 첫 review exit 2 | codex CLI 미설치 (리뷰는 codex 의존) | `/codex:setup` 후 재시도 |
| `task-write` App 후보 없음 | `/CLAUDE.md` Backend Services Overview 표 + `docs/<App>/` 부재 | App 행 추가 + 폴더 부트스트랩 |
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
