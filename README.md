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
/claudecode-for-me:atdd-pipeline 기능명
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
| atdd-pipeline | `/claudecode-for-me:atdd-pipeline [기능 요구사항서 경로/내용]` | ATDD 전체 파이프라인 오케스트레이터 (FRD → 테스트 → 구현 → 완료) |
| atdd-flow | atdd-pipeline Phase 1 하위 스킬 | 기능 요구사항서를 시니어 테크니컬 리뷰어 관점으로 검토하여 FRD 생성 |
| atdd-design | atdd-pipeline Phase 2 하위 스킬 | FRD 기반 테스트 코드 작성 + FRD↔테스트 자기 검증 (Red 단계) |
| atdd-implement | atdd-pipeline Phase 3 하위 스킬 | 테스트를 통과시키는 프로덕션 코드 구현 + 빌드/테스트 검증 (Green 단계) |
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | 기능별 E2E 메시지 흐름을 코드 추적하여 Mermaid 시퀀스 다이어그램 생성 |
| grill-me | `/claudecode-for-me:grill-me [주제]` | 아이디어/계획/작업을 집요한 질문으로 구체화하고 요구사항 정리 |
| meta-prompter | `/claudecode-for-me:meta-prompter [작업 요청]` | 거친 작업 요청을 다른 AI 에이전트(Claude Code 등)가 수행 가능한 구조화된 메타 프롬프트로 정제 |

> `atdd-flow` / `atdd-design` / `atdd-implement`는 `atdd-pipeline`이 Phase 1~3에서 각각 호출하는 하위 스킬이다. 개별 커맨드는 제공되지 않으며 파이프라인을 통해 실행된다.

### atdd-pipeline

```
/claudecode-for-me:atdd-pipeline 로그인 기능
```

- **4단계 파이프라인**: Phase 1 FRD 생성 → Phase 2 테스트 코드 작성 + 자기 검증 → Phase 3 구현 + 빌드/테스트 → Phase 4 완료 보고
- **파일 기반 계약**: Phase 간 데이터 전달은 `.atdd/` 폴더 파일과 소스 코드로만 이루어지며, 컨텍스트 변수에 의존하지 않는다
- **재개 가능**: 산출물(`frd_{기능명}.md`, 테스트 코드, `impl_{기능명}.md`)의 존재 여부로 완료된 Phase를 판별하여 중단된 지점부터 재개한다
- **에이전트 분담**: Phase 1은 메인 에이전트(Opus, 유저 대화 필요) / Phase 2·3은 서브 에이전트(Sonnet, Red→Green 순서를 구조적으로 강제)
- **산출물**: `.atdd/frd_{기능명}.md`, 테스트 코드, 프로덕션 코드, `.atdd/impl_{기능명}.md`

### atdd-flow

```
(atdd-pipeline Phase 1에서 호출됨)
```

- **시니어 테크니컬 리뷰어 페르소나** 기반 — 수동적 기록자가 아니라 허점을 찾아 지적
- 압박 수준 조절 가능: **약**(사용자 편의성·기본 예외) / **중**(비즈니스 로직·시스템 에러) / **강**(동시성·보안·아키텍처 결함, 전문 용어 사용)
- **4가지 분석 관점**: 논리적 모순 / 엣지 케이스 누락 / 구현 가능성 / 보안·성능
- **일괄 질문 방식**: 발견된 이슈를 Critical → Major → Minor 순으로 정렬하여 한 번에 제시 (각 질문에 Recommended 선택지 포함)
- 후속 질문은 최대 2라운드, 미해결 항목은 FRD "미해결 항목" 섹션에 기록
- 산출물: `.atdd/frd_{기능명}.md` (기능명, API 스펙, 설명, 시나리오, 보안/성능 고려사항, 미해결 항목, 핵심 Q&A)

### atdd-design

```
(atdd-pipeline Phase 2에서 Sonnet 서브 에이전트로 호출됨)
```

- **ATDD Red 단계**: 컴파일 실패 상태의 테스트 코드를 작성하고 프로덕션 코드는 작성하지 않는다
- FRD의 시나리오·예외·엣지·보안/성능 고려사항에서 테스트 케이스를 도출
- **세 종류의 검증 도출**: 응답 검증 / 상태 검증 / 행동 검증
- **FRD↔테스트 자기 검증 루프** (최대 3회): FRD 시나리오 항목을 한 줄씩 나열하고 각 항목에 매칭되는 테스트 메서드를 찾아 누락을 보완
- 완료 시 `[ATDD-DESIGN COMPLETE]` 또는 `[ATDD-DESIGN COMPLETE: GAPS_REMAIN]` 신호 출력

### atdd-implement

```
(atdd-pipeline Phase 3에서 Sonnet 서브 에이전트로 호출됨)
```

- **ATDD Green 단계**: 이미 존재하는 테스트를 통과시키는 프로덕션 코드를 작성 — 테스트 코드는 수정하지 않는다
- **Phase 분리**: 분석(Phase 1) → 구현 코드 작성(Phase 2) → 빌드&테스트(Phase 3) → 완료 보고(Phase 4)
- **빌드&테스트 3회 반복**: 빌드 실패/테스트 실패 시 프로덕션 코드만 수정하여 재시도
- 완료 시 `[ATDD-IMPLEMENT COMPLETE]` 또는 `[ATDD-IMPLEMENT COMPLETE: BUILD_TEST_FAILED]` 신호 출력
- 산출물: 프로덕션 코드 + `.atdd/impl_{기능명}.md` (생성/수정 파일, 빌드·테스트 결과, DEFERRED 항목)

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

## 커맨드 목록

| 커맨드 | 실행 명령 | 설명 |
|--------|----------|------|
| atdd-pipeline | `/claudecode-for-me:atdd-pipeline [기능 요구사항서]` | atdd-pipeline 스킬 실행 (ATDD 전체 파이프라인) |
| commit-analysis | `/claudecode-for-me:commit-analysis` | 변경사항 분석 후 구분자 선택하여 커밋 생성 |
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | e2e-sequence 스킬 실행 (커맨드 래퍼) |
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
├── skills/
│   ├── atdd-pipeline/
│   │   └── SKILL.md             # ATDD 전체 파이프라인 오케스트레이터
│   ├── atdd-flow/
│   │   └── SKILL.md             # FRD 생성 (Phase 1 하위 스킬)
│   ├── atdd-design/
│   │   └── SKILL.md             # 테스트 코드 작성 + 자기 검증 (Phase 2 하위 스킬)
│   ├── atdd-implement/
│   │   └── SKILL.md             # 구현 + 빌드/테스트 (Phase 3 하위 스킬)
│   ├── e2e-sequence/
│   │   └── SKILL.md             # E2E 시퀀스 다이어그램 스킬
│   ├── grill-me/
│   │   └── SKILL.md             # 아이디어/계획 구체화 스킬
│   └── meta-prompter/
│       └── SKILL.md             # 작업 요청 → 구조화된 메타 프롬프트 정제 스킬
├── commands/
│   ├── atdd-pipeline.md         # atdd-pipeline 커맨드
│   ├── commit-analysis.md       # 커밋 분석 커맨드
│   ├── e2e-sequence.md          # e2e-sequence 커맨드
│   ├── grill-me.md              # grill-me 커맨드
│   └── meta-prompter.md         # meta-prompter 커맨드
└── README.md
```

## 라이선스

MIT
