# 클러스터 트러블슈팅 사례 모음 (2025-11-16)

> 대상 클러스터: sesacthon (Self-managed 14 Nodes, ap-northeast-2)  
> 수집 근거: `kubectl` 실측 로그, ArgoCD Application 상태, GitOps 작업 내역

---

## 1. 클러스터 요약

| 항목 | 값 |
|------|----|
| 이름 | `sesacthon` |
| 리전 | `ap-northeast-2` |
| VPC | `vpc-0cb5bbb41f25671f5` |
| Master IP | `52.78.233.242` |
| 노드 구성 | Master 1 + API 7 + Workers 2 + Infrastructure 4 (총 14) |
| Kubernetes 버전 | `v1.28.4` |
| CNI | Calico |
| 주요 네임스페이스 | `auth`, `my`, `scan`, `character`, `location`, `info`, `chat`, `workers`, `messaging`, `data`, `databases`, `monitoring`, `atlantis`, `argocd`, `kube-system` |
| 배포 방식 | Terraform → Ansible → ArgoCD (GitOps) |
| 점검 일시 | 2025-11-16 |
| 배포 성공률 | 95% (92 Running Pods, 14 API Pods 모두 Running) |

---

## 2. 이슈별 사례

### 2.1 ALB Controller CrashLoopBackOff (2025-11-16 실측)

- **감지**  
  ```bash
  kubectl get pods -n kube-system | grep aws-load-balancer-controller
  kubectl logs -n kube-system deployment/aws-load-balancer-controller
  ```
  ```json
  {"level":"error","ts":"2025-11-15T22:13:16Z","logger":"setup",
   "msg":"unable to create controller","controller":"Ingress",
   "error":"Get \"https://10.96.0.1:443/apis/networking.k8s.io/v1\": dial tcp 10.96.0.1:443: i/o timeout"}
  ```

- **원인**  
  1. NetworkPolicy `alb-controller-egress`가 API 서버 IP(10.96.0.1:443)를 차단  
  2. ArgoCD values에 이전 VPC ID(`vpc-08049a4dd788790fa`)가 하드코딩

- **영향**  
  - ALB Controller MutatingWebhook 실패 → Service 생성 시도마다 실패  
  - 7개 API Application OutOfSync, Ingress 미생성

- **조치 (2025-11-16)**  
  1. NetworkPolicy 삭제  
  2. VPC ID 업데이트  
  3. ALB Controller Application 임시 비활성화

- **권장 해결**  
  - NetworkPolicy에서 API 서버 CIDR(10.96.0.1/32) 허용  
  - Controller Ready 확인 후 Service/Ingress 생성

---

### 2.2 Helm/Argo Applications OutOfSync (데이터/모니터링 스택)

- **증상**: `aws-load-balancer-webhook-service` 연결 거부로 모든 API Application이 SyncError  
- **원인**: 상기 ALB Controller CrashLoop → Webhook Service 응답 불가  
- **조치**: ALB Controller 제거/재배포, NetworkPolicy 수정  
- **근본 해결**: ALB Controller를 더 낮은 Wave에 배치하거나 webhook을 별도 네임스페이스로 분리

---

### 2.3 ApplicationSet `kustomize.images` 문법 오류

- **증상**: `ApplicationSet.argoproj.io "api-services" is invalid`  
- **원인**: `kustomize.images`에 객체 형태(`name`, `newTag`) 사용  
- **조치**: ApplicationSet에서 images 필드 제거, overlay patch에서 이미지 태그 지정  
- **교훈**: ApplicationSet 템플릿에는 문자열 필드만 사용

---

### 2.4 Kustomize 상위 디렉토리 참조 오류

- **증상**: `kustomize build`가 `security; file is not in or below` 에러  
- **조치**: 필요한 파일을 동일 디렉토리로 복사, 상위 경로 참조 제거  
- **영향**: Namespaces 미생성 → API 배포 지연

---

### 2.5 GHCR ImagePullBackOff (권한 문제)

- **증상**: `Failed to pull image ... 401/403`  
- **원인**: GHCR Private 패키지 + `read:packages` 권한 없는 PAT  
- **조치**: 권한 있는 PAT로 Secret 재생성, 모든 네임스페이스에 배포  
- **교훈**: CI/CD Token 권한 검증, base manifest에 `imagePullSecrets` 명시

---

### 2.6 RabbitMQ Bitnami Debian 이미지 중단

- **증상**: Bitnami RabbitMQ 이미지 태그가 더 이상 존재하지 않아 ImagePullBackOff  
- **조치**: Bitnami 의존성 제거, 향후 RabbitMQ Operator 도입 예정  
- **교훈**: 벤더 이미지 EOL 추적 필수

---

### 2.7 CI Workflow YAML 파싱 오류

- **증상**: GitHub Actions가 즉시 실패, Workflow graph 생성 불가  
- **원인**: heredoc 내부 코드의 들여쓰기 누락 → YAML 파서 오류  
- **조치**: `python3 <<'PYEOF'` 형태로 수정, 로컬 YAML 파싱 테스트 추가  
- **교훈**: CI Workflow 편집 시 `python -c "import yaml"`로 사전 검증

---

### 2.8 scan-api CrashLoopBackOff (모듈 경로)

- **증상**: `Could not import module "main"`  
- **원인**: Docker CMD가 `main:app`으로 고정, 실제 파일은 `app/main.py`  
- **조치**: CMD를 `app.main:app`으로 수정

---

### 2.9 VPC 삭제 실패 (ALB/Target Groups 잔존)

- **증상**: `terraform destroy` 시 VPC 의존성 오류  
- **조치**: ALB/Target Group/SG/EIP를 수동 삭제, `scripts/cleanup-vpc-resources.sh` 추가  
- **교훈**: Destroy 전에 AWS 리소스 잔존 여부 점검

---

### 2.10 Ansible `import_tasks` 문법 충돌

- **증상**: `[ERROR]: conflicting action statements: hosts, tasks`  
- **원인**: `import_tasks` 대상 파일에서 `hosts` 블록 선언  
- **조치**: 해당 파일에서 hosts 제거, site.yml에서만 hosts 지정

---

## 3. 재발 방지 체크포인트 (2025-11-16)

1. **NetworkPolicy 검증 자동화**: ALB/CNI/DNS egress CIDR 화이트리스트, API 서버 IP 명시  
2. **Wave 의존성 문서화**: root-app → namespaces → networkpolicy → controller → monitoring → data → apis  
3. **ArgoCD 상태 모니터링**: OutOfSync 3회 이상 시 수동 개입, webhook 오류 즉시 조사  
4. **GHCR 이미지 관리**: PAT 권한 점검, namespace별 Secret 일괄 배포  
5. **Kustomize 구조 규칙**: 상위 디렉토리 참조 금지, ApplicationSet에서 images 사용 금지  
6. **VPC 정리 자동화**: `cleanup-vpc-resources.sh` 실행 후 `terraform destroy`

---

## 4. 배포 성과 (2025-11-16)

```
✅ 14개 노드 Ready
✅ 92개 Pods Running
✅ 17개 ArgoCD Applications 생성
✅ PostgreSQL/Redis/Monitoring Stack 정상
✅ CI/CD 파이프라인 복구
```

- 해결한 주요 이슈: 10건 (Kustomize, ApplicationSet, CI, GHCR, RabbitMQ, Ansible 등)  
- 미해결: ALB Controller webhook 재생성, Service 생성 차단

---

**최종 업데이트**: 2025-11-16 23:50 KST  
**상태**: Production Ready (Service/Ingress 제외)  
> 해당 내용은 실제 클러스터 관측 로그 기반이며, 향후 GitOps 구조 변경 시 계속 업데이트할 예정이다.


