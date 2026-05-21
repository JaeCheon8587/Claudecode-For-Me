# CodeNavigator-FRD-001 — F001/F002/F004/F005 클래스 시맨틱 인덱스 검색·갱신

> **코드 상세 금지**: 코드 경로, 파일명, 클래스명, 메서드명, 구현 방식은 본 문서에 쓰지 않는다.

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-FRD-001 |
| 버전 | 0.1 (Draft) |
| 기능 ID | F001, F002, F004, F005 |
| 상태 | Done |
| 작성 가정 | AI 코딩 에이전트 전용. stdout JSON 출력. SQLite FTS5 + Claude CLI 환경. |
| 관련 문서 | [CodeNavigator-PRD](../CodeNavigator-PRD.md) · [CodeNavigator-FC](../CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](../CodeNavigator-ARCHITECTURE.md) · [CodeNavigator-ADR-CATALOG](../CodeNavigator-ADR-CATALOG.md) · [ADR-001](../ADR/CodeNavigator-ADR-001.md) · [ADR-002](../ADR/CodeNavigator-ADR-002.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## 1. 기능 요약
| 항목 | 내용 |
|---|---|
| 작업 유형 | 신규 |
| 기능 목적 | AI 코딩 에이전트가 자연어 키워드로 C# 클래스를 빠르게 찾아 Grep 범위를 줄인다 |
| 기대 결과 | `codenav search` 실행 시 관련 클래스 목록이 score 내림차순 JSON 으로 반환됨 |
| 완료 기준 | §17 수용 기준 충족 |
| 우선순위 | P0 |
| 의존 기능 | 없음 |

## 2. 범위
| 구분 | 내용 |
|---|---|
| 포함 | 클래스 시맨틱 검색(F001), 인덱스 갱신(F002), 상태 조회(F004), AI description 생성(F005) |
| 제외 | UI, C# 외 언어, embedding rerank, 실시간 파일 감시 |
| 변경되는 사용자 경험 | AI 에이전트가 전체 파일 Grep 대신 `codenav search` 1회 호출로 후보 클래스 좁히기 가능 |
| 변경되지 않아야 하는 것 | 기존 git commit 흐름, `.cs` 파일 내용 |

## 3. 사용자 역할
- AI 코딩 에이전트 (Claude Code 등) — `codenav search` 호출자
- 개발자 — `codenav reindex` / `codenav status` 실행자

## 4. 사전 조건
- `pip install -e .` 완료 (또는 `python -m codenav` 사용 가능)
- 대상 C# 레포 루트에서 `codenav reindex --full` 최소 1회 실행 완료
- AI description 생성을 원하는 경우 `claude` CLI 설치 및 인증 완료

## 5. 기본 흐름 — 검색 (F001)
1. 에이전트가 `codenav search "데이터 수집" --json` 실행
2. 시스템이 쿼리를 term 으로 분해 (PascalCase 분해, 소문자화)
3. CJK 문자 포함 term 은 bigram 으로 확장
4. FTS5 MATCH 표현식 조합 후 SQLite 실행
5. BM25 점수 + tag-hit bonus 로 재정렬
6. 상위 N 건 JSON 배열을 stdout 출력 (UTF-8)

## 6. 기본 흐름 — 전체 reindex (F002)
1. 개발자가 `codenav --root . reindex --full` 실행
2. 시스템이 레포 내 `.cs` 파일 수집 (생성 파일·제외 디렉터리 스킵)
3. 파일별 클래스·메서드·namespace·XML summary 추출
4. source_hash 변경된 항목만 AI description 생성 요청 (Claude CLI)
5. AI 성공 시 stale=0 upsert, 실패 시 stale=1 upsert
6. 완료 통계 stderr 출력

## 7. 예외 흐름
| # | 조건 | 기대 처리 | 사용자 메시지 | 기록 필요 여부 |
|---|---|---|---|---|
| E1 | Claude CLI 미설치 또는 인증 실패 | stale=1 upsert, 처리 계속 | stderr 경고 | 필요 (stale_files 목록) |
| E2 | FTS5 쿼리 parse 오류 (injection 시도 포함) | 빈 결과 반환 | stderr 에러 메시지 | 필요 |
| E3 | `.cs` 파일 파싱 실패 | 해당 파일 스킵 | stderr 경고 | 불필요 |
| E4 | 삭제된 `.cs` 파일 | 인덱스에서 해당 클래스 행 삭제 | 없음 | 불필요 |

## 8. 상세 기능 요구사항
- 쿼리 term 분해: PascalCase 입력은 단어 단위로 분해 후 소문자화.
- 한국어 bigram: CJK 문자 포함 term 은 문자 bigram 으로 확장해 FTS 조회에 OR 추가.
- FTS5 MATCH escape: 쿼리 내 `"` 는 `""` 로 이스케이프해야 함.
- BM25 가중치: class_name > tags > namespace ≈ bigram > description 순.
- tag-hit bonus: 쿼리 term 이 tags 배열에 존재할 때마다 +2.0 점.
- stale 제외: stale=1 클래스는 검색 결과에서 제외.
- source_hash skip: 파일 내용이 변경되지 않은 클래스는 AI re-call 생략.
- description/tags 분리: AI 가 자연어 description 과 keyword tags 를 별도로 생성. ([ADR-002](../ADR/CodeNavigator-ADR-002.md))
- 삭제 파일 정리: `--changed` 모드에서 staged 삭제 파일의 모든 클래스를 인덱스에서 제거.
- 고아 클래스 정리: 파일 내 클래스 이름 집합이 변경 시 인덱스에서 사라진 클래스 제거.
- exclusion list: `bin/`, `obj/`, `.git/`, `node_modules/`, `packages/`, `TestResults/`, `*.g.cs` 제외.

## 9. 입출력 개념
| 구분 | 내용 | 제약 | 예시 |
|---|---|---|---|
| 검색 입력 | 자연어 키워드 문자열 | 비어있으면 결과 없음 | `"데이터 수집"` · `"EventBus"` |
| 검색 출력 | score 내림차순 클래스 JSON 배열 | stdout UTF-8, `--json` 플래그 필요 | `[{"class":"DataCollector","score":6.06,...}]` |
| reindex 입력 | `--full` / `--changed` / `--files` 모드 선택 | 셋 중 하나 필수 | `--full`, `--changed` |
| reindex 출력 | written/skipped/stale/call 통계 | stderr 출력 | `Reindex done: 3 written, 0 skipped, 1 stale.` |

## 10. 상태 정의
- `stale=0`: AI description 생성 완료, 검색 가능.
- `stale=1`: AI description 생성 실패 또는 대기 중. 검색 결과 제외. `codenav status` 에 노출.

## 11. 권한 조건
| 역할 / 권한 | 허용 작업 | 거부 시 기대 결과 |
|---|---|---|
| 모든 CLI 호출자 | 검색·reindex·status | 없음 (권한 모델 없음) |

## 12. 데이터 처리 원칙
- 보존 대상: `file`, `class_name`, `description`, `tags`, `source_hash`, `indexed_at`.
- 보존 기간: 인덱스 DB 삭제 전까지 영구.
- 중복 처리: `(file, class_name)` UNIQUE 제약. source_hash 동일 시 upsert skip.
- 부분 실패: AI call 실패 → stale=1 upsert, 나머지 클래스 처리 계속.
- 민감정보: 없음.

## 13. 비기능 요구사항
| 분류 | 본 기능 적용 기준 |
|---|---|
| 성능 | 1,000 클래스 이하 SQLite FTS5 쿼리 100ms 이내 |
| 보안 | FTS5 MATCH 입력 이스케이프 필수 |
| 로깅 | reindex 통계 / stale 파일 목록은 stderr. stdout 은 JSON 전용 |
| 에러 처리 | AI 실패 non-fatal. FTS 에러 비어있는 결과 반환 + stderr |

## 14. 로그 / 알림 / 이력 정책
- 정보 기록: reindex 완료 통계 (written/skipped/stale/claude_calls) stderr.
- 오류 기록: FTS OperationalError, AI call 실패 stderr.
- 알림: 없음.
- 이력: `indexed_at` 컬럼에 갱신 시각 기록.

## 15. UI / 외부 연계 영향
| 구분 | 영향 |
|---|---|
| UI | 없음 (AI 코딩 에이전트 전용) |
| 외부 연계 | Claude CLI subprocess (description 생성). 미설치 시 stale 처리로 graceful degradation. |
| 운영 | `codenav status` 로 stale 현황 확인. DB 재구축 시 `rm .codenav/index.sqlite` 후 `reindex --full`. |

## 16. FC / ADR-CATALOG / ADR 반영 여부
| 문서 | 반영 여부 | 반영 내용 |
|---|---|---|
| FC | 완료 | F001·F002·F004·F005 행 등재 |
| ADR | 완료 | ADR-001(FTS5), ADR-002(분리 필드) |
| ADR-CATALOG | 완료 | ADR-001·002 Accepted 등재 |

## 17. 수용 기준
| ID | 기준 | 확인 방법 |
|---|---|---|
| AC-F001-001 | "데이터 수집" 검색 시 DataCollector 가 결과에 포함됨 | 수동 확인 |
| AC-F001-002 | "EventBus" 검색 시 InMemoryEventBus 가 결과에 포함됨 (PascalCase 분해) | 수동 확인 |
| AC-F001-003 | FTS5 injection 시도(`"; DROP--`) 시 crash 없이 빈 결과 반환 | 수동 확인 |
| AC-F001-004 | stdout 출력이 UTF-8 인코딩 JSON (한국어 description 깨짐 없음) | 수동 확인 |
| AC-F002-001 | `reindex --full` 후 `status` 에서 stale=0 클래스 수 정상 | 수동 확인 |
| AC-F002-002 | 삭제된 `.cs` 파일의 클래스가 reindex 후 검색 결과에서 사라짐 | 수동 확인 |
| AC-F005-001 | Claude CLI 미설치 환경에서 reindex 실행 시 stale 마킹 + exit 0 | 수동 확인 |

## 18. 테스트 관점
| ID | Given | When | Then | 확인 방식 |
|---|---|---|---|---|
| TC-F001-001 | 인덱스에 DataCollector(description="수집기") 등재 | `search "수집"` | DataCollector 포함 결과 반환 | Manual |
| TC-F001-002 | 인덱스에 InMemoryEventBus 등재 | `search "EventBus"` | InMemoryEventBus 포함 결과 반환 | Manual |
| TC-F001-003 | 임의 입력 | `search '"; DROP--'` | 빈 결과 + stderr 메시지 (no crash) | Manual |
| TC-F002-001 | CODENAV_INDEXER_MOCK=fail | `reindex --full` | stale 클래스 수 > 0, exit 2, commit 차단 없음 | Manual |
| TC-F002-002 | 파일 삭제 후 git staged | `reindex --changed` | 해당 클래스 인덱스에서 제거됨 | Manual |

## 19. 요구 근거
- [CodeNavigator-FC F001~F005 행](../CodeNavigator-FC.md)
- [CodeNavigator-PRD §2·§3](../CodeNavigator-PRD.md)
- [ADR-001: FTS5 채택](../ADR/CodeNavigator-ADR-001.md)
- [ADR-002: description + tags 분리 필드](../ADR/CodeNavigator-ADR-002.md)

## 20. 미확인 사항
없음.
