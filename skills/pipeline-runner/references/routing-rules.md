# pipeline-runner Routing Rules

이 문서는 `pipeline-runner`가 requirement-spec 산출물을 읽고 후속 스킬 체인을 고르는 기준이다.

## Scale Assessment

각 축은 0~3점으로 평가한다. 모든 점수는 `Evidence`와 함께 `pipeline-build.md`에 기록한다.

| Axis | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| 변경 범위 | 단일 파일, 단일 함수, 단순 수정 | 단일 모듈 또는 단일 화면 | 여러 모듈, 여러 화면, API와 UI 동시 변경 | 도메인 구조, 아키텍처, 여러 서비스/패키지 영향 |
| SSOT 영향도 | 영구 문서 변경 불필요 | TASK에만 기록하면 충분 | PRD/FC/FRD 등 기능 문서 갱신 필요 | ADR 또는 도메인 정책 변경 필요 |
| 데이터/API/계약 영향도 | 데이터/API 변경 없음 | 내부 함수 시그니처 또는 내부 타입 변경 | API request/response, DB schema, 공개 타입 변경 | migration, backward compatibility, 외부 시스템 연동 영향 |
| 테스트/검증 난이도 | 기존 테스트 또는 간단한 수동 확인으로 충분 | unit test 추가/수정 필요 | integration/e2e 또는 문서 기준 검증 필요 | 회귀 위험이 커서 ddr-loop/doc-driven-review/branch-review까지 강제 필요 |
| 실패 리스크 | 실패해도 영향 작음 | 일부 UX 문제 가능 | 사용자 데이터, 권한, 결제, 알림, 운영 플로우 영향 | 보안, 개인정보, 금전, 데이터 손실, 장애 가능성 |
| 의존성/불확실성 | 독립적으로 구현 가능 | 기존 내부 모듈 의존 | 외부 API, 배포 환경, 설정값 의존 | 아직 확인되지 않은 기술/정책/운영 의존성 있음 |
| 작업 분할 필요성 | 한 번에 끝나는 단일 작업 | 2~3개 작은 단계로 나누면 좋음 | 여러 implementation slice 필요 | epic/phase 단위 분할 필요 |

## Size Bands

| Total Score | Size |
|---:|---|
| 0~4 | XS/S |
| 5~8 | M |
| 9~13 | L |
| 14+ | XL |

## Default Routing

| Condition | Pipeline |
|---|---|
| XS/S | `task-write -> forge-scope -> branch-review` |
| M and SSOT 영향도 < 2 | `task-write -> forge-scope -> branch-review` |
| M/L/XL and SSOT 영향도 >= 2 | `task-write -> ssot-write -> work-packet-write -> forge-scope -> branch-review` |
| 고위험 또는 검증 난이도 높음 | `task-write -> ssot-write -> work-packet-write -> forge-scope -> ddr-loop -> branch-review` |

## Forced Conditions

- `ssot-write`가 포함되면 `work-packet-write`도 반드시 포함한다.
- `work-packet-write`는 `ssot-write` 결과를 `forge-scope` 입력 계약으로 연결하는 어댑터다.
- `work-packet-write`는 `ssot-write` 없이 기본 삽입하지 않는다.
- `SSOT 영향도 >= 2`이면 `ssot-write -> work-packet-write`를 포함한다.
- `테스트/검증 난이도 >= 2`이면 `ddr-loop` 포함을 우선 검토한다.
- `실패 리스크 >= 2`이면 `ddr-loop` 포함을 우선 검토한다.
- `데이터/API/계약 영향도 >= 3`이면 `ssot-write -> work-packet-write`와 `ddr-loop`를 포함한다.
- `작업 분할 필요성 >= 3`이면 pipeline-build.md에 phase/epic 분할 필요를 기록하고, 한 번에 구현 가능한 slice를 선택해야 한다.

## Override Policy

사용자가 명시적으로 요청하면 `task-write -> ssot-write -> forge-scope -> branch-review`를 허용할 수 있다.

이 경우 반드시 `pipeline-build.md`의 `Risk Notes`에 아래 문장을 기록한다.

```text
SSOT not enforced in forge-scope input: forge-scope TASK legacy path only reads TASK and does not automatically consume ssot-write Confirmed SSOT Action Matrix.
```

기본 라우팅에서는 이 override를 사용하지 않는다.
