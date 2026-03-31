## 기능 요구사항서

### 1. 기능명
이메일/비밀번호 로그인

### 2. API 스펙

| Method | Endpoint | Request Body | Response (성공) | Response (실패) | 설명 |
|--------|----------|-------------|----------------|----------------|------|
| POST | /api/v1/auth/login | `{ email: string, password: string }` | `{ accessToken: string, refreshToken: string, expiresIn: number }` | `{ statusCode: number, message: string, error: string }` | 이메일/비밀번호로 인증 후 토큰 발급 |

### 3. 설명
등록된 이메일과 비밀번호를 입력하여 인증 토큰을 발급받는다. 인증 성공 시 Access Token(30분)과 Refresh Token(7일)을 반환한다. NestJS + TypeScript 기반으로 구현한다.

### 4. 기능 시나리오

1. **사용자가 이메일과 비밀번호를 입력한다** — 클라이언트에서 POST /api/v1/auth/login 호출
   - 예외: 이메일 또는 비밀번호가 빈 값/null → 400 Bad Request, "이메일과 비밀번호를 입력해 주세요"
   - 예외: IP/이메일 기준 Rate Limit 초과 → 429 Too Many Requests, "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요"

2. **서버가 이메일로 사용자를 조회한다** — DB에서 이메일로 사용자 레코드 조회
   - 예외: 이메일에 해당하는 사용자가 존재하지 않음 → 401 Unauthorized, "존재하지 않는 이메일입니다"

3. **비밀번호를 검증한다** — 입력된 비밀번호와 저장된 해시를 비교
   - 예외: 비밀번호 불일치 → 401 Unauthorized, "비밀번호가 올바르지 않습니다"

4. **검증 성공 시 Access Token(30분)과 Refresh Token(7일)을 발급한다** — JWT 토큰 생성

5. **토큰을 응답으로 반환한다** — `{ accessToken, refreshToken, expiresIn: 1800 }` 형태로 응답

### 5. 보안 고려사항
- 로그인 실패 시 이메일 미존재와 비밀번호 불일치를 **분리된 에러 메시지**로 응답한다 (사용자 편의성 우선).
- Account Enumeration 공격을 완화하기 위해 **IP/이메일 기준 Rate Limit**을 적용한다.

### 6. 성능 고려사항
- 해당 없음 (세션에서 논의되지 않음)

### 7. 미해결 항목 ⚠️
- Rate Limit의 구체적 임계값 미결정 (IP당 분당 허용 횟수, 이메일별 실패 시 잠금 정책 등)
- Refresh Token 저장 전략 미논의 (DB 저장 vs Redis 등)
- Refresh Token 갱신/폐기 전략 미논의
- 비활성/탈퇴 계정 로그인 시도 처리 미논의
- 비밀번호 해싱 알고리즘 미논의 (bcrypt, argon2 등)
- Access Token / Refresh Token 전달 방식 미논의 (Response Body vs Cookie)

### 8. 핵심 Q&A 기록

**Q. 로그인 실패 시 에러 응답을 통합 메시지로 할지 분리 메시지로 할지?**
A. 분리 에러 메시지 선택 — "존재하지 않는 이메일"과 "비밀번호 불일치"를 구분하여 사용자 편의성을 높인다.

**Q. 분리 에러 메시지로 인한 Account Enumeration 위험을 어떻게 대응할지?**
A. 분리 에러를 유지하되 IP/이메일 기준 Rate Limit을 추가하여 대량 열거 공격을 완화한다.
