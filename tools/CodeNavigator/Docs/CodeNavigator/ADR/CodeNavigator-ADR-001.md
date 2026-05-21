# CodeNavigator-ADR-001 — FTS5 채택 — embedding 벡터 검색 보류

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-ADR-001 |
| 버전 | 0.1 |
| 상태 | Accepted |
| 작성 가정 | MVP 단계. AI 코딩 에이전트가 소비하는 도구. SQLite 표준 탑재, Python 추가 의존 최소화. |
| 관련 문서 | [CodeNavigator-ADR-CATALOG](../CodeNavigator-ADR-CATALOG.md) · [CodeNavigator-PRD](../CodeNavigator-PRD.md) · [CodeNavigator-FC](../CodeNavigator-FC.md) · [CodeNavigator-ARCHITECTURE](../CodeNavigator-ARCHITECTURE.md) · [FRD 폴더](../FRD/) |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 | 정재천 |

---

## ADR-001: FTS5 채택 — embedding 벡터 검색 MVP 보류

- **상태**: Accepted (2026-05-21)
- **우선순위**: P0
- **컨텍스트**:
  - AI 코딩 에이전트가 C# 클래스를 자연어 키워드로 검색할 수 있어야 한다.
  - 검색 엔진으로 SQLite FTS5(BM25 기반 텍스트 검색)와 embedding 벡터 검색(코사인 유사도) 두 옵션이 존재.
  - MVP 단계에서는 외부 ML 라이브러리 없이 SQLite 표준 기능만으로 구동 가능한 방식이 요구됨.
- **결정**:
  - **FTS5 채택**: SQLite FTS5 `unicode61` tokenizer + Python 레이어 CJK bigram 전처리 조합.
  - BM25 점수 + tag-hit 가중치(2.0/개)로 최종 점수 산출.
  - embedding 모델 호출·벡터 저장·유사도 계산은 MVP 범위 외로 보류.
- **결과**:
  - Python stdlib SQLite 만으로 구동 — 외부 ML 의존 없음.
  - 한국어 부분 일치는 bigram 인덱스(`bigram` FTS5 컬럼)로 처리.
  - embedding 재정렬(rerank) 은 Backlog(F101)로 이연.
  - 의미적 유사도 매칭(동의어·개념 근접) 은 FTS5 로 불가 — 이 한계는 수용.
- **대안 검토**:
  - 옵션 A (FTS5): **채택**. 외부 의존 없음, SQLite 내장, BM25 적합. 한국어 bigram 으로 부분 일치 보완.
  - 옵션 B (embedding + pgvector/sqlite-vec): 기각. MVP 단계에서 ML 모델·벡터 DB 의존 과다. Backlog 이연.
  - 옵션 C (Elasticsearch/OpenSearch): 기각. 별도 인프라 필요, 코딩 에이전트 로컬 환경 부적합.

### 문서 반영
- [CodeNavigator-ADR-CATALOG](../CodeNavigator-ADR-CATALOG.md) — Accepted 행 추가
- [CodeNavigator-PRD](../CodeNavigator-PRD.md) — §9 제약사항 인용
- [CodeNavigator-FC](../CodeNavigator-FC.md) — F001 검색 기능 근거
- [CodeNavigator-FRD-001](../FRD/CodeNavigator-FRD-001.md) — §9 인용
