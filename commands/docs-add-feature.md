# docs-add-feature

Create a preview-only feature documentation update (1 new FRD + FC `## 추가 기능` row) for a service registered in `.claude/docs-harness.config.json`. The real source repo is never modified.

## Instructions

1. Treat the current working directory as the target repo root unless the user provides another repo path.
2. Do not modify the source repo under any circumstances.
3. Confirm `.claude/docs-harness.config.json` exists. If missing, report:
   - "Missing `.claude/docs-harness.config.json`. Create one before running `/docs-add-feature`. See `scripts/docs-harness.config.example.json` for the schema."
   - Stop.
4. Require or infer these four inputs:
   - target repo path
   - service name (must match a `services[].name` in the config)
   - feature JSON path
   - preview-dir path (must be outside the target repo)
5. If `scripts/docs_add_feature.py` does not exist, report "docs_add_feature.py not found" and stop.
6. If `scripts/docs_check.py` does not exist, report "docs_check.py not found" and stop.
7. Verify the feature JSON path exists. If missing, report and stop.
8. Run:

   ```bash
   python scripts/docs_add_feature.py --repo "<repo>" --service "<service>" --feature "<feature.json>" --preview-dir "<preview-dir>"
   ```

9. The `--preview-dir` must be outside the target repo. The tool itself rejects an inside-repo path with `FAIL ARGS --preview-dir must be outside --repo`.
10. Summarize the output:
    - created FRD path
    - updated FC path
    - `Summary: <P> PASS, <W> WARN, <F> FAIL`
    - `Preview Summary: <C> CREATE, <U> UPDATE, <X> CONFLICT, <S> SKIP, <CF> CHECK_FAIL`
    - exit code (0, 1, or 2) and absolute preview-dir path
11. If exit code is 0:
    - State that preview generation succeeded.
    - State that the source repo was not modified.
    - Tell the user to manually inspect the preview-dir.
12. If exit code is 1:
    - Summarize CONFLICT and CHECK_FAIL items grouped by code.
    - Do not auto-fix.
13. If exit code is 2:
    - Summarize the `FAIL ARGS` / `FAIL FEATURE` / `FAIL REPO` / `FAIL PREVIEW` / `FAIL CONFIG` reason verbatim.
    - Do not retry with a different path unless the user instructs.
14. Never auto-copy preview files into the source repo.
15. Never auto-edit PRD / FC / FRD / CLAUDE.md.

## Default paths

If the user does not provide paths, use:

- target repo: current working directory
- feature JSON: `<repo>/.claude/feature.json` if present, else ask the user
- preview-dir: `<repo-parent>/.preview-<service-lower>-feature`

Important:

- Never place `--preview-dir` inside the target repo.
- Default preview-dir is the parent directory of the repo, not the repo itself.

## Rules

- Preview-only.
- No source repo mutation.
- No automatic merge into the source repo.
- Always run through `docs_add_feature.py`. The checker result is produced by that command internally via `docs_check.run_checks`.
- If the user asks to apply the preview to the source repo, stop and ask for explicit confirmation plus a separate apply plan. Do not apply in this command.
- Feature JSON must not contain `service`, `id`, or `project_code`. Unknown keys are rejected with `FAIL FEATURE unknown feature key: <key>`.
- `api_paths` may contain route braces like `{id}`; backtick, pipe, and newline are forbidden in any list item.
- Follow the `docs-harness` skill rules; do not conflict with `/docs-check` (check-only, no mutation).

## Expected success output

```
CREATE Docs/<Service>/FRD/FRD-<CODE>-FNNN.md
UPDATE Docs/<Service>/FC-<CODE>-001.md
Summary: <N> PASS, 0 WARN, 0 FAIL
Preview Summary: 1 CREATE, 1 UPDATE, 0 CONFLICT, 0 SKIP, 0 CHECK_FAIL
```
