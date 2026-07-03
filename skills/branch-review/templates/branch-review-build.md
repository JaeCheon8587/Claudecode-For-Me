# Branch Review Build — {{SLUG}}

## Inputs
- 기준점(ref): {{REF}} (merge-base = {{MERGE_BASE_SHA}})
- HEAD: {{HEAD_SHA}}
- 변경 규모: {{FILES}} files, {{LINES}} lines (+{{ADD}}/-{{DEL}})
- 모드: {{MODE}} (inline | standard | chunk)

{{CHUNK_PLAN_TABLE}}
<!-- chunk 모드일 때만 채움. 형식:
| 청크ID | 디렉터리/파일 | 파일수 | 라인수 |
|---|---|---|---|
-->

## Routing
- Spec source: {{SPEC_LABEL}} [{{SPEC_GRADE}}]
- Standards source: {{STANDARDS_FILES}} [{{STANDARDS_GRADE}}]
- Intent: {{INTENT_TEXT}}

## Guardrails
- read-only — 소스 파일 미수정, 자동 fix 없음, 커밋 없음.
- `.process/`·`.review/` 산출물 쓰기만 허용.
