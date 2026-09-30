# {App}-INT-CATALOG — {App명} Intent Catalog

> ⚠ **TEMPLATE** — 이 파일은 **참고용 예시**다. 실제 `docs/{App}/{App}-INT-CATALOG.md` 는 손으로 만들지 않는다 — `python scripts/docs_helpers.py intent-catalog --repo . --app {App} --write` 가 `INTENT/` 폴더를 훑어 생성한다.
>
> ADR-CATALOG 와 성격이 다르다. ADR-CATALOG 는 `영향 범위`·`반영 문서` 처럼 ADR 본문에 없는 값을 들고 있는 **수기 SSOT** 지만, INT-CATALOG 의 모든 열은 Intent 문서의 메타 표·H1·Outcome·항목 수에서 **파생**된다. 고유 정보가 0 이므로 손으로 고치면 아래 `## 재생성 시점` 의 **4 곳**(Phase 5 진입 · `draft`→`approved` · `approved`→`in-dev` · `in-dev`→`in-review`)에서 반드시 어긋난다.
>
> 값을 바꾸려면 **해당 Intent 문서를 고치고 재생성**한다. `docs_helpers.py check --app {App}` 이 불일치를 `INT_CATALOG` FAIL 로 잡는다.
>
> 식별자 규약은 [DOCUMENT_GUIDE §5](../DOCUMENT_GUIDE.md#5-식별자-규약) 참조.

## 생성 결과 예시

아래가 생성기가 내는 형태다. 열의 출처는 각각 이렇다.

| 열 | 출처 |
|---|---|
| Intent | 메타 `문서 ID` + 파일 경로 링크 |
| 제목 | H1 에서 `{App}-INT-{NNN} — ` 접두를 뗀 나머지 |
| 유형 | 메타 `유형` |
| 상태 | 메타 `상태` |
| 검증 | 메타 `검증` 축약 (`PASS — code PASS · llm PASS · 2/3` → `PASS 2/3`) |
| 요약 | `### Outcome` 첫 실질 줄 (주석·`Out of scope` 제외, 50자 컷) |
| 규모 | `Functional requirements` · `Acceptance` 항목 수 |

값을 못 읽으면 `?` 가 들어간다 — 그 Intent 의 메타 표가 깨진 것이므로 `check-intent` 로 확인한다.

```markdown
# {App}-INT-CATALOG — {App} Intent Catalog

> **생성물** — `docs_helpers.py intent-catalog --repo . --app {App} --write` 가 `INTENT/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — 값을 바꾸려면 해당 Intent 문서를 고치고 재생성한다. `check --app {App}` 이 불일치를 FAIL 로 잡는다.

| 항목 | 값 |
|---|---|
| 문서 ID | {App}-INT-CATALOG |
| 생성 | docs_helpers.py intent-catalog |
| 대상 | [INTENT 폴더](INTENT/) |

| Intent | 제목 | 유형 | 상태 | 검증 | 요약 | 규모 |
|---|---|---|---|---|---|---|
| [{App}-INT-001](INTENT/{App}-INT-001.md) | 워크트리 base 브랜치 선택 | 기능개발 | in-dev | PASS 2/3 | init 시 base 브랜치를 고를 수 있다 | FR 5 · A 4 |
| [{App}-INT-002](INTENT/{App}-INT-002.md) | 커밋 전 배포 게이트 | 기능개발 | approved | SKIPPED — --no-gate | 배포 커밋 본문에 [Deploy] 표기 | FR 3 · A 3 |
| [{App}-INT-003](INTENT/{App}-INT-003.md) | Intent 문서 통합 | 리팩토링 | draft | pending | TASK 와 SSOT 를 Intent 1문서로 합친다 | FR 4 · A 5 |

intents: 3
```

## 재생성 시점

카탈로그는 Intent 의 메타 표가 **확정되는 모든 지점**에서 다시 쓴다. Intent 파일이 갓 생성된 `draft` 시점에는 쓰지 않는다 — 제목·`검증`·항목 수가 아직 비어 있어 쓰는 순간부터 stale 이다.

| 시점 | 주체 | 커밋 |
|---|---|---|
| Phase 5 진입 (승인 질의 전 · `draft`) | requirement-spec Phase 5 1번 | 없음 (승인 전) |
| `draft` → `approved` | requirement-spec Phase 5 6번 | 없음 — `/forge-init` 1번(승인 커밋 게이트)이 `docs({App}-INT-{NNN}): Intent 승인` 으로 커밋 |
| `approved` → `in-dev` | `/forge-init` 3번 (`worktree_setup.py init`) | `chore({App}-INT-{NNN}): 상태 in-dev` 에 동봉 |
| `in-dev` → `in-review` | forge-scope F5 | `chore({App}-INT-{NNN}): 상태 in-review` 에 동봉 |

빠뜨려도 `check --app {App}` 이 `INT_CATALOG stale` 로 잡는다.
