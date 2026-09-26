---
description: grill-me 인터뷰로 요구사항을 도출해 Intent Part 1(기능 명세)을 쓰고 Part 2(작업 지시)를 파생한 뒤, 코드 생성 체크리스트 + opus 판정 루프(최대 3회)로 검증하고 품질 지표를 남겨 사용자 승인 1회로 확정하는 스킬. "요구사항 정리해서 명세까지", "기능 명세 만들어줘", "Intent 작성", "requirement-spec" 요청 시 트리거
argument-hint: "[--app <App>] [--type 기능개발|리팩토링] [--no-gate]"
---

$ARGUMENTS 를 인자로 requirement-spec 스킬을 실행하라.

skills/requirement-spec/SKILL.md 파일을 읽고, 그 안의 지침을 그대로 따라 수행하라.

- 산출물은 `docs/<App>/INTENT/<App>-INT-<NNN>.md` **1개**다. 다른 문서·코드·브랜치를 만들지 않는다.
- Phase 5 의 사용자 승인에서 멈춘다. 승인 후에도 후속 스킬을 자동으로 실행하지 않는다.
- Phase 3 검증 루프의 임시 파일은 `.process/intent-check/<ID>/` 에만 쓴다(gitignore).
