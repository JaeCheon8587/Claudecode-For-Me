# docs-check

Run the service-aware documentation harness checker and summarize PASS/WARN/FAIL results.

## Instructions

1. Treat the current working directory as the target repo root unless the user provides another path.
2. Confirm `.claude/docs-harness.config.json` exists in the repo. If missing, report the missing config and stop with the message:
   - "Missing `.claude/docs-harness.config.json`. Create one before running `/docs-check`. See `scripts/docs-harness.config.example.json` in the plugin for the schema."
3. Confirm `scripts/docs_check.py` is available (either in the target repo or via the plugin install path). If absent, report "docs_check.py not found" and stop.
4. Do not modify any files.
5. Run:

   ```bash
   python scripts/docs_check.py --repo .
   ```

6. Summarize:
   - total PASS/WARN/FAIL
   - FAIL items grouped by code (REPO, SERVICE_PATH, FRD_FILE, FRD_ID, FRD_SECTION, FC_FRD_LINK, CLAUDE_INDEX, CONFIG, READ_TEXT)
   - affected service (derived from path)
   - recommended next action
7. Do not automatically edit PRD/FC/FRD/CLAUDE.md.
8. If exit code is 2:
   - Report `FAIL CONFIG` / `FAIL invalid --repo` reason verbatim.
   - Do not retry with a different path unless the user instructs.

## Default paths

If the user does not provide a repo path, use the current working directory.

## Rules

- This command performs checks only.
- Do not auto-fix.
- Do not modify the source repo.
- Even if FAILs are present, report only — do not edit files.
- Follow the `docs-harness` skill rules; do not conflict with `/docs-add-feature` (preview generation, no source mutation).
