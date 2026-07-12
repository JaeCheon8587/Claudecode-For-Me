# ssot-write 서브에이전트 진행 상황 — 생성 호환 뷰

- 계약 버전: 8
- 원본: `state.json`, `events.jsonl`, artifact registry reducer
- 소유자: 결정적 runner
- 직접 편집: 금지

렌더링된 인스턴스는 thinker/critic/runner apply/commit 수명주기, 종료 결과,
변경 경로와 검증 결과를 표시한다. 역할은 엄격한 artifact JSON으로만 통신하고
이 뷰를 직접 갱신하지 않는다.
