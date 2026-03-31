# 인터페이스 설계서 — 이메일/비밀번호 로그인

## 입력
- FRD: .atdd/frd_이메일_비밀번호_로그인.md

## 1. 레이어 구조

| 레이어 | 책임 | 주요 클래스/모듈 |
|--------|------|-----------------|
| Controller | HTTP 요청 수신, 입력값 유효성 검사(null/빈값), 응답 변환 | `AuthController` |
| Service | 인증 비즈니스 로직(Rate Limit 확인, 이메일 정규화, 비밀번호 검증, 계정 상태 확인, 토큰 발급 위임, Audit Log 기록) | `IAuthService`, `AuthService` |
| Provider | JWT Access Token 생성, Refresh Token 생성 및 Rotation/Reuse Detection | `ITokenProvider`, `TokenProvider` |
| Repository | 사용자 조회(DB), Refresh Token CRUD, Audit Log 저장 | `IUserRepository`, `IRefreshTokenRepository`, `IAuditLogRepository` |

## 2. DTO 정의

### Request DTO

**`LoginRequest`**

| 필드 | 타입 | 유효성 규칙 | 필수 |
|------|------|------------|------|
| `Email` | `string` | null 또는 빈 문자열이면 400 VALIDATION_ERROR | Y |
| `Password` | `string` | null 또는 빈 문자열이면 400 VALIDATION_ERROR | Y |

### Response DTO

**`LoginResponse`**

| 필드 | 타입 | 설명 |
|------|------|------|
| `AccessToken` | `string` | JWT Access Token (HS256, 30분) |
| `RefreshToken` | `string` | Refresh Token (7일) |
| `ExpiresIn` | `int` | Access Token 만료까지 남은 시간(초). 항상 1800 |

### Error Response DTO

**`ErrorResponse`**

| 필드 | 타입 | 설명 |
|------|------|------|
| `Error` | `string` | 사람이 읽을 수 있는 에러 메시지 |
| `Code` | `string` | 기계가 읽을 수 있는 에러 코드 |

**에러 코드 매핑**

| Code | HTTP Status | 조건 |
|------|-------------|------|
| `VALIDATION_ERROR` | 400 | email 또는 password가 null/빈 문자열 |
| `INVALID_PASSWORD` | 401 | 비밀번호 불일치 |
| `ACCOUNT_DISABLED` | 403 | 계정 비활성화 |
| `ACCOUNT_LOCKED` | 403 | 계정 잠금 |
| `USER_NOT_FOUND` | 404 | 이메일에 해당하는 사용자 미존재 |
| `RATE_LIMIT_EXCEEDED` | 429 | IP당 분당 10회 또는 이메일당 분당 5회 초과 |

## 3. 메서드 시그니처

### AuthController
- `Task<IActionResult> Login(LoginRequest request)`: POST /api/v1/auth/login 엔드포인트. 입력값 null/빈값 검증 후 AuthService 호출, 결과에 따라 200 또는 에러 응답 반환

### IAuthService / AuthService
- `Task<LoginResult> LoginAsync(string email, string password, string ipAddress)`: Rate Limit 확인 → 이메일 정규화 → 사용자 조회 → 비밀번호 검증 → 계정 상태 확인 → 토큰 발급 → Audit Log 기록. LoginResult는 성공/실패 + 에러 정보를 포함하는 내부 결과 타입

### ITokenProvider / TokenProvider
- `string GenerateAccessToken(string userId, string email, string role)`: JWT Access Token(HS256, 30분) 생성. Claims: sub, email, role, iat, exp
- `Task<string> GenerateRefreshTokenAsync(string userId)`: Refresh Token 생성 + DB 저장. 기존 토큰이 있으면 Rotation 적용

### IUserRepository
- `Task<User?> FindByEmailAsync(string normalizedEmail)`: 정규화된 이메일로 사용자 조회. 미존재 시 null 반환

### IRefreshTokenRepository
- `Task SaveAsync(string userId, string token, DateTime expiresAt)`: Refresh Token 저장
- `Task RevokeAllByUserIdAsync(string userId)`: 특정 사용자의 모든 Refresh Token 폐기 (Reuse Detection 시)

### IAuditLogRepository
- `Task LogAsync(string email, string ipAddress, DateTime timestamp, bool success, string? failureReason)`: 로그인 시도 기록. 비밀번호는 절대 포함하지 않음

## 4. 의존성 맵

```
AuthController → IAuthService: 로그인 비즈니스 로직 위임
AuthService → ITokenProvider: 토큰 생성 위임
AuthService → IUserRepository: 사용자 조회
AuthService → IRefreshTokenRepository: Refresh Token 저장/폐기
AuthService → IAuditLogRepository: Audit Log 기록
```

## 5. 도메인 모델

### User (Entity)

| 속성 | 타입 | 설명 |
|------|------|------|
| `Id` | `string` | 사용자 고유 ID |
| `Email` | `string` | 정규화된(소문자) 이메일 |
| `PasswordHash` | `string` | BCrypt 해시 (work factor 12) |
| `Role` | `string` | 사용자 역할 |
| `IsActive` | `bool` | 계정 활성화 여부 (false → ACCOUNT_DISABLED) |
| `IsLocked` | `bool` | 계정 잠금 여부 (true → ACCOUNT_LOCKED) |

### LoginResult (Value Object)

| 속성 | 타입 | 설명 |
|------|------|------|
| `Success` | `bool` | 인증 성공 여부 |
| `AccessToken` | `string?` | 성공 시 JWT |
| `RefreshToken` | `string?` | 성공 시 Refresh Token |
| `ExpiresIn` | `int?` | 성공 시 1800 |
| `ErrorCode` | `string?` | 실패 시 에러 코드 |
| `HttpStatus` | `int?` | 실패 시 HTTP 상태 코드 |
| `ErrorMessage` | `string?` | 실패 시 에러 메시지 |

## DEFERRED 항목
- 없음 (FRD 미해결 항목 없음)
