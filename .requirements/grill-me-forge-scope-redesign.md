## forge-scope 재설계 요구사항 정리

### 배경 — 출발점
현 forge-scope는 `scripts/forge_scope.py`(~3400줄) 오케스트레이터가 scaffold·plan 생성·`record-step` 하드강제·finalize를 전부 떠안는다. 인라인 전환(v2.16)·읽기ROOT/쓰기worktree(v2.17)까지 진화했지만 무겁고 경로 분리가 복잡하다. **목표: python 본체 폐기, 전부 인라인. python은 셋업·검증만 하는 얇은 helper로 축소.**

### 전개
- **워크트리 모델**: 2~3개 세션 동시 병렬 개발 → 격리 필수. 단일 워킹트리는 한 브랜치만 체크아웃 → 병렬 격리하려면 **각 세션이 자기 워크트리 안에서 작업**. `.worktree/`(루트 하위)에 생성, python이 워크트리 이름 리턴.
- **가드레일 주입**: `Docs/`·`.claude/`·`CLAUDE.md`는 untracked → 워크트리에 안 들어옴. **python이 `Docs/` + `CLAUDE.md` + `.claude/rules`만 복사**(`.claude` 전체 복사 안 함). 서브모듈은 junction(Win)/symlink(Unix) 링크(오프라인).
- **상태 모델**: 워크트리 안 `.process/<docName>/`에 `forge-scope-build.md`(수행할 작업 스텝) + `forge-scope-progress.md`(완료 기록). **두 파일 템플릿 제공**, 세션이 작성·갱신. 워크트리가 격리 보장 → **sessionID 불필요**(폴더 키 = docName). `.process/`는 **gitignore**(휘발성 체크포인트, diff 오염 방지). **재호출 시 항상 제거 후 재생성**. resume = 산 세션이 progress.md 보며 인라인 진행을 이어가는 것으로 한정.
- **강제 모델**: **완전 세션 자율**. python 강제 0. 옛 `record-step` 하드게이트(TDD순서·step커밋·누수가드·시도상한) 전부 폐기. 순서·커밋·테스트 통과는 세션이 build.md 따라 self-discipline.
- **파이프라인**: **고정 계약-TDD 단일 파이프라인**, 프리셋(auto/single-step/frd-implementation) 전부 제거.
  1. 계약(인터페이스·DTO) + 테스트 작성 → **커밋(red)**
  2. 구현체 → **커밋**
  3. 프로젝트만 빌드 + 유닛테스트, 통과까지 개선 → **커밋**
- **빌드 제약 (절대)**: 빌드는 **절대 솔루션(`*.sln`) 빌드 금지**. **무조건 해당 프로젝트(.csproj)만** `dotnet build`/`dotnet test`. 타겟 = TASK §9.1 단위테스트 명세의 "프로젝트" 칸.
- **입력**: TASK 문서(`docs/.templates/App/TASK/APP-TASK-001-TEMPLATE.md` 형식). self-contained. §12 외부계약/데이터구조 → 계약, §9.1 단위테스트 명세(여기 "프로젝트" 칸 = 빌드 타겟) → 테스트, §8 작업단계 → 구현.
- **검증 게이트(python, 워크트리 생성 전)**: (1) 전제조건 일괄 — git repo·입력 doc·복사원(CLAUDE.md/.claude/rules/Docs) 존재. (2) 문서 미결 검사 — §7 결정 필요·§11 미확인 사항 절이 항목과 함께 존재하거나 `{...}` placeholder 잔존 → **중단**. 통과해야 워크트리 생성.
- **정리 도구**: 새 helper에 `cancel` 서브커맨드 흡수(별도 forge_cancel.py 폐지). 서브모듈 링크 해제 → `git worktree remove` → feat 브랜치 삭제(복사물은 워크트리와 함께 제거됨).

### 전환 — 핵심 결정
- **모순①** "워크트리 만들고 루트에서 작업" → 병렬 격리와 정면 충돌. 작업은 **워크트리 안**으로 확정, "루트 작업" 폐기.
- **모순②** 원 고민 "복사 vs 루트작업" → 루트작업 폐기로 진짜 선택지가 **복사 vs 링크**로 재정의. **복사 채택**(`.claude/rules`만), v2.17이 폐기했던 staleness 회귀는 세션 단명으로 감수.
- **모순③** `{sessionID}` 키 + "제거 후 생성" vs resume → 워크트리 격리로 sessionID 불필요 → docName 키로 단순화, 재호출은 늘 새 시작.
- **방향 전환**: 결정론(python record-step) 통째 포기 → 세션 자율. 프리셋 다양성 포기 → 단일 TDD 파이프라인. python은 "워크트리 + 서브모듈 링크 + 가드레일 복사 + 검증 게이트 + cancel"만.

### 결론 — 확정 요구사항·미결
**확정**: 위 전개 항목 전부 + 빌드 제약(프로젝트만, 솔루션 금지).

- **Open Items ⚠️**:
  - `forge_scope.py` 삭제가 `ddr_loop.py`·forge-full의 import(`ClaudeInvoker`/`StepExecutor`/`StepSplitter`)를 깨뜨림 → **나중 확인**(이번 범위 무관, 사용자 보류).
- **현재 구체화 수준**: 아키텍처·동작 흐름·커밋 경계·빌드 제약·상태/정리 규칙 전부 확정. forge-full 의존성 영향 1건만 후속 확인 대상.
