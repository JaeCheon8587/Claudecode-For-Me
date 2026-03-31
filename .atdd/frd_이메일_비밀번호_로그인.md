## 기능 요구사항서

### 1. 기능명
이메일/비밀번호 로그인

### 2. API 스펙

| Method | Endpoint | Request Body | Response | 설명 |
|--------|----------|-------------|----------|------|
| POST | /api/v1/auth/login | `{ email: string, password: string }` | `{ accessToken: string, refreshToken: string, expiresIn: number }` | 이메일/비밀번호 인증 후 토큰 발급 |

### 3. 설명
등록된 이메일과 비밀번호를 입력하여 인증 토큰을 발급받는다. 인증 성공 시 JWT 기반 Access Token(30분)과 GUID 기반 Refresh Token(7일)을 반환한다. 보안을 위해 로그인 실패 시 이메일/비밀번호 구분 없이 통합 에러 메시지를 반환하며, 5회 연속 실패 시 15분 계정 잠금을 적용한다.

### 4. 기능 시나리오

1. **입력값 검증** — 이메일과 비밀번호의 유효성을 검사한다.
   - 예외: 이메일이 빈 값 → 400 Bad Request (`"email 필드는 필수입니다"`)
   - 예외: 비밀번호가 빈 값 → 400 Bad Request (`"password 필드는 필수입니다"`)
   - 예외: 이메일 형식 오류 → 400 Bad Request (`"올바른 이메일 형식이 아닙니다"`)

2. **이메일 정규화** — 입력된 이메일을 소문자로 변환한다.
   - 엣지: `User@Email.COM` → `user@email.com`으로 정규화 후 조회

3. **계정 잠금 확인** — 해당 이메일의 로그인 실패 횟수를 확인한다.
   - 예외: 5회 연속 실패로 잠금 상태 → 429 Too Many Requests (`"계정이 일시적으로 잠금되었습니다. {남은시간}분 후 다시 시도해 주세요"`)

4. **사용자 조회** — 정규화된 이메일로 사용자를 조회한다.
   - 예외: 이메일에 해당하는 사용자 없음 → 401 Unauthorized (`"이메일 또는 비밀번호가 올바르지 않습니다"`)

5. **비밀번호 검증** — BCrypt로 해싱된 비밀번호와 입력 비밀번호를 비교한다.
   - 예외: 비밀번호 불일치 → 실패 횟수 증가 + 401 Unauthorized (`"이메일 또는 비밀번호가 올바르지 않습니다"`)
   - 엣지: 이메일 미존재와 비밀번호 불일치 모두 동일한 401 메시지 반환 (User Enumeration 방지)

6. **계정 상태 확인** — 인증 성공 후 계정 활성 상태를 검사한다.
   - 예외: 비활성화/정지된 계정 → 403 Forbidden (`"계정이 비활성화되었습니다"`)

7. **토큰 발급** — Access Token과 Refresh Token을 생성한다.
   - Access Token: JWT(HS256), 만료 30분, Claim에 userId와 email 포함
   - Refresh Token: GUID 랜덤 문자열, 만료 7일, ITokenRepository를 통해 저장
   - 로그인 실패 횟수 초기화
   - 응답: `{ accessToken, refreshToken, expiresIn: 1800 }`

### 5. 보안 고려사항
- 이메일 미존재와 비밀번호 불일치를 동일한 에러 메시지로 처리하여 User Enumeration 공격 방지
- BCrypt를 사용한 비밀번호 해싱/검증 (IPasswordHasher 인터페이스로 추상화)
- 5회 연속 로그인 실패 시 15분 계정 잠금으로 Brute Force 방지
- 잠금 상태에서 로그인 시도 시 429 Too Many Requests 반환

### 6. 성능 고려사항
- 해당 없음 (현재 스코프에서 특별한 성능 요구사항 없음)

### 7. 미해결 항목 ⚠️
- [DEFERRED] Refresh Token 저장소의 실제 DB 구현 (현재는 ITokenRepository 인터페이스만 정의)

### 8. 핵심 Q&A 기록

**Q. 로그인 실패 시 에러 메시지를 이메일/비밀번호 별로 구분할 것인가?**
A. 통합 메시지 사용. "이메일 또는 비밀번호가 올바르지 않습니다"로 통일하여 User Enumeration 공격을 방지한다.

**Q. 비활성화/정지 계정의 로그인 시도는 어떻게 처리하는가?**
A. 인증 성공 후 계정 상태를 검사하여 403 Forbidden으로 구분 처리. 401과 분리하여 사용자에게 명확한 안내 제공.

**Q. Refresh Token 저장 전략은?**
A. ITokenRepository 인터페이스로 추상화. 테스트에서는 Mock 사용, 실제 DB 구현은 후속 작업으로 DEFERRED.

**Q. 토큰 생성 방식은?**
A. Access Token은 JWT(HS256, 30분), Refresh Token은 GUID(7일). JWT Claim에 userId, email 포함.

**Q. 비밀번호 해싱은?**
A. BCrypt 사용. IPasswordHasher 인터페이스로 추상화하되 기본 구현은 BCrypt.

**Q. 로그인 시도 횟수 제한은?**
A. 5회 연속 실패 시 15분 계정 잠금. 잠금 상태에서는 429 반환. 성공 시 실패 횟수 초기화.
