# OAuth 로그인 플로우 비교

## ✅ 현재 동작 (v0.8.0 이상)

- 모든 콜백(`google/kakao/naver`)은 성공 시 `Settings.frontend_url` 로 302 리다이렉트, 실패 시 `Settings.oauth_failure_redirect_url` 로 리다이렉트합니다.
- 쿠키(`s_access`, `s_refresh`)는 콜백 내부에서 이미 설정되므로, 프론트는 리다이렉트 이후 `/api/v1/auth/me` 를 호출해 로그인 상태를 확인하기만 하면 됩니다.

### 전체 절차

```
[사용자] -- 1. 로그인 버튼 클릭
[프론트엔드] -- 2. GET /api/v1/auth/{provider}
[백엔드] -- 3. { authorization_url, state, expires_at } 응답
[프론트엔드] -- 4. window.location.href = authorization_url
[프로바이더] -- 5. 사용자 동의 후 /callback?code=...&state=...
[백엔드] -- 6. 로그인 처리 + 쿠키 설정
[백엔드] -- 7. 302 Redirect → {frontend_url} (실패 시 {frontend_url}/login?error=oauth_failed)
[프론트엔드] -- 8. /api/v1/auth/me 호출 → 세션 확인
```

### 성공 시 응답 예시
```
HTTP/1.1 307 Temporary Redirect
Location: https://frontend.dev.growbin.app/
Set-Cookie: s_access=...; HttpOnly; Secure; SameSite=Lax; Domain=.growbin.app
Set-Cookie: s_refresh=...; HttpOnly; Secure; SameSite=Lax; Domain=.growbin.app
```

### 프론트 체크리스트
- 로그인 버튼 → `/api/v1/auth/{provider}` 호출 후 `authorization_url` 로 이동
- 홈/대시보드 진입 시 `/api/v1/auth/me` 호출 (`credentials: 'include'`)
- 401 수신 시 `/api/v1/auth/refresh` → 재시도 (자세한 내용은 `FRONTEND_AUTH_GUIDE.md`)

---

### 전체 절차

```
[사용자]
  ↓ 1. "네이버로 로그인" 버튼 클릭
[프론트엔드]
  ↓ 2. GET /api/v1/auth/naver
[백엔드]
  ↓ 3. { authorization_url: "https://nid.naver.com/..." } 응답
[프론트엔드]
  ↓ 4. window.location.href = authorization_url
[네이버]
  ↓ 5. 사용자 로그인/동의
[네이버]
  ↓ 6. http://localhost:8000/api/v1/auth/naver/callback?code=...&state=...
[백엔드]
  ↓ 7. JSON 응답 + 쿠키 설정
  {
    "success": true,
    "data": {
      "user": { "id": "...", "email": "...", ... }
    }
  }
[브라우저]
  ↓ 8. JSON 화면 표시 (개발자 확인용)
[프론트엔드]
  ↓ 9. /me API 호출하여 로그인 상태 확인
```

### API 엔드포인트

**1단계: Authorization URL 생성**
```bash
GET http://localhost:8000/api/v1/auth/naver
GET http://localhost:8000/api/v1/auth/google
GET http://localhost:8000/api/v1/auth/kakao
```

**응답:**
```json
{
  "success": true,
  "data": {
    "provider": "naver",
    "state": "...",
    "authorization_url": "https://nid.naver.com/oauth2.0/authorize?...",
    "expires_at": "2025-11-20T12:08:17Z"
  }
}
```

**2단계: OAuth 콜백 (자동)**
```
GET http://localhost:8000/api/v1/auth/naver/callback?code=...&state=...
```

**응답:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "5d6adcfa-bde0-46d1-b80a-a4cd67075add",
      "provider": "naver",
      "email": "user@example.com",
      "username": "홍길동",
      "nickname": "홍길동",
      "profile_image_url": null,
      "created_at": "2025-11-20T11:33:18.229787Z",
      "last_login_at": "2025-11-20T11:33:18.242709Z"
    }
  }
}
```

**쿠키 자동 설정:**
- `s_access`: Access Token (15분)
- `s_refresh`: Refresh Token (14일)

**3단계: 로그인 확인**
```bash
GET http://localhost:8000/api/v1/auth/me
```

### 프론트엔드 구현 예시

```javascript
// 1. 로그인 버튼 클릭
async function handleLogin(provider) {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/auth/${provider}`);
    const data = await response.json();
    
    if (data.success) {
      // OAuth 페이지로 이동
      window.location.href = data.data.authorization_url;
    }
  } catch (error) {
    console.error('로그인 실패:', error);
  }
}

// 2. 콜백 후 로그인 확인 (앱 로드 시)
async function checkLoginStatus() {
  try {
    const response = await fetch('http://localhost:8000/api/v1/auth/me', {
      credentials: 'include'
    });
    const data = await response.json();
    
    if (data.success) {
      // 로그인 상태
      console.log('현재 사용자:', data.data);
    }
  } catch (error) {
    // 로그아웃 상태
  }
}
```

### 장점
✅ SPA 친화적  
✅ API 응답을 명확하게 확인 가능  
✅ 프론트엔드가 에러 처리 제어  
✅ 개발/디버깅 용이  

### 단점
❌ 콜백 후 JSON이 브라우저에 표시됨 (UX 개선 필요)  
❌ 프론트엔드에서 추가 처리 필요  

---

## 📋 버전 2: 프론트엔드 리다이렉트 방식

### 특징
- 콜백 엔드포인트가 **프론트엔드로 리다이렉트**
- 전통적인 OAuth 플로우
- 서버 사이드 렌더링(SSR)에 적합

### 전체 절차

```
[사용자]
  ↓ 1. "네이버로 로그인" 버튼 클릭
[프론트엔드]
  ↓ 2. GET /api/v1/auth/naver
[백엔드]
  ↓ 3. { authorization_url: "https://nid.naver.com/..." } 응답
[프론트엔드]
  ↓ 4. window.location.href = authorization_url
[네이버]
  ↓ 5. 사용자 로그인/동의
[네이버]
  ↓ 6. http://localhost:8000/api/v1/auth/naver/callback?code=...&state=...
[백엔드]
  ↓ 7. 로그인 처리 + 쿠키 설정
  ↓ 8. HTTP 302 Redirect
[브라우저]
  ↓ 9. http://localhost:3000/login/success 자동 이동
[프론트엔드]
  ↓ 10. 성공 페이지 표시 + /me API 호출
```

### 콜백 엔드포인트 수정 필요

**현재 (JSON 응답):**
```python
@naver_router.get("/callback", response_model=LoginSuccessResponse)
async def naver_callback(code: str, state: str, ...):
    user = await service.login_with_provider(...)
    return LoginSuccessResponse(data=LoginData(user=user))
```

이 방식은 현재 기본값이 아니지만, 필요 시 `FRONTEND_REDIRECT_URL` 환경 변수를 비워 두고 반환 값을 JSON 으로 유지하도록 커스텀할 수 있습니다.

**현재 기본 (리다이렉트):**
```python
@naver_router.get("/callback")
async def naver_callback(...):
    settings = get_settings()
    try:
        await service.login_with_provider(...)
        return RedirectResponse(url=settings.frontend_url)
    except Exception:
        return RedirectResponse(url=settings.oauth_failure_redirect_url)
```

### 프론트엔드 구현 예시

**로그인 페이지 (동일):**
```javascript
async function handleLogin(provider) {
  const response = await fetch(`http://localhost:8000/api/v1/auth/${provider}`);
  const data = await response.json();
  window.location.href = data.data.authorization_url;
}
```

**성공 페이지 (`/login/success`):**
```javascript
// 자동으로 로그인 완료됨 (쿠키 설정됨)
async function loadUserInfo() {
  const response = await fetch('http://localhost:8000/api/v1/auth/me', {
    credentials: 'include'
  });
  const data = await response.json();
  
  if (data.success) {
    displayUser(data.data);
  }
}

window.onload = loadUserInfo;
```

**에러 페이지 (`/login/error`):**
```javascript
const urlParams = new URLSearchParams(window.location.search);
const errorMessage = urlParams.get('message');
displayError(errorMessage);
```

### 장점
✅ 깔끔한 UX (JSON이 사용자에게 보이지 않음)  
✅ 성공/실패 페이지로 자동 이동  
✅ 전통적인 OAuth 플로우  
✅ 에러 처리가 명확  

### 단점
❌ 프론트엔드 URL 하드코딩 필요  
❌ CORS 설정 더 신경써야 함  
❌ 개발 시 리다이렉트로 인한 디버깅 어려움  

---

## 🎯 권장 사항

### 프로덕션 환경
→ **리다이렉트 방식 (현재 기본값)** 추천
- 사용자가 JSON을 직접 보지 않음
- 성공/실패 UX가 일관됨

### 개발/테스트 환경
→ JSON 응답 모드(레거시)를 일시적으로 유지하고 싶다면 `FRONTEND_REDIRECT_URL` 환경 변수를 비워 두고, 콜백에서 `LoginSuccessResponse` 를 반환하도록 코드를 유지하면 됩니다.
- 디버깅 용이

### 구현 방법
환경 변수로 분기 처리:
```python
FRONTEND_REDIRECT_URL = os.getenv("FRONTEND_REDIRECT_URL")

if FRONTEND_REDIRECT_URL:
    # 리다이렉트 모드
    return RedirectResponse(url=f"{FRONTEND_REDIRECT_URL}/login/success")
else:
    # JSON 응답 모드
    return LoginSuccessResponse(data=LoginData(user=user))
```

---

## 📝 환경 설정

### 환경 변수 추가
```bash
# .env.local (로컬 개발)
FRONTEND_REDIRECT_URL=

# .env.prod (프로덕션)
FRONTEND_REDIRECT_URL=https://growbin.app
```

### OAuth Redirect URI 설정
**네이버/구글/카카오 개발자 콘솔:**
```
http://localhost:8000/api/v1/auth/naver/callback
http://localhost:8000/api/v1/auth/google/callback
http://localhost:8000/api/v1/auth/kakao/callback
```

**배포:**
```
https://dev.api.growbin.app/api/v1/auth/naver/callback
https://dev.api.growbin.app/api/v1/auth/google/callback
https://dev.api.growbin.app/api/v1/auth/kakao/callback
```

