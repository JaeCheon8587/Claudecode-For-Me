# CodeNavigator-TASK-003 — 로컬 관리 UI 및 수동 메타데이터 기능 구현

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-TASK-003 |
| 버전 | 0.1 |
| 상태 | Ready |
| 작업 유형 | feature |
| 작성 가정 | 로컬 브라우저에서 인덱스 상태를 확인하고 수동 메타데이터를 관리할 수 있는 UI 를 추가한다. 영향 영구 SSOT 갱신 완료. |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## §1. 목적

CodeNavigator 에 개발자용 로컬 관리 UI 를 추가한다. UI 에서 인덱스 상태 확인, 목록/상세 조회, 전체 reindex 실행, description/tags 수동 수정, 수동 항목 추가/삭제, 파일 단위 삭제를 수행할 수 있어야 한다.
특히 각 항목이 어느 solution/project/file 에 속하는지 추적 가능해야 한다.

## §2. 범위

- **포함**: localhost 웹 UI, 대시보드/목록/상세 화면, 전체 reindex 버튼, 수동 메타데이터 수정, 수동 항목 추가/삭제, 파일 단위 삭제 UI, 서비스 계층 분리, 테스트 추가
- **제외**: 사용자 인증, 외부 공개 배포, 실시간 갱신, 소스 코드 편집, 멀티유저 충돌 제어

## §3. 사전 조건

- Python 3.11+ 실행 가능
- 기존 CLI 동작을 깨지 않아야 함
- 로컬 브라우저에서 `127.0.0.1` 접속 가능

## §4. 검증 기준

```powershell
# UI 서버 실행
codenav ui --root .
# 기대: localhost 주소 출력, 브라우저에서 대시보드 접근 가능

# 자동 테스트
pytest tests/ -q
# 기대: 기존 테스트 유지 + UI/서비스 테스트 통과
```

## §5. 변경 파일 요약

| 파일 | 변경 요지 |
|---|---|
| `src/codenav/__main__.py` | `ui` subcommand 추가, 서비스 계층 호출로 재정리 |
| `src/codenav/store.py` | 목록/상세/수동 저장/수동 삭제용 조회·갱신 API 추가 |
| `src/codenav/search.py` | 필요 시 UI 공용 검색 래퍼 정리 |
| `src/codenav/services.py` | CLI/UI 공용 유스케이스 계층 신규 |
| `src/codenav/app.py` | 로컬 웹 UI 서버 진입점 신규 |
| `src/codenav/templates/` | 대시보드/목록/상세/폼 템플릿 신규 |
| `tests/` | 서비스/UI/store 테스트 추가 |

## §6. 영향 SSOT 갱신 상태

| 문서 | 갱신 완료 여부 | 갱신 요지 |
|---|---|---|
| CodeNavigator-PRD | 완료 | F007/F008, UI 시나리오, 로컬 UI 제약 추가 |
| CodeNavigator-FC | 완료 | F007/F008 행 추가 |
| CodeNavigator-ARCHITECTURE | 완료 | UI 호스트, 서비스 계층, localhost 바인딩 규칙 추가 |
| CodeNavigator-FRD-004 | 완료 | 관리 UI/수동 메타데이터 요구 정의 |

## §8. 실행 단계
1. CLI 에서 재사용 가능한 조회/재인덱싱/삭제 흐름을 서비스 계층으로 분리한다.
2. 인덱스 항목의 source 유형(자동/수동)과 수동 수정 상태를 저장할 수 있도록 저장소를 확장한다.
3. 목록/상세/저장/삭제에 필요한 저장소 조회 API 를 추가한다.
4. localhost 전용 UI 서버와 화면 라우팅을 구현한다.
5. 대시보드, 목록, 상세, 수동 추가/수정 폼, 작업 결과 메시지를 구현한다.
6. 목록/상세에 solution, project, namespace, kind, folder, file 정보를 노출하고 해당 필터를 연결한다.
7. UI 에서 전체 reindex 와 파일 단위 삭제를 실행 가능하게 연결한다.
8. 서비스/저장소/UI 테스트를 추가하고 기존 테스트와 함께 검증한다.

## §12. 주요 컨텍스트 임베드

**UI 기본 범위**
- 대시보드: 총 클래스 수, stale 수, 마지막 인덱싱 시각, DB 경로
- 목록: query, solution, project, namespace, kind, stale 필터, source 필터, solution/project/class/namespace/file/description/tags 표시
- 상세: methods, file, folder, namespace, project, solution, kind, indexed_at, stale
- 작업: 전체 reindex, 수동 저장, 수동 항목 추가, 수동 항목 삭제, 파일 단위 삭제

**저장 정책**
- 자동 항목과 수동 항목을 구분 가능해야 함
- 자동 항목의 description/tags 수동 수정값은 재조회 시 유지
- 수동 항목은 실제 `.cs` 파일 파싱 결과와 별개로 관리

**운영 제약**
- UI 서버 기본 바인딩은 `127.0.0.1`
- UI 실패가 기존 CLI 동작에 영향을 주면 안 됨
