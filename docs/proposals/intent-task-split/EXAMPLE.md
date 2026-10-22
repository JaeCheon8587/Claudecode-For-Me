# 예시 — 초안 템플릿으로 쓴 Intent · Task

초안 템플릿([APP-INT-001-TEMPLATE.md](APP-INT-001-TEMPLATE.md) · [TSK-001-TEMPLATE.md](TSK-001-TEMPLATE.md))을 따라 쓴 예시입니다. 가상의 레포 `upload-suite`에 App 두 개(LOADER · VIEWER)가 있다고 가정합니다.

## 1. 여러 App에 걸친 계약 변경 — 업로드 재시도 (기능개발)

LOADER가 업로드 재시도를 하고 응답에 재시도 횟수를 담습니다. VIEWER는 그 값을 받아 표시합니다.

### 1.1 Intent를 먼저 고친 결과 (Part 2 발췌)

`docs/LOADER/INTENT/LOADER-INT-003.md` (업로드):

```markdown
### Functional requirements
- FR-1. 업로드는 파일 하나를 받아 저장하고 저장 결과를 응답한다. (D1)
- FR-2. 업로드 결과 응답에 처리 시간과, 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1, D2) [TSK-012 진행 중]
- FR-4. 업로드가 일시 오류로 실패하면 설정 키 `upload.retry.max` 횟수만큼 다시 시도한다. (D2) [TSK-012 진행 중]

### Edge cases
- E-4. 재시도 끝에 성공해도 파일은 한 번만 저장된다. (FR-4) [TSK-012 진행 중]

### Error cases
- X-2. 0바이트 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)
- X-3. 재시도가 모두 실패하면 상태 코드 `503` 과 오류 코드 `UPLOAD_RETRY_EXHAUSTED` 를 반환한다. (FR-4) [TSK-012 진행 중]
```

`docs/VIEWER/INTENT/VIEWER-INT-001.md` (업로드 목록):

```markdown
### Functional requirements
- FR-5. 업로드 목록은 응답 필드 `retryCount` 가 1 이상인 항목에 문구 "재시도 후 완료" 를 표시한다. (D3) [TSK-012 진행 중]
```

(FR-3은 예전 Task에서 지운 항목입니다. 번호는 재사용하지 않습니다.)

### 1.2 거기서 뽑아낸 Task — `.task/TSK-012.md`

```markdown
# TSK-012 — 업로드 일시 오류 자동 재시도

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-012 |
| 유형 | 기능개발 |
| 상태 | approved |
| 대상 Intent | LOADER-INT-003 · VIEWER-INT-001 |
| 작성 | 홍길동 · 2026-10-22 |
| 승인 | 홍길동 · 2026-10-22 |
| 검증 | PASS — code PASS · llm PASS · 1/3 |

## Goal
- 계기: 네트워크 일시 오류로 업로드가 실패해 사용자가 다시 올리는 문의가 반복된다.
- 완료 상태: 일시 오류는 사용자가 다시 올리지 않아도 재시도로 복구되고, 업로드 목록에서 재시도가 있었는지 보인다. 끝내 실패하면 원인을 알 수 있는 오류 코드가 돌아온다.

## Scope
- 변경 · LOADER-INT-003 FR-2. 업로드 결과 응답에 처리 시간과, 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1, D2)
  - 이전: 업로드 결과 응답에 처리 시간을 담는다. (D1)
- 신규 · LOADER-INT-003 FR-4. 업로드가 일시 오류로 실패하면 설정 키 `upload.retry.max` 횟수만큼 다시 시도한다. (D2)
- 신규 · LOADER-INT-003 E-4. 재시도 끝에 성공해도 파일은 한 번만 저장된다. (FR-4)
- 신규 · LOADER-INT-003 X-3. 재시도가 모두 실패하면 상태 코드 `503` 과 오류 코드 `UPLOAD_RETRY_EXHAUSTED` 를 반환한다. (FR-4)
- 신규 · VIEWER-INT-001 FR-5. 업로드 목록은 응답 필드 `retryCount` 가 1 이상인 항목에 문구 "재시도 후 완료" 를 표시한다. (D3)

- Out of scope: 업로드 화면의 재시도 진행 표시 (후속 Task)

## Acceptance
- [ ] A-1. 일시 오류가 두 번 난 뒤 성공하는 업로드는 성공 응답을 받고, 응답 필드 `retryCount` 가 2다. (LOADER-INT-003 FR-4, LOADER-INT-003 FR-2)
- [ ] A-2. 설정 키 `upload.retry.max` 가 1이면 재시도는 한 번만 일어난다. (LOADER-INT-003 FR-4)
- [ ] A-3. 일시 오류가 계속되면 상태 코드 `503` 과 오류 코드 `UPLOAD_RETRY_EXHAUSTED` 가 돌아온다. (LOADER-INT-003 X-3)
- [ ] A-4. 권한 없음처럼 일시 오류가 아닌 실패는 다시 시도하지 않는다. (LOADER-INT-003 FR-4)
- [ ] A-5. 일시 오류 한 번 뒤 성공한 업로드는 파일이 한 번만 저장된다. (LOADER-INT-003 E-4)
- [ ] A-6. LOADER 가 응답 필드 `retryCount` 2 를 돌려준 업로드는 VIEWER 업로드 목록에 문구 "재시도 후 완료" 로 보인다. (LOADER-INT-003 FR-2, VIEWER-INT-001 FR-5)
- [ ] A-7. 응답 필드 `retryCount` 가 없는 응답을 받으면 VIEWER 는 문구를 표시하지 않고 목록을 정상으로 보여 준다. (R-2)

## Verification
- 일시 오류를 흉내 내는 자동 테스트로 A-1 ~ A-5 를 확인한다.
- 두 App 을 함께 띄운 통합 확인으로 A-6 을, 필드가 빠진 응답을 흉내 내는 테스트로 A-7 을 확인한다.

## Risks
- R-1. 배포 전에 이미 실패한 업로드는 자동으로 다시 시도되지 않는다 → 배포 안내에 적는다.
- R-2. VIEWER 가 LOADER 보다 먼저 배포되면 응답 필드 `retryCount` 가 없는 응답을 받는다 → 필드가 없어도 목록이 깨지지 않는지 A-7 로 확인한다.

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | upload-suite · LOADER, VIEWER |
| base branch | main |
| 브랜치명 | task/TSK-012 |
| 손대지 말 영역 | `src/Loader.Billing/` |
| 완료 보고 방식 | 마감 보고 파일 + 채팅 요약 |
```

### 1.3 이 예시에서 각 항목이 놓인 자리

- **A-6**: App 사이의 완료 조건입니다. App마다 Task를 나눴다면 둘 곳이 없었습니다.
- **E-4** (중복 저장 방지): 작업이 끝난 뒤에도 유지되는 동작이라 Intent에 들어갔고, Scope 사본과 A-5로 판정됩니다.
- **R-1, R-2**: 배포 시점에만 생기는 상황이라 Task의 Risks에 남았습니다. R-2(App별 배포 순서)는 대비를 확인해야 해서 A-7이 `(R-2)`를 근거로 씁니다.
- **FR-2의 `이전` 줄**: Intent에는 바뀐 뒤 문장만 남으므로, 무엇이 바뀌었는지 보이는 곳은 여기뿐입니다. 이 Task를 취소(`dropped`)하면 이 줄로 FR-2를 되돌립니다.

### 1.4 마감 뒤 (forge-scope `in-review` 전이 커밋, 워크트리 안)

진행 표시만 지워지고 문장은 그대로입니다. 브랜치가 머지되면 코드와 함께 main에 반영됩니다.

```markdown
- FR-2. 업로드 결과 응답에 처리 시간과, 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1, D2)
- FR-4. 업로드가 일시 오류로 실패하면 설정 키 `upload.retry.max` 횟수만큼 다시 시도한다. (D2)
```

## 2. 버그수정 — Intent는 고치지 않음

`.task/TSK-011.md` (메타 표 · Verification · Risks · Handoff 생략):

```markdown
# TSK-011 — 업로드 0바이트 파일 거부

## Goal
- 계기: 크기가 0인 파일로 API `POST /uploads` 를 호출하면 상태 코드 `201` 이 돌아오고 빈 파일이 저장된다.
- 완료 상태: 0바이트 파일 업로드는 거부되고 아무것도 저장되지 않는다.

## Scope
- 위반 · LOADER-INT-003 X-2. 0바이트 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)

- Out of scope: 최대 크기 초과 파일 처리

## Acceptance
- [ ] A-1. 크기가 0인 파일로 API `POST /uploads` 를 호출하면 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 가 돌아오고 아무것도 저장되지 않는다. (LOADER-INT-003 X-2)
```

'위반' 항목에는 진행 표시를 붙이지 않습니다. X-2 문장은 이미 참이어야 하는 동작이기 때문입니다.

## 3. 이 예시에 나오는 이름

- **밖에서 보이는 이름만 나옵니다**: API `POST /uploads`, 응답 필드 `retryCount`, 설정 키 `upload.retry.max`, 상태 코드 `201` · `400` · `503`, 오류 코드 `UPLOAD_EMPTY_FILE` · `UPLOAD_RETRY_EXHAUSTED`, 화면 문구 "재시도 후 완료", App 코드 LOADER · VIEWER
- **경로**: Handoff `손대지 말 영역`의 폴더 경로 `src/Loader.Billing/` 하나
- **나오지 않는 것**: 클래스 · 인터페이스 · 메서드 · 속성 · 파일명
