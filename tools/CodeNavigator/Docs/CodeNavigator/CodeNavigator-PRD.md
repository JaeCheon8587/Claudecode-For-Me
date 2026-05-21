# CodeNavigator-PRD — CodeNavigator

> **본 App 의 product 요구사항**. 단일 App 레포이므로 솔루션 PRD 역할 겸유. 기술 시야 = [`CodeNavigator-ARCHITECTURE.md`](CodeNavigator-ARCHITECTURE.md). 기능 정의 SSOT = [`CodeNavigator-FC.md`](CodeNavigator-FC.md).

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-PRD |
| 버전 | 0.1 (Draft) |
| 작성 가정 | AI 코딩 에이전트(Claude Code 등) 가 사용하는 도구. 사람이 직접 사용하는 UI 없음. Python 3.11+, SQLite FTS5, Claude Code CLI 사용 가능 환경 전제. |
| 관련 문서 | [CodeNavigator-FC](CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](CodeNavigator-ARCHITECTURE.md) · [CodeNavigator-ADR-CATALOG](CodeNavigator-ADR-CATALOG.md) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.2 | 2026-05-21 | F006 delete 추가 | 정재천 |
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## 1. 배경
- AI 코딩 에이전트가 C# 코드베이스에서 특정 역할 클래스를 찾을 때 전체 파일 Grep 에 의존 → 검색 시간·토큰 소비 과다.
- 클래스의 자연어 의미(한국어 description + 태그)를 미리 인덱싱해 두면, 에이전트가 "데이터 수집" 같은 짧은 키워드만으로 후보를 좁힐 수 있다.

## 2. 문제 정의
- AI 에이전트가 대형 C# 솔루션에서 특정 기능 클래스를 찾으려면 수십~수백 파일을 Grep 해야 함.
- 클래스명 일치 검색만으로는 도메인 역할 기반 탐색 불가 (예: "이벤트를 발행하는 클래스" 검색 불가).

## 3. 목표
- 자연어 키워드로 C# 클래스를 검색해 BM25 점수 기반 상위 후보를 반환한다.
- C# 소스 변경 시 pre-commit hook 이 자동으로 인덱스를 갱신한다.
- AI 에이전트 호출 1회로 클래스 + 메서드 description/tags 를 생성한다.

### 3.1 릴리즈 범위

| 구분 | 범위 |
|---|---|
| MVP 필수 | FTS5 기반 클래스 시맨틱 검색(F001) · 전체/변경 파일 reindex(F002) · pre-commit hook 갱신(F003) · 인덱스 상태 조회(F004) · AI description 생성(F005) |
| 이번 릴리즈 포함 | 위 MVP 5개 기능 + 파일 단위 인덱스 삭제(F006) |
| 이번 릴리즈 제외 | embedding rerank, Roslyn 파서, 다국어 지원, 파일 감시 데몬, API 직접 호출 옵션 |

## 4. 비목표
- 사람이 직접 사용하는 UI/UX (웹 대시보드, IDE 플러그인 등).
- C# 이외 언어 (v1 범위 밖).
- 실시간 파일 감시 (daemon/watcher) — pre-commit hook 으로 충분.
- 의미 임베딩(embedding) 기반 벡터 검색 — Backlog(F101).

## 5. 사용자 / 이해관계자

| 구분 | 역할 | 관심사 |
|---|---|---|
| AI 코딩 에이전트 (Claude Code 등) | `codenav search` 호출자 | JSON 결과 정확성·속도·한국어 인코딩 정상 |
| 개발자 (인덱스 관리자) | `codenav reindex` 실행, hook 설치 | 설치 간편성, stale 가시성, AI call 비용 |

## 6. 핵심 시나리오

| # | 시나리오 | 기대 결과 |
|---|---|---|
| S1 | 에이전트가 "데이터 수집" 키워드로 검색 | `DataCollector` 등 관련 클래스 JSON 반환 (score 내림차순) |
| S2 | 개발자가 새 `.cs` 파일 커밋 | pre-commit hook 이 해당 파일 AI reindex 후 커밋 통과 |
| S3 | AI 호출 실패 | stale=1 로 저장, 커밋 차단 없음, `codenav status` 에 stale 파일 노출 |
| S4 | 에이전트가 `--scope method` 로 검색 | 클래스 + 메서드별 description/tags 포함 JSON 반환 |

## 7. 주요 기능 요약

| 기능 ID | 기능명 | 한 줄 설명 | 릴리즈 범위 |
|---|---|---|---|
| F001 | FTS5 기반 클래스 검색 | 자연어 키워드 → BM25 + tag-hit 점수 기반 클래스 후보 반환 | MVP |
| F002 | 전체/변경 파일 reindex | `--full` / `--changed` / `--files` 로 클래스 인덱스 갱신 | MVP |
| F003 | pre-commit hook 인덱스 갱신 | 스테이징된 `.cs` 파일 감지 후 자동 reindex | MVP |
| F004 | 인덱스 상태 조회 | DB 경로·클래스 수·stale 수·stale 파일 목록 출력 | MVP |
| F005 | AI description 생성 | Claude CLI 로 클래스+메서드 description/tags 생성 | MVP |
| F006 | 파일 단위 인덱스 삭제 | `codenav delete --file` — dry-run 기본, `--yes` 로 실제 삭제, `--json` 출력 | v0.2 |

## 8. 비기능 요구사항

| 분류 | 요구사항 |
|---|---|
| 검색 응답 | SQLite FTS5 쿼리 기준 1,000 클래스 이하 환경에서 100ms 이내 |
| stdout 인코딩 | UTF-8 강제 (AI 소비자 JSON 파싱 보장) |
| hook 비차단 | AI call 실패 시 stale 마킹 후 exit 0 — commit 차단 없음 |
| 크로스 플랫폼 | Windows / macOS / Linux 동작 (bash 의존 없음) |

## 9. 제약사항

- Claude Code CLI (`claude`) 가 설치돼 있어야 AI description 생성 가능. 미설치 시 stale 처리.
- SQLite FTS5 tokenizer `unicode61` 사용 — 한국어 bigram 은 Python 레이어에서 전처리.
- `--output-format json` wrapper 사용: `outer["response"]` → inner JSON 이중 파싱 필요. ([CodeNavigator-ADR-001](ADR/CodeNavigator-ADR-001.md) 참조)
- description + tags 분리 필드 설계. ([CodeNavigator-ADR-002](ADR/CodeNavigator-ADR-002.md) 참조)

## 10. Feature Catalog / FRD 진입점

| Feature Catalog | 주요 FRD |
|---|---|
| [`CodeNavigator-FC`](CodeNavigator-FC.md) | [`CodeNavigator-FRD-001`](FRD/CodeNavigator-FRD-001.md) (검색 API) · [`CodeNavigator-FRD-002`](FRD/CodeNavigator-FRD-002.md) (hook 갱신) |
