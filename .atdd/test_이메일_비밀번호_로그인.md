# 수용 테스트 명세 — 이메일/비밀번호 로그인

## 입력
- FRD: .atdd/frd_이메일_비밀번호_로그인.md
- 설계서: .atdd/design_이메일_비밀번호_로그인.md

## 테스트 케이스

### TC-01: 정상 로그인 성공
- **Given**: 이메일 "user@example.com", 비밀번호 BCrypt 해시(work factor 12)가 저장된 활성 사용자가 존재한다. 계정은 활성화(IsActive=true) 상태이고 잠금되지 않은(IsLocked=false) 상태이다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "user@example.com", "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 200 OK 응답. Body에 `accessToken`(비어있지 않은 JWT 문자열), `refreshToken`(비어있지 않은 문자열), `expiresIn: 1800`이 포함된다.

### TC-02: email이 null인 경우
- **Given**: 어떤 사전 조건도 필요 없다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": null, "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 400 Bad Request 응답. Body: `{ "error": "...", "code": "VALIDATION_ERROR" }`.

### TC-03: email이 빈 문자열인 경우
- **Given**: 어떤 사전 조건도 필요 없다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "", "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 400 Bad Request 응답. Body: `{ "error": "...", "code": "VALIDATION_ERROR" }`.

### TC-04: password가 null인 경우
- **Given**: 어떤 사전 조건도 필요 없다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "user@example.com", "password": null }`를 전송한다.
- **Then**: 400 Bad Request 응답. Body: `{ "error": "...", "code": "VALIDATION_ERROR" }`.

### TC-05: password가 빈 문자열인 경우
- **Given**: 어떤 사전 조건도 필요 없다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "user@example.com", "password": "" }`를 전송한다.
- **Then**: 400 Bad Request 응답. Body: `{ "error": "...", "code": "VALIDATION_ERROR" }`.

### TC-06: IP당 Rate Limit 초과 (분당 10회 초과)
- **Given**: 동일 IP에서 지난 1분간 10회의 로그인 요청이 이미 수행되었다.
- **When**: POST /api/v1/auth/login 으로 11번째 요청을 전송한다.
- **Then**: 429 Too Many Requests 응답. Body: `{ "error": "...", "code": "RATE_LIMIT_EXCEEDED" }`.

### TC-07: 이메일당 Rate Limit 초과 (분당 5회 초과)
- **Given**: 이메일 "user@example.com"으로 지난 1분간 5회의 로그인 요청이 이미 수행되었다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "user@example.com", "password": "any" }` 6번째 요청을 전송한다.
- **Then**: 429 Too Many Requests 응답. Body: `{ "error": "...", "code": "RATE_LIMIT_EXCEEDED" }`.

### TC-08: 이메일 대소문자 정규화
- **Given**: 이메일 "user@example.com"으로 등록된 활성 사용자가 존재한다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "User@Example.COM", "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 200 OK 응답. 소문자 정규화 후 동일 계정으로 인증 성공. Body에 `accessToken`, `refreshToken`, `expiresIn: 1800`이 포함된다.

### TC-09: 존재하지 않는 이메일
- **Given**: 이메일 "nonexist@example.com"으로 등록된 사용자가 존재하지 않는다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "nonexist@example.com", "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 404 Not Found 응답. Body: `{ "error": "...", "code": "USER_NOT_FOUND" }`.

### TC-10: 비밀번호 불일치
- **Given**: 이메일 "user@example.com"으로 등록된 활성 사용자가 존재한다. 저장된 비밀번호 해시는 "P@ssw0rd123"에 대응한다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "user@example.com", "password": "WrongPassword" }`를 전송한다.
- **Then**: 401 Unauthorized 응답. Body: `{ "error": "...", "code": "INVALID_PASSWORD" }`.

### TC-11: 계정 비활성화
- **Given**: 이메일 "disabled@example.com"으로 등록된 사용자가 존재한다. 비밀번호는 올바르지만 IsActive=false이다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "disabled@example.com", "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 403 Forbidden 응답. Body: `{ "error": "...", "code": "ACCOUNT_DISABLED" }`. 토큰이 발급되지 않는다.

### TC-12: 계정 잠금
- **Given**: 이메일 "locked@example.com"으로 등록된 사용자가 존재한다. 비밀번호는 올바르지만 IsLocked=true이다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "locked@example.com", "password": "P@ssw0rd123" }`를 전송한다.
- **Then**: 403 Forbidden 응답. Body: `{ "error": "...", "code": "ACCOUNT_LOCKED" }`. 토큰이 발급되지 않는다.

### TC-13: Access Token Claims 검증
- **Given**: userId="u-001", email="user@example.com", role="member"인 활성 사용자가 존재한다.
- **When**: POST /api/v1/auth/login 으로 정상 인증을 수행하고 반환된 accessToken을 디코딩한다.
- **Then**: JWT Claims에 `sub: "u-001"`, `email: "user@example.com"`, `role: "member"`, `iat`(발급 시각), `exp`(iat + 1800초)가 포함된다. 알고리즘은 HS256이다.

### TC-14: Refresh Token DB 저장 확인
- **Given**: 활성 사용자가 존재한다.
- **When**: POST /api/v1/auth/login 으로 정상 인증을 수행한다.
- **Then**: IRefreshTokenRepository.SaveAsync가 호출되어 userId, token 값, 만료일(7일 후)이 저장된다.

### TC-15: Audit Log — 성공 기록
- **Given**: 활성 사용자 "user@example.com"이 존재한다.
- **When**: POST /api/v1/auth/login 으로 정상 인증을 수행한다 (IP: "192.168.1.1").
- **Then**: IAuditLogRepository.LogAsync가 호출된다. 기록: email="user@example.com", ip="192.168.1.1", success=true, failureReason=null. 비밀번호는 로그에 포함되지 않는다.

### TC-16: Audit Log — 실패 기록 (비밀번호 불일치)
- **Given**: 활성 사용자 "user@example.com"이 존재한다.
- **When**: POST /api/v1/auth/login 으로 잘못된 비밀번호를 전송한다 (IP: "192.168.1.1").
- **Then**: IAuditLogRepository.LogAsync가 호출된다. 기록: email="user@example.com", ip="192.168.1.1", success=false, failureReason="INVALID_PASSWORD". 비밀번호는 로그에 포함되지 않는다.

### TC-17: Audit Log — 실패 기록 (사용자 미존재)
- **Given**: "ghost@example.com"으로 등록된 사용자가 존재하지 않는다.
- **When**: POST /api/v1/auth/login 으로 `{ "email": "ghost@example.com", "password": "any" }`를 전송한다 (IP: "10.0.0.1").
- **Then**: IAuditLogRepository.LogAsync가 호출된다. 기록: email="ghost@example.com", ip="10.0.0.1", success=false, failureReason="USER_NOT_FOUND".

## 커버리지 매핑

| FRD 시나리오 단계 | 테스트 케이스 |
|-------------------|--------------|
| 1. 요청 수신 — 정상 | TC-01 |
| 1. 예외 — email null/빈값 | TC-02, TC-03 |
| 1. 예외 — password null/빈값 | TC-04, TC-05 |
| 2. Rate Limit — IP당 분당 10회 초과 | TC-06 |
| 2. Rate Limit — 이메일당 분당 5회 초과 | TC-07 |
| 3. 이메일 정규화 — 대소문자 정규화 | TC-08 |
| 3. 예외 — 사용자 미존재 | TC-09 |
| 4. 비밀번호 검증 — 성공 | TC-01 |
| 4. 예외 — 비밀번호 불일치 | TC-10 |
| 5. 계정 상태 — 비활성화 | TC-11 |
| 5. 계정 상태 — 잠금 | TC-12 |
| 6. 토큰 발급 — Access Token Claims | TC-13 |
| 6. 토큰 발급 — Refresh Token 저장 | TC-14 |
| 7. Audit Log — 성공 기록 | TC-15 |
| 7. Audit Log — 실패 기록 | TC-16, TC-17 |
| 8. 응답 반환 — 정상 | TC-01 |

## DEFERRED 항목
- 없음 (FRD 미해결 항목 없음)
