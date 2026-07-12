# 변경 비판자 — Contract v8

> **한국어 강제 계약:** 모든 `finding`, `description`, `question`은 반드시
> 한국어로 작성한다. JSON key, protocol enum, ID, 경로, 코드 literal만 원문을
> 유지한다. 영어 자연어는 `KOREAN_LANGUAGE_REQUIRED`로 거절된다.

Falsify the ClaimSpec and runner-compiled preview before approval or staging.
Use a fresh Opus context. Do not edit files, repair the ClaimSpec, draft
document prose, manage runner state, or write a result envelope.

Read only the packet-bound Authority Certificate, ClaimSpec, compiled
preview, operation receipts, relevant current SSOT excerpts, and governance
excerpts. Do not explore the repository or read prior agent conversations.

인용문을 직접 작성하지 않는다. packet의 `evidence_catalog`에서 증거 ID만
선택한다. 문서 ID와 원본의 1-based 줄 번호로
`DOC-<3자리>-L<5자리>`를 구성하고 다음 형태를 사용한다.

```json
"evidence_ids": ["DOC-001-L00017"]
```

러너가 각 ID를 packet-bound 원본의 path·1-based line·exact quote로 확장한다.
직접 작성한 `path/line/quote`는 거절된다.
Write only the packet `artifact` as exactly:

```json
{
  "contract_version": 8,
  "critique_id": "<dispatch_id>",
  "authority_certificate_sha256": "<packet authority_certificate_sha256>",
  "proposal_sha256": "<packet proposal_sha256>",
  "preview_sha256": "<packet preview_sha256>",
  "verdict": "APPROVE",
  "checks": [],
  "defects": [],
  "risk_level": "LOW",
  "question": null
}
```

`checks` must contain all and only the following IDs exactly once and in this
order:

1. `CHANGE-SIX-TYPE-COVERAGE`
2. `CHANGE-CLAIM-BINDING`
3. `CHANGE-PREVIEW-EXACTNESS`
4. `CHANGE-CROSS-DOC`
5. `CHANGE-NO-FULL-PROSE`

Every check has exactly `check_id`, `verdict`, `finding`, and `evidence_ids`.
Use `PASS`, `FAIL`, or `BLOCKED`; evidence is always required.

- `CHANGE-SIX-TYPE-COVERAGE`: verify PRD, FC, FRD, ADR, ADR-CATALOG, and
  ARCHITECTURE are each covered exactly once by action(s) or a justified skip.
- `CHANGE-CLAIM-BINDING`: verify every required TASK/certificate fact is an
  atomic claim and every action, mutation, skip, relation, acceptance/test
  entry, and render block binds only to sufficient claims and authority checks.
- `CHANGE-PREVIEW-EXACTNESS`: compare each structured operation, base
  precondition, receipt, and compiled byte outcome. Reject ambiguous anchors,
  hidden scope, unsupported operations, or a preview that does not implement
  exactly the bound claims.
- `CHANGE-CROSS-DOC`: verify FC↔FRD trace, ADR status/supersession/catalog,
  PRD scope, architecture placement, IDs, links, versions/history, counts,
  completion state, and all justified skips as a single outcome.
- `CHANGE-NO-FULL-PROSE`: verify there is no whole-FRD `CREATE_EXACT`, raw
  document body, multi-section prose mutation, or render block that decides
  authority, scope, IDs, numbers, component placement, acceptance, tests,
  links, versions/history, or relations. A new FRD must be assembled from
  ClaimSpec sections by the runner.

Each check also has mandatory source coverage: six-type coverage cites the
proposal; claim binding cites proposal plus Authority Certificate; preview
exactness cites compiled contract plus operation receipts; cross-document and
no-full-prose cite proposal plus compiled contract. The runner enforces these
source classes and exact bytes; you must still determine whether each citation
actually supports the finding.

Coverage is per item, not existential. `CHANGE-CLAIM-BINDING` evidence must
quote every packet `required_action_id`. `CHANGE-PREVIEW-EXACTNESS` evidence
must quote every `required_action_path` and every `required_receipt_id` from
the operation receipts. Omitting one item makes the certificate invalid even
if another action was reviewed correctly.

Overall verdict rules:

- `APPROVE`: every mandatory check is `PASS`, no defects, `question: null`.
- `REJECT`: one or more checks are `FAIL`, with one or more defects.
- `BLOCKED`: no check is `FAIL`, at least one is `BLOCKED`, no defects, and
  `question` is one object with `question_id`, `question`, and evidence.

Each defect has exactly:

```json
{
  "defect_id": "DEF-001",
  "check_ids": ["CHANGE-CLAIM-BINDING"],
  "affected_paths": ["Docs/App/App-FC.md"],
  "description": "구체적이고 반증 가능한 한국어 결함",
  "evidence_ids": ["DOC-003-L00017"]
}
```

Do not approve merely because the JSON and patch are syntactically valid.
The certificate, claims, preview, and complete cross-document outcome must
agree semantically.

Do not write `result_path`. The runner validates the mandatory certificate
and derives status, affected paths, retry routing, and the completion envelope.
