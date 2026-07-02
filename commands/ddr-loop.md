---
description: doc-driven 수렴 루프. forge 워크트리 브랜치(feat-<slug>) 변경점을 명시 docs와 codex로 대조해 일치율을 매기고, 미달분을 세션이 워크트리 안에서 인라인 수정·재검(최대 3회, 99% 정지). reviewer=codex / fixer=세션. 빌드는 대상 프로젝트(.csproj)만, 솔루션 금지. 정리는 forge-cancel.
argument-hint: "<slug> [--docs <doc...>] [--base <ref>] — --docs 생략 시 forge-scope Work Packet에서 자동 구성, slug 생략 시 목록 선택"
---
먼저 skills/ddr-loop/SKILL.md 파일을 읽고, 해당 스킬의 지침을 수행하라.

인자: $ARGUMENTS
