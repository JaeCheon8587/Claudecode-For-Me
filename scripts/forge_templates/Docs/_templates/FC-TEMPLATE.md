# FC-{SYSTEM_CODE}-{NNN} — {프로젝트명} Feature Catalog

> ⚠ **TEMPLATE** — `{...}` placeholder를 채우거나 해당 줄을 삭제한다.
> 작성 규칙은 [DOCUMENT_GUIDE.md](../DOCUMENT_GUIDE.md), 식별자 규약은 [ADR-0008](../ADR.md#adr-0008-문서-식별자명명-규약) 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | FC-{SYSTEM_CODE}-{NNN} |
| 버전 | {예: 0.1 (Draft)} |
| 작성 가정 | {본 카탈로그 작성 시 깔린 가정} |
| 관련 문서 | [PRD](../PRD.md) · [FRD 폴더](../FRD/) · [ADR](../ADR.md) · [UI_GUIDE](../UI_GUIDE.md) |

> 본 문서는 전체 기능을 한눈에 보는 중앙 레지스트리이다. 미작성 컬럼은 빈칸이 아닌 "미작성/추후"로 명기.

## 기능 레지스트리

### 기본 식별·설명
| 기능 ID | 기능명 | 기능 설명 | 기능 상태 | 우선순위 |
|---|---|---|---|---|
| F001 | {기능명} | {한 줄 설명} | Draft / In Progress / Done | P0 / P1 / P2 |

### 문서 연결
| 기능 ID | 관련 PRD | 관련 FRD | 관련 API Spec | 관련 UI Spec | 관련 Data Spec |
|---|---|---|---|---|---|
| F001 | [PRD §{X}](../PRD.md) | [FRD-F001](../FRD/FRD-F001.md) | 미작성/추후 | [UI_GUIDE](../UI_GUIDE.md) | 미작성/추후 |

### 검증·근거·확인
| 기능 ID | 관련 Test Case | 구현 근거 | 확인 필요 여부 |
|---|---|---|---|
| F001 | 미작성/추후 | {요구사항 원본 인용} → [FRD-F001](../FRD/FRD-F001.md) | 없음 |

---

## 별도 문서 미작성 항목 안내
> 본 프로젝트의 초기 작업 범위에서 별도 문서를 만들지 않는 항목을 명시.

- **API Spec**: {각 FRD의 §14에 인라인 / OpenAPI 별도 / 미작성}
- **UI Spec**: {UI_GUIDE.md로 대체 / 별도 / 미작성}
- **Data Spec**: {PRD 부록 D·E로 대체 / 별도 / 미작성}
- **Test Case**: {테스트 단계에서 별도 작성 / 미작성}

---

## 확장 후보 기능 (Backlog)
> 본 절은 향후 확장 후보를 추적한다. F101부터 시작(현재 기능 F001~F099, Backlog F101~).

| 기능 ID | 기능명 | 설명 | 상태 | 우선순위 | 근거 |
|---|---|---|---|---|---|
| F101 | {기능명} | {설명} | Backlog | P1 / P2 | [PRD §4 비목표](../PRD.md), {요구사항 §X} |
