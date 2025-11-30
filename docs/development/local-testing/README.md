# 로컬 도메인 테스트 안내

프론트엔드 팀에서 각 도메인 API를 손쉽게 검증할 수 있도록, 공통 준비 사항과 도메인별 가이드를 정리했습니다. 아래 순서를 따르면 모든 서비스를 동일한 패턴으로 실행·종료할 수 있습니다.

## 1. 공통 준비물

- **필수 도구**: Python 3.12, Docker Desktop(또는 호환되는 컨테이너 런타임), `docker compose`, `curl`.
- **권장**: `direnv` 또는 `.envrc`를 이용해 서비스별 환경 변수를 쉽게 토글합니다.
- **외부 키**
  - `OPENAI_API_KEY`: Scan/Chat에서 이미지 분류 또는 GPT 응답이 필요할 때 필수입니다. (없으면 Scan은 실행 실패, Chat은 폴백 답변 제공)
  - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`: Image API가 S3에 Presigned URL을 발급하려면 필요합니다.

## 2. 가상환경 & 의존성

모든 명령은 `backend/` 루트에서 실행한다고 가정합니다.

```bash
cd /Users/mango/workspace/SeSACTHON/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# 필요할 때마다 도메인 requirements 설치
pip install -r domains/<domain>/requirements.txt
```

## 3. 빠른 헬스체크

각 가이드는 `pytest domains/<domain>/tests` 로 최소 Smoke 테스트를 먼저 실행하도록 안내합니다. 모든 도메인에 대해 2025-11-27 기준으로 테스트를 통과했음을 확인했습니다.

## 4. 인증 우회 규칙

- Auth 서비스를 제외한 모든 도메인은 `*_AUTH_DISABLED=true` 환경 변수를 제공하며, 기본값은 `false`입니다.
- 토큰 검증이 필요 없는 시나리오라면 `export <DOMAIN>_AUTH_DISABLED=true` 만으로 JWT 쿠키 없이도 요청을 통과시킬 수 있습니다.
- 실제 세션 쿠키를 확인하려면 `domains/auth/docker-compose.auth-local.yml` 로 Auth 스택을 함께 띄우고, 각 도메인의 `*_AUTH_DISABLED` 값을 `false` 로 바꿉니다.

## 5. 도메인별 문서

| Domain | 기본 포트 | Auth 우회 변수 | 문서 경로 |
| ------ | --------- | -------------- | --------- |
| Auth | 8000 | (없음) | [`auth.md`](./auth.md) |
| My | 8002 | `MY_AUTH_DISABLED` | [`my.md`](./my.md) |
| Scan | 8003 | `SCAN_AUTH_DISABLED` | [`scan.md`](./scan.md) |
| Character | 8004 | `CHARACTER_AUTH_DISABLED` | [`character.md`](./character.md) |
| Location | 8010 | `LOCATION_AUTH_DISABLED` | [`location.md`](./location.md) |
| Image | 8020 | `IMAGE_AUTH_DISABLED` | [`image.md`](./image.md) |
| Chat | 8030 | `CHAT_AUTH_DISABLED` | [`chat.md`](./chat.md) |
| Info | 8040 | (Public) | [`info.md`](./info.md) |

필요한 도메인의 문서를 펼쳐서 상세 절차(uvicorn 실행, docker compose 스택, 인증 토글 방법, 샘플 curl)를 확인하세요.

