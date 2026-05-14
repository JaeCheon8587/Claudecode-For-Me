---
description: HEAD ↔ 고정점(ref) diff을 Standards/Spec 2축으로 병렬 검토 (심각도 등급, 충돌 감지, 다언어 지원)
argument-hint: "[ref — 미지정 시 merge-base 자동]"
---

$ARGUMENTS 인자(고정점 ref)로 branch-review 스킬을 실행하라.

skills/branch-review/SKILL.md 파일을 읽고, 그 안의 지침을 그대로 따라 수행하라.

- 인자 없으면 SKILL.md Step 1의 자동 추정(`merge-base origin/main HEAD` 등) 사용.
- 인자 있으면 해당 ref를 고정점으로 사용.
- diff 크기에 따라 인라인/표준 병렬/청크 분할 모드 자동 선택 (Step 2).
- 결과는 Step 6 포맷으로 보고.
