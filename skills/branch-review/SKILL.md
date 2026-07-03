---
name: branch-review
description: HEAD ↔ 고정점(ref) diff을 bugs/style/spec/perf 4 dimension 병렬 finder로 검토. 심각도 등급, diff 크기 cap, 충돌 감지, commit-msg fallback, 다언어 컨벤션 지원, `.process`/`.review` 영속화, `--resume` 재개 지원. 사용자가 "브랜치 리뷰", "PR 리뷰", "review since X", "변경사항 검토", "중단된 리뷰 재개" 요청 시 트리거. 단순 PR 코멘트가 아닌 "버그 있나(bugs) + 규칙 따랐나(style) + 시킨 거 했나(spec) + 느려지진 않았나(perf)"를 독립 관점으로 분리 검증해야 하는 모든 상황에서 사용.
argument-hint: "[고정점 ref — 미지정 시 merge-base 자동 추정] [--resume]"
---

# Branch Review

HEAD ↔ 고정점(commit/branch/tag/merge-base) 사이 변경을 **bugs / style / spec / perf** 4개 독립 관점으로 **병렬** 검토한다.

## 왜 4 finder 인가

한 관점이 다른 관점을 가린다 (masking):
- 코드 깔끔 + **엉뚱한 기능** → style만 보면 통과 (spec이 가려짐)
- 요구사항 충족 + **숨은 버그** → spec만 보면 통과 (bugs가 가려짐)
- 정확하게 동작 + **N+1 쿼리로 느려짐** → bugs만 보면 통과 (perf가 가려짐)
- 성능 최적화 + **컨벤션 이탈** → perf만 보면 통과 (style이 가려짐)

네 관점을 **독립 서브에이전트**로 동시 평가하면 위 시나리오가 모두 노출된다. 종전 2축(Standards/Spec) 체계에서 Standards 축 하나가 정확성(bugs)·컨벤션(style)·성능(perf) 3종 판단을 동시에 지고 있어 관점이 희석됐다 — 이를 3개로 분해하고 spec을 그대로 둬 4 finder로 재편한다. **security**는 독립 finder를 두지 않고 bugs finder 범위에 **표면검사**로 흡수한다 (심층 보안 검토는 `/security-review`).

---

## 실행 환경

- 모든 git 명령은 PowerShell/Bash 양쪽 호환. 사용자가 Windows이면 Bash 툴 또는 PowerShell 둘 다 동작.
- `gh` CLI 선택적 — 없으면 Step 3에서 PR description fallback 건너뜀.
- 이슈 트래커 MCP (Linear/Jira/GitHub Issues/Notion 등) 선택적 — 없으면 커밋 메시지 본문만으로 이슈 내용 추정.
- 모든 서브에이전트는 `subagent_type: "general-purpose"` 사용. Read/Grep/Glob 권한 보유.
- **read-only 계약**: "read-only"는 **소스 파일 미수정**을 의미한다. `.process/`·`.review/` 산출물 쓰기는 이 계약 밖이다(레포 관례 — `doc-driven-review`도 동일하게 `.review/`를 쓰면서 read-only를 표방). 소스 파일 편집·자동 fix·git commit은 하지 않는다.

---

## 파이프라인 구조

```
[신규] Step 0  프로세스 파일 준비 (인자 파싱 + slug + 신규/재개 판정)
[Setup 순차]  Step 1 기준점+diff추출 → Step 2 크기측정+모드 → Step 3 컨텍스트 수집·라우팅
[Find 병렬]   Step 4 bugs/style/spec/perf 4 finder 동시 발사  (+ Step 4.5 verify 슬롯: 미구현)
[Aggregate]   Step 5 dedup+충돌 → Step 6 종합 보고+영속화
```

dimension은 순차 단계로 두지 않는다 — Step 4 내부의 병렬 슬롯이다 (독립 병렬 실행이 핵심 이점이므로 순차화하면 소멸한다).

각 Step은 진행하며 `.process/branch-review-<slug>/`의 build.md·progress.md를 갱신한다 (Step 0 참조). 이는 감사 추적(audit trail)과 `--resume` 재개를 위한 것이며, 로직 자체(Step 1~6)는 이 기록 여부와 무관하게 동일하게 동작한다.

---

## Process

### Step 0 — 프로세스 파일 준비

1. `$ARGUMENTS` 파싱: `ref`(위치 인자, 선택) + `--resume`(플래그, 선택).
2. `slug = git rev-parse --short HEAD`. (Step 4가 임시 patch 파일명에 쓰는 short-sha와 동일 값 — 네이밍 일관성.)
3. `.process/branch-review-<slug>/` 존재 확인:
   - **없음 (신규 실행)**: 디렉터리 생성. `templates/branch-review-build.md`·`templates/branch-review-progress.md`를 복사해 `.process/branch-review-<slug>/branch-review-build.md`·`branch-review-progress.md`로 둔다. 값은 아직 미채움(placeholder 그대로) — Step 1~3이 진행하며 채운다.
   - **있음 + `--resume` 없음**: "기존 진행 있음 — `--resume` 없이 새로 시작(이전 진행 폐기)" 1줄 안내 후 두 파일을 덮어써 신규 실행으로 진행.
   - **있음 + `--resume`**: `branch-review-progress.md`를 Read. `Stage Status`에서 `done`이 아닌 첫 항목부터 재개한다. `Chunk Status` 표가 있으면 `done`인 청크는 `Log`에 저장된 4 finder raw 출력을 그대로 재사용(재실행하지 않음), `pending`/`doing`/`blocked`인 청크만 Step 4에서 재실행 대상으로 표시한다. `branch-review-build.md`의 기존 Inputs/Routing 값(Spec/Standards 등급 등)도 재사용해 Step 1~3 재계산을 생략할 수 있다(단, HEAD sha가 slug와 일치하는지 재확인 — 불일치하면 "재개 대상 없음, HEAD 이동됨 — 새 리뷰로 시작" 안내 후 신규 실행).

---

### Step 1 — 비교 기준점 확정

**입력 우선순위**:
1. 사용자가 ref 명시
2. 미지정 시 **자동 추정** (순서대로 시도):
   - `git merge-base origin/main HEAD`
   - `git merge-base upstream/main HEAD` (fork 워크플로우)
   - `git merge-base origin/master HEAD`
   - `git merge-base main HEAD`
   - 모두 실패 시 `HEAD~10`
3. detached HEAD (`git symbolic-ref -q HEAD` 실패) 시 사용자에게 ref 요청.
4. 자동 추정 결과를 출력에 명시: `기준점: <ref> (merge-base = <sha>)`.

**실행 명령**:
```bash
git diff <ref>...HEAD --stat
git diff <ref>...HEAD
git log <ref>..HEAD --oneline
git log <ref>..HEAD --format='%H%n%B%n---'
```

**3-dot vs 2-dot**:
- `<ref>...HEAD` (3-dot): merge-base 이후 **내 변경만**. ref 쪽 진행분 노이즈 제거 → diff 본문 추출에 사용.
- `<ref>..HEAD` (2-dot): 내 커밋 목록만 → log 추출에 사용.

**rebase 주의**: 3-dot은 merge-base 의존. rebase 시 결과 변동. `merge-base=<sha>` 표기로 사용자가 인지 가능.

**기록**: build.md `Inputs`의 `기준점(ref)`·`HEAD` 채움. progress.md `Step1-기준점` → `done`, Log에 1줄 append.

---

### Step 2 — Diff 크기 측정 및 전략 선택

**스크립트 호출** (부트스트랩 없음, in-place 실행 — doc-driven-review와 동일 관례):
```bash
SCRIPT="scripts/branch_review_chunk_plan.py"
[ -f "$SCRIPT" ] || SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/branch_review_chunk_plan.py"
python "$SCRIPT" --ref <Step1에서 확정한 ref>
```
이 스크립트가 (a) `git diff --no-renames --numstat`로 크기 측정(rename을 삭제+추가로 분리해 pathspec 매칭 안전 확보 — `--stat` 요약과 파일/라인 수가 달라질 수 있음, 정상 동작), (b) 아래 제외 패턴 적용, (c) 모드 판정, (d) chunk 모드면 청크 분할, (e) 표준/인라인은 단일 patch·chunk는 청크별 patch를 `.git/info/`에 직접 생성까지 전부 수행한다. 출력(마크다운)을 build.md `Chunk Plan` 섹션에 그대로 붙여넣는다.

**모드 판정 표** (총 변경 라인 = additions + deletions, 제외 패턴 적용 후):

| 변경 라인 | 변경 파일 | 전략 | 서브에이전트 |
|---|---|---|---|
| 0 | 0 | "변경 없음" 보고 후 종료 | — |
| 1~50 | 1~2 | **인라인 통합 모드** (메인이 4렌즈 1패스, 병렬 불필요) | 0 |
| 51~2000 | 3~50 | **표준 4-finder 병렬 모드** | 4 |
| 2001 초과 또는 파일 51개 이상 | — | **청크 분할 모드** | 4 × N청크 |

**임계값 근거**:
- 50라인 미만은 메인 컨텍스트로 충분 — 서브에이전트 오버헤드가 작업 비용 초과.
- 2000라인은 서브에이전트 컨텍스트 안정 영역 상한 (diff + 표준 파일 + 지시 합산).

**제외 패턴** (스크립트 내장, 크기측정과 patch 생성 양쪽에 적용):
- lockfile: `*.lock`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `Cargo.lock`, `poetry.lock`, `uv.lock`, `Gemfile.lock`
- 빌드 산출물 디렉토리: `dist`, `build`, `out`, `node_modules` (경로 세그먼트 일치)
- 바이너리/생성 자산: `*.min.js`, `*.min.css`, `*.map`, 이미지(`*.png`/`*.jpg`/`*.jpeg`/`*.gif`/`*.ico`), 폰트(`*.woff`/`*.woff2`/`*.ttf`/`*.eot`)
- `git check-attr -a` 결과 `linguist-generated: set`인 파일

**알려진 한계**: 위 목록에 없는 형태의 생성 산출물(예: 특정 리포트/스냅샷 성격의 개별 `.html` 파일)은 `linguist-generated` 속성으로 명시되지 않는 한 자동 제외되지 않는다 — 확장자만으로 "생성됨"을 일반화 판단하지 않기 위한 의도적 설계(오탐 방지, 예: 정당한 `.html` 뷰 파일까지 제외되는 사고 방지). 이런 파일을 배제하고 싶으면 대상 레포 `.gitattributes`에 `linguist-generated`를 명시하는 것이 정석 경로.

**청크 분할 알고리즘** (스크립트 내부, 참고용 — 직접 구현할 필요 없음):
1. 최상위 디렉토리(경로 첫 세그먼트)로 1차 그룹화.
2. 그룹이 캡(1500줄/30파일) 초과 시 그룹 내부에서 파일 단위 greedy bin-packing으로 서브청크 분할(경로 알파벳순, 결정적 재현 가능).
3. 각 청크에 **4 finder** 병렬 실행 (N개 청크 = 4N 서브에이전트). 종전 2축 체계(2N) 대비 **서브에이전트 수 2배** — 정확도와 비용 트레이드오프임을 사용자에게 보고 시 명시.
4. 결과 병합: 청크간 dedup (Step 5 규칙 그대로 적용), 카운트 합산.
5. **cross-chunk blindness**: 청크는 서로 독립 리뷰되므로 청크 A의 변경이 청크 B를 깨는 교차 영향은 검출되지 않는다 — Step 5-0이 이 중 일부(finding이 다른 청크로 해소되는 케이스)를 잡아내지만 전부는 아니다. Step 6 최종 보고에 경고 1줄 필수 (silent 누락 금지).

**비용 고지 (필수)**: chunk 모드로 판정되면 Step 4 진입(서브에이전트 발사) 전에 반드시 1줄 출력한다 — `"청크 N개 × 4 finder = M개 서브에이전트 발사 예정 (대형 diff 리뷰 — 비용/시간 소요 큼)"`. 사용자가 진행 여부를 인지한 상태로 다음 단계가 시작되게 함(하드 게이트는 아님 — 필요하면 사용자가 중단).

**기록**: build.md `Inputs`의 `변경 규모`·`모드` 채움 (chunk 모드면 스크립트 출력의 청크 계획 표를 그대로 붙여넣음). progress.md `Step2-모드결정` → `done`. **chunk 모드면 `Chunk Status` 표 신설**(청크당 1행, `pending`). 인라인/표준 모드는 단일 가상 청크 `C0` 1행으로 둔다(Step 4 진행 단위를 일관되게 추적하기 위함).

---

### Step 3 — 컨텍스트 수집 & 라우팅

#### 3-1. Spec 위치 탐색 (다층 fallback)

원 요구사항 출처를 다음 우선순위로 **모두 수집** (첫 매치에서 멈추지 않음 — 누락 방지):

1. **커밋 메시지 이슈 참조** — 정규식 `#\d+|[A-Z]+-\d+|(?i)closes\s+#\d+|fixes\s+#\d+` 추출. 이슈 트래커 MCP 있으면 본문 조회. 없으면 이슈 번호 + 커밋 메시지만 기록.
2. **사용자 명시 경로** — 인자로 받은 spec 파일.
3. **레포 표준 위치** — 최근 30일 내 변경된 매칭 문서:
   - `docs/**/*.md`, `specs/**/*.md`, `.scratch/**/*.md`, `.atdd/**/*.md`
   - 브랜치명과 유사 토큰 매칭 (e.g. `feature/auth` → `auth`, `authentication` 포함 파일).
4. **PR description** — `gh pr view --json title,body` 가능 시 본문. 실패 시 건너뜀.
5. **Commit message fallback** — 위 모두 빈약 시 `git log <ref>..HEAD` 본문 전체를 **합성 spec**으로 사용.
6. **완전 부재** — 위 모두 실패.

**Spec source 신뢰도 등급** (spec finder에 전달 — 3-4 라우팅 매트릭스 참조):
- `HIGH`: 이슈 본문 확보 + docs 매칭 둘 다.
- `MEDIUM`: 이슈 본문 or docs 한쪽만.
- `LOW`: 이슈 번호만 (본문 미확보) or PR description만.
- `FALLBACK`: 커밋 메시지 합성 — spec finder는 MISSING/PARTIAL 보고 자제, SCOPE-CREEP/FLAW 위주.
- `NONE`: 완전 부재 — spec finder는 SCOPE-CREEP과 명백한 결함만 보고. MISSING/PARTIAL 보고 금지.

#### 3-2. Standards 문서 수집 (다언어, 인라인 로드 포함) + 신뢰도

**수집 대상 glob (범용)**:
- `CLAUDE.md`, `**/CLAUDE.md` (최대 깊이 3)
- `CONTRIBUTING.md`, `CONTEXT.md`, `STYLE.md`, `STYLE_GUIDE.md`
- `docs/architecture/**/*.md`, `**/ADR-*.md`, `**/adr/*.md`, `**/decisions/*.md`
- `.editorconfig`, `.gitattributes`

**언어/스택 자동 감지** (레포 루트 마커 기준 — **멀티스택은 모두 수집**):

| 마커 | 추가 수집 |
|---|---|
| `tsconfig.json`, `package.json` | `eslint.config.*`, `.eslintrc*`, `biome.json`, `.prettierrc*`, `tsconfig*.json` |
| `pyproject.toml`, `setup.py`, `requirements.txt` | `ruff.toml`, `.ruff.toml`, `setup.cfg`, `mypy.ini`, `.flake8`, `pyrightconfig.json` |
| `go.mod` | `.golangci.yml`, `.golangci.yaml` |
| `Cargo.toml` | `clippy.toml`, `rustfmt.toml`, `.clippy.toml` |
| `pom.xml`, `build.gradle*` | `checkstyle.xml`, `detekt.yml`, `pmd-ruleset.xml` |
| `*.csproj`, `*.sln` | `.editorconfig`, `Directory.Build.props`, `*.ruleset` |
| `Gemfile` | `.rubocop.yml` |
| `*.swift`, `Package.swift` | `.swiftlint.yml`, `.swiftformat` |

**인라인 vs 경로 전달**:
- **≤200 라인 파일**: 메인이 Read → 서브에이전트 프롬프트에 본문 인라인 (재로딩 비용 회피).
- **>200 라인 파일**: 경로 + 목차만 전달, 에이전트가 필요 섹션 Read.
- 합산 인라인 본문이 6000 토큰 초과 시 모든 파일을 경로 전달로 다운그레이드.

**Standards source 신뢰도 등급** (Spec 축과의 비대칭 해소, style finder에 전달 — 3-4 라우팅 매트릭스 참조):
- `STRONG`: lint/formatter 설정 파일 **+** (`CLAUDE.md` 또는 `CONTRIBUTING.md`) 둘 다 존재.
- `WEAK`: 위 둘 중 하나만 존재.
- `NONE`: 표준 문서·lint 설정 0건 — style finder는 일반론 스타일 의견을 자제하고 주변 코드 대비 명백 일탈만 보고.

#### 3-3. 변경 의도 추출

커밋 메시지 첫 줄들을 별도 "Intent" 블록으로 추출해 **4 finder 모두**에 전달 (bugs/style/perf는 의도와 변경 일치 평가, spec은 spec과의 일치 평가).

#### 3-4. 라우팅 매트릭스

| finder | 전달 컨텍스트 | 신뢰도 등급 |
|---|---|---|
| bugs | diff patch 경로 + 변경 파일 목록 + Intent + 레포 루트(Grep용) | — (코드 자체가 판단 기준) |
| style | 위 + 표준문서 번들(인라인/경로) | Standards 등급 (STRONG/WEAK/NONE) |
| spec | diff patch 경로 + 변경 파일 목록 + Intent + spec 번들(출처 라벨) | Spec 등급 (HIGH~NONE) |
| perf | diff patch 경로 + 변경 파일 목록 + Intent + 레포 루트(Grep용) | — (규모 가정이 근거) |

**기록**: build.md `Routing` 섹션(Spec source/Standards source/Intent) 채움. progress.md `Step3-라우팅` → `done`.

---

### Step 4 — 4 Finder 병렬 호출

#### 모드 분기

**A. 인라인 통합 모드** (≤50라인, 1~2 파일):
메인 에이전트가 직접 4렌즈로 검토. 서브에이전트 호출 없음. 출력 포맷은 Step 6과 동일 (bugs/style/spec/perf 4섹션 분리 작성). 진행 단위는 가상 청크 `C0` 1개로 기록.

**B. 표준 병렬 모드**:
4개 서브에이전트를 **동일 assistant 메시지 안에서, 서로 다른 tool 호출 4개로 동시 발신**한다 — "메시지"란 하나의 assistant 턴에 담긴 tool 호출 묶음을 뜻한다. 하나 호출하고 발사 확인을 받은 뒤 다음 것을 호출하는 방식은 **설령 비동기/백그라운드 발사라도 메시지가 나뉘면 순차 발사이며 금지**(결과 품질엔 지장이 적어도 진행상황 추적·리소스 관리 일관성이 깨짐). **발사 직전 자가점검**: "지금 보내는 메시지에 bugs/style/spec/perf 4개 호출이 전부 포함됐는가?" 하나라도 준비 안 됐으면 넷 다 준비된 뒤 한번에 보낸다. 진행 단위는 가상 청크 `C0` 1개.

**C. 청크 분할 모드**:
청크 내부는 **B와 동일한 단일메시지 4-블록 동시발신 규칙**을 그대로 적용(청크당 4개 서브에이전트 동시 발신). 청크간은 순차(한 청크의 4개 완료 확인 후 다음 청크 발사) — 이는 진행상황 추적과 `--resume` 단위 정합을 위한 **의도적 설계**이며 B의 동시발신 규칙과 모순이 아니다(축간=동시, 청크간=순차). 청크마다 진행 단위 1개.

#### Diff 임시 파일

Step 2의 `branch_review_chunk_plan.py`가 이미 생성해 둔 patch 파일을 그대로 사용한다 (이 Step에서 새로 만들지 않음):

- **인라인/표준 모드**: `<repo-root>/.git/info/branch-review-<short-sha>.patch` 1개 — 모든 finder가 동일 경로를 `{{DIFF_PATH}}`로 받는다.
- **청크 모드**: `<repo-root>/.git/info/branch-review-<short-sha>-<chunk-id>.patch` (예: `-C1.patch`, `-C2.patch`, ...) — 청크마다 별도 파일, 해당 청크의 4 finder가 전부 이 경로를 `{{DIFF_PATH}}`로 받는다(다른 청크의 patch는 참조하지 않음 — cross-chunk blindness의 근원이자 Step 5-0이 필요한 이유).
- `.git/info/`는 항상 ignored — 정리 자동. 서브에이전트는 경로만 받고 Read로 자체 로드(중복 전송 회피).

#### 청크(진행 단위) resume 처리

- `Chunk Status`가 이미 `done`인 청크는 **재실행하지 않는다** — `.process/branch-review-<slug>/chunk-<id>.log`를 Read해 해당 청크의 4 finder raw 출력을 그대로 Step 5 입력에 포함시킨다.
- `pending` / `doing`(중단 흔적) / `blocked`인 청크만 이번 실행에서 (재)발사한다.
- 청크 하나 완료 시(4 finder 전부 성공): 4 finder raw 출력 **verbatim**을 `.process/branch-review-<slug>/chunk-<id>.log`에 Write(신규 파일, 청크당 1개). `Chunk Status` 해당 행 → `done`, `Findings(b/s/sp/p)` 카운트 채움. `progress.md` `Log`에는 **파일 경로 참조 + 1줄 요약만** append(verbatim 원문을 progress.md에 직접 넣지 않는다 — 대형 diff에서 청크 수십 개 × finder 응답 수천 토큰이 누적되면 progress.md 자체가 다루기 어려워지므로, 원문은 청크별 파일로 분리하고 progress.md는 인덱스 역할만 한다).
- 청크 내 finder 1개라도 실패하면 그 청크는 `blocked`로 표시(부분 완료 허용 안 함 — 재개 시 청크 전체를 다시 실행한다. 단순성 우선). `.log` 파일은 만들지 않는다(불완전 결과 보존 안 함).

#### 공통 출력 제약 (4 finder 동일 적용)

- **CRITICAL/MAJOR는 개수 제한 없이 전부 보고** (구버전 400단어 cap이 대형 diff에서 저심각도만 살아남기고 CRITICAL을 자르는 실패를 방지).
- **MINOR/NIT는 카운트 + 대표 2건만** 본문 노출, 나머지는 개수만 Summary에 반영.
- 확신이 낮은 finding은 TYPE에 `JUDGMENT`/`추정` 표기로 자기표시 (verify 패스가 없으므로 finder 스스로 신뢰도를 드러낸다 — Step 4.5 참조).

#### 4 finder 프롬프트 — 템플릿 참조

각 finder 서브에이전트 프롬프트는 SKILL.md에 인라인으로 두지 않고 `skills/branch-review/templates/`의 전용 템플릿을 참조한다:

| finder | 템플릿 파일 | 치환 placeholder |
|---|---|---|
| bugs | `templates/bugs-finder.md` | `{{DIFF_PATH}}` `{{FILE_LIST}}` `{{INTENT}}` `{{REPO_ROOT}}` |
| style | `templates/style-finder.md` | 위 + `{{STANDARDS_BUNDLE}}` `{{STANDARDS_CONFIDENCE}}` |
| spec | `templates/spec-finder.md` | `{{DIFF_PATH}}` `{{FILE_LIST}}` `{{INTENT}}` + `{{SPEC_BUNDLE}}` `{{SPEC_CONFIDENCE}}` |
| perf | `templates/perf-finder.md` | `{{DIFF_PATH}}` `{{FILE_LIST}}` `{{INTENT}}` `{{REPO_ROOT}}` |

절차: 각 템플릿을 Read → Step 3-4 라우팅 매트릭스에서 정한 실제 값으로 `{{...}}`를 치환 → 치환된 전문을 해당 서브에이전트 프롬프트로 그대로 전달. 4개 템플릿 모두 청크 단위로 (즉, 청크마다 그 청크의 diff 하위집합에 맞는 `{{FILE_LIST}}` 등으로) 독립 치환한다.

---

### Step 4.5 — verify 슬롯 (문서화만, 미구현)

향후 확장 지점: 각 finding을 skeptic 서브에이전트가 adversarial 재검(다수결 반증)해 오탐을 제거하는 단계를 여기 삽입할 수 있다. **현재는 미구현** — finder 결과를 그대로 Step 5로 넘긴다. 확신이 낮은 finding은 각 finder가 스스로 `JUDGMENT`/추정 표기로 자기표시하는 것으로 대신한다 (Step 4 공통 출력 제약 참조).

(참고: 청크 모드의 특정 오탐 패턴 — 다른 청크에 해소 근거가 존재하는 경우 — 은 이 슬롯과 별개로 Step 5-0에서 이미 필수 처리된다. 이 슬롯은 그 외 **전체** finding에 대한 범용 재검증이며 여전히 미구현이다.)

---

### Step 5 — 통합 및 충돌 감지

입력 = 이번 실행에서 새로 완료한 청크 결과 **+** `--resume`으로 재사용한 기존 `done` 청크 결과(둘을 합쳐서 집계). 로직 자체는 청크 출처와 무관하게 동일하다.

#### 5-0. Cross-chunk 재검증 (청크 모드 전용, 필수)

청크는 서로의 diff를 못 보므로(cross-chunk blindness), 한 청크에서 "삭제됨/없어짐"으로 보이는 것이 실제로는 **다른 청크에 대응 파일이 존재**해서 생기는 오탐일 수 있다. 다음 패턴의 finding은 최종 집계에 포함하기 전에 반드시 재검증한다:

- **대상**: spec 축 `MISSING`/`PARTIAL`이면서 SEVERITY `CRITICAL`/`MAJOR`인 finding. bugs 축에서 "삭제된 코드의 대응 구현을 확인 못 함"류 문구가 있는 finding(예: "이 클래스가 삭제됐는데 대체 구현이 diff에 안 보인다").
- **절차**: 메인 에이전트가 Grep/Read로 **레포의 현재 상태**(diff가 아니라 실제 파일 트리)를 직접 확인한다 — 삭제됐다고 지목된 기능/클래스/디스크립터의 신규 버전이 다른 청크(다른 파일 경로)에 실존하는지 찾는다. 서브에이전트 재호출 없음(메인이 직접 Grep/Read) — 추가 비용 없음.
- **판정**:
  - 신규 대응 확인됨 → finding을 최종 보고서 본문에서 제외하고, 대신 "Cross-chunk 검증 결과" 섹션에 `~~원문~~ — REFUTED, 근거: <확인한 파일:경로>`로 투명하게 남긴다(silent 삭제 금지 — 왜 빠졌는지 추적 가능해야 함).
  - 신규 대응 못 찾음 → 그대로 finding 유지, 본문에 남긴다.
- 이 재검증은 spec/bugs 축의 특정 오탐 패턴 하나만 좁게 잡는다 — Step 4.5(전체 finding에 대한 범용 adversarial verify)와는 범위가 다르며 Step 4.5는 여전히 미구현이다.

#### 5-1. Dedup

다음 키로 중복 감지:
- 같은 파일 + 라인 ±3 범위 → 동일 위치로 간주
- 같은 파일 + 동일 함수/심볼명 → 동일 위치로 간주
- diff 헝크 식별자 일치 → 동일 위치로 간주

병합 표시 (4축 중 몇 개가 겹치든 접두어에 나열):
```
[bugs+perf] <path>:<line> | <max-severity> | ...
  bugs: <원문>
  perf: <원문>
```

이 병합 판정은 최종 리포트 "6-1.5 Cross-axis 중복" 섹션에 노출한다.

#### 5-2. 충돌 감지

다음 패턴을 "Conflicts" 섹션으로 분리:
- 한쪽 finder가 "X 추가하라" + 다른 finder가 "X 제거하라"
- 한쪽이 "Y 방식으로 구현" + 다른쪽이 "Y 금지" (예: style "추상화 계층 추가" vs perf "인라인화로 오버헤드 제거")
- 한쪽이 "테스트 추가" + 다른쪽이 "이 변경 자체 SCOPE-CREEP"
- spec "기능 제거 요구" vs bugs "이 함수의 버그 수정 필요" (제거 대상에 수정 제안)

감지 방법: 같은 파일/심볼에 대해 여러 finder의 동사("add"/"remove", "use"/"don't use") 또는 Fix 텍스트 의미 비교. **확신 부족하면 충돌로 표기하지 않는다** (false positive 회피).

메인 에이전트는 해결 시도 금지 — 사용자에게 결정 위임.

#### 5-3. NIT 억제 (기본 동작)

NIT 항목은 finder 자체가 이미 Step 4 공통 출력 제약("카운트 + 대표 2건")으로 축약해 verbatim 출력에 포함한다 — 6-1 verbatim 원칙에 따라 그 대표 2건은 최종 리포트에도 그대로 노출된다(이는 정상이며 본 조항 위반이 아니다). 본 조항은 finder 출력을 넘어선 추가 편집(대표 예시까지 지우는 등)을 금지하는 취지다. 사용자가 "NIT 포함"을 요청하면 대표 2건을 넘는 나머지는 `.process/branch-review-<slug>/chunk-<id>.log`의 원본 finder 응답에서 전체 목록을 확인해 펼친다(재호출 불필요 — 원본에 이미 존재).

**기록**: progress.md `Step5-집계` → `done`.

---

### Step 6 — 종합 보고 및 영속화

#### 6-1. Verbatim 노출

4개 finder 출력을 **재정렬·재작성 없이** 그대로 노출 (bugs / style / spec / perf 4섹션). 메인 에이전트의 편향 차단.

#### 6-1.5. Cross-axis 중복 노출

Step 5-1에서 2개 이상 축이 겹친다고 판정된 그룹만 4개 verbatim 섹션 + Conflicts 다음, Summary 이전에 노출:
```
[axis+axis+...] <path>:<line 또는 symbol> | max=<SEVERITY>
  <axis1>: <원문 1줄 요약>
  <axis2>: <원문 1줄 요약>
```
겹친 그룹이 0개면 이 섹션 자체를 생략한다(빈 섹션 노출 금지). 4개 verbatim 섹션(6-1)은 이 섹션과 무관하게 원문 그대로 유지 — 이 섹션은 추가이지 대체가 아니다.

#### 6-2. 최종 요약

```
## Summary
- bugs:  <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed)
- style: <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed) | Standards source: <STRONG|WEAK|NONE>
- spec:  <N> findings (Missing: A, Partial: B, Scope-creep: C, Flaw: D) | Spec source: <라벨 + 신뢰도>
- perf:  <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed)
- Conflicts: <N>
- Tests: <added | partial | missing | n/a>
- Intent mismatches: <N>
[청크 모드였다면] ⚠ 청크 분할 리뷰 — 청크간 ripple(교차 영향) 미검출.
[spec 등급이 FALLBACK 또는 NONE] ⚠ spec 근거 빈약 — MISSING/PARTIAL 판정 보수적으로 자제된 상태, bugs/perf 결과에 상대적으로 더 의존할 것.
[standards 등급이 NONE] ⚠ style 근거 문서·lint 설정 전무 — 주변 코드 대비 명백 일탈만 보고됨.
[CRITICAL이 1건이라도 있으면 필수] CRITICAL 목록: <axis> <path>:<line> — <한줄 요약> (전건 나열, 축 무관)
```

**CRITICAL 목록이 필수인 이유**: 6-3 precedence 규칙은 "가장 우선한 규칙 1개"만 Recommendation 라벨로 노출한다 — 즉 bugs CRITICAL 1건 때문에 `FIX-CRITICAL-FIRST`가 뜨면 style/perf 축에 있는 다른 CRITICAL들은 라벨 하나에 가려진다. Summary에 축 무관 전체 CRITICAL을 별도로 나열해 이 정보손실을 막는다.

#### 6-3. Recommendation — precedence 규칙

복수 조건이 동시에 성립하면 **번호가 빠른(상위) 규칙 1개만** 채택한다:

```
1. bugs CRITICAL ≥ 1                              → FIX-CRITICAL-FIRST (머지 보류)
2. Conflicts ≥ 1                                  → RESOLVE-CONFLICTS (의도 재확인 필요)
3. Intent mismatch ≥ 1                            → RECONFIRM-INTENT (작성자 의도 확인 필요)
4. spec MISSING/PARTIAL ≥ 2 (등급 HIGH 또는 MEDIUM) → BLOCK-SPEC-MISMATCH (재작업 필요)
5. 임의 축(bugs/style/spec/perf)에 MAJOR ≥ 1        → FIX-MAJOR-THEN-SHIP (수정 후 머지)
6. (위 전부 미해당)                                → SHIP (머지 가능)
```

**부연설명 (조건부 필수)**: 채택된 규칙이 1~4번(5번 "임의 축 MAJOR≥1"보다 먼저 매치)이면서 4축 MAJOR 총합이 2건 이상이면, Recommendation 아래 1줄 필수: "참고: 채택된 규칙(<번호>)이 MAJOR <N>건보다 우선순위가 높아 라벨을 차지함 — Summary 참조." (6-2 CRITICAL 목록 요구사항과 동일한 정보손실 방지 목적.)

#### 6-4. 결과 영속화

최종 보고 전문(4섹션 verbatim + Summary + Recommendation)을 `.review/branch-review-<slug>.md`에 Write한다. 저장 직후 `.gitignore`에 `.review/` 항목이 없으면 1줄 advisory만 출력한다 (예: `참고: .gitignore에 .review/ 추가를 권장합니다`) — **`.gitignore` 파일 자체는 자동 편집하지 않는다** (read-only 계약 유지, doc-driven-review와 동일).

**기록**: progress.md `Step6-보고` → `done`.

---

## 출력 포맷 옵션

| 옵션 | 트리거 | 동작 |
|---|---|---|
| 기본 | (없음) | 위 long-form, NIT 억제 |
| compact / 1줄 / 짧게 | 사용자 요청 | finding마다 1줄, 섹션 헤더 최소화 |
| verbose / 전체 / NIT 포함 | 사용자 요청 | NIT 펼침 + JUDGMENT 별도 섹션 |

Compact 예시:
```
[CRITICAL][bugs][BOUNDARY] src/auth.ts:42 토큰 만료 `<` 사용. Fix: `<=`.
[MAJOR][spec][PARTIAL] PRD §3.2 리프레시 grace period 누락. Fix: 5분 window 추가.
[MAJOR][perf][N+1] src/orders.ts:60 루프당 DB 호출. Fix: 배치 조회.
[MINOR][style][JUDGMENT] src/utils.ts:88 export 불필요.
```

---

## 예시 출력 (표준 모드)

```
## Branch Review: feature/auth-refactor

기준점: origin/main (merge-base = abc1234)
변경 규모: 12 files, 487 lines (+312/-175), 제외 후
Spec source: GitHub issue #234 [HIGH]
Standards source: CLAUDE.md + eslint.config.js [STRONG]
Intent: "Add JWT refresh rotation per security audit Q1"

---

## bugs (verbatim)

src/auth/middleware.ts:42 | CRITICAL | BOUNDARY | 토큰 만료 비교에 `<` 사용 — 경계 시각 통과. Fix: `<=`.
src/auth/refresh.ts:88 | MAJOR | LOGIC | async 함수 try/catch 누락. Fix: try/catch 감싸기 + logger.error.

Tests: added (src/auth/__tests__/refresh.test.ts)
Intent mismatch: none.

---

## style (verbatim)

src/utils/jwt.ts:15 | MINOR | JUDGMENT | private 함수 export. 레포 패턴 위반. Rule: "N/A (관례)". Fix: export 제거.

---

## spec (verbatim)

§3.2 리프레시 토큰 회전 | MAJOR | PARTIAL | 회전 구현됐으나 "직전 토큰 5분 grace period" 누락. Spec: "회전 후 직전 토큰은 5분간 유효해야 한다". Fix: refresh.ts grace window 추가.
src/utils/logger.ts | MINOR | SCOPE-CREEP | 이슈 #234 범위 밖. Spec: 로깅 변경 요구 없음. Fix: 별도 PR 분리.

---

## perf (verbatim)

없음.

---

## Conflicts
없음.

---

## Summary
- bugs:  2 findings (Critical: 1, Major: 1, Minor: 0, Nit: 0)
- style: 1 findings (Critical: 0, Major: 0, Minor: 1, Nit: 0) | Standards source: STRONG
- spec:  2 findings (Missing: 0, Partial: 1, Scope-creep: 1, Flaw: 0) | Spec source: issue #234 [HIGH]
- perf:  0 findings
- Conflicts: 0
- Tests: added
- Intent mismatches: 0
- CRITICAL 목록: bugs src/auth/middleware.ts:42 — 토큰 만료 비교 `<` 사용

## Recommendation
FIX-CRITICAL-FIRST: 토큰 만료 비교 버그 보안 영향. 머지 전 수정 필수.

---
저장됨: .review/branch-review-abc1234.md
```

---

## 트리거 문구 예시

- "main부터 리뷰해줘"
- "이 PR 리뷰"
- "review since v1.4.0"
- "브랜치 검토"
- "변경사항이 spec 맞는지 봐줘"
- "내 작업 컨벤션 따랐는지 확인"
- "성능 저하 없는지 봐줘"
- "머지 전 검토"
- "중단된 리뷰 재개" / "branch-review --resume"

---

## 한계 / 비범위

- **verify(전체 대상 adversarial 재검) 없음** — 4 finder 각각 1회 결과를 그대로 신뢰. 오탐 가능성 있음. 확신 낮은 finding은 JUDGMENT/추정 표기로 자기표시하나, 전체 finding 대상 검증 패스는 Step 4.5 슬롯 참조(미구현). 단, 청크 모드의 "다른 청크에 해소 근거가 있는 오탐" 패턴만은 Step 5-0에서 필수 재검증됨(좁은 범위).
- **보안 전문 리뷰는 별도** — bugs finder는 표면 검사(SECURITY-SURFACE)만. 심층 보안 검토는 `/security-review` 사용.
- **자동 수정 안 함** — read-only 리뷰(소스 파일 미수정). fix는 사용자 또는 별도 스킬. `.process/`·`.review/` 산출물 쓰기는 이 계약 밖(위 "실행 환경" 참조).
- **CI 통합 안 함** — 로컬 또는 대화 내 검토.
- **청크 분할 시 cross-chunk blindness** — 청크간 교차 영향(ripple)은 완전히 검출되지 않는다(Step 5-0이 spec MISSING/PARTIAL·bugs 삭제-확인불가 패턴만 좁게 재검증). Step 6 Summary에 경고 필수.
- **생성 파일 배제는 확장자 일반화가 아님** — lockfile/빌드산출물/이미지·폰트·`.min.*`/`linguist-generated` 속성만 자동 제외한다. 이름만으로 "생성됨"이 짐작되는 개별 파일(예: 리포트 스냅샷 `.html`)은 자동 제외 대상이 아니다 — `.gitattributes`에 `linguist-generated` 명시가 정석 경로.
- **5만 라인급 머지** — 청크 분할로 동작은 하나 정확도 보장 안 됨. 사람 검토 권장. 청크 수가 많아지면 서브에이전트 수(4N)도 비례 증가 — Step 2가 발사 전 개수를 고지하나 비용 자체를 줄이진 않는다.
- **`.process/`·`.review/` 산출물은 sha별로 누적되며 자동 정리 안 함** — 오래된 디렉터리·리포트 파일은 수동 삭제 필요(비파괴적 — 소스 파일이 아니므로 방치해도 안전). 청크별 raw 로그(`chunk-<id>.log`)도 같은 디렉터리에 누적됨.
- **finder 1개 실패 시** — 해당 축(또는 그 청크)에 "실행 실패 — 재호출 권장" 표기하고 나머지는 정상 보고(전체 중단하지 않음). 청크는 `blocked`로 표시되어 `--resume` 시 전체 재실행 대상이 된다.
