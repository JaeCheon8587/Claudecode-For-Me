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
| 버전 | {예: 0.1 (Draft) 또는 0.1 (Ready)} |
| 상태 | Draft / Ready |
| 연결 TASK | [{App}-TASK-{NNN}](../TASK/{App}-TASK-{NNN}.md) |
| 작성 가정 | TASK 확정 및 관련 SSOT 반영 완료 |
| 관련 문서 | [DOCUMENT_GUIDE](../../DOCUMENT_GUIDE.md) |

> Work Packet 생성 시 상태는 `Draft` 또는 `Ready`만 사용한다. `In Progress` / `Done` / `Dropped`는 후속 운영 단계에서 별도 갱신할 때만 사용한다.

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
| 완료 판단 | TASK §9 완료 기준 + §9.2 엣지 케이스 + §9.3 오류 처리 + 본 Work Packet §8 검증 입력 |
| 다음 단계 | forge-scope |

## 2. TASK
| 구분 | 링크 | 사용 목적 |
|---|---|---|
| Scope Authority | [{App}-TASK-{NNN}](../TASK/{App}-TASK-{NNN}.md) | 작업 범위, 비목표, 완료 기준, 엣지 케이스, 오류 처리, 테스트 기준 |

## 3. Execution Gate

> `Ready`만 후속 `forge-scope` 또는 구현 에이전트가 진행할 수 있다.
> `Draft = do not implement`: 미확정/누락/충돌을 먼저 해결해야 하며 구현을 시작하지 않는다.

| 상태 | 실행 판단 | 기준 |
|---|---|---|
| Ready | forge-scope 진행 가능 | blocking 없음, Required SSOT 존재, 구현 범위 명확 |
| Draft | 구현 금지 | 미확정/누락/충돌 존재, `Blocking / Open Questions` 해결 필요 |

| 현재 판정 | 근거 |
|---|---|
| Draft / Ready | {blocking 여부, Required SSOT target path 존재 여부, 구현 범위 명확성 요약} |

## 4. Required SSOT Execution Matrix

> `ssot-write`의 `handoff.json.actions`에서 변환한 `Confirmed SSOT Action Matrix`를 기준 입력으로 삼는다.
> `CREATE` / `UPDATE` 대상은 기본 `Required`다.
> 실행에 직접 필요 없는 `SKIP` 대상은 넣지 않는다.
> 각 Action의 `authority_paths`는 구현의 Truth Authority이므로 `Required`다. authority가 없거나 충돌하면 상태는 `Draft`다.
> authority가 이미 CREATE/UPDATE target 행이거나 연결 TASK이면 중복 `AUTHORITY` 행을 만들지 않는다(그 행이 authority 링크를 겸함). target·TASK가 아닌 authority만 전용 `AUTHORITY` 행으로 둔다.
> `Optional`은 CREATE/UPDATE를 느슨하게 낮추는 용도가 아니라, TASK 실행 판단에 실제로 도움이 되는 예외 입력에만 허용한다.
> `CREATE/UPDATE target path`가 비어 있거나 파일이 없으면 임의 링크를 만들지 않는다.
> 이 경우 상태는 `Draft`이며, 해당 source row를 `Blocking / Open Questions`에 기록한다.

| SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority |
|---|---|---|---|---|---|---|
| FRD | CREATE / UPDATE | [{App}-FRD-{NNN}](../FRD/{App}-FRD-{NNN}.md) | {예: §1, §2, §17, §18} | 기능 의도·수용 기준 확인 | {예: handoff action ACT-001} | Required |
| FC | UPDATE | [{App}-FC](../{App}-FC.md) | {예: 해당 기능 행} | 기능 레지스트리·상태 확인 | {예: handoff action ACT-002} | Required |
| ADR | CREATE / UPDATE | [{App}-ADR-{NNN}](../ADR/{App}-ADR-{NNN}.md) | {예: §3 결정, §4 결과} | 구조 결정·금지사항 확인 | {예: handoff action ACT-003} | Required / Optional |
| ADR | AUTHORITY | [{App}-ADR-{NNN}](../ADR/{App}-ADR-{NNN}.md) | {controlling 결정 범위} | handoff Action의 현재 설계 권위 | {예: handoff action ACT-001 authority} | Required |
| ARCHITECTURE | UPDATE | [{App}-ARCHITECTURE](../{App}-ARCHITECTURE.md) | {예: 관련 호스트 책임} | App 런타임/호스트 제약 확인 | {예: handoff action ACT-004} | Required / Optional |

## 5. 실행 규칙
- TASK 에 없는 작업은 구현하지 않는다.
- SSOT 와 충돌하는 TASK 는 실행하지 않고 충돌 내용을 보고한다.
- 각 handoff Action의 `instruction`과 `authority_paths`를 함께 따른다. 둘이 충돌하면 구현하지 않고 `Draft`로 되돌린다.
- 명시적 supersession 없이 TASK와 SSOT가 충돌하면 실행하지 않고 `Draft`로 되돌린다.
- TASK 가 애매하면 Required SSOT 로 해석한다.
- Required SSOT 에도 근거가 없으면 질문하거나 미확인으로 보고한다.
- 코드 현실이 TASK/SSOT 와 다르면 구현 전에 차이를 보고한다.
- Work Packet 에 없는 문서를 임의로 넓게 탐색하지 않는다. 단, 빌드/테스트/컴파일 오류를 해결하기 위한 직접 관련 파일 탐색은 허용한다.

## 6. 실행 경계
| 구분 | 내용 |
|---|---|
| 반드시 수행 | {이번 실행에서 반드시 수행할 일} |
| 금지 | {범위 밖 구현·문서 수정·리팩토링 등 금지사항} |
| 허용 | {테스트 보강, 국소 리팩토링 등 허용 범위} |
| 중단 조건 | {충돌/미확인/환경 실패 등 중단해야 하는 조건} |

## 7. Blocking / Open Questions

> `Ready`일 때는 `none`으로 명시한다. 미확정 사항이 하나라도 실행 판단을 막으면 상태는 `Draft`다.
> `CREATE/UPDATE target path`가 비어 있거나 파일이 없으면 해당 source row를 반드시 기록한다.

| Issue | Source | Impact | Required decision |
|---|---|---|---|
| none | none | none | none |

## 8. 검증 입력
| 구분 | 기준 |
|---|---|
| 완료 기준 | TASK §9, §9.2, §9.3 |
| 단위 테스트 | TASK §9.1 |
| 문서-코드 정합 검증 | `doc-driven-review` 또는 `ddr-loop` 에 TASK + Required SSOT Execution Matrix 를 입력 |
| 빌드/테스트 명령 | {명령 또는 "코드베이스 기준으로 탐색"} |

## 9. Readiness Checklist
- [ ] TASK 상태가 `Accepted` 또는 실행 가능한 상태다.
- [ ] Required SSOT Execution Matrix 의 링크가 실제 존재한다.
- [ ] CREATE/UPDATE 대상 SSOT가 기본 Required 로 반영됐다.
- [ ] Optional 은 구현 판단상 필요한 예외 입력이며 사유가 있다.
- [ ] CREATE/UPDATE target path 누락 또는 파일 미존재가 있으면 상태가 `Draft`다.
- [ ] 모든 handoff `authority_paths`가 Required로 들어갔고 unrelated authority는 추가되지 않았다.
- [ ] 모든 downstream Work Packet instruction이 §5 실행 규칙에 반영됐다.
- [ ] TASK 와 Required SSOT Execution Matrix 사이 명백한 충돌이 없다.
- [ ] Execution Gate 가 `Ready`면 Blocking / Open Questions 가 `none`이다.
- [ ] Execution Gate 가 `Draft`면 후속 구현 금지 의미가 명확하다.
- [ ] §5 실행 규칙과 §6 실행 경계가 비어 있지 않다.
- [ ] 검증 입력이 코드 작업자가 실행 가능한 수준이다.

## 10. Implementation Output Contract

후속 구현 에이전트는 완료 보고에 아래 항목을 반드시 포함한다.

| 항목 | 필수 내용 |
|---|---|
| Changed files | 변경한 파일 목록 |
| Scope match | TASK 와 Required SSOT Execution Matrix 대비 구현 범위 일치 여부 |
| Tests run | 실행한 빌드/테스트 명령과 결과 |
| Not run | 실행하지 못한 검증과 사유 |
| Deviations | TASK/SSOT/Work Packet 대비 이탈, 추가 판단, 후속 조치 |
