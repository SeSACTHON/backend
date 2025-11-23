# OAuth 리다이렉트 설정

## 환경별 프론트엔드 URL

### Dev/Staging
```
https://frontend.dev.growbin.app   # 권장 (Vercel 커스텀 도메인)
```
> Vercel 기본 도메인(`*.vercel.app`)을 사용하면 growbin.app 쿠키가 전송되지 않으므로 반드시 커스텀 도메인을 연결하세요.

### Prod
```
https://growbin.app
```

## 리다이렉트 경로

### 성공 시
```
${AUTH_FRONTEND_URL}
```
`Settings.frontend_url` (기본: `https://frontend-beta-gray-c44lrfj3n1.vercel.app`)이 사용되며, 환경 변수 `AUTH_FRONTEND_URL` 로 덮어쓸 수 있습니다.

### 실패 시
```
${AUTH_FRONTEND_URL}/login?error=oauth_failed
```
`Settings.oauth_failure_redirect_url` 은 `frontend_url` 값을 기준으로 자동 생성됩니다.

## 프론트엔드 구현

### 홈 페이지 (/)
```javascript
useEffect(() => {
  // 로그인 상태 확인
  const checkAuth = async () => {
    try {
      const response = await fetch('https://api.dev.growbin.app/api/v1/auth/me', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setUser(data.data); // 로그인 상태
      } else {
        setUser(null); // 로그아웃 상태
      }
    } catch (error) {
      setUser(null);
    }
  };
  
  checkAuth();
  
  // URL 쿼리 파라미터 확인
  const params = new URLSearchParams(window.location.search);
  const error = params.get('error');
  
  if (error) {
    showErrorToast('로그인 실패: ' + params.get('message'));
  }
}, []);
```

