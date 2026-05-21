# CodeNavigator-FRD-003 — F006 파일 단위 인덱스 삭제

> **코드 상세 금지**: 코드 경로, 파일명, 클래스명, 메서드명, 구현 방식은 본 문서에 쓰지 않는다.

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-FRD-003 |
| 버전 | 0.1 |
| 기능 ID | F006 |
| 상태 | Done |
| 작성 가정 | AI 에이전트 또는 개발자가 특정 `.cs` 파일의 인덱스 row 를 명시적으로 제거해야 하는 시나리오 대응. dry-run 기본으로 의도치 않은 삭제 방지. |
| 관련 문서 | [CodeNavigator-PRD](../CodeNavigator-PRD.md) · [CodeNavigator-FC](../CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](../CodeNavigator-ARCHITECTURE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## 1. 기능 요약
| 항목 | 내용 |
|---|---|
| 작업 유형 | 신규 |
| 기능 목적 | 특정 파일의 인덱스 row 를 CLI 로 명시 삭제. reindex 자동 경로(git diff)와 별개로 수동 삭제 진입점 제공. |
| 기대 결과 | 삭제 후 해당 파일 클래스가 검색 결과에서 완전히 제거됨 |
| 완료 기준 | §17 수용 기준 충족 |
| 우선순위 | P1 |
| 의존 기능 | 없음 (F002 reindex 와 독립) |

## 2. 범위
| 구분 | 내용 |
|---|---|
| 포함 | 파일 1개 단위 삭제, dry-run 기본 동작, `--yes` 실제 삭제, `--json` 출력, 경로 정규화 (상대/절대 혼합 허용) |
| 제외 | 클래스 1개 단위 삭제, 네임스페이스/솔루션 단위 삭제, stale 일괄 삭제 — 이후 별도 기능 |
| 변경되는 사용자 경험 | `codenav delete --file <path>` 로 즉시 삭제 preview + 확인 |
| 변경되지 않아야 하는 것 | FTS5 인덱스 정합성 — 삭제 시 FTS external-content 동기화 유지 |

## 3. 사용자 역할
- AI 코딩 에이전트 — 파일 삭제 후 인덱스 정리 시 호출
- 개발자 — 잘못 인덱싱된 파일 수동 정리

## 4. 입력

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `--file <path>` | 필수 | 삭제할 파일 경로 (절대 또는 `--root` 기준 상대) |
| `--yes` | 선택 | 실제 삭제 실행 (없으면 dry-run) |
| `--json` | 선택 | 출력 JSON 포맷 |
| `--root <dir>` | 선택 | DB 위치 결정 기준 디렉터리 (기본: cwd) |

## 5. 출력

### dry-run (기본)

텍스트:
```
[dry-run] Would delete N class(es) for /abs/path/Foo.cs. Re-run with --yes to confirm.
```

JSON (`--json`):
```json
{"file": "/abs/path/Foo.cs", "would_delete": 1, "dry_run": true}
```

### 실제 삭제 (`--yes`)

텍스트:
```
Deleted N class(es) for /abs/path/Foo.cs
```

JSON (`--json`):
```json
{"file": "/abs/path/Foo.cs", "deleted": 1, "dry_run": false}
```

### 대상 없음

텍스트:
```
No indexed classes for file: /abs/path/Foo.cs
```

JSON (`--json`):
```json
{"file": "/abs/path/Foo.cs", "deleted": 0, "dry_run": false}
```

## 6. 정상 흐름

1. 사용자가 `codenav delete --file <path>` 실행
2. 경로 정규화 (resolve → 절대경로)
3. DB 에서 해당 file 의 클래스 수 조회
4. `--yes` 없으면 예상 삭제 수 출력 후 종료 (row 보존)
5. `--yes` 있으면 FTS5 외부 콘텐츠 동기화 포함 row 삭제 후 완료 메시지

## 7. 예외 흐름

| 케이스 | 동작 |
|---|---|
| 파일이 인덱스에 없음 | `deleted: 0` 메시지, exit 0 |
| DB 없음 (초기화 전) | open_db 가 DB 생성 → 0건 삭제 결과 반환 |

## 17. 수용 기준

| ID | 기준 |
|---|---|
| AC-01 | `--yes` 없이 실행하면 row 가 DB 에 보존된다 |
| AC-02 | `--yes` 실행 후 해당 파일 클래스가 `codenav search` 결과에 나타나지 않는다 |
| AC-03 | `--json` 출력이 JSON 파싱 가능하고 `file`, `dry_run`, `deleted`/`would_delete` 키를 포함한다 |
| AC-04 | 미인덱싱 파일 입력 시 exit 0, `deleted: 0` 반환 |
| AC-05 | 상대경로 입력도 절대경로로 정규화돼 DB 매칭 성공 |

## 18. 테스트 관점

- `tests/test_main_delete.py` 4개 케이스 통과 확인 (dry-run / --yes / 미존재 파일 / --json)
