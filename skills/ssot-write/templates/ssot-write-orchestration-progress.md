# ssot-write 메인 오케스트레이션 진행 상황 — 생성 뷰

- 계약 버전: 8
- 원본: `state.json`과 `events.jsonl`
- 소유자: 결정적 runner
- 직접 편집: 금지

렌더링된 인스턴스는 제어 상태, 실제 격리 role/mode, 재시도 횟수, 차단 질문과
append-only 이벤트를 표시한다. `next`, `accept-artifact`, `resolve`, `render`가
이 뷰를 갱신한다. 메인은 Markdown을 파싱하지 않고 runner JSON을 사용한다.
