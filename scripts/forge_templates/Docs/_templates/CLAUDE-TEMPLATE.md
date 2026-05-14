# 프로젝트: {프로젝트명} ({SYSTEM_CODE})

> ⚠ **TEMPLATE** — 모든 `{...}` placeholder를 실제 값으로 채우거나 해당 줄을 삭제한다. 본 파일은 레포 루트(`/CLAUDE.md`)에 배치한다.
> 작성 규칙은 [DOCUMENT_GUIDE.md](../DOCUMENT_GUIDE.md), 식별자 규약은 [ADR-0008](../ADR.md#adr-0008-문서-식별자명명-규약) 참조.

> {프로젝트 한 줄 요약 — 무엇을 하는 시스템인가}. **모든 설계·결정·기능 명세는 아래 문서들이 단일 진실 공급원(SSOT)**. 코드 작성 전 관련 문서를 직접 읽어 최신 정합성을 확보한다.

## 설계 문서 인덱스

| 영역 | 경로 | 역할 |
|---|---|---|
| **메타 가이드** | [`Docs/DOCUMENT_GUIDE.md`](Docs/DOCUMENT_GUIDE.md) | 문서 양식·SSOT 원칙·인용 패턴·식별자 규약·이식 부트스트랩 단계 |
| **빈 템플릿** | [`Docs/_templates/`](Docs/_templates/) | PRD/FC/FRD/ADR/UI_GUIDE/ARCHITECTURE/CLAUDE/README 빈 양식 8종 |
| 아키텍처 단일 SSOT | [`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md) | {레이어 모델·참조 매트릭스·폴더→레이어 매핑·호스트 책임} |
| 제품 요구사항 | [`Docs/PRD.md`](Docs/PRD.md) | 배경·목표·범위·시나리오 + 부록 A(매핑)·B(에러코드)·C(상태머신)·D(도메인모델)·E(DTO) |
| 기능 레지스트리 | [`Docs/Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md`](Docs/Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md) | F001~F0{NN} 현재 + F101~ Backlog |
| 기능별 상세 | [`Docs/FRD/`](Docs/FRD/) | {각 FRD의 한 줄 요약 — F001 ~ / F002 ~ / ...} |
| 결정 이력 | [`Docs/ADR.md`](Docs/ADR.md) | ADR-0001~ADR-0{NNN} 결정 누적 |
| UX 가이드 | [`Docs/UI_GUIDE.md`](Docs/UI_GUIDE.md) | {인터페이스 종류 — 콘솔/GUI/Web 등} 출력 포맷·흐름·검증 |
| {Forge/CI 자동화} | {경로 또는 "해당 없음"} | {도구 역할 한 줄} |

## 진입 순서

- 본 레포 작업 패턴이 처음이면 [`Docs/DOCUMENT_GUIDE.md`](Docs/DOCUMENT_GUIDE.md)를 먼저 읽는다 (양식·SSOT 원칙·식별자 규약).
- 코드 작성 전 [`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md)의 절대 금지 매트릭스를 확인.
- 신규 기능은 [PRD](Docs/PRD.md) → [Feature Catalog](Docs/Feature_Catalog/FC-{SYSTEM_CODE}-{NNN}.md) → [FRD](Docs/FRD/) → 테스트 → 구현 순서로 Docs를 먼저 갱신·작성한 후 코드 작성.

## 행동 지침

@Docs/BEHAVIORAL_GUIDELINES.md

## 절대 변경 금지

- `Docs/**` — 사용자 승인 전 수정 금지.
- `CLAUDE.md`(본 파일), `MEMORY.md` — 사용자 승인 전 수정 금지.
- {`README.md`, CI 설정, Forge 도구 등 도메인별 보존 항목}.
