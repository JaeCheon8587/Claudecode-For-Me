# docs-add-frd

신규 기능 FRD + ARD 작성, App-PRD §3.1/§7 갱신, FC 5표 행 추가, ARD-CATALOG Proposed 행 추가.

v0.7 per-App SSOT 체계 (`Docs/_templates/App/` 양식). Legacy (`FRD-<CODE>-F<NNN>.md` 등) 미지원. source repo in-place 수정 (preview 없음).

## 사용

```text
/docs-add-frd 주문 검색 기능 추가, 운영자가 status·createdAt 으로 필터링
/docs-add-frd <기능 요청 자연어>
```

## Instructions

1. `skills/docs-add-frd/SKILL.md` Phase 0~11 따름.
2. App 결정 → 입력 수집 (필수만 질문) → 번호 할당 → 컨텐츠 준비 → 사전 확정 (`AskUserQuestion`) → in-place 쓰기 → 자기 검증 → 결과 보고.
3. 모든 작성 전 사용자 확정 1회 필수.
4. ARD 항상 동반 생성. 결정 없을 시 본문 placeholder 자동.
5. TASK 인용 금지 (v0.7 룰).
6. Cross-cutting 영향 감지 시 경고만 (솔루션 PRD/ARCHITECTURE 자동 수정 안 함).

## 기본 동작

- App 1개 = 자동 채택. 다수 = `AskUserQuestion`.
- 필수 부족 = `name` / `summary` / `purpose` / `actor` / `work_type` 묻기.
- 선택 = "미작성/추후" 또는 "없음" 자동 채움.
- Backlog (F101~) = 사용자가 "backlog" / "확장 후보" 명시 시.

## 비범위

- Legacy 호환 X (v0.7 전용)
- TASK 생성 X (별도 `/docs-add-task`)
- 솔루션 PRD / 솔루션 ARCHITECTURE 자동 수정 X
- App 부트스트랩 X (별도 절차)
