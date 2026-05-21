# CodeNavigator-ADR-002 — description + tags 분리 필드 채택

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-ADR-002 |
| 버전 | 0.1 |
| 상태 | Accepted |
| 작성 가정 | FTS5 인덱스 스키마 설계 시점. 검색 정확도와 AI 생성 비용의 균형 고려. |
| 관련 문서 | [CodeNavigator-ADR-CATALOG](../CodeNavigator-ADR-CATALOG.md) · [CodeNavigator-PRD](../CodeNavigator-PRD.md) · [CodeNavigator-FC](../CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](../CodeNavigator-ARCHITECTURE.md) · [FRD 폴더](../FRD/) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## ADR-002: description + tags 분리 필드 채택

- **상태**: Accepted (2026-05-21)
- **우선순위**: P0
- **컨텍스트**:
  - AI 가 생성하는 클래스 메타데이터를 FTS5 인덱스에 저장하는 방식 결정 필요.
  - 옵션 1: 단일 `description` 텍스트만 저장.
  - 옵션 2: 자연어 `description` + 키워드 `tags` 분리 저장 후 각기 다른 FTS5 컬럼 가중치 적용.
  - BM25 에서 컬럼 가중치를 달리 적용하면 단순 키워드 매칭 시 tags 컬럼을 우선시할 수 있음.
- **결정**:
  - `description` (자연어 문장, 한국어 선호) 과 `tags` (3~8개 키워드 list) 를 분리 필드로 저장.
  - `tags_json` (JSON array) 으로 원본 보존, `tags` (space-joined) 로 FTS5 인덱싱.
  - FTS5 bm25 컬럼 가중치: `class_name=3.0, namespace=2.0, description=1.0, tags=2.0, bigram=1.5`.
  - 검색 시 tag-hit bonus: 쿼리 term 이 tags 에 존재할 때 마다 +2.0 추가 (BM25 재정렬 후 적용).
- **결과**:
  - 정확 키워드 매칭(tags) 과 문맥 매칭(description) 을 독립적으로 가중 가능.
  - AI 에게 두 필드를 구분해서 요청해야 하므로 SKILL.md 프롬프트가 두 키를 명시해야 함.
  - `tags` 단독 필드 → PascalCase 분해 단어도 기본 태그로 사전 삽입 가능 (AI call 없이도 동작).
- **대안 검토**:
  - 옵션 A (description 단일 필드): 기각. 키워드 가중치 구분 불가. 정확 매칭 precision 낮음.
  - 옵션 B (description + tags 분리, 본 결정): **채택**. 이중 인덱싱으로 precision/recall 균형.
  - 옵션 C (description + tags + synonyms 3 분리): 기각. MVP 범위 초과. synonyms 는 Backlog.

### 문서 반영
- [CodeNavigator-ADR-CATALOG](../CodeNavigator-ADR-CATALOG.md) — Accepted 행 추가
- [CodeNavigator-PRD](../CodeNavigator-PRD.md) — §9 제약사항 인용
- [CodeNavigator-FC](../CodeNavigator-FC.md) — F001·F005 근거
- [CodeNavigator-FRD-001](../FRD/CodeNavigator-FRD-001.md) — §8 상세 기능 요구사항 인용
