# 프로젝트: 주문 처리 시스템 (Order Managing System, OMS)

> 클라이언트와 서비스를 분리한 학습용 토이 프로젝트. **모든 설계·결정·기능 명세는 아래 문서들이 단일 진실 공급원(SSOT)**. 코드 작성 전 관련 문서를 직접 읽어 최신 정합성을 확보한다.

## 설계 문서 인덱스

| 영역 | 경로 | 역할 |
|---|---|---|
| **메타 가이드** | [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md) | 문서 양식·SSOT 원칙·인용 패턴·식별자 규약·이식 부트스트랩 단계 |
| **빈 템플릿** | [`docs/.templates/`](docs/.templates/) | PRD/FC/FRD/ADR/UI_GUIDE/ARCHITECTURE/CLAUDE/README 빈 양식 8종 (새 프로젝트 복사 시작점) |
| 아키텍처 단일 SSOT | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | DDD 5-레이어·참조 매트릭스·폴더→레이어 매핑·호스트 2종 책임 |
| 제품 요구사항 | [`docs/PRD.md`](docs/PRD.md) | 배경·목표·범위·시나리오 + 부록 A(매핑)·B(에러코드)·C(상태머신)·D(도메인모델)·E(DTO) |
| 기능 레지스트리 | [`docs/Feature_Catalog/FC-OMS-001.md`](docs/Feature_Catalog/FC-OMS-001.md) | F001~F007 현재 + F101~F106 Backlog |
| 기능별 상세 | [`docs/FRD/`](docs/FRD/) | F001 초기화·조회 / F002 생성 / F003 조회 / F004 결제 / F005 취소 / F006 목록 조회·필터링 / F007 수정 |
| 결정 이력 | [`docs/ADR.md`](docs/ADR.md) | ADR-0001~0008 결정 누적 (0008=명명·식별자 규약) |
| 콘솔 UX | [`docs/UI_GUIDE.md`](docs/UI_GUIDE.md) | 출력 포맷·6개 흐름 자동 실행·검증 diff |
| Forge 자동화 | [`PHASE_SCHEMA.md`](PHASE_SCHEMA.md) | `scripts/forge_full.py` phase 단계 실행기 |

## 진입 순서

- 본 레포 작업 패턴이 처음이면 [`docs/DOCUMENT_GUIDE.md`](docs/DOCUMENT_GUIDE.md)를 먼저 읽는다 (양식·SSOT 원칙·식별자 규약).
- 코드 작성 전 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §6.1 절대 금지 매트릭스를 확인.
- 신규 기능은 [PRD](docs/PRD.md) → [Feature Catalog](docs/Feature_Catalog/FC-OMS-001.md) → [FRD](docs/FRD/) → 테스트 → 구현 순서로 docs를 먼저 갱신·작성한 후 코드 작성.

## 행동 지침

@docs/.rules/BEHAVIORAL_GUIDELINES_RULES.md

## 절대 변경 금지

- `docs/**` — 사용자 승인 전 수정 금지.
- `PHASE_SCHEMA.md`, `scripts/**` — Forge 자동화 도구.
- `CLAUDE.md`(본 파일), `MEMORY.md` — 사용자 승인 전 수정 금지.
