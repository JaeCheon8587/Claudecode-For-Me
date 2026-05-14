# Claudecode-For-Me

Claude Code 커스텀 스킬/커맨드 모음 플러그인

## 설치 (다른 프로젝트에서 처음 사용할 때)

다른 작업 디렉터리(예: 사내 프로젝트, 새 레포 등)에서 Claude Code를 켜고 다음을 순서대로 실행한다.

```
# 1. 마켓플레이스 등록
/plugin marketplace add JaeCheon8587/Claudecode-For-Me

# 2. 플러그인 설치 (글로벌 캐시 ~/.claude/plugins/cache/ 에 다운로드됨)
/plugin install claudecode-for-me@claudecode-for-me

# 3. ★ 반드시 Claude Code 세션을 종료하고 다시 시작 ★
# (세션 시작 시점에 plugin manifest를 한 번만 로드하므로 install 직후 같은 세션에서는 호출 안 됨)

# 4. 새 세션에서 동작 검증 — 슬래시 자동완성에 노출 확인
/claudecode-for-me:meta-prompter 작업 요청 텍스트
/claudecode-for-me:grill-me 주제
/claudecode-for-me:forge-scope 작업 prompt
```

플러그인은 글로벌(`~/.claude/plugins/`)에 설치되므로 한 번 설치하면 **모든 프로젝트의 새 세션**에서 자동으로 사용 가능하다. 프로젝트별 재설치 불필요.

## 업데이트

다른 프로젝트에서 이 플러그인을 이미 설치했다면, 새 커맨드/스킬은 다음으로 가져온다.

```
/plugin marketplace update claudecode-for-me
/plugin update claudecode-for-me@claudecode-for-me
```

- `plugin.json` / `marketplace.json`의 `version` 값이 올라가야 클라이언트가 변경을 인식한다.
- **업데이트 후 Claude Code 세션 재시작 필수**: Claude Code는 세션 시작 시점에 플러그인 매니페스트를 한 번만 로드하며 런타임 hot-reload를 하지 않는다. 업데이트만 하고 같은 세션을 유지하면 새로 추가된 스킬/커맨드가 보이지 않는다.
  - 현재 세션 종료 → 새 세션 시작 → `/claudecode-for-me:<name>` 호출 가능
  - 캐시 위치: `~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<version>/` (구버전과 신버전이 공존할 수 있으나 활성 버전은 최신 1개)

## 스킬 목록

| 스킬 | 실행 명령 | 설명 |
|------|----------|------|
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | 기능별 E2E 메시지 흐름을 코드 추적하여 Mermaid 시퀀스 다이어그램 생성 |
| grill-me | `/claudecode-for-me:grill-me [주제]` | 아이디어/계획/작업을 집요한 질문으로 구체화하고 요구사항 정리 |
| meta-prompter | `/claudecode-for-me:meta-prompter [작업 요청]` | 거친 작업 요청을 다른 AI 에이전트(Claude Code 등)가 수행 가능한 구조화된 메타 프롬프트로 정제 |

### e2e-sequence

```
/claudecode-for-me:e2e-sequence 로그인
```

- **2단계 파이프라인**: Explore 에이전트가 코드 추적 → 메인 에이전트가 Mermaid 다이어그램 생성
- 서비스 간 통신 흐름을 시각화 (HTTP, WebSocket, 메시지 큐 등)
- **참여자 통합 규칙**: 같은 프로세스 내 레이어(ViewModel, UseCase, Service 등)는 하나의 participant로 묶고, 내부 처리는 `Note over`로 표현
- **alt/deactivate 충돌 방지**: `alt`/`else` 블록 내부에서 `deactivate` 금지 — 블록 바깥 또는 `else` 분기 끝에서만 비활성화
- **외부 시스템 부재 가시화**: DB/메시지 큐/WebSocket/캐시/외부 HTTP를 모두 기재, 미사용도 X로 명시
- MCP Mermaid Chart 도구로 렌더링 검증
- 출력: `Docs/E2E-Sequence/{기능명}_Sequence.md`

### grill-me

```
/claudecode-for-me:grill-me 알림 시스템 설계
```

- **1문 1답 방식** (`AskUserQuestion` 도구 사용)으로 아이디어/계획의 모호한 부분을 파고듦
- 각 질문은 추천 선택지 2개(`(Recommended)` 표기) + "Other" 자동 옵션
- 탐색 영역: Purpose / Scope / Success Criteria / Assumptions / Key Decisions / Constraints / Dependencies / Stakeholders / Failure Modes / Alternatives / Priorities / Execution
- **논리적 모순 발견 시 명시적으로 지적**하고 해소될 때까지 해당 가지에 머무름
- 3~4 교환마다 진행 트래커로 영역별 완료 여부 표시
- 세션 종료 시 Requirements Summary (영역별 정리 + Key Decisions Q&A + Open Items + Next Steps) 생성 후 확정 리뷰

### meta-prompter

```
/claudecode-for-me:meta-prompter ApiGateway에 health check 엔드포인트 추가
```

- **요구사항 정제기**: 단순 포매터가 아니라 모호 표현 challenge / 가정 표면화 / 모순 지적까지 수행
- **작업 유형 자동 분류**: 기능 개발 / 리팩토링 / 문서화 / 분석 (혼합 시 주·보조 표기)
- **유형별 템플릿 매칭**: 베이스 12개 항목 + 유형별 추가 항목에서 근거·기본값 있는 것만 채움 (빈 자리표시자 금지)
- **필수 항목 누락 시** 한 번에 묶어 질문 (≤3개), 그 외는 합리적 가정으로 처리하고 메타 헤더에 `추가한 가정 N개`로 카운트
- **출력은 채팅 전용**: 마크다운 코드블록 1개로 감싸 그대로 복사 가능, 별도 `.md` 파일로 저장하지 않음
- 개조식 종결 강제(서술형 금지), 출력 끝에 `[에이전트 행동 규칙]` 가드레일 4문구 자동 부착

## Forge Phase Runner (harness_framework 임베디드)

harness_framework의 phase runner 3종이 플러그인에 내장되어 있다.
**첫 호출 시 사용자 프로젝트에 필요한 파일을 자동으로 부트스트랩**한다.

### 전제 조건

| 조건 | 필수 여부 | 비고 |
|---|---|---|
| Python 3.10+ (`python` 또는 `py -3`) | **필수** | 없으면 명령 실행 즉시 가이드 메시지 출력 후 중단 |
| `claude` CLI PATH 등록 | **필수** | child claude spawn에 사용 |
| git repository | 권장 | 없으면 경고만 출력, 브랜치/커밋 자동화 실패 가능 |
| `FORGE_TRUST=1` 환경변수 또는 `--trust` | **필수** | 미설정 시 child claude 즉시 종료 |

### 환경변수

| 변수 | 설명 |
|---|---|
| `FORGE_TRUST` | `1` / `true` / `yes` — `--trust` 와 동일. child claude 권한 부여 |
| `FORGE_CLAUDE_TIMEOUT` | step 실행 최대 시간(초). 기본 1800 |
| `ANTHROPIC_API_KEY` | API 키. `--bare` child 모드 사용 시 필수 |

### 명령

| 커맨드 | 실행 명령 | 설명 |
|---|---|---|
| forge-scope | `/claudecode-for-me:forge-scope <prompt>` | 경량 scoped phase. 단일 FRD·기능·버그픽스. **일반 사용 권장** |
| forge-full | `/claudecode-for-me:forge-full <phase-dir> [options]` | 문서 기반 full phase. 전체 프로젝트 구현 |
| forge-cancel | `/claudecode-for-me:forge-cancel <phase-dir> [--kind full\|scoped]` | 진행 중인 phase 취소 및 정리 |

### 첫 호출 시 자동 부트스트랩

사용자 프로젝트 cwd에 아래 파일을 **없는 것만** 복사한다 (기존 파일 덮어쓰기 없음):

```
./scripts/forge_full.py
./scripts/forge_scope.py
./scripts/forge_cancel.py
./CLAUDE.md
./PHASE_SCHEMA.md
./FORGE_SCOPE.md
./Docs/_templates/  (8개 템플릿 파일)
```

복사된 파일과 skip된 파일 목록을 한 번 출력한다.

### 사용 예시

```bash
# FRD 단건 구현 (권장 — splitter 우회, 토큰 절감)
/claudecode-for-me:forge-scope /Docs/FRD/FRD-F003.md FRD-F003 주문 상태 API 구현

# 자유 텍스트 prompt (phase-dir 자동 도출, 확인 1회)
/claudecode-for-me:forge-scope 로그인 기능에 소셜 로그인 옵션 추가

# full phase (전체 프로젝트 구현)
/claudecode-for-me:forge-full mvp-v2 --prompt="MVP v2 전체 구현" --docs-mode=recursive --trust

# plan 미리보기 (파일/브랜치 생성 없음)
/claudecode-for-me:forge-full order-flow --plan-only --prompt="주문 흐름 구현" --doc=Docs/FRD/FRD-F009.md --trust

# 취소 (dry-run으로 대상 먼저 확인)
/claudecode-for-me:forge-cancel login-feature --dry-run
/claudecode-for-me:forge-cancel login-feature --kind scoped
```

### forge-scope 인자 상세

`$ARGUMENTS`를 두 모드로 해석한다:

- **Mode 1 (prompt-only)**: 일반 텍스트 → phase-dir 자동 도출 후 확인 1회
- **Mode 2 (doc + prompt)**: 첫 토큰이 `Docs/...md` 또는 `/Docs/...md` (대소문자 무시) → `--doc` 로 분리

FRD 파일(`Docs/FRD/` 하위)이면 자동으로 `--preset=frd-implementation --compact-docs` 적용.
일반 문서이면 `--single-step --compact-docs` 적용.

### forge-full 주요 옵션

| 옵션 | 설명 |
|---|---|
| `--prompt` | plan 생성 입력 (반복 가능) |
| `--doc` | guardrail 문서 (`Docs/` 하위 `.md`). 반복 가능 |
| `--docs-mode=root\|recursive\|explicit` | 문서 인입 정책. `explicit` 이면 `--doc` 만 사용 |
| `--trust` | child claude 권한 부여 (`FORGE_TRUST=1` 과 동일) |
| `--yes` | plan 자동 승인 |
| `--quiet` | 진행 표시기 억제 (Claude Code spawn 시 권장) |
| `--plan-only` | plan 생성·출력만 수행. 파일·브랜치·커밋 없음 |
| `--preset=auto\|contract-tdd` | 기본: 문서 기반 splitter. `contract-tdd`: OMS 샘플 전용 |
| `--compact-docs` | guardrail 문서를 핵심 섹션만 압축 주입 |

### 한계 사항

- **`--preset=contract-tdd`는 OMS 샘플 전용**: `Src/OrderManagingSystem.sln` 경로가 AC에 하드코딩되어 있다. 일반 프로젝트에서는 `auto` / `frd-implementation` / `--single-step` 을 사용하라.
- **타임존 KST 고정**: step timestamp가 KST(UTC+9) 기준으로 기록된다.
- **step.md 헤딩 한국어 고정**: `## 읽어야 할 파일` 등 5개 헤딩이 강제된다 (harness_framework 원본 동작).

### .gitignore 권장 항목

```gitignore
# forge 산출물 — 팀 정책에 따라 추적 여부 결정
phases/
```

---

## 커맨드 목록

| 커맨드 | 실행 명령 | 설명 |
|--------|----------|------|
| commit-analysis | `/claudecode-for-me:commit-analysis` | 변경사항 분석 후 구분자 선택하여 커밋 생성 |
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | e2e-sequence 스킬 실행 (커맨드 래퍼) |
| forge-cancel | `/claudecode-for-me:forge-cancel <phase-dir>` | forge phase 취소 및 정리 |
| forge-full | `/claudecode-for-me:forge-full <phase-dir> [options]` | forge-full phase runner |
| forge-scope | `/claudecode-for-me:forge-scope <prompt>` | forge-scope 경량 phase runner |
| grill-me | `/claudecode-for-me:grill-me [주제]` | grill-me 스킬 실행 (커맨드 래퍼) |
| meta-prompter | `/claudecode-for-me:meta-prompter [작업 요청]` | meta-prompter 스킬 실행 (커맨드 래퍼) |

### commit-analysis

```
/claudecode-for-me:commit-analysis
```

- 구분자 자동 판단: `[ADD]` 추가 / `[MOD]` 수정 / `[FIX]` 버그 수정
- `.md` 파일 자동 제외 (`git add --all` 후 `git reset -- "*.md"`)
- Co-Authored-By/"Generated with Claude Code" 등의 문구 제외
- 변경 내용 기반 한글 커밋 메시지 작성

## 프로젝트 구조

```
Claudecode-For-Me/
├── .claude-plugin/
│   ├── plugin.json              # 플러그인 매니페스트
│   └── marketplace.json         # 마켓플레이스 설정
├── scripts/
│   ├── forge_full.py            # harness_framework full phase runner
│   ├── forge_scope.py           # harness_framework scoped phase runner
│   ├── forge_cancel.py          # harness_framework cancel runner
│   └── forge_templates/         # 부트스트랩 리소스
│       ├── CLAUDE.md            # 프로젝트 가드레일 템플릿
│       ├── PHASE_SCHEMA.md      # phase 스키마 명세
│       ├── FORGE_SCOPE.md       # forge-scope 운영 참조
│       └── Docs/_templates/     # 문서 템플릿 8종
├── skills/
│   ├── e2e-sequence/
│   │   └── SKILL.md             # E2E 시퀀스 다이어그램 스킬
│   ├── forge-cancel/
│   │   └── SKILL.md             # forge phase 취소 스킬
│   ├── forge-full/
│   │   └── SKILL.md             # forge-full phase runner 스킬
│   ├── forge-scope/
│   │   └── SKILL.md             # forge-scope 경량 phase runner 스킬
│   ├── grill-me/
│   │   └── SKILL.md             # 아이디어/계획 구체화 스킬
│   └── meta-prompter/
│       └── SKILL.md             # 작업 요청 → 구조화된 메타 프롬프트 정제 스킬
├── commands/
│   ├── commit-analysis.md       # 커밋 분석 커맨드
│   ├── e2e-sequence.md          # e2e-sequence 커맨드
│   ├── forge-cancel.md          # forge-cancel 커맨드
│   ├── forge-full.md            # forge-full 커맨드
│   ├── forge-scope.md           # forge-scope 커맨드
│   ├── grill-me.md              # grill-me 커맨드
│   └── meta-prompter.md         # meta-prompter 커맨드
└── README.md
```

## 라이선스

MIT
