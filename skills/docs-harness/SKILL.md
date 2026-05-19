---
name: docs-harness
description: Use when working with service-aware documentation harnesses driven by `.claude/docs-harness.config.json`. Validates per-service `<docs_dir>/PRD-{CODE}-001.md`, `FC-{CODE}-001.md`, `FRD/FRD-{CODE}-F{NNN}.md` trees and adds new feature FRDs preview-only.
---

# Docs Harness — Skill

## 1. 목적

- 서비스-단위 문서(PRD/FC/FRD) SSOT 구조를 검사·확장하는 결정적 도구.
- 단일 프로젝트 = service 1개, 멀티 서비스 = service N개. config로 선언.
- `xlab-` prefix 없는 범용 어댑터. 모든 프로젝트는 `.claude/docs-harness.config.json` 작성 후 사용.

## 2. 핵심 원칙

- **Preview-only**: source repo는 절대 수정하지 않는다. `--preview-dir` 외부 디렉터리에만 기록.
- **결정적 출력**: 동일 입력 → 동일 출력. 자동 수정 X.
- **자기 검증**: preview 생성 후 `docs_check.run_checks`로 즉시 검증.
- **명시 강제**: config 없으면 즉시 reject (`FAIL CONFIG`). silent fallback 없음.

## 3. Config 스키마

`.claude/docs-harness.config.json` (target repo 루트):

```json
{
  "services": [
    {
      "name": "Master",
      "code": "MASTER",
      "docs_dir": "Docs/Master",
      "app_dir": "Src/MyApp/App/Master"
    }
  ],
  "repo_required_files": ["CLAUDE.md"],
  "repo_required_dirs": ["Docs"],
  "protected_subpaths": ["Docs", "Src", ".git", "scripts"],
  "excluded_docs_dirs": []
}
```

| 필드 | 필수 | 기본 |
|---|---|---|
| `services[]` | ✓ | — |
| `services[].name` | ✓ | — |
| `services[].code` (대문자 영숫자) | ✓ | — |
| `services[].docs_dir` | ✓ | — |
| `services[].app_dir` | ✗ | `""` (코드 매핑 skip) |
| `repo_required_files` | ✗ | `["CLAUDE.md"]` |
| `repo_required_dirs` | ✗ | `[]` |
| `protected_subpaths` | ✗ | `["Docs", "docs", "Src", "src", ".git", "scripts"]` |
| `excluded_docs_dirs` | ✗ | `[]` |

## 4. 디렉터리 규약

각 service는:

```
<docs_dir>/PRD-<CODE>-001.md
<docs_dir>/FC-<CODE>-001.md
<docs_dir>/FRD/FRD-<CODE>-F<NNN>.md   ← N개
```

`NNN` = 세 자리 (F001, F042 등). FRD는 19 section 고정 (`## 1. 기능 개요` ~ `## 19. 미확인 사항`).

## 5. 커맨드

```
/docs-check          # 검사 전용. 파일 수정 0.
/docs-add-feature    # 신규 기능 preview 생성. source repo 무수정.
```

직접 CLI:

```bash
python scripts/docs_check.py --repo <repo>
python scripts/docs_add_feature.py --repo <repo> --service <name> --feature <feature.json> --preview-dir <outside-repo>
```

## 6. 문서 하네스 실행 원칙

- 문서 검사 전에는 source repo를 수정하지 않는다.
- 먼저 `docs_check`를 실행한다.
- FAIL이 나오면 **자동 수정하지 말고 결과를 요약**한다.
- PRD/FC/FRD 생성·수정 작업은 후속 명시 지시가 있을 때만 수행한다.

## 7. 신규 기능 추가 (`docs_add_feature.py`)

- 신규 FRD 1개 생성 (`<docs_dir>/FRD/FRD-<CODE>-F<NNN>.md`)
- 해당 service FC의 `## 추가 기능` 섹션 생성 또는 갱신
- `preview-dir` 기준 `docs_check.run_checks` 자기 검증
- `--preview-dir`은 반드시 repo 바깥. 내부에 두면 `FAIL ARGS --preview-dir must be outside --repo`.
- feature JSON에는 `service`, `id`, `project_code` 키 금지.
  - `service`는 CLI 인자
  - `id`는 기존 FRD 번호에서 자동 계산
  - `project_code`는 service code에서 도출
- 정의되지 않은 key는 reject (`FAIL FEATURE unknown feature key: <key>`).
- `api_paths`는 `{id}` 같은 route brace 허용. backtick/pipe/newline 금지.
- 결과가 0 FAIL이어도 자동으로 source repo에 복사하지 않음 — 사용자 수동 검토.

## 8. 출력 코드

| Exit | 의미 |
|---|---|
| 0 | 모든 검사 통과 / preview 성공 |
| 1 | CHECK FAIL 또는 CONFLICT 존재 |
| 2 | `FAIL ARGS` / `FAIL FEATURE` / `FAIL REPO` / `FAIL PREVIEW` / `FAIL CONFIG` |

## 9. 금지 사항

- 기존 PRD/FC/FRD를 자동으로 수정하지 않는다.
- preview를 자동으로 source repo에 적용하지 않는다.
- config 없는 상태에서 추론 동작하지 않는다 (`FAIL CONFIG`로 즉시 종료).
- `excluded_docs_dirs`에 명시된 디렉터리는 검사 대상에 포함하지 않는다.
