---
description: CodeNavigator parser-only baseline index builder. AI enrichment 없이 C# 파일을 읽어 SQLite 인덱스를 빠르게 생성/복구.
argument-hint: "[repo-root] [scan-path] [--reset]"
---

CodeNavigator baseline index를 직접 생성/복구하라.

인자: $ARGUMENTS

목표:
- `repo-root/.codenav/index.sqlite`에 C# class/interface/struct/record 골격 인덱스를 만든다.
- AI 설명 생성은 하지 않는다.
- `file`, `folder`는 반드시 `repo-root` 기준 상대경로로 저장한다.
- `solution`은 각 파일 기준 가장 가까운 상위 `.sln` 파일명(stem)을 사용한다.
- `project`는 각 파일 기준 가장 가까운 상위 `.csproj` 파일명(stem)을 사용한다.
- 모든 자동 생성 entry는 `stale=1`, `source_type='auto'`로 저장한다.
- 기존 manual entry는 삭제하지 않는다.

인자 해석:
- 첫 번째 인자가 있으면 `repo-root`로 사용한다. 없으면 현재 작업 디렉터리를 사용한다.
- 두 번째 인자가 있으면 해당 경로만 스캔한다. 없으면 `repo-root` 전체를 스캔한다.
- `--reset`이 있으면 기존 `source_type='auto'` entry만 삭제한 뒤 다시 생성한다.

실행 절차:
1. `repo-root`와 `scan-path`를 절대경로로 정규화한다.
2. SQLite DB가 없으면 CodeNavigator schema와 FTS 테이블을 생성한다. 가능하면 `tools/CodeNavigator/src/codenav/store.py`의 schema와 동일하게 만든다.
3. 스캔 대상 `.cs` 파일을 수집한다.
   - 제외 디렉터리: `.cache`, `.claire`, `.codenav`, `.git`, `.pytest_cache`, `.worktrees`, `bin`, `obj`, `node_modules`, `packages`, `TestResults`
   - 제외 파일 suffix: `.g.cs`, `.AssemblyAttributes.cs`, `.AssemblyInfo.cs`
4. 각 `.cs` 파일에서 다음을 추출한다.
   - namespace: `namespace Foo.Bar`
   - type: `class`, `interface`, `struct`, `record`
   - class_name
   - XML summary가 있으면 `description` 초기값으로 사용하고, 없으면 빈 문자열
   - method 이름은 public/private/protected/internal/static/virtual/override/abstract/async/sealed 형태의 일반 메서드만 가볍게 추출한다.
5. class name PascalCase를 단어로 쪼개 `tags`를 만든다.
6. `classes`에 `(file, class_name)` 기준으로 upsert한다.
7. 관련 FTS row도 delete/insert 방식으로 동기화한다.
8. 마지막에 전체 건수, solution별 건수, absolute path 잔존 건수, 샘플 3건을 출력한다.

주의:
- 이 커맨드는 빠른 bootstrap/복구용이다. semantic description 품질을 올리는 작업은 나중에 별도 reindex/enrich로 수행한다.
- 실행 전후로 사용자가 만든 manual entry를 삭제하거나 덮어쓰지 않는다.
- 대량 작업이므로 진행 전에 어떤 `repo-root`, `scan-path`, `reset 여부`로 실행하는지 한 줄로 알린다.
