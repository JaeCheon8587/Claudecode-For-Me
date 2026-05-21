# {App}-ADR-CATALOG — {App명} ADR Catalog

> ⚠ **TEMPLATE** — ADR 결정 인덱스. 본 카탈로그는 단일 App (`{App}`) 의 ADR 인덱스. 새 ADR 등재 시 [ADR 폴더](ADR/) 의 개별 파일 (`{App}-ADR-{NNN}.md`) 신규 + 본 카탈로그 행 추가 (2 곳 동기화).
> 식별자 규약은 [DOCUMENT_GUIDE §5](../DOCUMENT_GUIDE.md#5-식별자-규약) 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-ADR-CATALOG |
| 작성 가정 | ADR 본문 (개별 파일 [ADR/{App}-ADR-{NNN}.md](ADR/)) 과 1:1 동기화. 본 카탈로그가 상태/영향 범위/반영 문서 SSOT |
| 관련 문서 | [ADR 폴더](ADR/) · [{App}-PRD]({App}-PRD.md) · [{App}-FC]({App}-FC.md) · [{App}-ARCHITECTURE]({App}-ARCHITECTURE.md) · [FRD 폴더](FRD/) · [솔루션 ARCHITECTURE](../ARCHITECTURE.md) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | 초안 | {이름} |

---

## Accepted

> 채택된 결정. 영향 범위·반영 문서는 본 표가 SSOT.

| ADR | 제목 | 일자 | 영향 범위 | 영향 모듈 | 반영 문서 |
|---|---|---|---|---|---|
| [{App}-ADR-001](ADR/{App}-ADR-001.md) | {결정 제목} | YYYY-MM-DD | {영향 모듈/책임/외부 시스템. App 전체 적용 시 "전체"} | {모듈/레이어/폴더 경로} | [App PRD §X]({App}-PRD.md) · [{App}-FC]({App}-FC.md) · [{App}-FRD-{NNN}](FRD/{App}-FRD-{NNN}.md) |

## Proposed

> 제안 중. 결정 기한 명시로 Open 무한정 방지.

| ADR | 제목 | 제안 일자 | 영향 범위 | 결정 기한 | 결정 필요자 |
|---|---|---|---|---|---|
| [{App}-ADR-002](ADR/{App}-ADR-002.md) | {결정 제목} | YYYY-MM-DD | {영향 모듈/책임} | YYYY-MM-DD | {담당자 / PO / 개발 리드} |

## Deprecated / Superseded

> 폐기 또는 후속 ADR 로 교체. Deprecated 시 후속 ADR 반드시 인용.

| ADR | 제목 | Deprecated 일자 | 후속 ADR | 사유 |
|---|---|---|---|---|
| [{App}-ADR-003](ADR/{App}-ADR-003.md) | {결정 제목} | YYYY-MM-DD | [{App}-ADR-010](ADR/{App}-ADR-010.md) | {교체 사유 한 줄} |
