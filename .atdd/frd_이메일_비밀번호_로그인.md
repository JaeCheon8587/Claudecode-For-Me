## 기능 요구사항서

### 1. 기능명
이메일/비밀번호 로그인

### 2. API 스펙

| Method | Endpoint | Request Body | Response (200) | 설명 |
|--------|----------|-------------|----------------|------|
| POST | /api/v1/auth/login | `{ email: string, password: string }` | `{ accessToken: string, refreshToken: string, expiresIn: number }` | 이메일/비밀번호로 인증 후 JWT 토큰 발급 |

**에러 응답 포맷**: `{ error: string, code: string }`

| Status | Code | 조건 |
|--------|------|------|
| 400 Bad Request | VALIDATION_ERROR | email 또는 password가 null이거나 빈 문자열 |
| 401 Unauthorized | INVALID_PASSWORD | 비밀번호 불일치 |
| 403 Forbidden | ACCOUNT_DISABLED | 계정 비활성화 |
| 403 Forbidden | ACCOUNT_LOCKED | 계정 잠금 |
| 404 Not Found | USER_NOT_FOUND | 이메일에 해당하는 사용자 미존재 |
| 429 Too Many Requests | RATE_LIMIT_EXCEEDED | Rate Limit 초과 |

### 3. 설명
등록된 이메일과 비밀번호를 입력하여 인증 토큰을 발급받는다. 인증 성공 시 JWT Access Token(30분)과 Refresh Token(7일)을 반환한다. 분리된 에러 응답을 통해 사용자에게 구체적인 실패 사유를 안내하며, Rate Limiting으로 User Enumeration 공격을 방어한다.

### 4. 기능 시나리오

1. **요청 수신** — 클라이언트가 email, password를 POST로 전송한다.
   - 예외: email 또는 password가 null/빈 문자열 → 400 Bad Request (VALIDATION_ERROR)

2. **Rate Limit 확인** — IP 및 이메일 기준으로 요청 빈도를 확인한다.
   - 예외: IP당 분당 10회 초과 → 429 Too Many Requests (RATE_LIMIT_EXCEEDED)
   - 예외: 이메일당 분당 5회 초과 → 429 Too Many Requests (RATE_LIMIT_EXCEEDED)

3. **이메일 정규화 및 사용자 조회** — 이메일을 소문자로 변환한 뒤 DB에서 사용자를 조회한다.
   - 예외: 사용자 미존재 → 404 Not Found (USER_NOT_FOUND)
   - 엣지: 대소문자가 다른 이메일 입력 → 소문자 정규화 후 동일 계정으로 조회

4. **비밀번호 검증** — BCrypt (work factor 12)로 해싱된 비밀번호와 비교한다.
   - 예외: 비밀번호 불일치 → 401 Unauthorized (INVALID_PASSWORD)

5. **계정 상태 확인** — 사용자 계정의 활성화/잠금 상태를 확인한다.
   - 예외: 계정 비활성화 → 403 Forbidden (ACCOUNT_DISABLED), 토큰 발급하지 않음
   - 예외: 계정 잠금 → 403 Forbidden (ACCOUNT_LOCKED), 토큰 발급하지 않음

6. **토큰 발급** — Access Token(JWT, HS256, 30분)과 Refresh Token(7일)을 생성한다.
   - Access Token Claims: sub(userId), email, role, iat, exp
   - Refresh Token: SQL Server에 저장, Rotation 적용 (사용 시 기존 폐기 + 새 토큰 발급)
   - Reuse Detection: 탈취된 토큰 재사용 감지 시 해당 사용자의 모든 Refresh Token 폐기

7. **Audit Log 기록** — 로그인 성공 및 실패 모두를 기록한다.
   - 기록 항목: 이메일, IP, 시각, 성공/실패 사유
   - 비밀번호는 절대 로그에 포함하지 않음

8. **응답 반환** — `{ accessToken, refreshToken, expiresIn: 1800 }` 반환 (expiresIn 단위: 초)

### 5. 보안 고려사항
- 분리된 에러 응답(404/401) 사용 — User Enumeration 위험은 Rate Limiting으로 방어
- Rate Limit: IP당 분당 10회, 이메일당 분당 5회, 초과 시 429 반환
- 비밀번호 해싱: BCrypt (work factor 12), BCrypt.Net-Next 패키지 사용
- Refresh Token Rotation + Reuse Detection으로 토큰 탈취 대응
- Audit Log에 비밀번호를 절대 포함하지 않음

### 6. 성능 고려사항
- BCrypt work factor 12는 해싱에 약 200-300ms 소요 — 로그인 API 응답 시간에 반영
- Refresh Token DB 저장 시 인덱스 설계 필요 (userId, token 값 기준)

### 7. 미해결 항목 ⚠️
- 없음

### 8. 핵심 Q&A 기록

**Q. 에러 응답을 통합(401)할 것인가, 분리(404/401)할 것인가?**
A. 분리 에러 응답 선택. User Enumeration 위험은 Rate Limiting으로 방어.

**Q. Refresh Token의 수명 주기를 어떻게 관리할 것인가?**
A. SQL Server에 저장 + Rotation 적용. 탈취된 토큰 재사용 시 해당 사용자의 모든 토큰 폐기(Reuse Detection).

**Q. 입력값 유효성 검증 범위는?**
A. null/빈 문자열 검증만 수행. 이메일 형식이나 비밀번호 길이 검증은 하지 않음.

**Q. 계정 비활성화/잠금 시 어떻게 처리하는가?**
A. 인증 성공 후 계정 상태 확인. 비활성화/잠금 시 403 Forbidden + 사유 반환.
