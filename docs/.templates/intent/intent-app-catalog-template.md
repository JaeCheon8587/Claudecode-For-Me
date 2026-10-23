# intent-app-catalog — Intent App Catalog

> ⚠ **TEMPLATE** — 이 파일은 **참고용 예시**다. 실제 `intent/intent-app-catalog.md` 는 손으로 만들지 않는다 — `python ~/.claude/plugins/cache/claudecode-for-me/claudecode-for-me/<버전>/scripts/docs_helpers.py intent-catalog --repo . --app {app} --write` 가 App 카탈로그(`intent/{app}/intent-catalog.md`)를 쓰면서 `intent/` 를 훑어 함께 생성한다. `intent/` 는 **커밋하지 않는다**.
>
> 상위 카탈로그는 **Intent 진입점**이다. 문서는 `.git/info/exclude` 에 올라 있어 검색 도구(Grep · Glob — ripgrep 기반)가 건너뛴다. 세션은 링크를 따라 찾는다 — `CLAUDE.md` → 이 파일 → App 카탈로그 → Intent.
>
> 모든 열은 Intent 문서의 메타 `상태` 와 폴더 구성에서 **파생**된다. 손으로 고치지 않는다 — `docs_helpers.py check` 가 불일치를 `INT_APP_CATALOG` FAIL 로 잡는다.
>
> 식별자 규약은 [DOCUMENT_GUIDE §5](../docs/DOCUMENT_GUIDE.md#5-식별자-규약) 참조.

## 생성 결과 예시

| 열 | 출처 |
|---|---|
| App | `intent/` 아래 폴더 이름 (소문자) — Intent 가 하나 이상 있는 폴더만 |
| 카탈로그 | 그 App 카탈로그 링크 (`{app}/intent-catalog.md`) |
| Intents | 그 폴더의 `{app}-int-{NNN}.md` 수 |
| active · retired | 메타 `상태` 별 수 |

```markdown
# intent-app-catalog — Intent App Catalog

> **생성물** — `docs_helpers.py intent-catalog --repo . --app <app> --write` 가 App 카탈로그와 함께 `intent/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — Intent 문서를 고치고 재생성한다. `check` 가 불일치를 FAIL 로 잡는다.

| 항목 | 값 |
|---|---|
| 문서 ID | intent-app-catalog |
| 생성 | docs_helpers.py intent-catalog |
| 대상 | [intent 폴더](./) |

| App | 카탈로그 | Intents | active | retired |
|---|---|---|---|---|
| loader | [loader-intent-catalog](loader/intent-catalog.md) | 3 | 2 | 1 |
| viewer | [viewer-intent-catalog](viewer/intent-catalog.md) | 1 | 1 | 0 |

apps: 2
```

## 재생성 시점

App 카탈로그를 다시 쓰는 모든 지점(`intent-catalog --app <app> --write`)에서 함께 다시 쓴다 — 시점 표는 [App 카탈로그 템플릿](app/intent-catalog-template.md#재생성-시점) 과 같다. 빠뜨려도 `check` 가 `INT_APP_CATALOG stale` 로 잡는다.
