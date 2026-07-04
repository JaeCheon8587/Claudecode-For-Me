---
description: requirement-spec 산출물 이후 작업 규모를 판단해 후속 스킬 파이프라인을 설계하고, 승인 후 build/progress 문서 기반으로 실행한다.
argument-hint: "<requirement-path> [--app <APP>] [--name <slug>] [--resume]"
---

$ARGUMENTS 인자로 pipeline-runner 스킬을 실행하라.

`skills/pipeline-runner/SKILL.md` 파일을 읽고 그 안의 지침을 그대로 따라 수행하라.

- 기본 입력은 `.requirements/requirement-{slug}.md` 같은 requirement-spec 산출물이다.
- 신규 실행은 `.process/pipeline-<slug>/pipeline-build.md`와 `pipeline-progress.md`를 만들고 `Approval: pending`에서 멈춘다.
- 사용자 승인 전에는 `task-write`, `ssot-write`, `work-packet-write`, `forge-scope`, `ddr-loop`, `branch-review`를 실행하지 않는다.
- 승인 후에는 각 단계의 `SKILL.md`를 읽고 현재 세션에서 인라인 수행한다.
- `--resume`은 `pipeline-progress.md`를 읽어 `done`이 아닌 첫 단계부터 재개한다.

절대 금지:
- build/progress 문서 없이 후속 스킬을 실행하지 않는다.
- `ssot-write`가 포함된 파이프라인에서 `work-packet-write`를 임의 생략하지 않는다.
