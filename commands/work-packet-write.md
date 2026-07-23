---
description: Opus Main이 build/progress만 기준으로 Opus Builder→Opus Critic을 최대 3회 순환해 TASK와 반영된 SSOT를 연결하는 Work Packet 1개를 생성한다. Main은 본문을 읽지 않아 context를 보호한다.
argument-hint: "<TASK-path> [--app <APP>] [--process <process-dir>] [--name <title>]"
model: opus
effort: high
---

`${CLAUDE_PLUGIN_ROOT}/skills/work-packet-write/SKILL.md`를 읽고 `$ARGUMENTS`로 그대로 실행한다. 대상 repository에서 상대경로 `skills/work-packet-write/SKILL.md`를 찾으면 **절대로 안 된다.**

- 이 스킬은 `task-write → ssot-write` 이후 단계다. 입력은 ssot-write `handoff.json.actions` + TASK다.
- Main은 **무조건 Opus**이며 **완전 비대화형**이다. 상위 handoff가 불량/부재면 `BLOCKED`, 그 외 부족은 `FAILED`로 종료한다.
- Builder(Opus), Critic(Opus)을 `general-purpose` 실제 독립 에이전트로 호출한다.
- Main은 **TASK/SSOT/Work Packet/manifest/review 본문을 절대로 읽지 않는다.** 오케스트레이션은 `build.md`·`progress.md`만 보고 하고, 라우팅은 에이전트 반환 토큰으로만 한다. (context 보호)
- Agent에는 파일 내용이나 수정 힌트 없이 **무조건 `KEY=절대경로`만 전달한다.** manifest/review/handoff JSON 내부 path 값은 **REPO_ROOT 기준 상대경로**로 기록한다.
- Work Packet 파일 1개만 생성한다. TASK 링크, Required SSOT Execution Matrix, Execution Gate, 실행 규칙/경계, 검증 입력, Implementation Output Contract를 채운다.
- Builder는 `SUCCESS WP_PATH=<path>` 또는 `FAIL WP_PATH=<path>`만 반환한다.
- Critic은 `SUCCESS REVIEW_PATH=<path> WP_STATE=Ready|Draft` 또는 `FAIL REVIEW_PATH=<path>`만 반환한다. `MANIFEST_PATH`를 전달하면 **절대로 안 된다.**
- Critic의 관심사는 **오직 링킹 정확성**이다. 내용의 참·거짓을 검사하면 **절대로 안 된다.** `ROUTER-DISCIPLINE`, `LINK-COVERAGE`, `LINK-VALIDITY`, `LINK-TRACEABILITY`, `GATE-LINKAGE` 다섯 check를 수행하며 하나라도 실패하면 **무조건 FAIL**이다.
- Critic `FAIL`은 **Builder부터** REPAIR cycle을 시작하며 링킹 결함만 수정한다.
- Critic 최대 횟수는 3회이며 세 번째 FAIL은 `MANUAL_REQUIRED`(handoff 없음)다.
- 승인, git stage, git commit, resume, baseline을 사용하면 **절대로 안 된다.**
- 모든 자연어는 **반드시 한국어**로 작성한다.

절대 금지:
- TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일을 수정하지 않는다.
- Work Packet 안에 SSOT 본문을 길게 복제하지 않는다.
- `CREATE/UPDATE target path` 누락 또는 파일 미존재가 있는데 임의 링크를 만들거나 `Ready`로 쓰지 않는다.

결과 보고 형식:

```text
CREATE <docs_root>/<App>/WORK_PACKET/<App>-WP-<NNN>.md (WP_STATE: Ready | Draft)
Task: <docs_root>/<App>/TASK/<App>-TASK-<NNN>.md
Review: SUCCESS | MANUAL_REQUIRED (cycles: N)
Next: forge-scope
```
