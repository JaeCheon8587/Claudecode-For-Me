# Claudecode-For-Me

> **Claude Code Plugin** · v1.14.0 · 커스텀 스킬 8종 + 슬래시 커맨드 10종 모음

`/plugin marketplace add` 한 번으로 모든 프로젝트에서 동일한 워크플로(요구사항 정제 → 문서 하네스 → 구현 자동화 → 브랜치 리뷰 → 커밋)를 슬래시 커맨드로 호출할 수 있게 묶은 Claude Code 플러그인이다.

---

## 1. 플러그인 개요

| 항목 | 값 |
|---|---|
| 이름 | `claudecode-for-me` |
| 버전 | `1.14.0` |
| 매니페스트 | `.claude-plugin/plugin.json` |
| 마켓플레이스 | `.claude-plugin/marketplace.json` |
| 설치 위치 | `~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<version>/` (글로벌) |
| 네임스페이스 | `/claudecode-for-me:<name>` |
| 구성요소 | Skill 8 · Command 10 · Python runner 4 (`scripts/`) |

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
```

## 3. 업데이트

```text
/plugin marketplace update claudecode-for-me
/plugin update claudecode-for-me@claudecode-for-me
```

- `plugin.json` / `marketplace.json`의 `version`이 올라가야 클라이언트가 변경을 인식한다.
- **세션 재시작 필수**. 기존 세션은 구버전 매니페스트를 그대로 보유.
- 캐시: `~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<version>/` — 구·신버전 공존 가능, 활성은 최신 1개.

## 4. 제거

```text
/plugin uninstall claudecode-for-me@claudecode-for-me
/plugin marketplace remove claudecode-for-me
```

---

## 5. 플러그인 구성요소

### Skill 8종

| Skill | 슬래시 커맨드 | 역할 |
|---|---|---|
| `branch-review` | `/claudecode-for-me:branch-review [ref]` | HEAD↔ref diff을 Standards/Spec 2축 병렬 검토 |
| `docs-add-frd` | `/claudecode-for-me:docs-add-frd [요청]` | v0.7 per-App 신규 기능 FRD + ARD 생성, PRD/FC/ARD-CATALOG 갱신 |
| `docs-add-task` | `/claudecode-for-me:docs-add-task [요청]` | v0.7 per-App 기존 기능 수정 TASK + ARD 생성, FC/영향 FRD/ARD-CATALOG 갱신 |
| `e2e-sequence` | `/claudecode-for-me:e2e-sequence [기능]` | E2E 메시지 흐름 → Mermaid 시퀀스 다이어그램 |
| `forge-cancel` | `/claudecode-for-me:forge-cancel <phase>` | forge phase 브랜치·산출물 정리 |
| `forge-full` | `/claudecode-for-me:forge-full <phase>` | 문서 기반 전체 프로젝트 구현 phase runner |
| `forge-scope` | `/claudecode-for-me:forge-scope <prompt>` | 단일 FRD·기능·버그픽스용 경량 phase runner |
| `grill-me` | `/claudecode-for-me:grill-me [주제]` | 1문 1답으로 요구사항 모호점 추적 |
| `meta-prompter` | `/claudecode-for-me:meta-prompter [요청]` | 거친 요청 → 구조화된 메타 프롬프트 |

### Command 10종 (Skill 래퍼 + 단독 커맨드)

| Command | 설명 |
|---|---|
| `branch-review` | branch-review skill 진입 |
| `commit-analysis` | 변경 분석 후 `[ADD]`/`[MOD]`/`[FIX]` 자동 판단 한글 커밋 생성 |
| `docs-add-frd` | docs-add-frd skill 진입 (신규 기능 FRD + ARD) |
| `docs-add-task` | docs-add-task skill 진입 (기존 기능 수정 TASK + ARD) |
| `e2e-sequence` | e2e-sequence skill 진입 |
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
- **Spec 5층 fallback**: 이슈본문 → docs/specs → PR description → 커밋 메시지 → 부재 (HIGH/MEDIUM/LOW/FALLBACK/NONE)
- **다언어**: TS/JS · Python · Go · Rust · Java/Kotlin · C#/.NET · Ruby · Swift
- **충돌**: 축간 모순 finding을 별도 "Conflicts" 섹션
- **Recommendation**: SHIP / FIX-MINOR-THEN-SHIP / FIX-CRITICAL-FIRST / BLOCK-SPEC-MISMATCH / RESOLVE-CONFLICTS / RECONFIRM-INTENT
- **비범위**: 심층 보안 리뷰는 `/security-review` 위임, 자동 fix·CI 통합 없음

### 6.2 docs-add-frd / docs-add-task (v0.7 per-App SSOT)

```
/claudecode-for-me:docs-add-frd 주문 검색 기능 추가
/claudecode-for-me:docs-add-task 주문 검색에 cursor 페이지네이션 추가
```

- **v0.7 per-App 전용** — `Docs/_templates/App/` 양식 (20 section FRD, 5 표 FC, ARD/ARD-CATALOG/TASK)
- **In-place 수정** — source repo 직접 쓰기. preview 없음.
- **ARD 항상 강제** — FRD 또는 TASK 1개 = ARD 1개 동반 (결정 없으면 placeholder 자동)
- **/docs-add-frd**: 신규 기능 — FRD + ARD 생성, App-PRD §3.1·§7 갱신, FC 5표 행 추가, ARD-CATALOG Proposed +1
- **/docs-add-task**: 기존 기능 수정/refactor — TASK + ARD 생성, AI 가 FC 보고 영향 FRD 다수 자동 식별, 영향 FRD 변경 이력 + section 갱신, FC 상태 갱신, ARD-CATALOG Proposed +1
- **TASK 양방향 인용 금지** (v0.7) — TASK 본문 ↔ 영구 SSOT 마크다운 링크 X
- **자기 검증** — 쓰기 후 `python scripts/docs_helpers.py check --repo .` 자동
- **사전 확정** — 모든 변경 사전 요약 → `AskUserQuestion` 확정 → 쓰기
- Python helper (read-only): `python scripts/docs_helpers.py {list-apps|next-id|parse-fc|parse-frd|git-user|check}`

### 6.3 e2e-sequence

```
/claudecode-for-me:e2e-sequence 로그인
```

- **2단계 파이프라인**: Explore 에이전트 코드 추적 → 메인 Mermaid 생성
- 서비스 간 통신 (HTTP·WebSocket·메시지 큐 등) 시각화
- **참여자 통합**: 같은 프로세스 레이어(ViewModel/UseCase/Service)는 단일 participant, 내부 처리는 `Note over`
- **alt/deactivate 충돌 방지**: `alt`/`else` 블록 내부 `deactivate` 금지
- **외부 시스템 부재 가시화**: DB·MQ·WS·캐시·외부 HTTP 모두 기재(미사용도 X로 명시)
- MCP Mermaid Chart 도구로 렌더링 검증
- 출력: `Docs/E2E-Sequence/{기능명}_Sequence.md`

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
./Docs/_templates/   (8 템플릿)
```

#### 사용 예시

```bash
# FRD 단건 구현 (권장 — splitter 우회, 토큰 절감)
/claudecode-for-me:forge-scope /Docs/FRD/FRD-F003.md FRD-F003 주문 상태 API 구현

# 자유 텍스트 prompt (phase-dir 자동 도출, 확인 1회)
/claudecode-for-me:forge-scope 로그인 기능에 소셜 로그인 옵션 추가

# 전체 프로젝트 구현
/claudecode-for-me:forge-full mvp-v2 --prompt="MVP v2 전체 구현" --docs-mode=recursive --trust

# plan 미리보기 (파일·브랜치 생성 없음)
/claudecode-for-me:forge-full order-flow --plan-only --prompt="주문 흐름" --doc=Docs/FRD/FRD-F009.md --trust

# 취소
/claudecode-for-me:forge-cancel login-feature --dry-run
/claudecode-for-me:forge-cancel login-feature --kind scoped
```

#### forge-scope 인자 모드

- **Mode 1 (prompt-only)**: 일반 텍스트 → phase-dir 자동 도출 + 확인 1회
- **Mode 2 (doc + prompt)**: 첫 토큰이 `Docs/...md` / `/Docs/...md`(대소문자 무시) → `--doc` 분리
- FRD(`Docs/FRD/` 하위) → `--preset=frd-implementation --compact-docs` 자동
- 일반 문서 → `--single-step --compact-docs` 자동

#### forge-full 주요 옵션

| 옵션 | 설명 |
|---|---|
| `--prompt` | plan 생성 입력 (반복 가능) |
| `--doc` | guardrail 문서 (`Docs/` 하위 `.md`, 반복 가능) |
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
- step.md 5개 헤딩 **한국어 고정** (`## 읽어야 할 파일` 등, harness_framework 원본 동작).

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

---

## 7. 프로젝트 구조

```
Claudecode-For-Me/
├── .claude-plugin/
│   ├── plugin.json              # 매니페스트 (name·version·author)
│   └── marketplace.json         # 마켓플레이스 등록 정보
├── skills/
│   ├── branch-review/           # 2축 diff 리뷰
│   ├── docs-add-frd/            # v0.7 신규 기능 FRD + ARD
│   ├── docs-add-task/           # v0.7 기존 기능 TASK + ARD
│   ├── e2e-sequence/            # Mermaid 시퀀스 생성
│   ├── forge-cancel/            # phase 취소
│   ├── forge-full/              # full phase runner
│   ├── forge-scope/             # scoped phase runner
│   ├── grill-me/                # 요구사항 추적
│   └── meta-prompter/           # 메타 프롬프트 정제
├── commands/
│   ├── branch-review.md
│   ├── commit-analysis.md
│   ├── docs-add-frd.md
│   ├── docs-add-task.md
│   ├── e2e-sequence.md
│   ├── forge-cancel.md
│   ├── forge-full.md
│   ├── forge-scope.md
│   ├── grill-me.md
│   └── meta-prompter.md
├── scripts/
│   ├── docs_helpers.py          # v0.7 read-only inspection (list-apps/next-id/parse-fc/parse-frd/git-user/check)
│   ├── forge_full.py            # harness_framework full
│   ├── forge_scope.py           # harness_framework scoped
│   ├── forge_cancel.py          # harness_framework cancel
│   └── forge_templates/         # forge 부트스트랩 리소스
│       ├── CLAUDE.md
│       ├── PHASE_SCHEMA.md
│       ├── FORGE_SCOPE.md
│       └── Docs/_templates/     # 문서 템플릿 8종
├── .gitattributes               # scripts/*.py LF 강제
└── README.md
```

---

## 8. 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| install 직후 슬래시 자동완성에 안 보임 | 매니페스트는 세션 시작 시 1회 로드 | 세션 종료 → 재시작 |
| update 후 신규 스킬 호출 불가 | 동일 — 캐시는 갱신됐으나 세션은 구버전 보유 | 세션 재시작 |
| `/claudecode-for-me:forge-*` 실행 즉시 종료 | `FORGE_TRUST` 미설정 | `FORGE_TRUST=1` 또는 `--trust` |
| `docs-add-frd` / `docs-add-task` "App 0건" | `/CLAUDE.md` Backend Services Overview 표 + `Docs/<App>/` 부재 | App 행 추가 + 폴더 부트스트랩 (`_templates/App/` 양식 복사) 후 재시도 |
| `docs-add-task` "영향 FRD 0건" + feature/변경/버그수정 | 신규 기능에 해당 | `/docs-add-frd` 사용 권장 |
| `docs_helpers.py` next-id `FAIL LIMIT` | FRD active F099 / TASK · ARD 999 도달 | 사용자 수동 결정 (구식 FRD 정리 또는 Backlog 이전) |
| `forge-scope` phase-dir 자동 도출 실패 | prompt 너무 모호 | 명시적 phase-dir 지정 또는 `Docs/...md` 경로 선행 |

---

## 9. 라이선스

MIT
