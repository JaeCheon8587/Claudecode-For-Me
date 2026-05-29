---
description: 첨부 문서가 코드 변경점에 반영됐는지 Codex 위임으로 검증 (Missing/Improve/Overengineered/Conformance%)
argument-hint: "<doc-path> [추가 doc-path...] [--wait|--background] [--scope working-tree|branch] [--base <ref>] [--model <name>] [--effort <level>] [--no-auto-context]"
---

$ARGUMENTS 인자로 doc-driven-review 스킬을 실행하라.

`skills/doc-driven-review/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

- 첫 doc 경로 인자 비어있으면 "문서 경로 필수" 안내 후 종료.
- `--wait` / `--background` 미명시 시 변경 규모 측정 후 AskUserQuestion 1회.
- scope 미명시 시 auto (변경 있으면 working-tree, 없으면 branch).
- Python 스크립트 stdout verbatim 노출. exit code별 한국어 안내.
- `OUTPUT-SCHEMA-VIOLATION` 라인 있더라도 가공 없이 그대로 노출.
