---
description: forge-scope 워크트리와 그 브랜치(feat-<slug>)를 제거한다. 링크된 서브모듈의 메인 repo 원본은 절대 제거하지 않는다(junction 링크만 해제). 인자 없으면 forge 워크트리 목록에서 선택.
argument-hint: "[<slug>] — 생략 시 목록에서 선택"
---

forge-scope 정리 커맨드. 설정한 워크트리 + 브랜치를 제거하되 **서브모듈 메인 원본은 보존**한다.

helper 경로:

```bash
FORGE="${CLAUDE_PLUGIN_ROOT}/scripts/worktree_setup.py"
```

`$ARGUMENTS` 해석:

## 인자 있음 (slug 지정)
첫 토큰을 slug로 보고 바로 제거한다:

```bash
python "$FORGE" cancel <slug>
```

## 인자 없음 (목록에서 선택)
1. forge 워크트리 목록을 가져온다:
   ```bash
   python "$FORGE" list
   ```
   stdout 마지막 줄의 JSON 배열 `[{"slug","branch","worktree"}, ...]`를 파싱한다.
2. 빈 배열(`[]`)이면 "제거할 forge 워크트리가 없습니다" 보고 후 종료.
3. 목록을 표로 보여주고 `AskUserQuestion`으로 **어느 워크트리를 제거할지** 사용자에게 확인한다 (여러 개 선택 허용).
4. 선택된 각 slug에 대해 `python "$FORGE" cancel <slug>` 실행.

## 동작 / 보고
- `cancel`이 하는 일: 워크트리 서브모듈 junction/symlink **링크만 해제**(메인 repo 서브모듈 원본은 100% 보존) → `git worktree remove`(dirty면 자동 `--force`) → `git branch -D feat-<slug>`.
- 제거된 워크트리·브랜치를 한 줄씩 보고한다.

> **서브모듈 안전**: 메인 repo의 서브모듈 디렉토리·내용은 절대 건드리지 않는다. 링크 해제는 워크트리 쪽 junction만 끊는 것이며, 이를 안 하면 `git worktree remove`가 junction을 따라가 메인 서브모듈을 삭제하는 사고가 나므로 필수다.

> 정리 대상 워크트리 **내부에서** 이 커맨드를 실행하면 안 된다(cwd 가드가 막는다). 메인 repo 루트에서 실행한다.
