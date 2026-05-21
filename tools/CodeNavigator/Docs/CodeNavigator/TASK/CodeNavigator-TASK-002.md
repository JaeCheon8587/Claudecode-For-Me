# CodeNavigator-TASK-002 — codenav delete --file 서브커맨드 추가

| 항목 | 값 |
|---|---|
| 문서 ID | CodeNavigator-TASK-002 |
| 버전 | 0.1 |
| 상태 | Done |
| 작업 유형 | feature |
| 작성 가정 | MVP 이후 파일 단위 명시 삭제 진입점 부재 → F006 신규 추가. SSOT 갱신 완료. |

## 변경 이력
| 버전 | 일자 | 변경 요약 | 작성자 |
|---|---|---|---|
| 0.1 | 2026-05-21 | 초안 + 완료 | 정재천 |

---

## §1. 목적

`codenav delete --file <path>` 서브커맨드 노출. dry-run 기본 + `--yes` 실제 삭제 + `--json` 출력.

## §2. 범위

- **포함**: `store.count_file_classes`, `cmd_delete`, argparse subparser, `tests/test_main_delete.py`, FC/PRD/FRD-003/TASK-002 갱신
- **제외**: 클래스/네임스페이스/stale 단위 삭제, UI

## §3. 검증 기준

```powershell
# dry-run 기본
codenav delete --file <path>
# 기대: [dry-run] Would delete N class(es)...

# 실제 삭제
codenav delete --file <path> --yes
# 기대: Deleted N class(es)...

# pytest
python -m pytest tests/ -v
# 기대: 28 passed
```

## §4. 변경 파일 요약

| 파일 | 변경 요지 |
|---|---|
| `src/codenav/store.py` | `count_file_classes` 헬퍼 추가 |
| `src/codenav/__main__.py` | `cmd_delete` + `delete` subparser + dispatch 등록 |
| `tests/test_main_delete.py` | 신규 4 케이스 |
| `Docs/CodeNavigator/CodeNavigator-FC.md` | F006 행 추가, v0.2 |
| `Docs/CodeNavigator/CodeNavigator-PRD.md` | §3.1 / §7 F006 추가, v0.2 |
| `Docs/CodeNavigator/FRD/CodeNavigator-FRD-003.md` | 신규 |
| `Docs/CodeNavigator/TASK/CodeNavigator-TASK-002.md` | 본 파일 |
