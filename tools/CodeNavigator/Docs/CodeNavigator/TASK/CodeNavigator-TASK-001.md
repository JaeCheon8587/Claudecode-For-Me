# CodeNavigator-TASK-001 — MVP 검증 결함 수정 (P0/P1 fix + Docs 채움)

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-TASK-001 |
| 버전 | 0.1 |
| 상태 | Done |
| 작업 유형 | maintenance |
| 작성 가정 | MVP 구현 후 전체 검증에서 발견된 P0 4건·P1 다수 결함을 수정. Docs placeholder 채움. 영구 SSOT 갱신 완료. |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 + 완료 | 정재천 |

---

## §1. 목적
MVP 전체 검증에서 발견된 P0(즉시 차단형) 4건, P1(정확성 결함) 다수를 수정하고 Docs placeholder 를 채운다.

## §2. 범위
- **포함**: P0 fix(indexer/search/store/main), P1 fix(parser/search/store/main/hook/skill), Docs 채움(/CLAUDE.md·PRD·FC·ARCH·ADR-CATALOG·ADR-001·ADR-002·FRD-001·FRD-002·TASK-001), Docs/PRD.md·ARCHITECTURE.md 삭제
- **제외**: 테스트 코드 신설(Step 4), embedding rerank, Roslyn 파서

## §3. 사전 조건
- Python 3.11+, pip, git 설치
- `pip install -e .` 완료

## §4. 검증 기준
- `CODENAV_INDEXER_MOCK=fail python -m codenav --root . reindex --full --verbose` → exit 2, stale classes 수 > 0
- `python -m codenav --root . search "수집"` → DataCollector 포함 결과
- `python -m codenav --root . search '"; DROP--'` → 빈 결과 + stderr 메시지 (no crash)
- `python -m codenav --root . status` → 한국어 깨짐 없음

## §5. 변경 파일 요약

| 파일 | 변경 요지 |
|---|---|
| `src/codenav/indexer.py` | claude flags 정정(`-p --output-format json --append-system-prompt-file`), `shutil.which`, JSON wrapper 이중 파싱, FileNotFoundError break, tags list 검증 |
| `src/codenav/__main__.py` | UTF-8 stdout, `_collect_cs_files` exclusion list, `--changed` 삭제 파일 처리, 고아 클래스 정리 |
| `src/codenav/search.py` | bigram column filter 공백 제거(`bigram:"token"`), FTS injection `"` escape, OperationalError stderr 로그 |
| `src/codenav/store.py` | dead `SCHEMA` 삭제, FK pragma 제거, FTS delete old-row 정확성 수정, `mark_stale` → `delete_file` 대체 |
| `src/codenav/parser_cs.py` | kind 판정 `\b(interface|struct|record|class)\b` regex, dead keyword guard 제거 |
| `.githooks/pre-commit` | bash → Python 재작성 (cross-platform) |
| `.claude/skills/codenav-indexer/SKILL.md` | 예시 ``` fence → indent block |

## §6. 영향 SSOT 갱신 상태

| 문서 | 갱신 완료 여부 | 갱신 요지 |
|---|---|---|
| /CLAUDE.md | 완료 | placeholder 채움, PRD/ARCH 행 제거 |
| CodeNavigator-PRD | 완료 | §1~§10 채움 |
| CodeNavigator-FC | 완료 | F001~F005 5행 등재 |
| CodeNavigator-ARCHITECTURE | 완료 | 모듈 구조·데이터 흐름 기술 |
| CodeNavigator-ADR-CATALOG | 완료 | ADR-001·002 Accepted 등재 |
| CodeNavigator-ADR-001 | 완료 | FTS5 채택 근거 |
| CodeNavigator-ADR-002 (신규) | 완료 | description+tags 분리 필드 근거 |
| CodeNavigator-FRD-001 | 완료 | 검색·reindex·status·AI description 기능 명세 |
| CodeNavigator-FRD-002 (신규) | 완료 | pre-commit hook 갱신 명세 |
| Docs/PRD.md | 삭제 (단일 App 레포) | |
| Docs/ARCHITECTURE.md | 삭제 (단일 App 레포) | |

## §8. 실행 단계 (완료)
1. P0 fix: indexer(claude flags), main(UTF-8), search(bigram space), store(SCHEMA 삭제) ✓
2. P1 fix: parser(kind regex, dead guard), search(injection guard, stderr), store(FTS delete, delete_file), main(exclusion, deletion), hook(Python), skill(fence) ✓
3. Docs 채움: /CLAUDE.md, PRD, FC, ARCH, ADR-CATALOG, ADR-001, ADR-002, FRD-001, FRD-002, TASK-001 ✓
4. Docs/PRD.md·ARCHITECTURE.md 삭제 (별도 `git rm`) ✓

## §12. 주요 컨텍스트 임베드

**claude CLI 올바른 호출 인터페이스:**
```
claude -p --output-format json --append-system-prompt-file <path>
# stdin = class info text
# stdout = {"result": "...", "response": "...", ...}
# parse: outer = json.loads(stdout); inner = json.loads(outer["response"])
```

**FTS5 column filter 문법:**
- 올바름: `bigram:"토큰"` (공백 없음)
- 잘못됨: `bigram : "토큰"` (공백 있으면 별도 phrase token 으로 해석)

**FTS5 quote escape:**
- `"` → `""` (FTS5 표준)

**FTS external-content 테이블 delete:**
- delete 명령에 OLD row 값(갱신 전 namespace/description/tags) 전달 필수
- NEW 값 전달 시 인덱스 corruption
