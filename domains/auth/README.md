# Version 0.7.3 - GitOps Deployment

## Local Docker Testing

1. `cp domains/auth/env.local.sample domains/auth/.env.local` 후 OAuth/JWT 값을 채워주세요.
2. `docker compose -f domain/docker-compose.auth-local.yml up --build` (worktree 루트에서 실행).
   - Postgres: `localhost:5433`
   - Redis: `localhost:6380`
3. 테스트 후 `docker compose -f domain/docker-compose.auth-local.yml down -v` 로 정리합니다.

## Remote ArgoCD Sync

Auth 서버 변경 사항을 배포하려면 master, worker-1, worker-2, storage 노드에서 모두 `sync-argocd-all.sh`를 실행해 Wave 전체를 강제 동기화해야 합니다.

```bash
for node in master worker-1 worker-2 storage; do
  SSH_NODE="$node" ./scripts/sync-argocd-all.sh dev
done
```

`scripts/sync-argocd-all.sh`는 로컬에서 AWS CLI로 `k8s-$SSH_NODE` 인스턴스 Public IP를 조회한 뒤 해당 노드로 SSH 접속해 `kubectl` 동기화를 순차 실행합니다. 실행 환경에 SSH 키와 AWS 자격 증명이 준비되어 있어야 합니다.
