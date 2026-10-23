# {app}-intent-catalog — {app} Intent Catalog

> ⚠ **TEMPLATE** — 이 파일은 **참고용 예시**다. 실제 `intent/{app}/intent-catalog.md` 는 손으로 만들지 않는다 — `python ~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<버전>/scripts/docs_helpers.py intent-catalog --repo . --app {app} --write` 가 `intent/{app}/` 폴더를 훑어 생성한다(상위 카탈로그 `intent/intent-app-catalog.md` 도 함께). `intent/` 는 **커밋하지 않는다**.
>
> App 카탈로그의 모든 열은 Intent 문서의 메타 표·H1·Outcome·항목·진행 표시에서 **파생**된다. 고유 정보가 0 인 **생성물**이므로 손으로 고치면 아래 `## 재생성 시점` 의 지점에서 반드시 어긋난다.
>
> 값을 바꾸려면 **해당 Intent 문서를 고치고 재생성**한다. `docs_helpers.py check --app {app}` 이 불일치를 `INT_CATALOG` FAIL 로 잡는다.
>
> 식별자 규약은 [DOCUMENT_GUIDE §5](../../docs/DOCUMENT_GUIDE.md#5-식별자-규약) 참조.

## 생성 결과 예시

아래가 생성기가 내는 형태다. 열의 출처는 각각 이렇다.

| 열 | 출처 |
|---|---|
| Intent | 메타 `문서 ID` + 파일 링크 (같은 폴더) |
| 제목 | H1 에서 `{app}-int-{NNN} — ` 접두를 뗀 나머지 (기능 이름) |
| 기능 ID | 메타 `기능 ID` (App PRD §7 행) |
| 상태 | 메타 `상태` (`active` · `retired`) |
| 진행 중 Task | FR · E · X 의 진행 표시(`[tsk-{NNN} 진행 중]` · `[tsk-{NNN} 삭제 예정]`)를 단 Task — Task 문서 링크, 없으면 `none` |
| 요약 | `### Outcome` 첫 실질 줄 (주석·`Out of scope` 제외, 50자 컷) |
| 규모 | `Functional requirements` · `Edge cases` · `Error cases` 항목 수 |

값을 못 읽으면 `?` 가 들어간다 — 그 Intent 의 메타 표가 깨진 것이므로 `check-intent` 로 확인한다. 유형 · 검증은 이 카탈로그에 없다 — 변경마다 Task 가 갖고 `.task/task-catalog.md` 에 나온다.

```markdown
# loader-intent-catalog — loader Intent Catalog

> **생성물** — `docs_helpers.py intent-catalog --repo . --app loader --write` 가 `intent/loader/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — 값을 바꾸려면 해당 Intent 문서를 고치고 재생성한다. `check --app loader` 이 불일치를 FAIL 로 잡는다.

| 항목 | 값 |
|---|---|
| 문서 ID | loader-intent-catalog |
| 생성 | docs_helpers.py intent-catalog |
| 대상 | [loader 폴더](./) |

| Intent | 제목 | 기능 ID | 상태 | 진행 중 Task | 요약 | 규모 |
|---|---|---|---|---|---|---|
| [loader-int-001](loader-int-001.md) | 업로드 재시도 | F001 | active | [tsk-012](../../.task/tsk-012.md) · [tsk-013](../../.task/tsk-013.md) | 일시 오류로 실패한 업로드를 다시 시도한다 | FR 5 · E 3 · X 2 |
| [loader-int-002](loader-int-002.md) | 업로드 이력 조회 | F002 | active | none | 사용자가 지난 업로드 결과를 본다 | FR 3 · E 1 · X 1 |
| [loader-int-003](loader-int-003.md) | 일괄 업로드 | F003 | retired | none | 여러 파일을 한 번에 올린다 | FR 0 · E 0 · X 0 |

intents: 3
```

## 재생성 시점

카탈로그는 열의 원천(제목 · 기능 ID · 상태 · 진행 표시 · Outcome · 항목 수)이 바뀌는 지점에서 다시 쓴다. 같은 명령이 상위 카탈로그(`intent/intent-app-catalog.md`)도 함께 다시 쓴다. 어느 지점도 커밋하지 않는다 — 문서는 커밋하지 않는다.

| 시점 | 주체 |
|---|---|
| Intent 를 새로 쓰거나 고친 뒤 (확정 · 중단 처리 후) | `requirement-spec` Phase 5 |
| Task 일괄 승인 — 자르면서(초안) 붙인 진행 표시가 카탈로그에 들어간다 | `/task-split` 승인 |
| 자르기 중단 — 지운 초안 Task 의 진행 표시가 빠진다 | `/task-split` 중단 |
| Task `done` — 진행 표시 · `삭제 예정` 줄이 지워진다 | `/worktree-delete` (머지를 확인한 뒤) |
| Task `dropped` — Task Scope 로 Intent 를 되돌린 뒤 | 되돌린 세션 (사용자 확인 후, 손으로 `--write`) |

빠뜨려도 `check --app {app}` 이 `INT_CATALOG stale` 로 잡는다.
