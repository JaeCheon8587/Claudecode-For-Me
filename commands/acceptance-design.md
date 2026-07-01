---
description: 타겟 문서 기준 완료조건·검증방법 중심(lite) 또는 완료조건·엣지케이스·오류케이스·검증방법 4축(full)을 같이 설계
argument-hint: "[--lite|--full] <doc-path>"
---

$ARGUMENTS 인자로 acceptance-design 스킬을 실행하라.

`skills/acceptance-design/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

- doc 경로 인자 비어있으면 "문서 경로 필수" 안내 후 종료.
- 타겟 doc는 Read로 1회만 읽고 ground truth로 삼는다.
- 모든 질문은 AskUserQuestion으로 1문1답. 텍스트 질문 금지.
- 확정 시 `.requirements/{slug}-acceptance.md`에 저장 후 경로 한 줄 보고.
