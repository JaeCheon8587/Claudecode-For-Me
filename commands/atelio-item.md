---
allowed-tools: ToolSearch, AskUserQuestion, mcp__atelio__list_projects, mcp__atelio__list_modules, mcp__atelio__create_action_item, mcp__atelio__get_action_item
description: 대화 맥락에서 제목과 개발 요구사항을 정리해, 사용자 승인 후 atelio 액션 아이템을 생성한다. 사용자가 직접 호출할 때만 쓴다.
argument-hint: "[제목]"
---

# atelio 액션 아이템 생성

대화 맥락에서 액션 아이템의 제목과 개발 요구사항을 정리하고, **사용자가 승인하면** atelio 에 생성한다.

인자: `$ARGUMENTS` — 있으면 제목으로 쓴다. 없으면 대화에서 제목을 정한다.

## 절차

1. **도구 로드** — `ToolSearch("select:mcp__atelio__list_projects,mcp__atelio__list_modules,mcp__atelio__create_action_item,mcp__atelio__get_action_item")`.
   도구가 하나도 로드되지 않으면 atelio MCP 서버가 등록되지 않은 것이다 — 멈추고 등록 명령을 안내한다:
   `claude mcp add --transport http --scope user atelio https://atelio.site/mcp/mcp` (등록 후 새 세션).
2. **프로젝트 · 모듈 확정** — id 를 추측하지 않는다.
   - `list_projects` 로 조회해 `AskUserQuestion` 으로 고르게 한다.
   - `list_modules(project_id)` 로 조회해 고르게 한다. 하위 모듈(레벨2)은 `상위 / 하위` 로 보여 준다. `모듈 없음` 도 선택지에 둔다.
   - 맞는 모듈이 없으면 만들지 않고 알린다 — 모듈 생성은 이 커맨드의 일이 아니다.
3. **초안 작성**
   - **제목** — 한 줄, 기능 단위 명사구.
   - **requirements** — 배경(왜) → 요구사항(무엇을, 항목별) → 완료 조건 순서의 마크다운. 대화에서 확인된 것만 쓰고, 정해지지 않은 것은 `미정` 으로 남긴다.
   - **priority**(`urgent` · `high` · `normal` · `low`), **plan_start · plan_end**(`YYYY-MM-DD`) — 대화에 근거가 있을 때만 채우고 아니면 비운다.
4. **승인** — 프로젝트 · 모듈 · 제목 · 우선순위 · 일정 · requirements 전체를 보여 주고 `AskUserQuestion` 으로 묻는다: `생성` / `수정` / `취소`.
   **승인 없이 `create_action_item` 을 호출하지 않는다.**
5. **생성** — `create_action_item`. 반환된 `item_id` 를 보고한다.
6. **상태 확인** — 위키 문서는 백그라운드 잡이 만든다. `get_action_item` 으로 `wiki_status` 를 한 번 확인해 그대로 보고한다. 아직이면 "위키 생성 대기" 로 보고하고 기다리지 않는다.
