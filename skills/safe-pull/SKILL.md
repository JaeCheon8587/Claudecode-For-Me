---
name: safe-pull
description: git pull 전에 fetch(태그 포함)로 비파괴 수집 후 "기존 vs 풀 후" 변경·깃 관점 충돌(크래쉬)·사이드이펙트를 브리핑하고, AskUserQuestion으로 확인받은 뒤에만 pull 실행하는 안전 게이트. 사용자가 "풀 받아도 돼?", "pull 하기 전에 확인", "safe pull", "당겨오면 뭐 바뀌어?", "이 브랜치 최신화", "원격 변경 확인하고 풀", "충돌 날까?" 등 pull/fetch/원격 동기화 전 영향 파악이 필요한 모든 상황에서 트리거. 단순 즉시 pull 요청이어도 변경 규모가 크거나 충돌 위험이 있으면 적극 사용.
argument-hint: "[원격/브랜치 — 미지정 시 현재 추적 upstream 자동]"
---

# Safe Pull

`git pull`은 한 번 실행하면 워킹트리·HEAD·히스토리가 즉시 바뀜. 결과를 받아본 뒤에야 충돌이나 예상 못 한 변경을 인지하면 늦음. 이 스킬은 **비파괴 단계(fetch)까지만 먼저 실행**해 "지금 상태 → 풀 받으면 이렇게 바뀐다"를 브리핑하고, **충돌(깃 관점 크래쉬)을 실제 머지 없이 예측**하고, **사이드이펙트**를 정리한 뒤, 사용자가 **AskUserQuestion으로 명시 확인**한 경우에만 `git pull`(merge)을 실행한다.

핵심 원칙: **pull/merge는 컨펌 게이트 뒤에만**. fetch는 비파괴이므로 브리핑을 위해 컨펌 전에 실행해도 안전하다.

---

## 실행 환경

- 모든 git 명령은 PowerShell/Bash 양쪽에서 동작. Windows 사용자이면 Bash 툴 또는 PowerShell 둘 다 가능.
- **PowerShell 주의**: `@{u}`(upstream 약칭)는 PowerShell이 hashtable 리터럴로 파싱하므로 반드시 작은따옴표로 감쌀 것 → `'@{u}'`. Bash에서도 작은따옴표 무해.
- 외부 도구 불필요 — 순수 `git`만 사용 (`gh` 등 안 씀).
- 인자로 원격/브랜치를 주면 그 대상으로, 미지정이면 현재 브랜치의 추적 upstream을 사용.

---

## Process

### Step 0 — 안전 게이트 (비정상 상태면 즉시 중단)

순서대로 검사. 하나라도 걸리면 **원인·해결책을 설명하고 거기서 멈춤** (fetch도 하지 않음). 자동 보정하지 않는다 — 사용자가 의도를 갖고 직접 처리해야 안전하기 때문.

1. **git 저장소 여부**: `git rev-parse --is-inside-work-tree` 실패 → 저장소 아님, 중단.
2. **detached HEAD**: `git symbolic-ref -q HEAD` 실패(출력 없음) → 브랜치에 붙어있지 않음. 어떤 커밋에 있는지(`git rev-parse --short HEAD`)와 `git switch <branch>`로 복귀하는 법 안내 후 중단.
3. **remote 없음**: `git remote` 빈 출력 → 당겨올 원격이 없음. `git remote add origin <url>` 안내 후 중단.
4. **upstream 없음**: `git rev-parse --abbrev-ref --symbolic-full-name '@{u}'` 실패 → 현재 브랜치에 추적 대상 미설정. `git branch --set-upstream-to=origin/<branch>` 안내 후 중단. (인자로 명시 대상을 받은 경우는 그 대상으로 진행 가능 — 이땐 `git fetch <remote> <branch>`로 처리.)
5. **dirty working tree**: `git status --porcelain` 출력이 비어있지 않음 → 미커밋 변경/untracked 존재. **변경 파일 목록을 분류해 브리핑하고 풀을 막음.** stash를 자동 실행하지 않는다. "커밋하거나 `git stash` 후 다시 시도" 안내.
   - 출력 첫 두 글자로 분류: ` M`/`MM`=수정, `A`=스테이징 추가, `D`=삭제, `??`=untracked, `UU`=충돌 미해결 등.
   - 이유: pull(merge)이 dirty 파일과 겹치면 머지를 거부하거나 로컬 변경을 위험에 빠뜨림. 깨끗한 상태에서만 영향이 명확.

### Step 1 — fetch (태그 포함, 비파괴)

Step 0 전부 통과 시에만 진행.

```bash
git tag > <before-tags-snapshot>          # fetch 전 로컬 태그 스냅샷
git fetch --tags --prune                  # 원격 ref + 태그 갱신. 워킹트리/HEAD 안 건드림 (안전)
git tag                                    # fetch 후 — before와 diff로 새 태그 추출
```

- `--tags`: 사용자가 명시 요청한 "태그도 가져옴". 새 릴리스 태그가 이번 동기화에 포함됐는지 파악.
- `--prune`: 원격에서 삭제된 ref 정리 — 유령 브랜치로 인한 오판 방지.
- fetch는 원격 추적 ref(`origin/...`)와 태그만 갱신할 뿐 로컬 브랜치/워킹트리를 바꾸지 않음. 그래서 컨펌 전에 실행해도 무방.
- **새 태그**: fetch 전/후 `git tag` 출력의 차집합. 단, 태그는 fetch 시점에 이미 로컬에 반영됨 → Step 4 사이드이펙트에서 "pull과 무관하게 이미 들어옴"으로 명시.

### Step 2 — 브리핑 계산

대상 ref를 `UP`(upstream, 보통 `'@{u}'` 또는 인자로 받은 `origin/<branch>`)로 둔다.

- **ahead / behind** — 따옴표 중첩 함정을 피해 두 명령으로 분리(PowerShell/Bash 공통 안전):
  ```bash
  git rev-list --count HEAD..'@{u}'      # behind — 원격에만 있는 커밋(풀 받으면 들어올 커밋)
  git rev-list --count '@{u}'..HEAD      # ahead  — 로컬에만 있는 커밋
  ```
- **상태 판정**:
  - `behind==0` → 이미 최신. 풀 받아도 변화 없음. 브리핑하고 종료(pull 불필요) 안내.
  - `ahead==0 && behind>0` → **fast-forward 가능**. 충돌 0 확정, 머지 커밋 없음.
  - `ahead>0 && behind>0` → **diverged**. merge가 머지 커밋을 생성. 충돌 예측 필요.
- **들어올 커밋 로그**: `git log --oneline --no-merges HEAD..'@{u}'` (behind 커밋들).
- **변경 파일**: `git diff --name-status HEAD..'@{u}'` → 앞글자 A/M/D/R로 추가·수정·삭제·이름변경 분류. 규모는 `git diff --stat HEAD..'@{u}'`.
- **핵심 파일 diff 발췌**: 다음 우선순위로 골라 `git diff HEAD..'@{u}' -- <file>` 일부 인용:
  1. lock/의존성 파일(`*.lock`, `package.json`, `requirements*.txt`, `*.csproj`, `go.mod` 등)
  2. 마이그레이션/스키마, CI/빌드 설정(`.github/`, `*.yml`, `Dockerfile`)
  3. `--stat` 변경량 상위 파일
  - **출력 cap**: 파일당 약 40줄, 전체 약 200줄. 초과 시 `... (N줄 생략)`로 표시. 브리핑이 본문 폭주하지 않게.

### Step 3 — 크래쉬(충돌) 예측 — 깃 관점

"크래쉬"는 깃 관점에서 **머지 충돌**을 뜻함. 실제로 머지하지 않고 미리 예측한다.

- `ahead==0` (FF 가능) → **충돌 0건 확정**. fast-forward는 머지하지 않고 포인터만 전진하므로 충돌 불가.
- `diverged` →
  ```bash
  git merge-tree --write-tree HEAD '@{u}'     # git 2.38+
  ```
  - 종료코드 비0 또는 출력에 충돌 섹션이 있으면 충돌. 출력의 `CONFLICT`/충돌 파일 경로를 파싱해 **충돌 예상 파일 목록** 제시.
  - 충돌 없으면 "merge 커밋은 생기지만 충돌 없음".
- **fallback** (git < 2.38로 `merge-tree --write-tree` 미지원): 양쪽 변경 파일 교집합 계산.
  ```bash
  git diff --name-only HEAD...'@{u}'    # 원격 쪽 변경
  git diff --name-only '@{u}'...HEAD    # 로컬 쪽 변경
  ```
  교집합 파일을 **"충돌 가능 후보"**로 표시하되, **확정이 아님**을 명시(같은 파일이어도 다른 줄이면 자동 머지됨). git 버전 한계로 정밀 예측 불가함을 사용자에게 알림.

### Step 4 — 사이드이펙트 정리

- **머지 커밋 생성 여부**: diverged면 `git pull`(merge)이 머지 커밋 1개 생성 → 히스토리에 분기/합류 기록됨. FF면 생성 안 됨.
- **로컬 ahead 커밋**: merge는 로컬 커밋을 보존(rewrite 안 함). rebase였다면 SHA가 바뀌지만 기본 전략은 merge라 안전.
- **새 태그**: Step 1 fetch 시점에 이미 로컬에 반영됨 → "pull 실행과 무관하게 이미 들어와 있음" 명시. 기존 로컬 태그와 이름 충돌 시 fetch가 갱신하지 않을 수 있으니 그 경우 경고.
- **submodule**: 변경 파일에 `.gitmodules`나 submodule 경로 포인터 변경이 있으면 `git submodule update` 필요할 수 있음을 알림.
- **빌드/환경 영향**: lock·의존성·CI 설정 변경이 들어오면 풀 후 의존성 재설치/재빌드가 필요할 수 있음을 플래그.
- **원격 히스토리 재작성 흔적**: `behind`인데 공통 조상 대비 원격이 force-push된 흔적(예전 origin SHA가 사라짐)이 감지되면 강하게 경고 — 머지가 꼬일 수 있음.

### Step 5 — 브리핑 출력 (기존 → 풀 후)

아래 고정 템플릿을 한국어 개조식으로 출력. 비어있는 섹션은 "해당 없음"으로 간결히.

```
## Safe Pull 브리핑: <branch> ← <remote>/<branch>

**요약**: behind N · ahead M · <FF가능 | diverged(머지커밋 생성) | 이미 최신>

### 들어올 커밋 (N개)
<git log --oneline 결과>

### 변경 파일
- 추가(A): ...
- 수정(M): ...
- 삭제(D): ...
(총 X파일, +추가/-삭제 줄)

### 새 태그
<fetch로 새로 들어온 태그, 없으면 "없음">

### 핵심 파일 diff 발췌
<cap 적용된 발췌>

### ⚠️ 충돌 예측 (깃 관점)
<충돌 없음 | 충돌 예상 파일 목록 | (fallback) 충돌 가능 후보 — 확정 아님>

### 사이드이펙트
<머지커밋 / submodule / 빌드영향 / 태그 / force-push 경고 등>

### 풀 후 상태
<예: HEAD가 <new-short-sha>로 fast-forward | 머지 커밋 1개 생성되어 합류>
```

### Step 6 — 컨펌 (AskUserQuestion)

브리핑 출력 후 **반드시** AskUserQuestion으로 물음. 텍스트로만 묻고 넘어가지 말 것 — 명시 선택을 받아야 pull 실행.

- 질문: "위 내용으로 `git pull`(merge) 진행할까요?"
- 옵션:
  - **진행** — `git pull` (merge) 실행
  - **중단** — 아무것도 안 함 (fetch는 이미 됨, 비파괴라 무해)
  - **rebase로 대신** — `diverged`인 경우에만 노출. `git pull --rebase`로 머지 커밋 없이 로컬 커밋을 원격 위로 재배치
- `behind==0`(이미 최신)이면 컨펌 생략하고 "풀 불필요"로 종료.

### Step 7 — pull 실행

컨펌에서 진행/rebase를 선택한 경우에만:

```bash
git pull              # 진행(merge)
# 또는
git pull --rebase     # rebase 선택 시
```

- **성공**: 새 `HEAD` short SHA와 결과(fast-forward / 머지 커밋 생성 / N파일 변경) 보고.
- **충돌 발생**: 충돌 파일 목록과 해결 흐름(`git status`로 충돌 확인 → 편집 → `git add` → `git commit` / rebase면 `git rebase --continue`, 취소는 `git merge --abort` / `git rebase --abort`) 안내. 자동 해결하지 않음.
- **거부됨**(예: 막판 dirty): 메시지 그대로 전달하고 원인 설명.

---

## 설계 노트

- **왜 fetch를 먼저 하나**: behind 커밋·변경 파일·충돌은 원격 객체가 로컬에 있어야 계산 가능. fetch 없이는 브리핑이 불가능하고, fetch 자체는 워킹트리/HEAD를 안 건드려 안전.
- **왜 dirty면 막나**: merge가 미커밋 변경과 겹치면 거부되거나 로컬 작업을 위험에 빠뜨림. 자동 stash는 pop 충돌이라는 새 위험을 만들어 의도적으로 배제.
- **왜 merge 기본**: 로컬 커밋 SHA를 보존해 가장 예측 가능. rebase는 히스토리를 선형화하지만 SHA가 바뀌어 공유 브랜치에서 위험 — diverged 한정 옵션으로만 제공.
