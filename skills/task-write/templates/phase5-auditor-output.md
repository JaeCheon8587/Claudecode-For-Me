# task-write Phase 5 Audit

Result: PASS | FAIL

Result rule:
- Use `Result: PASS` only when every Checklist item is PASS.
- Use `Result: FAIL` if any Checklist item is FAIL.
- If a read-only subagent cannot run at all, the main agent reports `Audit: AUDIT_BLOCKED - read-only subagent unavailable` instead of using this output template.

## Checklist

- PASS | FAIL: TASK 파일 외 문서를 수정하지 않았다.
- PASS | FAIL: FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 를 생성·수정·upsert 하지 않았다.
- PASS | FAIL: FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 같은 영구 SSOT 문서를 분석하지 않았다.
- PASS | FAIL: FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE 갱신 후보 목록을 작성하지 않았다.
- PASS | FAIL: §6 이 "영구 SSOT 갱신 여부"가 아니라 "입력 근거"다.
- PASS | FAIL: §9.2 엣지 케이스와 §9.3 오류 처리가 존재한다.
- PASS | FAIL: §7/§11은 실제 항목이 없으면 절 전체가 없다.
- PASS | FAIL: 미치환 `{...}` placeholder 와 `TEMPLATE` 경고가 없다.
- PASS | FAIL: TASK 본문에 영구 SSOT 마크다운 링크가 없다.

## Required Fixes

Rules:
- List only TASK file fixes.
- Do not list SSOT candidates, SSOT change suggestions, or Work Packet candidates.

Fixes:
- <FAIL 항목별로 TASK 파일에 필요한 보강만 작성. 없으면 "없음">

## Evidence

- TASK file checked: <path>
- Requirement reference checked: <path or "none">
- Changed files observed: <git status/diff 요약>
- Helper/conformance result: <실행했으면 요약, 생략했으면 사유>

## Scope Guard

- Auditor read only TASK and requirement reference.
- Auditor did not read FRD/FC/ADR/ADR-CATALOG/PRD/ARCHITECTURE files.
- Auditor did not edit files.
