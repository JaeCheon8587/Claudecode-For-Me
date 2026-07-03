---
description: HEAD ↔ 고정점(ref) diff을 bugs/style/spec/perf 4 dimension 병렬 finder로 검토 (심각도 등급, 충돌 감지, 다언어 지원, .process/.review 영속화, --resume)
argument-hint: "[ref — 미지정 시 merge-base 자동] [--resume]"
---

$ARGUMENTS 인자(고정점 ref, `--resume`)로 branch-review 스킬을 실행하라.

skills/branch-review/SKILL.md 파일을 읽고, 그 안의 지침을 그대로 따라 수행하라.

- Step 0에서 인자 파싱 + slug(HEAD short-sha) 결정 + `.process/branch-review-<slug>/` 신규/재개 판정.
- `--resume` 있으면 기존 progress.md를 읽어 미완 단계·청크부터 재개(완료된 청크는 재실행 없이 재사용).
- 인자 없으면 SKILL.md Step 1의 자동 추정(`merge-base origin/main HEAD` 등) 사용.
- diff 크기에 따라 인라인/표준 4-finder 병렬/청크 분할 모드 자동 선택 (Step 2).
- 표준·청크 모드에서는 bugs/style/spec/perf 4개 서브에이전트를 동일 메시지에서 동시 호출, 각 프롬프트는 `skills/branch-review/templates/*-finder.md`를 치환해 사용 (Step 4).
- 결과는 Step 6 포맷(4섹션 verbatim + Summary + Recommendation)으로 보고하고 `.review/branch-review-<slug>.md`에 저장.
