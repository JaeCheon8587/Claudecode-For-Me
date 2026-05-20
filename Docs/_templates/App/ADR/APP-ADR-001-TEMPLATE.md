# {App}-ADR-{NNN} — {결정 제목}

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다.
> 본 파일은 단일 App (`{App}`) 의 개별 ADR 1건이다. 결과 파일명과 문서 ID는 항상 `{App}-ADR-{NNN}` 형식을 사용한다.
> 결정 인덱스/메타(상태·영향 범위·반영 문서)는 [`../{App}-ADR-CATALOG.md`](../{App}-ADR-CATALOG.md)가 SSOT. 새 ADR 추가 시 본문 + 카탈로그 2곳을 동기화한다.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-ADR-{NNN} |
| 버전 | {예: 0.1 (Draft)} |
| 상태 | Proposed / Accepted / Deprecated / Superseded |
| 작성 가정 | {이 결정 작성 시 깔린 가정} |
| 관련 문서 | [{App}-ADR-CATALOG](../{App}-ADR-CATALOG.md) · [{App}-PRD](../{App}-PRD.md) · [{App}-FC](../{App}-FC.md) · [{App}-ARCHITECTURE](../{App}-ARCHITECTURE.md) · [FRD 폴더](../FRD/) · [DOCUMENT_GUIDE](../../DOCUMENT_GUIDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

---

## ADR-{NNN}: {결정 제목 — 한 문장}

- **상태**: Proposed / Accepted / Deprecated / Superseded ({YYYY-MM-DD})
- **우선순위**: P0 / P1 / P2
- **컨텍스트**:
  - {왜 이 결정이 필요한가. 배경·문제·제약}
  - {현재 코드/문서/운영 조건}
- **결정**:
  - {무엇을 결정했는가. 구체적·검증 가능한 표현}
  - {결정 항목 N}
- **결과**:
  - {이 결정으로 가능해지는 것}
  - {제약·부채·후속 작업}
- **대안 검토**:
  - 옵션 A ({대안명}): {채택/기각 여부와 이유}
  - 옵션 B ({대안명}): {채택/기각 여부와 이유}

### 코드 인용
- `{코드 경로}:{라인}` — {근거}

### 문서 반영
- [{App}-ADR-CATALOG](../{App}-ADR-CATALOG.md) — 상태/영향 범위/반영 문서 행 추가 또는 갱신
- [{App}-PRD](../{App}-PRD.md) — {반영 절 또는 "없음"}
- [{App}-FC](../{App}-FC.md) — {반영 절 또는 "없음"}
- [{App}-FRD-{NNN}](../FRD/{App}-FRD-{NNN}.md) — {반영 절 또는 "없음"}

> TASK 인용 X (v0.7 룰 — 영구 SSOT 는 휘발성 TASK 를 인용하지 않는다). TASK 가 본 ADR 결정을 영향받으면 TASK §6 영향 표에 본 ADR 이름을 텍스트로 명시한다.
