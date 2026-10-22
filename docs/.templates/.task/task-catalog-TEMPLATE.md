# TASK-CATALOG — Task Catalog

> ⚠ **TEMPLATE** — 이 파일은 **참고용 예시**다. 실제 `.task/task-catalog.md` 는 손으로 만들지 않는다 — `python ~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<버전>/scripts/docs_helpers.py task-catalog --repo . --write` 가 `.task/` 폴더를 훑어 생성한다.
>
> task-catalog 의 모든 열은 Task 문서의 H1 · 메타 표에서 **파생**된다. 고유 정보가 0 인 **생성물**이므로 손으로 고치면 아래 `## 재생성 시점` 에서 반드시 어긋난다.
>
> 값을 바꾸려면 **해당 Task 문서를 고치고 재생성**한다. `docs_helpers.py check` 가 불일치를 `TSK_CATALOG` FAIL 로 잡는다. `.task/` 는 커밋하지 않는다 — 정본은 메인 작업트리에 하나뿐이다.
>
> 식별자 규약은 [DOCUMENT_GUIDE §5](../docs/DOCUMENT_GUIDE.md#5-식별자-규약) 참조.

## 생성 결과 예시

아래가 생성기가 내는 형태다. 열의 출처는 각각 이렇다.

| 열 | 출처 |
|---|---|
| Task | 메타 `문서 ID` + Task 파일 링크 (`.task/` 기준 상대경로) |
| 설명 | H1 에서 `TSK-{NNN} — ` 접두를 뗀 나머지 |
| 유형 | 메타 `유형` |
| 상태 | 메타 `상태` |
| 선행 | 메타 `선행 Task` 의 ID 마다 해당 Task 파일 링크. `none` 이면 `none` |
| 대상 Intent | 메타 `대상 Intent` 의 ID 마다 해당 Intent 파일 링크. `none` 이면 `none` |

- 값을 못 읽으면 `?` 가 들어간다. 그 Task 의 메타 표가 깨진 것이므로 `check-task` 로 확인한다.
- 대상 Intent · 선행 Task 의 ID 에 해당하는 파일이 없으면 링크 대신 `?ID` 가 들어가고, `check-task` 가 FAIL 로 잡는다.
- Intent 링크는 레포에 실제로 있는 문서 폴더 표기를 쓴다. `Docs` 레포면 `../Docs/…` 이다. Linux 는 대소문자를 구분해서 표기가 다르면 링크가 깨진다.

```markdown
# TASK-CATALOG — Task Catalog

> **생성물** — `docs_helpers.py task-catalog --repo . --write` 가 `.task/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — 값을 바꾸려면 해당 Task 문서를 고치고 재생성한다. `check` 가 불일치를 FAIL 로 잡는다.

| 항목 | 값 |
|---|---|
| 문서 ID | TASK-CATALOG |
| 생성 | docs_helpers.py task-catalog |
| 대상 | [.task 폴더](./) |

| Task | 설명 | 유형 | 상태 | 선행 | 대상 Intent |
|---|---|---|---|---|---|
| [TSK-011](TSK-011.md) | 업로드 0바이트 파일 거부 | 버그수정 | done | none | [LOADER-INT-003](../docs/LOADER/INTENT/LOADER-INT-003.md) |
| [TSK-012](TSK-012.md) | 업로드 일시 오류 자동 재시도 | 기능개발 | in-review | none | [LOADER-INT-003](../docs/LOADER/INTENT/LOADER-INT-003.md) |
| [TSK-013](TSK-013.md) | 재시도 횟수 화면 표시 | 기능개발 | approved | [TSK-012](TSK-012.md) | [LOADER-INT-003](../docs/LOADER/INTENT/LOADER-INT-003.md) · [VIEWER-INT-001](../docs/VIEWER/INTENT/VIEWER-INT-001.md) |

tasks: 3
```

**역방향 찾기**: "이 Intent 를 바꾼 Task" 는 `대상 Intent` 열을 검색한다. Intent 쪽에 Task 목록을 따로 두지 않는다 — 끝나지 않은 Task 는 Intent 항목의 진행 표시로도 보인다.

## 재생성 시점

카탈로그는 Task 의 메타 표가 **확정되는 모든 지점**에서 다시 쓴다. 문서는 커밋하지 않으므로 어느 시점에도 커밋이 없다.

| 시점 | 주체 |
|---|---|
| `draft` → `approved` | `/task-split` 일괄 승인 |
| `approved` → `in-review` | 개발 세션이 워크트리 안에서 `worktree_setup.py finish TSK-{NNN}` — 메인 정본을 고치고 다시 쓴다 |
| `in-review` → `done` | `/worktree-delete` — 브랜치 머지를 확인한 뒤 |
| → `dropped` | 사람 (Intent 되돌리기와 함께) — 고친 뒤 `task-catalog --write` |

빠뜨려도 `check` 가 `TSK_CATALOG stale` 로 잡는다.

## 워크트리의 사본

`/worktree-init` 이 워크트리에 `.task/` 를 복사한다 — 개발 세션이 읽는 스냅샷이다. 상태 전이는 늘 메인 정본에 쓰므로 워크트리 사본의 카탈로그는 만든 시점에 멈춰 있다. 워크트리에서 카탈로그를 다시 만들거나 고치지 않는다.
