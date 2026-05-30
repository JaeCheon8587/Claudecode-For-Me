# ADR — {프로젝트명} 결정 이력

> ⚠ **TEMPLATE** — 본 파일은 결정을 누적하는 단일 파일이다. 새 결정은 가장 아래에 ADR-NNNN 절로 추가한다.
> 양식은 [DOCUMENT_GUIDE.md](DOCUMENT_GUIDE.md), 식별자 규약은 [ADR-0008](#adr-0008-문서-식별자명명-규약) 참조.

| 항목 | 값 |
|---|---|
| 문서 ID | ADR (단일 파일 누적식) |
| 작성 가정 | 표준 ADR 7항목 형식(식별자/제목/상태/컨텍스트/결정/결과/대안 검토) 사용 |
| 관련 문서 | [PRD](PRD.md) · [Feature Catalog](Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md) · [ARCHITECTURE](ARCHITECTURE.md) |

> **ARCHITECTURE.md와의 관계**: 솔루션 단위의 아키텍처 규칙은 [ARCHITECTURE.md](ARCHITECTURE.md)가 단일 SSOT. 본 ADR은 그 위 또는 그와 무관한 결정을 누적한다. ARCHITECTURE.md에 이미 기술된 결정도 후행 등재 가능하나, 본문은 ARCHITECTURE.md를 정합성 기준으로 인용한다.

---

## ADR-{NNNN}: {결정 제목 — 한 문장}

- **상태**: {Proposed / Accepted / Deprecated / Superseded by ADR-NNNN} ({YYYY-MM-DD})
- **컨텍스트**: {왜 이 결정이 필요했는가. 배경·제약·대안의 부재 등}
- **결정**: {무엇을 결정했는가. 구체적·검증 가능한 표현}
  - {결정 항목 1}
  - {결정 항목 N}
- **결과**: {결정으로 인해 무엇이 가능/불가능해졌는가. 후속 영향}
- **대안 검토**: {고려했지만 채택 안 한 안과 그 이유}
  - {대안 1}: {기각 사유}
  - {대안 2}: {기각 사유}
