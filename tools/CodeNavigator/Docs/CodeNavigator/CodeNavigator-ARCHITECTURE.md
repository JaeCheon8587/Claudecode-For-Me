# CodeNavigator-ARCHITECTURE — CodeNavigator 호스트 아키텍처

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-ARCHITECTURE |
| 버전 | 0.2 (Draft) |
| App 코드 | CodeNavigator |
| 작성 가정 | Python 3.11+ 단일 패키지. DDD 레이어 모델 미적용 (Python CLI + localhost 관리 UI). 솔루션 ARCHITECTURE 는 단일 App 레포이므로 미사용. |
| 관련 문서 | [CodeNavigator-PRD](CodeNavigator-PRD.md) · [CodeNavigator-FC](CodeNavigator-FC.md) · [CodeNavigator-ADR-CATALOG](CodeNavigator-ADR-CATALOG.md) · [FRD 폴더](FRD/) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.2 | 2026-05-21 | 로컬 관리 UI 호스트 및 서비스 계층 추가 | 정재천 |
| 0.1 | 2026-05-21 | 초안 | 정재천 |

## 1. App 개요

| 항목 | 값 |
|---|---|
| App 코드 | CodeNavigator |
| 한 줄 설명 | AI 코딩 에이전트용 C# 클래스 시맨틱 인덱서 + 개발자용 로컬 관리 UI |
| TFM/런타임 | Python 3.11+ |
| 진입점 경로 | `src/codenav/__main__.py` (`main()`) + UI 서버 진입점 (추가 예정) |
| 호스트 종류 | Python CLI + localhost 웹 UI |
| 패키지 설치 | `pip install -e .` (pyproject.toml, `[project.scripts] codenav = "codenav.__main__:main"`) |

## 2. 모듈 구조

```
src/codenav/
├── __main__.py     CLI 진입점 (argparse, 서브커맨드 dispatch)
├── parser_cs.py    C# 소스 파싱 (regex — class/namespace/method/xml-summary)
├── indexer.py      AI description 생성 (Claude CLI subprocess)
├── store.py        SQLite FTS5 인덱스 (upsert, delete, stats)
└── search.py       FTS5 검색 (BM25 + tag-hit, bigram, PascalCase 분해)

추가 예정:
src/codenav/
├── app.py          로컬 웹 UI 서버 진입점
├── services.py     CLI/UI 공용 조회·재인덱싱·수정 유스케이스
└── templates/      서버 렌더링 HTML 템플릿

.claude/skills/codenav-indexer/
└── SKILL.md        Claude CLI 시스템 프롬프트 (description+tags JSON 형식 지시)

.githooks/
└── pre-commit      Python 훅 — staged .cs 감지 → reindex --changed

sample/src/          검증용 C# fixture (3파일, 6클래스)
```

## 3. 핵심 책임

- **반드시** SQLite FTS5 인덱스 CRUD 정합성 유지 (외부-콘텐츠 테이블 FTS 동기화 포함).
- **반드시** FTS5 MATCH 쿼리 입력 이스케이프 (FTS injection 방지).
- **반드시** UI 수정 작업과 CLI 작업이 동일한 서비스 계층을 사용해 데이터 규칙이 일치해야 함.
- **허용** Claude CLI subprocess 실패 시 stale=1 upsert 후 계속 진행 (commit 차단 없음).
- **금지** SQLite 파일을 `.codenav/` 외부 경로에 생성.
- **금지** UI 서버를 `localhost` 외 인터페이스에 기본 바인딩.
- **절대 금지** 외부 시스템(DB, 네트워크) 에 직접 데이터 전송 — Claude CLI subprocess 제외.

## 4. 핵심 설계 결정 (ADR 인용)

| 결정 | ADR |
|---|---|
| FTS5 채택 (embedding 보류) | [CodeNavigator-ADR-001](ADR/CodeNavigator-ADR-001.md) |
| description + tags 분리 필드 | [CodeNavigator-ADR-002](ADR/CodeNavigator-ADR-002.md) |

## 5. 데이터 흐름

```
codenav reindex --full
  → parser_cs.parse_cs_file()          # .cs 파일 → ClassInfo[]
  → parser_cs.classes_to_index_entries()  # ClassInfo → entry dict[]
  → indexer.enrich_entries()           # Claude CLI subprocess → description+tags
  → store.upsert_class()               # SQLite INSERT/UPDATE + FTS5 동기화

codenav search "키워드"
  → search._query_terms()              # PascalCase 분해 + 소문자화
  → search._build_bigrams()            # CJK-only 문자 bigram 생성
  → FTS5 MATCH expression 조합         # term AND bigram:token 형식
  → BM25 score + tag-hit bonus 재정렬
  → JSON 출력 (stdout UTF-8)

UI GET /classes
  → services.list_entries()            # stale/filter/query/page 정규화
  → store/search 조회
  → HTML 렌더링

UI POST /classes/{id}
  → services.update_entry()            # description/tags/manual 상태 갱신
  → store upsert/update
  → 상세/목록으로 redirect

UI POST /reindex
  → services.run_reindex()             # 기존 reindex 유스케이스 재사용
  → 작업 결과 메시지 표시
```

## 6. 외부 의존

| 의존 | 용도 | 실패 처리 |
|---|---|---|
| Claude Code CLI (`claude`) | description+tags 생성 | `shutil.which` 실패 또는 subprocess 오류 시 stale=1 |
| SQLite (stdlib) | FTS5 인덱스 저장 | WAL 모드, FTS5 unicode61 tokenizer |
| Git CLI (`git`) | staged 파일 목록 조회 | FileNotFoundError 시 reindex 중단 |
| 로컬 웹 프레임워크 (추가 예정) | 관리 UI 라우팅·렌더링 | 미설치 시 UI 기능 비활성, CLI 영향 없음 |

## 7. 파일 경로 규약

- 인덱스 DB: `{repo-root}/.codenav/index.sqlite` (RW 모드 자동 생성)
- `file` 컬럼: `Path.resolve()` 절대 경로 저장 (중복 방지)
- `--root` 옵션: DB 경로 기준 루트 (기본값 cwd)
- UI 서버 기본 바인딩: `127.0.0.1`
