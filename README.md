# Claudecode-For-Me

Claude Code 커스텀 스킬/커맨드 모음 플러그인

## 설치

```
/plugin marketplace add JaeCheon8587/Claudecode-For-Me
/plugin install claudecode-for-me@claudecode-for-me
```

## 스킬 목록

| 스킬 | 실행 명령 | 설명 |
|------|----------|------|
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | 기능별 E2E 메시지 흐름을 코드 추적하여 Mermaid 시퀀스 다이어그램 생성 |

### e2e-sequence

```
/claudecode-for-me:e2e-sequence 로그인
```

- 2단계 파이프라인: Explore 에이전트가 코드 추적 → 메인 에이전트가 다이어그램 생성
- 서비스 간 통신 흐름을 시각화 (HTTP, WebSocket, 메시지 큐 등)
- MCP Mermaid Chart 도구로 렌더링 검증
- 출력: `Docs/E2E-Sequence/{기능명}_Sequence.md`

## 커맨드 목록

| 커맨드 | 실행 명령 | 설명 |
|--------|----------|------|
| commit-analysis | `/claudecode-for-me:commit-analysis` | 변경사항 분석 후 구분자 선택하여 커밋 생성 |
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | e2e-sequence 스킬 실행 (커맨드 래퍼) |

### commit-analysis

```
/claudecode-for-me:commit-analysis
```

- 구분자 자동 판단: `[ADD]` 추가 / `[MOD]` 수정 / `[FIX]` 버그 수정
- `.md` 파일 자동 제외
- 변경 내용 기반 한글 커밋 메시지 작성

## 프로젝트 구조

```
Claudecode-For-Me/
├── .claude-plugin/
│   ├── plugin.json          # 플러그인 매니페스트
│   └── marketplace.json     # 마켓플레이스 설정
├── skills/
│   └── e2e-sequence/
│       └── SKILL.md         # E2E 시퀀스 다이어그램 스킬
├── commands/
│   ├── e2e-sequence.md      # e2e-sequence 커맨드
│   └── commit-analysis.md   # 커밋 분석 커맨드
└── agents/                  # (향후 에이전트 추가 예정)
```

## 라이선스

MIT
