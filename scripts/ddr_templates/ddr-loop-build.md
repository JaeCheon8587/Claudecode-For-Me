# DDR-Loop Build — {docName}

> **doc-driven 수렴 루프.** codex가 워크트리 브랜치 변경점을 docs와 대조해 일치율(Conformance %)을 매기고,
> 세션이 미달 항목을 워크트리 안에서 인라인 수정·재검을 반복한다.
>
> **작업 위치**: 이 워크트리 안에서만 (Edit/Write/commit/dotnet 모두 워크트리 cwd).
> **빌드 절대 제약**: 솔루션(`*.sln`) 빌드 **금지**. 무조건 대상 **프로젝트(.csproj)만** `dotnet build`/`dotnet test`.

## 입력
- 대상 브랜치: `{branch}` (워크트리)
- 비교 문서 source: `{docsSource}`
- Work Packet: `{workPacketPath}`
- TASK 문서: `{taskDocPath}`
- Required SSOT: {requiredSsotDocs}
- 비교 문서(최종 docs): {docPath}
- 빌드 타겟(.csproj): _(forge-scope-build.md 있으면 그 타겟 재사용 / 없으면 docs·사용자 지정 — 여기 명시)_
- base ref(vs): _(feat-{slug} 분기 모브랜치 — `git merge-base feat-{slug} <develop|main>`, 여기 명시)_

## 루프 설정 (고정)
- scope: `branch` (브랜치 누적 변경 vs base)
- 최대 회차: **3**
- 정지 임계: 일치율 **≥ 99%**

## 회차 절차 (각 iter)
1. **검증**: `doc_driven_review.py --docs <docs> --worktree {branch} --scope branch [--base <ref>]` → stdout 마지막 줄 `Conformance: N%` 추출. 자동 문서 source면 `<docs>`는 Work Packet + TASK + Required SSOT 전체다.
2. **기록**: progress.md iter 행에 일치율 + 주요 findings(Top Priorities/Review Comments) 요약.
3. **판정**: N ≥ 99 → 수렴 정지(수정 불요). iter==3 → cap 정지.
4. **수정**: codex 리뷰의 `Top Priorities` / `Review Comments`([CRITICAL]>[MAJOR]>[MINOR]) / `Overengineered`를 워크트리 안에서 인라인 수정 — 코드를 docs 요구에 맞춘다.
5. **빌드/테스트**: `dotnet build <타겟>.csproj` → `dotnet test <타겟>.csproj` (**.sln 금지**) 통과까지.
6. **커밋**: `fix(ddr-{docName}): iter N 일치율 N%`.

## 금지사항
- 솔루션(`*.sln`) 빌드·테스트.
- 메인 repo(워크트리 상위) 파일 수정. 작업은 워크트리 안에서만.
- **비교 문서·영구 SSOT(PRD/FRD/ADR 등) 자동 수정** — 일치율을 올리려 docs를 고치지 않는다. docs는 정답, 코드를 거기 맞춘다.
- Work Packet의 Required SSOT Execution Matrix를 DDR 비교에서 누락.
- 테스트 약화·삭제로 통과 위장. `.review/` 산출물 편집.
- 범위 밖 리팩토링(Overengineered 지적분 제거는 예외).
