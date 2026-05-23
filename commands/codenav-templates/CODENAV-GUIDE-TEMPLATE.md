# codenav 사용 가이드 — {프로젝트명}

> ⚠ **TEMPLATE** — `/codenav-install` 슬래시 커맨드가 본 파일을 사용자 워크스페이스의 `Docs/codenav-guide.md` (또는 `docs/codenav-guide.md`) 로 복사한다. `{프로젝트명}` placeholder 는 cwd 디렉토리명으로 치환. 작성 후 본 경고 줄은 삭제한다.

이 워크스페이스는 [codenavigator](https://github.com/JaeCheon8587/codenavigator) 시맨틱 클래스 인덱스 도구를 사용해 C# 코드베이스를 빠르게 탐색한다.

## AI 에이전트 검색 가이드

클래스/심볼을 찾을 때 다음 순서:

1. **`.\codenav.ps1 --root . search "<키워드>"` 먼저** — SQLite FTS5 인덱스. PascalCase 자동 분해 + 한글 bigram 지원.
2. 결과 부족하거나 파일 내부 라인 필요 → Grep / Glob.
3. 결과 0건 + 최근 `.cs` 변경 의심 → `.\codenav.ps1 --root . reindex --changed --no-ai` 후 재검색.

## PreToolUse hook 강제

`.claude/settings.json` 의 PreToolUse hook (`codenav-prefer.ps1`) 가 Grep/Glob 의 첫 C# 검색을 자동 deny → "use: codenav search ..." 안내. 동일 도구 두 번째 호출은 통과 (fallback).

자동 통과 조건:
- C# 시그널 없음 (pattern/glob/path 가 `.cs` 또는 PascalCase 아님).
- `.codenav/index.sqlite` 부재 (인덱스 아직 안 만든 상태).
- stale ratio ≥ 30% (인덱스 신뢰도 낮음 → Grep/Glob 폴백 허용).
- 세션당 도구별 카운터 1회 소진 (deny 한 번 한 뒤엔 자동 통과).

## 도구 위치 (격리 패턴)

| 자원 | 위치 |
|---|---|
| codenav CLI | `Tools/codenavigator/Scripts/codenav.exe` (Windows venv) |
| launcher | `codenav.ps1` (PowerShell), `codenav.sh` (Bash) |
| 인덱스 DB | `.codenav/index.sqlite` (`.gitignore` 처리됨) |
| hook | `.claude/hooks/codenav-prefer.ps1` |

**격리 원칙**: `Tools/codenavigator/` 는 self-contained venv. `.gitignore` 로 commit 차단. 다른 프로젝트와 별개.

## 재인덱싱

`.cs` 추가/수정/삭제 후:

```powershell
.\codenav.ps1 --root . reindex --changed --no-ai   # git staged 파일만
.\codenav.ps1 --root . reindex --full --no-ai      # 전체
```

## Frontmatter 검증 pre-commit hook

`.git/hooks/pre-commit` 에 frontmatter 정합성 검사 자동화 가능 (AI 호출 X, 1초 미만):

```powershell
.\codenav.ps1 --root . frontmatter install-hook        # 설치
.\codenav.ps1 --root . frontmatter install-hook --uninstall   # 제거
```

hook 동작:
- staged `.cs` 의 클래스 검사.
- frontmatter / XML doc 둘 다 없는 클래스 → WARN (commit 허용).
- frontmatter 본문 깨짐 (빈 description, 잘못된 tags, 닫는 `// ---` 누락) → FAIL (commit 차단).
- bypass: `git commit --no-verify`.

수동 검사:
```powershell
.\codenav.ps1 --root . frontmatter check --staged            # staged 만
.\codenav.ps1 --root . frontmatter check --files Foo.cs Bar.cs
.\codenav.ps1 --root . frontmatter check --staged --strict   # WARN 도 exit 1
```

## 슬래시 커맨드

- `/codenav-install` — 도구 셋업 (venv + launcher + hook + Docs/CLAUDE.md 자동).
- `/codenav-bootstrap` — parser-only 인덱스 빌드.
- `/codenav-frontmatter-gen` — AI 가 클래스 description 자동 채움.

CLI 직접 호출 가능 (슬래시 미제공):
- `codenav frontmatter check` — frontmatter 정합성 검증.
- `codenav frontmatter install-hook` — pre-commit hook 설치.

## 검색 점수

- FTS5 `bm25` (class_name 3.0, namespace 2.0, description 1.0, tags 2.0, bigram 1.5).
- tag 정확 매칭 보너스 +2.0/hit.
- PascalCase 자동 분해 (`DataCollector` → `data`, `collector`).
- 한글 bigram (`"문서처리"` → `["문서", "서처", "처리"]`).
- stale 항목도 description 있으면 검색 노출 (`[stale]` 마크).

## 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| `codenav` 명령 못 찾음 | venv 부재 또는 launcher 누락 | `/codenav-install` 재실행 |
| hook 호출 시 에러 | `.claude/hooks/codenav-prefer.ps1` 부재 | `/codenav-install` 로 hook 재설치 |
| Grep/Glob 매번 deny | hook session counter 가 매번 reset (다른 세션) | 정상 동작. fallback 시 두 번째 호출 |
| description 빈 칸 다수 | bootstrap (parser-only) 결과. AI 채움 필요 | `/codenav-frontmatter-gen --apply` |
