# CodeNavigator-FRD-004 — F007/F008 로컬 관리 UI·수동 메타데이터 관리

> **코드 상세 금지**: 코드 경로, 파일명, 클래스명, 메서드명, 구현 방식은 본 문서에 쓰지 않는다.

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-FRD-004 |
| 버전 | 0.1 (Draft) |
| 기능 ID | F007, F008 |
| 상태 | Ready |
| 작성 가정 | 개발자 로컬 환경에서 `localhost` 로만 접근하는 관리 UI. 인증/권한 모델 없음. |
| 관련 문서 | [CodeNavigator-PRD](../CodeNavigator-PRD.md) · [CodeNavigator-FC](../CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](../CodeNavigator-ARCHITECTURE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.2 | 2026-05-21 | solution/project/file 중심 조회·필터 요구 명확화 | 정재천 |
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## 1. 기능 요약
| 항목 | 내용 |
|---|---|
| 작업 유형 | 신규 |
| 기능 목적 | 개발자가 인덱스 상태를 브라우저에서 빠르게 확인하고 수동 보정 작업을 수행한다 |
| 기대 결과 | 목록/상세/수정/삭제/재인덱싱을 CLI 없이 UI 로 수행 가능 |
| 완료 기준 | §17 수용 기준 충족 |
| 우선순위 | P1 |
| 의존 기능 | F001, F002, F004, F006 |

## 2. 범위
| 구분 | 내용 |
|---|---|
| 포함 | 로컬 대시보드, 인덱스 목록/검색/필터, 상세 보기, stale 확인, 전체 reindex 실행, 수동 description/tags 수정, 수동 항목 추가, 수동 항목 삭제 |
| 제외 | 외부 공개 배포, 사용자 인증, 다중 사용자 동시 편집, 실시간 푸시 업데이트, 소스 코드 편집 |
| 변경되는 사용자 경험 | 개발자가 터미널 없이 브라우저로 인덱스 상태와 수동 보정 작업을 수행 |
| 변경되지 않아야 하는 것 | 기존 CLI 인터페이스와 pre-commit hook 동작 |

## 3. 사용자 역할
- 개발자 — 로컬 인덱스 운영자
- AI 코딩 에이전트 — 기존 CLI 소비자 (변경 없음)

## 4. 사전 조건
- Python 환경에서 CodeNavigator 패키지 실행 가능
- 대상 레포에 `.codenav/index.sqlite` 접근 가능
- 브라우저에서 `localhost` 접속 가능

## 5. 기본 흐름 — 조회
1. 개발자가 UI 서버를 실행
2. 첫 화면에서 총 클래스 수, stale 수, 마지막 인덱싱 시각, DB 경로를 확인
3. 목록 화면에서 query, solution, project, namespace, stale 여부, source 유형으로 필터링
4. 상세 화면에서 solution, project, namespace, class kind, folder, file, description, tags, methods, indexed_at 을 확인

## 6. 기본 흐름 — 수동 수정
1. 개발자가 상세 화면에서 description/tags 를 수정
2. 저장 시 시스템이 입력값을 정규화하여 저장
3. 저장 완료 후 상세 화면과 목록 검색 결과에 즉시 반영

## 7. 기본 흐름 — 수동 추가/삭제
1. 개발자가 새 인덱스 항목 추가 폼을 연다
2. class, namespace, file, description, tags 를 입력한다
3. 저장 시 시스템이 source 유형을 수동 항목으로 부여해 인덱스에 반영한다
4. 삭제 시 확인 후 해당 수동 항목을 제거한다

## 8. 기본 흐름 — 재인덱싱
1. 개발자가 UI 에서 전체 reindex 를 실행
2. 시스템이 기존 reindex 유스케이스를 호출한다
3. 완료/실패 요약을 UI 에 표시한다
4. stale 변화와 최신 목록이 화면에 반영된다

## 9. 예외 흐름
| # | 조건 | 기대 처리 | 사용자 메시지 | 기록 필요 여부 |
|---|---|---|---|---|
| E1 | 인덱스 DB 미생성 | 빈 상태 대시보드 표시 + 전체 reindex 유도 | 화면 배너 | 불필요 |
| E2 | 수동 저장 입력 누락 | 저장 거부 | 필드별 검증 메시지 | 불필요 |
| E3 | reindex 중 AI 호출 실패 | 일부 stale 저장 후 UI 에 결과 요약 표시 | 작업 결과 메시지 | 필요 |
| E4 | 존재하지 않는 항목 삭제 요청 | no-op 처리 | 경고 메시지 | 불필요 |

## 10. 상세 기능 요구사항
- UI 는 `localhost` 전용이며 기본 바인딩 주소는 loopback 이다.
- 첫 화면은 대시보드이며 목록 진입 없이 핵심 상태를 즉시 보여준다.
- 목록은 query, solution, project, namespace, stale 여부, 수동/자동 source 유형, kind 로 필터 가능해야 한다.
- 목록은 solution, project, namespace, class, kind, file, stale, source 를 컬럼으로 보여야 한다.
- 상세는 solution, project, namespace, class, kind, folder, file, description, tags, methods, indexed_at, stale 여부를 보여준다.
- description/tags 수정은 수동 편집값으로 저장되어 재조회 시 유지돼야 한다.
- 수동 추가 항목은 실제 `.cs` 파일 파싱 결과와 별개로 생성 가능해야 한다.
- 수동 추가 항목은 source 유형이 명확히 구분되어 목록/상세에서 식별 가능해야 한다.
- 수동 삭제는 수동 항목에 대해 허용해야 한다.
- 파일 단위 삭제는 기존 F006 동작을 UI 에서도 호출 가능해야 한다.
- UI 에서 실행한 reindex 는 기존 CLI 와 동일한 규칙(stale 처리, 삭제 파일 정리)을 따라야 한다.

## 11. 입출력 개념
| 구분 | 내용 | 제약 | 예시 |
|---|---|---|---|
| 조회 입력 | query, solution, project, namespace, kind, stale 필터, source 필터 | 모두 선택적 | `"collector"`, `Core`, `stale only` |
| 조회 출력 | HTML 목록/상세 화면 | 브라우저 렌더링 | 테이블, 상세 패널 |
| 수정 입력 | description, tags | 빈 description 금지 | `"PLC 이벤트를 집계..."`, `["plc","event"]` |
| 추가 입력 | solution, project, namespace, class, kind, folder, file, description, tags | class/description 필수 | 수동 항목 1건 |
| 작업 출력 | 성공/실패 플래시 메시지 | 브라우저 화면 표시 | `Reindex done: 3 written...` |

## 12. 상태 정의
- `자동 항목`: 파싱/reindex 로 생성된 항목.
- `수동 항목`: UI 에서 명시 추가된 항목.
- `수동 편집됨`: 자동 항목 중 description/tags 가 사람이 수정된 상태.
- `stale=0`: 검색 가능.
- `stale=1`: 검색 제외, UI 에서 stale 필터로 확인 가능.

## 13. 권한 조건
| 역할 / 권한 | 허용 작업 | 거부 시 기대 결과 |
|---|---|---|
| 로컬 개발자 | 조회, 재인덱싱, 수동 추가/수정/삭제 | 없음 (인증 모델 없음) |

## 14. 데이터 처리 원칙
- 보존 대상: 수동 항목, 수동 편집된 description/tags, source 유형.
- 부분 실패: reindex 실패 시 기존 저장 데이터 보존, 실패 항목만 stale 처리.
- 중복 처리: 수동 항목 식별자는 기존 자동 항목과 충돌 없이 구분 가능해야 한다.
- 민감정보: 없음.

## 15. 비기능 요구사항
| 분류 | 본 기능 적용 기준 |
|---|---|
| 접근 범위 | `localhost` 전용 |
| 성능 | 1,000 클래스 이하 목록 필터 응답 300ms 이내 |
| 사용성 | 목록에서 상세 진입, 상세에서 저장/삭제/복귀 흐름이 2클릭 이내 |
| 안정성 | UI 실패가 기존 CLI 동작에 영향을 주지 않음 |

## 16. FC / ADR-CATALOG / ADR 반영 여부
| 문서 | 반영 여부 | 반영 내용 |
|---|---|---|
| FC | 완료 | F007, F008 행 등재 |
| ADR | 불필요 | 기존 결정 범위 내 구현 |
| ADR-CATALOG | 불필요 | 없음 |

## 17. 수용 기준
| ID | 기준 | 확인 방법 |
|---|---|---|
| AC-F007-001 | UI 첫 화면에서 총 클래스 수, stale 수, 마지막 인덱싱 시각, DB 경로가 보인다 | 수동 확인 |
| AC-F007-002 | 목록에서 query/solution/project/namespace/kind/stale/source 필터를 적용할 수 있다 | 수동 확인 |
| AC-F007-003 | 상세 화면에서 solution, project, folder, file, methods 정보를 확인할 수 있다 | 수동 확인 |
| AC-F007-004 | UI 에서 전체 reindex 실행 후 결과 메시지가 보인다 | 수동 확인 |
| AC-F008-001 | 자동 항목의 description/tags 수정 후 재조회 시 값이 유지된다 | 수동 확인 |
| AC-F008-002 | 수동 항목 추가 후 목록/검색 결과에 나타난다 | 수동 확인 |
| AC-F008-003 | 수동 항목 삭제 후 목록/검색 결과에서 사라진다 | 수동 확인 |
| AC-F008-004 | 파일 단위 삭제를 UI 에서 실행할 수 있다 | 수동 확인 |

## 18. 테스트 관점
| ID | Given | When | Then | 확인 방식 |
|---|---|---|---|---|
| TC-F007-001 | 인덱스가 존재함 | UI 진입 | 대시보드와 목록이 표시됨 | Manual |
| TC-F007-002 | 서로 다른 solution/project 항목이 존재 | solution 또는 project 필터 선택 | 선택한 범위의 항목만 보임 | Manual |
| TC-F007-005 | stale 항목 1건 이상 존재 | stale 필터 선택 | stale 항목만 보임 | Manual |
| TC-F007-003 | 자동 항목 1건 존재 | description/tags 수정 후 저장 | 상세/목록에 갱신 반영 | Manual |
| TC-F008-001 | 빈 인덱스 또는 기존 인덱스 | 수동 항목 추가 | 검색 결과에 노출 | Manual |
| TC-F008-002 | 수동 항목 존재 | 삭제 실행 | 결과에서 제거 | Manual |
| TC-F007-004 | AI 실패 환경 | UI 에서 reindex 실행 | stale 증가 + 결과 메시지 표시 | Manual |

## 19. 요구 근거
- [CodeNavigator-FC F007~F008 행](../CodeNavigator-FC.md)
- [CodeNavigator-PRD §3.1·§6·§7](../CodeNavigator-PRD.md)

## 20. 미확인 사항
없음.
