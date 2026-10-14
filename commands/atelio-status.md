---
allowed-tools: ToolSearch, mcp__atelio__list_action_items, mcp__atelio__get_action_item
description: atelio 액션 아이템의 상태(위키 · 진행 기록 · monday 게시)를 조회해 요약한다. 인자가 없으면 최근 아이템 목록을 보여 준다. 읽기 전용.
argument-hint: "[item_id]"
---

# atelio 상태 조회

읽기 전용이다 — 생성 · 기록 · 게시를 하지 않는다.

인자: `$ARGUMENTS` — 조회할 `item_id`. 없으면 최근 목록.

## 절차

1. **도구 로드** — `ToolSearch("select:mcp__atelio__list_action_items,mcp__atelio__get_action_item")`.
   도구가 하나도 로드되지 않으면 atelio MCP 서버가 등록되지 않은 것이다 — 멈추고 등록 명령을 안내한다:
   `claude mcp add --transport http --scope user atelio https://atelio.site/mcp/mcp` (등록 후 새 세션).
2. **`item_id` 가 없으면** `list_action_items(limit=10)` 을 표로 보여 주고 끝낸다: `id` · 제목 · 프로젝트 · 모듈 · 우선순위.
3. **`item_id` 가 있으면** `get_action_item` 을 아래 양식으로 요약한다. 값이 없는 칸은 `-`. 응답에 없는 값을 지어내지 않는다.

## 양식

```
## #<id> <제목>
- 프로젝트 / 모듈: <프로젝트> / <모듈>
- 우선순위 · 일정: <priority> · <plan_start> ~ <plan_end>
- 위키: <wiki_status>
- 진행 기록: <N>건 — 최근 <날짜>: <첫 항목 한 줄>
- monday: <상태> · <번호> · <URL>
```
