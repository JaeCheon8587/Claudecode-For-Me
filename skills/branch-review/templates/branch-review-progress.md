# Branch Review Progress — {{SLUG}}

## Stage Status
| Stage | Status |
|---|---|
| Step1-기준점 | pending |
| Step2-모드결정 | pending |
| Step3-라우팅 | pending |
| Step4-finder실행 | pending |
| Step5-집계 | pending |
| Step6-보고 | pending |

{{CHUNK_STATUS_TABLE}}
<!-- chunk 모드일 때만 채움(표준/인라인 모드는 단일 가상 청크 "C0" 1행). 형식:
## Chunk Status
| Chunk | 디렉터리/파일 | Status | Findings(b/s/sp/p) |
|---|---|---|---|
-->

## Log (append-only)
<!-- 각 Stage/Chunk 완료 시 1개 항목 추가. 형식:
- <Step 또는 Chunk 이름>: <done|blocked> — <한줄 요약>
  (Chunk 완료 항목은 4 finder raw 출력을 verbatim으로 여기 넣지 않는다 — 대신
   `.process/branch-review-<slug>/chunk-<id>.log`에 별도 저장하고 여기엔 그 경로만
   참조로 남긴다. resume 시 그 파일을 Read해 재실행 없이 재사용한다.)
-->
