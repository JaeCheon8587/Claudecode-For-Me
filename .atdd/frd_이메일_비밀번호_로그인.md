## 기능 요구사항서

### 1. 기능명
이메일/비밀번호 로그인

### 2. API 스펙

| Method | Endpoint | Request Body | Response | 설명 |
|--------|----------|-------------|----------|------|
| POST | /api/v1/auth/login | `{ email: string, password: string }` | `{ accessToken: string, refreshToken: string, expiresIn: number }` | 이메일/비밀번호 인증 후 JWT 토큰 발급 |

**에러 응답:**

| HTTP Status | 에러 코드 | 조건 |
|-------------|----------|------|
| 400 | `VALIDATION_ERROR` | email 형식 불일치, password 길이 위반 등 입력 유효성 실패 |
| 401 | `INVALID_CREDENTIALS` | 이메일 미존재 또는 비밀번호 불일치 (동일 응답으로 User Enumeration 방지) |
| 429 | `RATE_LIMIT_EXCEEDED` | IP 기반 Rate Limit 초과 (Retry-After 헤더 포함) |

### 3. 설명
등록된 이메일과 비밀번호를 입력하여 인증 토큰을 발급받는다. 인증 성공 시 Access Token(30분)과 Refresh Token(7일)을 반환한다. Refresh Token은 Oracle DB에 저장하며, 사용 시 Rotation(새 토큰 발급 + 기존 폐기)을 적용한다.

### 4. 기능 시나리오

1. **클라이언트가 POST /api/v1/auth/login 요청을 전송한다**
   - 예외: Request Body가 null 또는 Content-Type이 application/json이 아님 → 400 `VALIDATION_ERROR`

2. **IP 기반 Rate Limit을 검사한다** — 동일 IP에서 분당 10회 초과 시 차단
   - 예외: Rate Limit 초과 → 429 `RATE_LIMIT_EXCEEDED` + `Retry-After` 헤더 반환
   - 엣지: Rate Limit 카운터는 분 단위로 리셋 (Sliding Window 또는 Fixed Window — 구현 시 결정)

3. **Request Body 유효성을 검증한다**
   - email: RFC 5322 규격, 최대 254자
   - password: 최소 8자, 최대 128자
   - 예외: 유효성 실패 → 400 `VALIDATION_ERROR` + 실패 필드 목록
   - 엣지: 빈 문자열(""), null, 공백만 있는 문자열 → 모두 유효성 실패로 처리

4. **서버가 이메일로 사용자를 조회한다** — Dapper를 사용하여 Oracle DB에서 파라미터 바인딩으로 조회
   - 예외: 사용자 미존재 → **더미 BCrypt 해시와 비교를 수행한 뒤** 401 `INVALID_CREDENTIALS` 반환 (Timing Attack 방어)
   - 엣지: email은 대소문자 구분 없이 조회 (LOWER 비교 또는 DB 컬럼 정규화)

5. **비밀번호를 BCrypt로 검증한다** — BCrypt.Net-Next 라이브러리 사용
   - 예외: 비밀번호 불일치 → 401 `INVALID_CREDENTIALS`
   - 엣지: 사용자 미존재 시에도 동일한 BCrypt.Verify 호출로 응답 시간 균일화 (Step 4에서 처리)

6. **검증 성공 시 Access Token(30분)과 Refresh Token(7일)을 발급한다**
   - Access Token: JWT, Claims = `sub`(사용자 ID) + `email` + `exp` + `iat` + `jti`
   - Refresh Token: 랜덤 문자열 (GUID 또는 crypto-secure random), Oracle DB에 저장
   - 엣지: 기존에 해당 사용자의 유효한 Refresh Token이 있으면 폐기(Revoke)하고 새로 발급 (Rotation)

7. **로그인 결과를 감사 로깅한다** — 성공/실패 모두 기록
   - 기록 항목: IP, email, timestamp, 결과(SUCCESS/FAIL), 실패 사유

8. **응답을 반환한다**
   - 성공: 200 `{ accessToken, refreshToken, expiresIn: 1800 }`
   - expiresIn 단위: 초(seconds)

### 5. 보안 고려사항
- **User Enumeration 방지**: 이메일 미존재와 비밀번호 불일치를 동일한 에러 응답(401 `INVALID_CREDENTIALS`)으로 반환
- **Timing Attack 방어**: 사용자 미존재 시에도 더미 BCrypt 해시와 비교하여 응답 시간 균일화
- **IP 기반 Rate Limit**: 분당 10회, 초과 시 429 + Retry-After
- **Refresh Token DB 저장 + Rotation**: 사용 시 새 토큰 발급, 기존 폐기
- **SQL Injection 방지**: Dapper 파라미터 바인딩 필수
- **감사 로깅**: 모든 로그인 시도를 IP, email, timestamp, 결과와 함께 기록

### 6. 성능 고려사항
- BCrypt 해싱은 CPU-intensive — 비동기 처리 필요
- Oracle DB 조회는 email 컬럼에 인덱스 필요
- Rate Limit 카운터는 인메모리(IMemoryCache 등)로 처리하여 DB 부하 방지

### 7. 미해결 항목
- **JWT Secret Key 관리 방식**: 키 저장 위치(appsettings, 환경 변수, Key Vault), 알고리즘(HS256/RS256), 키 길이 — 인프라 팀과 협의 필요 (DEFERRED)

### 8. 핵심 Q&A 기록

**Q. Refresh Token을 Stateless JWT로 운용할지, DB에 저장할지?**
A. Oracle DB에 저장하고 사용 시 Rotation 적용. 탈취 시 서버 측에서 무효화 가능하도록.

**Q. Brute Force 방어 전략은?**
A. IP 기반 Rate Limit(분당 10회, 429 + Retry-After)만 적용. 계정 잠금(Account Lockout)은 미적용.

**Q. 이메일 미존재와 비밀번호 불일치를 구분할지?**
A. 동일한 401 + INVALID_CREDENTIALS로 반환. User Enumeration 방지 목적.

**Q. Timing Attack은?**
A. 사용자 미존재 시 더미 BCrypt 해시와 비교하여 응답 시간 균일화.

**Q. Refresh Token Rotation은?**
A. 적용. 사용 시 새 토큰 발급 + 기존 토큰 폐기. (1번과 6번 모순 해소 후 확정)

**Q. JWT Secret Key 관리는?**
A. DEFERRED — 인프라 이슈로 분리. 구현 시 appsettings.json 기본값 사용.

**Q. 입력 유효성 규칙은?**
A. email: RFC 5322, 최대 254자. password: 최소 8자 ~ 최대 128자. 위반 시 400 VALIDATION_ERROR.

**Q. Access Token Claims 구성은?**
A. sub(사용자 ID) + email + exp + iat + jti 최소 구성.

**Q. Dapper + Oracle 패키지는?**
A. Dapper + Oracle.ManagedDataAccess.Core 추가 필요.

**Q. 감사 로깅은?**
A. 성공/실패 모두 로깅(IP, email, timestamp, 결과).

### Refresh Token 테이블 스키마

```sql
CREATE TABLE REFRESH_TOKENS (
    TOKEN         VARCHAR2(256)  NOT NULL,
    USER_ID       NUMBER         NOT NULL,
    EXPIRES_AT    TIMESTAMP      NOT NULL,
    IS_REVOKED    NUMBER(1)      DEFAULT 0 NOT NULL,
    CREATED_AT    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_REFRESH_TOKENS PRIMARY KEY (TOKEN),
    CONSTRAINT FK_REFRESH_TOKENS_USER FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID)
);

CREATE INDEX IDX_REFRESH_TOKENS_USER_ID ON REFRESH_TOKENS(USER_ID);
```
