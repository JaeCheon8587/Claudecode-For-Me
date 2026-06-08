---
description: git pull 전 fetch(태그 포함)로 "기존 vs 풀 후" 변경·충돌·사이드이펙트 브리핑 후 컨펌받고 pull (안전 게이트)
argument-hint: "[원격/브랜치 — 미지정 시 추적 upstream 자동]"
---

$ARGUMENTS 인자(원격/브랜치)로 safe-pull 스킬을 실행하라.

skills/safe-pull/SKILL.md 파일을 읽고, 그 안의 지침을 그대로 따라 수행하라.

- 인자 없으면 현재 브랜치의 추적 upstream(`@{u}`)을 대상으로 사용.
- 인자 있으면 해당 원격/브랜치를 fetch·비교 대상으로 사용 (upstream 미설정 시 explicit-target 경로).
- Step 0 안전 게이트(detached HEAD·no-remote·no-upstream·dirty)에 걸리면 원인·해결책 설명 후 중단.
- fetch는 비파괴이므로 컨펌 전 실행. pull/merge는 Step 6 AskUserQuestion 컨펌 뒤에만 (Step 7).
