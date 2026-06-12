# docs-add-task

기존 기능 수정/개선/refactor TASK + ADR 작성, AI 가 FC 보고 영향 FRD 다수 자동 식별 후 변경 이력 + 영향 section 갱신, FC 행 상태 갱신, ADR-CATALOG Proposed 행 추가.

v0.7 per-App SSOT 체계. TASK 는 휘발성 + self-contained. 외부 SSOT 인용 금지 (양방향). source repo in-place 수정.

## 사용

```text
/docs-add-task 주문 검색 기능 추가, 운영자가 status·createdAt 으로 필터링
/docs-add-task 주문 검색에 cursor 페이지네이션 추가
/docs-add-task <신규 기능 또는 수정/개선/refactor 자연어>
/docs-add-task 주문 검색 기능 추가 --no-verify          # 검증-fix 루프 생략
```

## Instructions

1. `skills/docs-add-task/SKILL.md` Phase 0~13 따름.
2. App 결정 → 입력 수집 → **AI 가 FC 파싱 영향 FRD 식별 + 모드 자동 판정(NEW/CHANGE)** → 사용자 확인 → 번호 할당 → 컨텐츠 준비 → 사전 확정 → in-place 쓰기 → 검증-fix 루프 → 결과 보고.
3. TASK 본문에 영구 SSOT 마크다운 링크 절대 금지 (v0.7 양방향 룰).
4. ADR 항상 동반 생성. 결정 narrative AI 추론.
5. 영향 FRD 본문 자동 부분 갱신 (변경 이력 + 영향 section). TASK ID 인용 X.
6. 호스트 영향 (refactor/migration) 감지 시 APP-ARCHITECTURE 검토 권고만.
7. Phase 12 = Codex 2축 검증-fix 루프 (기본 ON, max 3·임계 99%). `--no-verify` 스킵, codex 미설치 시 구조 check 폴백.

## 작업 유형 (work_type)

- `refactor` — 코드 구조 개선
- `maintenance` — 의존성/운영 갱신
- `migration` — 데이터/시스템 이전
- `setup` — 초기 환경 구성
- `investigation` — 분석/조사
- `feature` — 기존 기능 확장
- `변경` / `버그수정` — 기능 변경 / 버그픽스

신규 기능/기존 수정 자동 판정 — 신규는 FRD 생성(NEW 모드), 기존은 영향 FRD 갱신(CHANGE 모드). 둘 다 TASK + ADR 동반.

## 비범위

- Legacy 호환 X (v0.7 전용)
- TASK 완료 후 삭제 X (사용자 수동)
- 솔루션 PRD / 솔루션 ARCHITECTURE 자동 수정 X
