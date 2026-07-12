# ssot-write 메인 오케스트레이션 빌드 — 생성 뷰

- 계약 버전: 8
- 원본: `state.json`
- 소유자: 결정적 runner
- 직접 편집: 금지. `python <runner> render --process <process>`가 재생성한다.

## Dispatch 계획

| 단계 | 소유자 | 전이 권한 |
|---|---|---|
| source | runner | TASK 사실·권위 그래프·문서 색인·증거/후보 목록 생성 |
| authority-review | fresh Opus critic | 모든 Authority 후보와 governance 판정 |
| think | Opus thinker | 하나의 6종 ClaimSpec 제안 |
| change-review | fresh Opus critic | staging 전 제안과 미리보기 반증 |
| apply/check | runner | 승인 변경 재현, 관계·helper·ADR·hash 검증 |
| outcome-review | fresh Opus critic | 전체 staging 결과 반증 |
| commit/finalize | runner | journal 기반 commit/rollback과 한국어 `final-report.txt` 생성 |

렌더링된 인스턴스는 입력, 정확한 단계 상태, artifact registry와 runner 승인
작업 행렬을 표시한다. 메인과 서브에이전트는 이를 덮어쓰거나 초기화하지 않는다.
