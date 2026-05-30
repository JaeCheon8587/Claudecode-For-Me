---
name: branch-review
description: HEAD ↔ 고정점(ref) diff을 Standards/Spec 2축으로 병렬 검토. 심각도 등급, diff 크기 cap, 충돌 감지, commit-msg fallback, 다언어 컨벤션 지원. 사용자가 "브랜치 리뷰", "PR 리뷰", "review since X", "변경사항 검토" 요청 시 트리거. 단순 PR 코멘트가 아닌 "규칙 따랐나(Standards) + 시킨 거 했나(Spec)" 분리 검증이 필요한 모든 상황에서 사용.
argument-hint: "[고정점 ref — 미지정 시 merge-base 자동 추정]"
---

# Branch Review

HEAD ↔ 고정점(commit/branch/tag/merge-base) 사이 변경을 **Standards 축**(레포 컨벤션 준수)과 **Spec 축**(원 요구사항 충족) 두 갈래로 **병렬** 검토한다.

## 왜 2축 분리인가

한 축이 다른 축을 가린다 (masking):
- 코드 깔끔 + **엉뚱한 기능** → 단일 리뷰는 Standards만 보고 통과시킨다
- 요구사항 충족 + **컨벤션 위반** → 단일 리뷰는 Spec만 보고 통과시킨다

두 축을 **독립 서브에이전트**로 동시 평가하면 위 시나리오가 모두 노출된다.

---

## 실행 환경

- 모든 git 명령은 PowerShell/Bash 양쪽 호환. 사용자가 Windows이면 Bash 툴 또는 PowerShell 둘 다 동작.
- `gh` CLI 선택적 — 없으면 Step 3에서 PR description fallback 건너뜀.
- 이슈 트래커 MCP (Linear/Jira/GitHub Issues/Notion 등) 선택적 — 없으면 커밋 메시지 본문만으로 이슈 내용 추정.
- 모든 서브에이전트는 `subagent_type: "general-purpose"` 사용. Read/Grep/Glob 권한 보유.

---

## Process

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

---

### Step 2 — Diff 크기 측정 및 전략 선택

`--stat` 결과로 임계값 분기 (총 변경 라인 = additions + deletions, 제외 패턴 적용 후):

| 변경 라인 | 변경 파일 | 전략 |
|---|---|---|
| 0 | 0 | "변경 없음" 보고 후 종료 |
| 1~50 | 1~2 | **인라인 통합 모드** (단일 호출, 병렬 불필요) |
| 51~2000 | 3~50 | **표준 2축 병렬 모드** |
| 2001 초과 또는 파일 51개 이상 | — | **청크 분할 모드** |

**임계값 근거**:
- 50라인 미만은 메인 컨텍스트로 충분 — 서브에이전트 오버헤드가 작업 비용 초과.
- 2000라인은 서브에이전트 컨텍스트 안정 영역 상한 (diff + 표준 파일 + 지시 합산).

**제외 패턴** (`--stat` 측정 전 적용):
```
:(exclude)*.lock
:(exclude)package-lock.json :(exclude)pnpm-lock.yaml :(exclude)yarn.lock
:(exclude)Cargo.lock :(exclude)poetry.lock :(exclude)uv.lock :(exclude)Gemfile.lock
:(exclude)dist :(exclude)build :(exclude)out :(exclude)node_modules
:(exclude)*.min.js :(exclude)*.min.css :(exclude)*.map
:(exclude)*.png :(exclude)*.jpg :(exclude)*.jpeg :(exclude)*.gif :(exclude)*.ico
:(exclude)*.woff :(exclude)*.woff2 :(exclude)*.ttf :(exclude)*.eot
```

추가로 `git check-attr -a -- <path>` 출력에 `linguist-generated: set` 포함된 파일도 제외.

**청크 분할 규칙**:
1. 그룹 기준 — 최상위 디렉토리 → 같은 디렉토리는 한 청크.
2. 단일 디렉토리가 2000라인 초과 시 → 파일 단위 청크.
3. 청크당 상한 = 1500라인, 30파일.
4. 각 청크에 표준 2축 병렬 실행 (N개 청크 = 2N 서브에이전트, 동시 발사 가능하면 동시, 아니면 청크별 순차 + 축 동시).
5. 결과 병합: 청크간 dedup (Step 6-2 규칙 그대로 적용), 카운트 합산.

---

### Step 3 — Spec 위치 탐색 (다층 fallback)

원 요구사항 출처를 다음 우선순위로 **모두 수집** (첫 매치에서 멈추지 않음 — 누락 방지):

1. **커밋 메시지 이슈 참조** — 정규식 `#\d+|[A-Z]+-\d+|(?i)closes\s+#\d+|fixes\s+#\d+` 추출. 이슈 트래커 MCP 있으면 본문 조회. 없으면 이슈 번호 + 커밋 메시지만 기록.
2. **사용자 명시 경로** — 인자로 받은 spec 파일.
3. **레포 표준 위치** — 최근 30일 내 변경된 매칭 문서:
   - `docs/**/*.md`, `specs/**/*.md`, `.scratch/**/*.md`, `.atdd/**/*.md`
   - 브랜치명과 유사 토큰 매칭 (e.g. `feature/auth` → `auth`, `authentication` 포함 파일).
4. **PR description** — `gh pr view --json title,body` 가능 시 본문. 실패 시 건너뜀.
5. **Commit message fallback** — 위 모두 빈약 시 `git log <ref>..HEAD` 본문 전체를 **합성 spec**으로 사용.
6. **완전 부재** — 위 모두 실패.

**Spec source 신뢰도 등급** (Step 5 Spec 에이전트에 전달):
- `HIGH`: 이슈 본문 확보 + docs 매칭 둘 다.
- `MEDIUM`: 이슈 본문 or docs 한쪽만.
- `LOW`: 이슈 번호만 (본문 미확보) or PR description만.
- `FALLBACK`: 커밋 메시지 합성 — Spec 에이전트는 MISSING/PARTIAL 보고 자제, SCOPE-CREEP/FLAW 위주.
- `NONE`: 완전 부재 — Spec 에이전트는 SCOPE-CREEP과 명백한 결함만 보고. MISSING/PARTIAL 보고 금지.

**변경 의도 추출**: 커밋 메시지 첫 줄들을 별도 "Intent" 블록으로 추출해 두 에이전트 **모두**에 전달 (Standards는 의도와 변경 일치 평가, Spec은 spec과의 일치 평가).

---

### Step 4 — Standards 문서 수집 (다언어, 인라인 로드 포함)

#### 4-1. 수집 대상 glob

**범용**:
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
| `*.csproj`, `*.sln` | `.editorconfig`, `Directory.Build.props`, `*.ruleset`, `.editorconfig` |
| `Gemfile` | `.rubocop.yml` |
| `*.swift`, `Package.swift` | `.swiftlint.yml`, `.swiftformat` |

#### 4-2. 인라인 vs 경로 전달

- **≤200 라인 파일**: 메인이 Read → 서브에이전트 프롬프트에 본문 인라인 (재로딩 비용 회피).
- **>200 라인 파일**: 경로 + 목차만 전달, 에이전트가 필요 섹션 Read.
- 합산 인라인 본문이 6000 토큰 초과 시 모든 파일을 경로 전달로 다운그레이드.

---

### Step 5 — 서브에이전트 호출

#### 모드 분기

**A. 인라인 통합 모드** (≤50라인, 1~2 파일):
메인 에이전트가 직접 검토. 서브에이전트 호출 없음. 출력 포맷은 Step 6과 동일 (Standards/Spec 두 섹션 분리 작성).

**B. 표준 2축 병렬 모드**:
두 서브에이전트를 **동일 메시지 내 동시 호출** (parallel tool call). 직렬 발사 금지.

**C. 청크 분할 모드**:
청크당 2개 서브에이전트. 청크간 순차, 축간 동시.

#### Diff 임시 파일

- 경로: `<repo-root>/.git/info/branch-review-<short-sha>.patch` — `.git/info/`는 항상 ignored, 정리 자동.
- 종료 시 (성공/실패 무관) 삭제 시도.
- 서브에이전트는 경로만 받고 Read로 자체 로드 (중복 전송 회피).

#### 5-A. Standards 서브에이전트 프롬프트

```
역할: 변경 코드의 레포 코딩 컨벤션 준수 검토.

도구: Read, Grep, Glob.

입력:
- diff 파일 경로: <path>
- 변경 파일 목록: <list>
- 표준 파일 (인라인 + 경로): <bundle>
- Intent 블록 (커밋 메시지 요약): <text>
- 레포 루트: <path>

지시:
1. Finding 포맷 강제:
   `<path>:<line> | <SEVERITY> | <TYPE> | <문제 1줄>. Fix: <조치>.`
   - SEVERITY: CRITICAL / MAJOR / MINOR / NIT
   - TYPE: VIOLATION (명백 위반) / JUDGMENT (판단 사안)
2. SEVERITY 정의:
   - CRITICAL: 보안/데이터 손실/심각한 컨벤션 위반 — 머지 차단 사유
   - MAJOR: 명백한 표준 위반, 일관성 깨짐 — 머지 전 수정 권장
   - MINOR: 사소한 스타일/네이밍 — 후속 가능
   - NIT: 의견 차원 — 보고 자제 (확신 있을 때만)
3. lint/formatter 자동 캐치 항목 보고 금지 (prettier, eslint --fix, ruff format 등).
4. 변경 헝크만으로 판단 불가하면 Grep으로 호출처/유사 패턴 확인 후 판단.
5. Intent와 실제 변경 불일치 발견 시 별도 [INTENT-MISMATCH] 라벨로 보고.
6. 테스트 동반 평가 한 줄: "Tests: added / partial / missing / N/A".
7. 출력 400단어 이하. CRITICAL/MAJOR 우선, NIT 최소.
```

#### 5-B. Spec 서브에이전트 프롬프트

```
역할: 변경 코드의 원 요구사항 충족 검토.

도구: Read, Grep, Glob.

입력:
- diff 파일 경로: <path>
- 변경 파일 목록: <list>
- Spec 내용 (인라인 + 출처 라벨): <text>
- Spec source 신뢰도: HIGH | MEDIUM | LOW | FALLBACK | NONE
- Intent 블록: <text>

지시:
1. Finding 포맷:
   `<requirement-or-area> | <SEVERITY> | <TYPE> | <문제>. Spec: "<인용 또는 N/A>". Fix: <조치>.`
   - TYPE: MISSING / PARTIAL / SCOPE-CREEP / FLAW
2. 신뢰도별 행동:
   - HIGH/MEDIUM: 모든 TYPE 활성
   - LOW: MISSING/PARTIAL은 "강한 증거 있을 때만"
   - FALLBACK: SCOPE-CREEP/FLAW 위주, MISSING/PARTIAL 자제
   - NONE: SCOPE-CREEP과 명백한 FLAW만
3. spec 원문 인용 필수 (FALLBACK/NONE은 커밋 메시지/Intent 인용 가능).
4. 변경된 함수의 호출자/소비자 확인이 필요하면 Grep 사용.
5. 출력 400단어 이하.
```

---

### Step 6 — 통합 보고

#### 6-1. Verbatim 노출

두 서브에이전트 출력을 **재정렬·재작성 없이** 그대로 노출. 메인 에이전트의 편향 차단.

#### 6-2. Dedup

다음 키로 중복 감지:
- 같은 파일 + 라인 ±3 범위 → 동일 위치로 간주
- 같은 파일 + 동일 함수/심볼명 → 동일 위치로 간주
- diff 헝크 식별자 일치 → 동일 위치로 간주

병합 표시:
```
[Standards+Spec] <path>:<line> | <max-severity> | ...
  Standards: <원문>
  Spec: <원문>
```

#### 6-3. 충돌 감지

다음 패턴을 "Conflicts" 섹션으로 분리:
- 한쪽이 "X 추가하라" + 다른쪽이 "X 제거하라"
- 한쪽이 "Y 방식으로 구현" + 다른쪽이 "Y 금지"
- 한쪽이 "테스트 추가" + 다른쪽이 "이 변경 자체 SCOPE-CREEP"

감지 방법: 같은 파일/심볼에 대해 양 축 finding의 동사("add"/"remove", "use"/"don't use") 또는 Fix 텍스트 의미 비교. 확신 부족하면 충돌로 표기하지 않음 (false positive 회피).

메인 에이전트는 해결 시도 금지 — 사용자에게 결정 위임.

#### 6-4. NIT 억제 (기본 동작)

NIT 항목은 기본 출력에서 카운트만 표기, 본문 노출 안 함. 사용자가 "NIT 포함" 요청 시에만 펼침.

#### 6-5. 최종 요약

```
## Summary
- Standards: <N> findings (Critical: X, Major: Y, Minor: Z, Nit: W — suppressed)
- Spec: <N> findings (Missing: A, Partial: B, Scope-creep: C, Flaw: D)
- Spec source: <라벨 + 신뢰도>
- Conflicts: <N>
- Tests: <added | partial | missing | n/a>
- Intent mismatches: <N>

## Recommendation
<한 줄 — 다음 중 하나>
- SHIP: CRITICAL/MAJOR 0건. 머지 가능.
- FIX-MINOR-THEN-SHIP: MAJOR ≤2건, CRITICAL 0건. 작은 수정 후 머지.
- FIX-CRITICAL-FIRST: CRITICAL ≥1건. 머지 보류.
- BLOCK-SPEC-MISMATCH: Spec MISSING/PARTIAL ≥2건. 재작업 필요.
- RESOLVE-CONFLICTS: 축간 모순 존재. 의도 재확인 필요.
- RECONFIRM-INTENT: Intent mismatch ≥1건. 작성자 의도 확인 필요.
```

---

## 출력 포맷 옵션

| 옵션 | 트리거 | 동작 |
|---|---|---|
| 기본 | (없음) | 위 long-form, NIT 억제 |
| compact / 1줄 / 짧게 | 사용자 요청 | finding마다 1줄, 섹션 헤더 최소화 |
| verbose / 전체 / NIT 포함 | 사용자 요청 | NIT 펼침 + JUDGMENT 별도 섹션 |

Compact 예시:
```
[CRITICAL][Standards][VIOLATION] src/auth.ts:42 토큰 만료 `<` 사용. Fix: `<=`.
[MAJOR][Spec][PARTIAL] PRD §3.2 리프레시 grace period 누락. Fix: 5분 window 추가.
[MINOR][Standards][JUDGMENT] src/utils.ts:88 export 불필요.
```

---

## 예시 출력 (표준 모드)

```
## Branch Review: feature/auth-refactor

기준점: origin/main (merge-base = abc1234)
변경 규모: 12 files, 487 lines (+312/-175), 제외 후
Spec source: GitHub issue #234 [HIGH]
Intent: "Add JWT refresh rotation per security audit Q1"

---

## Standards Review (verbatim)

src/auth/middleware.ts:42 | CRITICAL | VIOLATION | 토큰 만료 비교에 `<` 사용 — 경계 시각 통과. Fix: `<=`.
src/auth/refresh.ts:88 | MAJOR | VIOLATION | async 함수 try/catch 누락. CLAUDE.md §4 위반. Fix: try/catch 감싸기 + logger.error.
src/utils/jwt.ts:15 | MINOR | JUDGMENT | private 함수 export. 레포 패턴 위반. Fix: export 제거.

Tests: added (src/auth/__tests__/refresh.test.ts)
Intent mismatch: none.

---

## Spec Review (verbatim)

§3.2 리프레시 토큰 회전 | MAJOR | PARTIAL | 회전 구현됐으나 "직전 토큰 5분 grace period" 누락. Spec: "회전 후 직전 토큰은 5분간 유효해야 한다". Fix: refresh.ts grace window 추가.
src/utils/logger.ts | MINOR | SCOPE-CREEP | 이슈 #234 범위 밖. Spec: 로깅 변경 요구 없음. Fix: 별도 PR 분리.

---

## Conflicts
없음.

---

## Summary
- Standards: 3 findings (Critical: 1, Major: 1, Minor: 1, Nit: 0)
- Spec: 2 findings (Missing: 0, Partial: 1, Scope-creep: 1, Flaw: 0)
- Spec source: issue #234 [HIGH]
- Conflicts: 0
- Tests: added
- Intent mismatches: 0

## Recommendation
FIX-CRITICAL-FIRST: 토큰 만료 비교 버그 보안 영향. 머지 전 수정 필수.
```

---

## 트리거 문구 예시

- "main부터 리뷰해줘"
- "이 PR 리뷰"
- "review since v1.4.0"
- "브랜치 검토"
- "변경사항이 spec 맞는지 봐줘"
- "내 작업 컨벤션 따랐는지 확인"
- "머지 전 검토"

---

## 한계 / 비범위

- **보안 전문 리뷰는 별도** — 본 스킬은 표면 검사. 심층 보안 검토는 `/security-review` 사용.
- **자동 수정 안 함** — read-only 리뷰. fix는 사용자 또는 별도 스킬.
- **CI 통합 안 함** — 로컬 또는 대화 내 1회성 검토.
- **5만 라인급 머지** — 청크 분할로 동작은 하나 정확도 보장 안 됨. 사람 검토 권장.
- **재시도 메커니즘 없음** — 결과 빈약 시 사용자가 재호출. 자동 재발사 안 함.
- **결과 영속화/캐시 없음** — 같은 ref 재리뷰 시 매번 재실행.
