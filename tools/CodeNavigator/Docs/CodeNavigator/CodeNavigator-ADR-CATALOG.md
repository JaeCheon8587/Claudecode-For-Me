# CodeNavigator-ADR-CATALOG — CodeNavigator ADR Catalog

> ADR 결정 인덱스. 새 ADR 등재 시 [ADR 폴더](ADR/) 의 개별 파일 (`CodeNavigator-ADR-{NNN}.md`) 신규 + 본 카탈로그 행 추가 (2 곳 동기화).
> 식별자 규약은 [DOCUMENT_GUIDE §5](../DOCUMENT_GUIDE.md#5-식별자-규약) 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-ADR-CATALOG |
| 작성 가정 | ADR 본문 (개별 파일 [ADR/CodeNavigator-ADR-{NNN}.md](ADR/)) 과 1:1 동기화 |
| 관련 문서 | [ADR 폴더](ADR/) · [CodeNavigator-PRD](CodeNavigator-PRD.md) · [CodeNavigator-FC](CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](CodeNavigator-ARCHITECTURE.md) · [FRD 폴더](FRD/) · [/CLAUDE.md](../../CLAUDE.md) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | ADR-001·002 Accepted 등재 | 정재천 |

---

## Accepted

| ADR | 제목 | 일자 | 영향 범위 | 영향 모듈 | 반영 문서 |
|---|---|---|---|---|---|
| [CodeNavigator-ADR-001](ADR/CodeNavigator-ADR-001.md) | FTS5 채택 — embedding 벡터 검색 보류 | 2026-05-21 | 전체 (검색 엔진 기반) | `search.py`, `store.py` | [PRD §9](CodeNavigator-PRD.md#9-제약사항) · [FC F001](CodeNavigator-FC.md) · [FRD-001](FRD/CodeNavigator-FRD-001.md) |
| [CodeNavigator-ADR-002](ADR/CodeNavigator-ADR-002.md) | description + tags 분리 필드 채택 | 2026-05-21 | 인덱스 스키마·검색 가중치 | `store.py`, `search.py`, `indexer.py` | [PRD §9](CodeNavigator-PRD.md#9-제약사항) · [FC F001·F005](CodeNavigator-FC.md) · [FRD-001](FRD/CodeNavigator-FRD-001.md) |

## Proposed

없음.

## Deprecated / Superseded

없음.
