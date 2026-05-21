# CodeNavigator-FRD-002 — F003 pre-commit 기반 인덱스 갱신

> **코드 상세 금지**: 코드 경로, 파일명, 클래스명, 메서드명, 구현 방식은 본 문서에 쓰지 않는다.

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-FRD-002 |
| 버전 | 0.1 (Draft) |
| 기능 ID | F003 |
| 상태 | Done |
| 작성 가정 | git pre-commit hook 환경. bash 의존 없이 Python 으로만 동작. AI 실패 시 commit 차단 없음. |
| 관련 문서 | [CodeNavigator-PRD](../CodeNavigator-PRD.md) · [CodeNavigator-FC](../CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](../CodeNavigator-ARCHITECTURE.md) · [CodeNavigator-ADR-CATALOG](../CodeNavigator-ADR-CATALOG.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## 1. 기능 요약
| 항목 | 내용 |
|---|---|
| 작업 유형 | 신규 |
| 기능 목적 | C# 파일 변경 커밋 시 자동으로 인덱스 갱신하여 항상 최신 description 유지 |
| 기대 결과 | 커밋 후 검색 시 stale 없이 최신 클래스 정보 반환 |
| 완료 기준 | §17 수용 기준 충족 |
| 우선순위 | P0 |
| 의존 기능 | F002 (reindex --changed 기능) |

## 2. 범위
| 구분 | 내용 |
|---|---|
| 포함 | git staged `.cs` 파일 감지, `reindex --changed` 자동 실행, AI 실패 시 stale 마킹 |
| 제외 | push hook, 비스테이지 파일 감시, `.cs` 외 파일 처리 |
| 변경되는 사용자 경험 | 개발자가 커밋하면 hook 이 자동 실행 — 별도 reindex 명령 불필요 |
| 변경되지 않아야 하는 것 | commit 흐름 차단 없음 — AI 실패해도 hook exit 0 |

## 3. 사용자 역할
- 개발자 — git commit 실행자 (hook 직접 실행 없음)
- AI 코딩 에이전트 — hook 실행 이후 `codenav search` 로 최신 인덱스 소비

## 4. 사전 조건
- hook 등록: `install-hook.ps1` (Windows) 또는 `install-hook.sh` (Linux/macOS) 실행 완료
- `codenav` (또는 `python -m codenav`) 실행 가능한 Python 환경

## 5. 기본 흐름
1. 개발자가 `git commit` 실행
2. hook 이 staged 파일 목록 조회
3. `.cs` 파일이 없으면 hook exit 0 (skip)
4. `.cs` 파일이 있으면 `reindex --changed` 실행
5. reindex 내부에서 staged 삭제 파일 → 인덱스 행 제거
6. staged 수정/추가 파일 → 파싱 → AI description 생성 → upsert
7. AI 실패 시 stale=1 upsert
8. hook exit 0 (항상 — commit 차단 없음)

## 6. 대안 흐름
- staged `.cs` 없음: 즉시 exit 0.

## 7. 예외 흐름
| # | 조건 | 기대 처리 | 사용자 메시지 | 기록 필요 여부 |
|---|---|---|---|---|
| E1 | `codenav` 미설치 | hook exit 0 (skip) | 없음 | 불필요 |
| E2 | AI (Claude CLI) call 실패 | stale=1 upsert, hook exit 0 | 없음 (stale files는 `codenav status` 확인) | 필요 (stale_files) |
| E3 | `git` CLI 미설치 환경 | reindex 실패, hook exit 0 | stderr 경고 | 불필요 |

## 8. 상세 기능 요구사항
- hook 은 bash 에 의존하지 않는다. Python interpreter 로 직접 실행.
- hook 실패 (예외) 가 commit 을 차단해서는 안 된다. 항상 exit 0.
- staged `.cs` 가 없으면 reindex 호출 없이 즉시 종료.
- 삭제된 staged `.cs` 파일은 인덱스에서 해당 클래스 제거.
- hook 등록은 `install-hook.ps1`(Windows) / `install-hook.sh`(Linux·macOS) 로 수동 1회 수행.

## 9. 입출력 개념
| 구분 | 내용 | 제약 | 예시 |
|---|---|---|---|
| 입력 | staged 파일 목록 (git 내부) | commit 시 자동 | 없음 (사용자 직접 입력 없음) |
| 출력 | reindex 통계 (stderr) | commit 로그에는 나타나지 않음 | `Reindex done: 2 written, 0 skipped, 0 stale.` |

## 10. 상태 정의
없음.

## 11. 권한 조건
| 역할 / 권한 | 허용 작업 | 거부 시 기대 결과 |
|---|---|---|
| git commit 실행자 | hook 자동 실행 | 없음 (hook 미등록 시 hook 실행 안 됨) |

## 12. 데이터 처리 원칙
- 보존 대상: reindex 결과 인덱스 항목.
- 부분 실패: AI 실패 시 stale=1 저장 후 계속.
- 민감정보: 없음.

## 13. 비기능 요구사항
| 분류 | 본 기능 적용 기준 |
|---|---|
| 성능 | commit 차단 없음 — hook timeout 60초 이내 (AI call 포함) |
| 플랫폼 | Windows / macOS / Linux (bash 의존 없음) |
| 에러 처리 | 모든 예외 catch → exit 0 (commit 비차단) |

## 14. 로그 / 알림 / 이력 정책
- 정보 기록: reindex 완료 통계 stderr.
- 오류 기록: hook 예외 발생 시 stderr 경고.
- 알림: 없음.
- 이력: 없음.

## 15. UI / 외부 연계 영향
| 구분 | 영향 |
|---|---|
| UI | 없음 |
| 외부 연계 | Claude CLI subprocess (F005 통해 간접 호출) |
| 운영 | hook 등록/해제는 수동 (install-hook 스크립트). 등록 여부는 `.git/hooks/pre-commit` 존재 여부로 확인. |

## 16. FC / ADR-CATALOG / ADR 반영 여부
| 문서 | 반영 여부 | 반영 내용 |
|---|---|---|
| FC | 완료 | F003 행 등재 |
| ADR | 불필요 | 별도 기술 결정 없음 |
| ADR-CATALOG | 불필요 | 없음 |

## 17. 수용 기준
| ID | 기준 | 확인 방법 |
|---|---|---|
| AC-F003-001 | `.cs` 파일 staged 커밋 시 hook 자동 실행되어 reindex 완료 | 수동 확인 |
| AC-F003-002 | AI 실패(`CODENAV_INDEXER_MOCK=fail`) 시 commit 차단 없음 + stale 마킹 | 수동 확인 |
| AC-F003-003 | staged `.cs` 없는 커밋 시 hook 즉시 exit 0 (reindex 미실행) | 수동 확인 |
| AC-F003-004 | Windows / macOS 에서 모두 hook 정상 동작 (bash 불필요) | 수동 확인 |

## 18. 테스트 관점
| ID | Given | When | Then | 확인 방식 |
|---|---|---|---|---|
| TC-F003-001 | hook 등록 완료, `.cs` 파일 staged | `git commit` | reindex 실행 + stderr 통계 출력 + commit 성공 | Manual |
| TC-F003-002 | `CODENAV_INDEXER_MOCK=fail` | `git commit -am "test"` | commit 성공 + `codenav status` 에 stale 파일 노출 | Manual |
| TC-F003-003 | `.md` 파일만 staged | `git commit` | hook exit 0, reindex 미실행 | Manual |

## 19. 요구 근거
- [CodeNavigator-FC F003 행](../CodeNavigator-FC.md)
- [CodeNavigator-PRD §3 S2·S3 시나리오](../CodeNavigator-PRD.md)

## 20. 미확인 사항
없음.
