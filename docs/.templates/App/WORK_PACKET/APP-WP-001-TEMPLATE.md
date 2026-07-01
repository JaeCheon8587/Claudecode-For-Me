# {App}-WP-{NNN} — {작업명}

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다.
> 본 파일은 단일 App (`{App}`) 의 **AI 코드 실행용 Work Packet** 이다. 결과 파일명과 문서 ID는 `{App}-WP-{NNN}` 형식을 사용한다.
>
> **Work Packet 은 Context Router**: TASK 와 관련 SSOT 를 연결하는 얇은 실행 manifest 다. 요구사항·SSOT 본문을 길게 복제하지 않는다.
>
> **권한 분리**: TASK 는 작업 범위 기준(Scope Authority), SSOT 는 제품/시스템 진실 기준(Truth Authority), Work Packet 은 이번 실행에서 읽을 문서와 충돌 규칙을 지정한다.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-WP-{NNN} |
| 버전 | {예: 0.1 (Ready)} |
| 상태 | Draft / Ready / In Progress / Done / Dropped |
| 연결 TASK | [{App}-TASK-{NNN}](../TASK/{App}-TASK-{NNN}.md) |
| 작성 가정 | TASK 확정 및 관련 SSOT 반영 완료 |
| 관련 문서 | [DOCUMENT_GUIDE](../../DOCUMENT_GUIDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

---

## 1. 실행 요약
| 항목 | 내용 |
|---|---|
| 작업명 | {작업명} |
| 작업 유형 | feature / refactor / maintenance / migration / setup / investigation / 기타 |
| 실행 대상 | {코드 작업 대상 App/모듈} |
| 완료 판단 | TASK §9 완료 기준 + §9.2 엣지 케이스 + §9.3 오류 처리 + 본 Work Packet §6 검증 입력 |

## 2. TASK
| 구분 | 링크 | 사용 목적 |
|---|---|---|
| Scope Authority | [{App}-TASK-{NNN}](../TASK/{App}-TASK-{NNN}.md) | 작업 범위, 비목표, 완료 기준, 엣지 케이스, 오류 처리, 테스트 기준 |

## 3. Required SSOT

> 이번 작업에 반드시 읽어야 하는 영구 SSOT 만 남긴다. 관련 없는 문서는 넣지 않는다.

| 우선순위 | 문서 | 읽을 범위 | 사용 목적 |
|---|---|---|---|
| Required | [{App}-FRD-{NNN}](../FRD/{App}-FRD-{NNN}.md) | {예: §1, §2, §17, §18} | 기능 의도·수용 기준 확인 |
| Required / Optional | [{App}-FC](../{App}-FC.md) | {예: 해당 기능 행} | 기능 레지스트리·상태 확인 |
| Required / Optional | [{App}-ADR-{NNN}](../ADR/{App}-ADR-{NNN}.md) | {예: §3 결정, §4 결과} | 구조 결정·금지사항 확인 |
| Required / Optional | [{App}-ARCHITECTURE](../{App}-ARCHITECTURE.md) | {예: 관련 호스트 책임} | App 런타임/호스트 제약 확인 |
| Required / Optional | [ARCHITECTURE](../../ARCHITECTURE.md) | {예: §6.1 절대 금지 매트릭스} | 솔루션 레이어 제약 확인 |

## 4. 실행 규칙
- TASK 에 없는 작업은 구현하지 않는다.
- SSOT 와 충돌하는 TASK 는 실행하지 않고 충돌 내용을 보고한다.
- TASK 가 애매하면 Required SSOT 로 해석한다.
- Required SSOT 에도 근거가 없으면 질문하거나 미확인으로 보고한다.
- 코드 현실이 TASK/SSOT 와 다르면 구현 전에 차이를 보고한다.
- Work Packet 에 없는 문서를 임의로 넓게 탐색하지 않는다. 단, 빌드/테스트/컴파일 오류를 해결하기 위한 직접 관련 파일 탐색은 허용한다.

## 5. 실행 경계
| 구분 | 내용 |
|---|---|
| 반드시 수행 | {이번 실행에서 반드시 수행할 일} |
| 금지 | {범위 밖 구현·문서 수정·리팩토링 등 금지사항} |
| 허용 | {테스트 보강, 국소 리팩토링 등 허용 범위} |
| 중단 조건 | {충돌/미확인/환경 실패 등 중단해야 하는 조건} |

## 6. 검증 입력
| 구분 | 기준 |
|---|---|
| 완료 기준 | TASK §9, §9.2, §9.3 |
| 단위 테스트 | TASK §9.1 |
| 문서-코드 정합 검증 | `doc-driven-review` 또는 `ddr-loop` 에 TASK + Required SSOT 를 입력 |
| 빌드/테스트 명령 | {명령 또는 "코드베이스 기준으로 탐색"} |

## 7. Readiness Checklist
- [ ] TASK 상태가 `Accepted` 또는 실행 가능한 상태다.
- [ ] Required SSOT 가 실제 존재한다.
- [ ] TASK 와 Required SSOT 사이 명백한 충돌이 없다.
- [ ] §4 실행 규칙과 §5 실행 경계가 비어 있지 않다.
- [ ] 검증 입력이 코드 작업자가 실행 가능한 수준이다.
