---
name: hooks-setup
description: harness_framework hooks 12개(pre-commit/pre-push + tools/quality/* + install-hooks.sh)를 사용자 레포에 멱등 배치한다. 기존 파일 충돌 시 사용자 프롬프트, 백업 + 롤백 지원. /claudecode-for-me:hooks-setup 으로 실행.
argument-hint: "[--dry-run | --apply | --rollback] [--yes | --force]"
input: 선택적 CLI 플래그
output: 사용자 레포에 tools/hooks/, tools/quality/, tools/install-hooks.sh 배치 + .hooks-setup/state.json 기록
requires-user-interaction: true
---

# Hooks Setup — Skill

`hooks-setup`은 `scripts/hooks_setup.py`를 통해 harness_framework hooks 자산을 사용자 레포에 배치한다.
직접 파일 작성·설정 변경을 수행하지 않고, 사전 검사 → 계획 출력 → 사용자 승인 → 적용 순으로 위임한다.

## 배치 대상 (12개)

```
tools/hooks/pre-commit
tools/hooks/pre-push
tools/quality/secret-scan.sh
tools/quality/lint.sh
tools/quality/dependency-check.sh
tools/quality/dependency_check.py
tools/quality/build.sh
tools/quality/test.sh
tools/install-hooks.sh
ruff.toml
requirements-dev.txt
.gitattributes (fragment append)
```

추가로 `git config --local core.hooksPath tools/hooks` 설정 (기존 `.git/hooks/` 무손상).

---

## 단계 1 — Python 사전 검사

```bash
python --version 2>&1 || py -3 --version 2>&1
```

3.10 미만이면 중단. `py -3` 만 가능 시 이후 `python` 호출을 `py -3` 로 대체.

---

## 단계 2 — Git 레포 검증

```bash
git rev-parse --show-toplevel
```

비-git 디렉토리면 중단 + 사용자에게 `git init` 안내.

---

## 단계 3 — 드라이런 실행 (기본)

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/hooks_setup.py" --dry-run
```

출력 예:
```
=== hooks-setup 계획 (repo: ...) ===
[파일 배치]
  + tools/hooks/pre-commit   (write_file, conflict=none, decision=install)
  ! ruff.toml                 (write_file, conflict=differs, decision=prompt)
[git config]
  + core.hooksPath = 'tools/hooks'  (decision=install)
범례: + 신규설치  = 동일/건너뜀  ! 충돌(apply 시 결정)
```

전체 출력을 사용자에게 그대로 보여준다.

---

## 단계 4 — 사용자 승인 후 적용

사용자가 `--apply` 진행 의사 표명 시:

**충돌 없음 케이스** (전부 `+` 또는 `=`):
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/hooks_setup.py" --apply --yes
```

**충돌 있음 케이스** (`!` 존재):
- 각 충돌 항목별로 사용자 선택지 안내:
  - `overwrite`: 백업 후 덮어쓰기 (.hooks-setup/backups/ 에 timestamp .bak 저장)
  - `skip`: 기존 파일 유지
- 일괄 정책 선택 시:
  - 전부 skip → `--yes` (안전)
  - 전부 overwrite → `--force` (위험)
  - 항목별 결정 → 플래그 없이 인터랙티브 실행 (각 항목 prompt)

`--yes`, `--force` 동시 사용 금지.

---

## 단계 5 — 후속 안내

apply 성공 후 사용자에게 안내:

```
배치 완료. 다음 단계:

  1. cd <user-repo>
  2. bash tools/install-hooks.sh   # prerequisite 점검 + chmod +x
  3. git commit / git push 시 훅 자동 발화

prerequisite (Windows 기준):
  - Git Bash (Git for Windows 설치 시 포함)
  - dotnet SDK 9+ (build/test)
  - python 3.10+ + pytest, ruff
  - gitleaks (secret-scan)

상태 파일: .hooks-setup/state.json (롤백용)
백업 경로: .hooks-setup/backups/<path>.<timestamp>.bak
```

---

## 단계 6 — 롤백 (필요 시)

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/hooks_setup.py" --rollback
```

`state.json`의 액션을 역순 실행:
- 백업 있는 파일: 백업으로 복원
- 백업 없는 파일 (신규 생성): 제거
- `core.hooksPath`: 이전 값으로 복원 (이전 값 없으면 unset)

`.hooks-setup/backups/` 디렉토리는 보존됨 (수동 정리 가능).

---

## 에러 처리

| 에러 | 원인 | 대응 |
|---|---|---|
| `templates/hooks_manifest.json` 없음 | `${CLAUDE_PLUGIN_ROOT}` 미설정 + fallback 실패 | 수동 export `CLAUDE_PLUGIN_ROOT=<plugin-cache>` |
| `not a git repository` | cwd가 git 레포 아님 | `git init` 후 재시도 |
| 충돌 시 `--yes --force` 동시 | 상호배타 플래그 | 둘 중 하나만 |
| 롤백 시 backup 파일 사라짐 | 사용자가 .hooks-setup/ 수동 삭제 | 경고 출력 + 다음 항목 진행 |

---

## 동작 원칙

1. **멱등성**: 동일 manifest version으로 재실행 시 변경 없음 (conflict=identical → skip)
2. **비파괴**: 기존 파일은 백업 없이 덮어쓰지 않음
3. **명시적 동의**: 충돌 시 사용자 프롬프트 (`--yes`/`--force` 명시적 옵트인)
4. **롤백 가능**: state.json + backups로 완전 복원
5. **OS**: Windows 우선 (Git Bash 전제). Unix는 부수적 동작
