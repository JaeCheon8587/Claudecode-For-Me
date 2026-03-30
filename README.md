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
| atdd-flow | `/claudecode-for-me:atdd-flow [기능명]` | Backend Architect 페르소나로 기능 요구사항서를 검토하여 엣지 케이스 발견 및 완성된 FRD 생성 |
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | 기능별 E2E 메시지 흐름을 코드 추적하여 Mermaid 시퀀스 다이어그램 생성 |
| grill-me | `/claudecode-for-me:grill-me [주제]` | 아이디어/계획/작업을 집요한 질문으로 구체화하고 요구사항 정리 |

### atdd-flow

```
/claudecode-for-me:atdd-flow 로그인 기능
```

- **Backend Architect 페르소나** 기반: DB 스키마, API 설계, 보안, 성능, 마이크로서비스 관점으로 질문
- 압박 수준 조절 가능: 약(UX 중심) / 중(비즈니스 로직) / 강(보안, 동시성, 아키텍처)
- 4가지 관점 분석: 논리적 모순(데이터 정합성), 엣지 케이스(Circuit Breaker, Timeout), 구현 가능성(인프라 제약), 보안/성능(Rate Limit, 캐싱)
- 턴당 최대 2개 질문 + 확정 사항 동기화
- 세션 종료 시 구조화된 기능 요구사항서 (API 스펙 + 시나리오 + 엣지 케이스) 생성

### e2e-sequence

```
/claudecode-for-me:e2e-sequence 로그인
```

- 2단계 파이프라인: Explore 에이전트가 코드 추적 → 메인 에이전트가 다이어그램 생성
- 서비스 간 통신 흐름을 시각화 (HTTP, WebSocket, 메시지 큐 등)
- MCP Mermaid Chart 도구로 렌더링 검증
- 출력: `Docs/E2E-Sequence/{기능명}_Sequence.md`

### grill-me

```
/claudecode-for-me:grill-me 알림 시스템 설계
```

- 1문 1답 방식으로 아이디어/계획의 모호한 부분을 파고듦
- 논리적 모순 발견 시 명시적으로 지적하고 해소될 때까지 추궁
- 진행 상황 트래커로 탐색 영역별 완료 여부 표시
- 세션 종료 시 Requirements Summary (영역별 정리 + Q&A + 미해결 항목) 생성

## 커맨드 목록

| 커맨드 | 실행 명령 | 설명 |
|--------|----------|------|
| atdd-flow | `/claudecode-for-me:atdd-flow [기능명]` | Backend Architect + atdd-flow 스킬 실행 |
| commit-analysis | `/claudecode-for-me:commit-analysis` | 변경사항 분석 후 구분자 선택하여 커밋 생성 |
| e2e-sequence | `/claudecode-for-me:e2e-sequence [기능명]` | e2e-sequence 스킬 실행 (커맨드 래퍼) |
| grill-me | `/claudecode-for-me:grill-me [주제]` | grill-me 스킬 실행 (커맨드 래퍼) |

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
│   ├── atdd-flow/
│   │   └── SKILL.md         # 기능 요구사항서 검토 스킬
│   ├── e2e-sequence/
│   │   └── SKILL.md         # E2E 시퀀스 다이어그램 스킬
│   └── grill-me/
│       └── SKILL.md         # 아이디어/계획 구체화 스킬
├── commands/
│   ├── atdd-flow.md         # atdd-flow 커맨드
│   ├── e2e-sequence.md      # e2e-sequence 커맨드
│   ├── grill-me.md          # grill-me 커맨드
│   └── commit-analysis.md   # 커밋 분석 커맨드
├── agents/
│   └── engineering/
│       ├── engineering-backend-architect.md   # Backend Architect 페르소나
│       └── engineering-software-architect.md  # Software Architect 페르소나
```

## 라이선스

MIT
