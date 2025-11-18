# Kubernetes 디버깅용 `kubectl` 명령어 모음

## 🎯 문서 목적
- 운영/플랫폼 엔지니어가 클러스터 이슈 발견 시 바로 사용할 수 있는 **명령 템플릿 모음**
- `kubectl` + 표준 리눅스 도구 조합을 통해 **관찰 → 가설 → 검증** 사이클을 빠르게 반복
- 실전에서 자주 등장하는 **문제 상황별 레시피**와 **확장 패턴** 중심으로 정리

---

## 🧪 빠른 문제-명령 매트릭스
| 상황 | 핵심 명령 | 활용 포인트 |
| --- | --- | --- |
| 현재 컨텍스트/네임스페이스 확인 | `kubectl config get-contexts && kubectl config view --minify` | 실수로 다른 클러스터를 건드리는 사고 예방 |
| 전체 노드 상태 & 조건 | `kubectl get nodes -o wide` <br> `kubectl describe node <node>` | Ready/Taint/Allocatable/Metrics 동시 확인 |
| 비정상 Pod 즉시 필터 | `kubectl get pods -A --field-selector status.phase!=Running` | CrashLoopBackOff 등 문제 리소스만 표면화 |
| 배포 롤아웃 추적 | `kubectl rollout status deploy/<name> -n <ns>` | CI/CD 후 상태 안정성 확인 |
| 최근 이벤트 타임라인 | `kubectl get events -A --sort-by=.lastTimestamp | tail -n 40` | 이벤트 기반 RCA 출발점 |
| 컨테이너 로그 | `kubectl logs -n <ns> <pod> -c <container> --tail=200 -f` | 짧은 타임프레임 + 실시간 추적 |
| 네트워크 접근성 | `kubectl exec -it <pod> -- curl -v http://<svc>:<port>` | 서비스 인-클러스터 연결 상태 확인 |
| 임시 진단 Pod | `kubectl run netshoot --rm -it --image=nicolaka/netshoot -- /bin/bash` | CLI 도구 풀세트로 현장 조사 |
| 스토리지 디버깅 | `kubectl describe pvc <name> -n <ns>` | 바인딩 오류, 이벤트 확인 |
| RBAC/권한 체크 | `kubectl auth can-i <verb> <resource> --as <user>` | 접근 거부시 원인 규명 |

---

## 1. 컨텍스트 & 네임스페이스
```bash
# 현재 컨텍스트, 클러스터, 사용자 확인
kubectl config get-contexts
kubectl config current-context
kubectl config view --minify --flatten

# 기본 네임스페이스 변경
kubectl config set-context --current --namespace=<ns>

# 권한 관점에서 내가 할 수 있는 작업
kubectl auth can-i list pods --namespace <ns>
kubectl auth can-i '*' '*' --as <serviceaccount> --namespace <ns>
```

---

## 2. 클러스터 & 노드 상태
```bash
# 노드 현황과 리소스
kubectl get nodes -o wide
kubectl describe node <node>
kubectl top nodes
kubectl top nodes --use-protocol-buffers   # 메트릭 서버 응답 지연 시

# 컨트롤 플레인 헬스 엔드포인트
kubectl get --raw='/readyz?verbose'
kubectl get --raw='/livez?verbose'

# 노드 조건 (NotReady, DiskPressure 등)만 필터
kubectl get nodes \
  --no-headers \
  | awk '$2!="Ready"{print}'

# 노드별 문제 Pod 목록
kubectl get pods -A --field-selector spec.nodeName=<node>
```

- **Taint/Label 확인**: `kubectl describe node <node> | egrep 'Taints|Labels'`
- **CRI 컨테이너 런타임 체크**: `kubectl get node <node> -o jsonpath='{.status.nodeInfo.containerRuntimeVersion}'`

---

## 3. 워크로드 (Deployment/StatefulSet/DaemonSet)
```bash
# Deployment 전반
kubectl get deploy -A -o wide
kubectl describe deploy <name> -n <ns>
kubectl rollout status deploy/<name> -n <ns>
kubectl rollout history deploy/<name> -n <ns>

# 빠른 비정상 상태 감지
kubectl get deploy -A \
  --no-headers \
  | awk '$4!=$5 || $5==0'

# StatefulSet & DaemonSet
kubectl get sts -A -o wide
kubectl get ds -A -o wide
kubectl describe ds <name> -n <ns>

# 이미지 강제 새로고침 (강제 재배포)
kubectl rollout restart deploy/<name> -n <ns>
```

- **HPA 연동 상태**: `kubectl describe hpa <name> -n <ns>`
- **Job/CronJob 실패 건수**: `kubectl get jobs -A --sort-by=.status.startTime`

---

## 4. Pod 디버깅 패턴
```bash
# 상태별 필터
kubectl get pods -A --field-selector status.phase!=Running
kubectl get pods -n <ns> -o wide --watch

# 상세 원인 조사
kubectl describe pod <pod> -n <ns>
kubectl get pod <pod> -n <ns> -o yaml

# 환경 변수, 마운트, 이미지 확인
kubectl exec -n <ns> <pod> -- env
kubectl exec -n <ns> <pod> -- mount

# 컨테이너 재시작/CrashLoop 원인
kubectl logs <pod> -n <ns> --previous

# 특정 필드 기반 검색 (예: Pending)
kubectl get pods -A --field-selector=status.phase==Pending
```

- **PodDisruptionBudget 영향**: `kubectl describe pdb -A`
- **노드 할당 실패 메시지**: `kubectl describe pod | grep -A5 "Events"`에서 SchedulingFailures 확인

---

## 5. 이벤트 & 감사 타임라인
```bash
# 최근 이벤트 40건 (전역)
kubectl get events -A --sort-by=.lastTimestamp | tail -n 40

# 특정 리소스에 대한 이벤트
kubectl describe pod <pod> -n <ns> | sed -n '/Events/,$p'
kubectl events -n <ns> --for Pod/<pod>

# 원인 필터링 (ex. OOMKilled)
kubectl get events -A --field-selector='reason=OOMKilled'

# watch 모드
kubectl events -A --watch --types Warning,Normal
```

> **Tip:** `kubectl events` 플러그인은 1.26+에서 기본 제공. 이전 버전은 `kubectl get events` 사용.

---

## 6. 로그 & Exec
```bash
# 단일 컨테이너 로그
kubectl logs -n <ns> <pod> -c <container> --tail=200 -f

# 이전 컨테이너 인스턴스
kubectl logs -n <ns> <pod> -c <container> --previous

# 여러 Pod를 label selector로 묶어 보기
kubectl logs -n <ns> -l app=<label> --all-containers=true

# Busybox/Alpine 쉘 접근
kubectl exec -it -n <ns> <pod> -- /bin/sh
kubectl exec -it -n <ns> <pod> -- bash -c 'ps aux'

# 애플리케이션 포트 헬스 체크
kubectl exec -it <pod> -n <ns> -- curl -vk http://127.0.0.1:<port>/healthz
```

- **멀티컨테이너 Pod**: `kubectl logs <pod> --all-containers`
- **JSON 로그**: `kubectl logs <pod> | jq '.'`

---

## 7. 네트워크/서비스 진단
```bash
# Service / Endpoint 대응
kubectl get svc -A -o wide
kubectl describe svc <name> -n <ns>
kubectl get endpoints <name> -n <ns> -o wide
kubectl get endpointslice -n <ns> -l kubernetes.io/service-name=<name>

# 네트워크 정책 영향
kubectl get networkpolicy -A
kubectl describe networkpolicy <np> -n <ns>

# port-forward로 로컬에서 재현
kubectl port-forward svc/<svc-name> 8080:<targetPort> -n <ns>

# 인-클러스터 연결 시험
kubectl exec -it <pod> -n <ns> -- curl -v http://<svc>.<ns>.svc.cluster.local:<port>
kubectl exec -it <pod> -n <ns> -- nc -zvw2 <ip> <port>
```

- **DNS 확인**: `kubectl exec -it <pod> -- nslookup <svc>.<ns>.svc`
- **네트워크 패킷 캡처**: `kubectl exec -it <pod> -- tcpdump -i eth0 port <port>`

---

## 8. 임시 디버그 Pod & 컨테이너
```bash
# Netshoot 기반 툴킷
kubectl run netshoot \
  --rm -it --restart=Never \
  --image=nicolaka/netshoot \
  -- bash

# Busybox 단발성 테스트
kubectl run tmp-shell \
  --rm -it --restart=Never \
  --image=busybox \
  -- /bin/sh

# 기존 Pod 옆에 디버그 컨테이너 붙이기 (Ephemeral Container)
kubectl debug -n <ns> pod/<pod> -it --image=nicolaka/netshoot

# 노드 수준 디버그 (chroot)
kubectl debug node/<node> -it --image=registry.k8s.io/e2e-test-images/node-debug:latest \
  -- chroot /host
```

> **권장 이미지**: `nicolaka/netshoot`, `praqma/network-multitool`, `busybox`, `curlimages/curl`

---

## 9. 스토리지 (PVC/PV/CSI)
```bash
# PVC/PV 상태
kubectl get pvc -A -o wide
kubectl describe pvc <name> -n <ns>
kubectl get pv -o wide

# 바인딩 이벤트 추적
kubectl get events -A --field-selector=involvedObject.kind=PersistentVolumeClaim

# CSI 드라이버 & 노드 플러그인
kubectl get csidrivers
kubectl get ds -n kube-system -l app=csi-node

# Pod 내 마운트 확인
kubectl exec -it <pod> -n <ns> -- df -h | grep <mountPath>
```

---

## 10. 자원 사용 & 스케일
```bash
# 메트릭 API
kubectl top pods -A --containers
kubectl top pods -n <ns> --sort-by=cpu

# HPA & VPA
kubectl describe hpa <name> -n <ns>
kubectl get hpa -A -o wide

# 노드 자원 요약
kubectl describe node <node> | sed -n '/Allocated resources/,/Events/p'
```

- **스케줄 불가 원인**: `kubectl describe pod | grep -A3 '0/.* nodes are available'`
- **리밋 폭주 감시**: `kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\t"}{.status.qosClass}{"\n"}{end}'`

---

## 11. RBAC & 보안
```bash
# 서비스어카운트 토큰 문제
kubectl describe secret $(kubectl get sa <sa> -n <ns> -o jsonpath='{.secrets[0].name}')

# 권한 매트릭스 훑기
kubectl get rolebinding,clusterrolebinding --all-namespaces
kubectl describe clusterrole <name>

# API 접근 시험
kubectl auth can-i list secrets --as system:serviceaccount:<ns>:<sa>
kubectl get --raw='/apis' | jq '.groups[].name'
```

---

## 12. 레이블/셀렉터 활용 패턴
```bash
# 공통 레이블로 서비스맵 만들기
kubectl get pods -A -l app=<app> -o custom-columns='NAMESPACE:.metadata.namespace,POD:.metadata.name,NODE:.spec.nodeName,IMAGE:.spec.containers[*].image'

# 필드 셀렉터 템플릿
kubectl get pods -A --field-selector spec.nodeName=<node>
kubectl get pods -A --field-selector status.hostIP=<ip>
kubectl get pods -A --field-selector metadata.namespace!=kube-system
```

---

## 13. 자동 진단 번들
```bash
# 전체 상태 덤프
OUT=/tmp/cluster-dump-$(date +%Y%m%d-%H%M)
kubectl cluster-info dump \
  --all-namespaces \
  --output-directory="${OUT}"

# 네임스페이스 단위 덤프
kubectl cluster-info dump --namespaces <ns> > /tmp/<ns>-dump.yaml

# 리소스 API 목록
kubectl api-resources --sort-by=name
kubectl api-versions
```

---

## 14. 운영 팁
- **일관된 출력 포맷**: `-o wide`, `-o yaml`, `-o jsonpath`를 상황에 맞게 활용하여 자동화 스크립트에 쉽게 연결한다.
- **watch와 jq 조합**: `watch -n 2 "kubectl get pods -A -o json | jq '.items[] | select(.status.phase!=\"Running\") | {ns:.metadata.namespace,name:.metadata.name,phase:.status.phase}'"` 패턴을 자주 쓰는 필터로 저장해두면 효율적이다.
- **명령 히스토리 공유**: 장애 대응 후 `kubectl` 명령 이력과 출력 예시를 Runbook에 추가해 재현 가능성을 높인다.
- **Stern/ktrace 활용**: Pod 다중 로그 tail이 필요하면 `stern`과 같은 외부 CLI를 보조로 사용한다.
- **kubectl 플러그인**: `kubectl-neat`, `kubectl-tree`, `kubectl-debug` 등 krew 기반 플러그인을 설치해 디버깅 시간을 단축한다.

---

### ✅ 다음 단계 제안
1. 실제 운영에서 자주 쓰는 커맨드를 추려 `docs/troubleshooting/` 하위 Runbook과 링크.
2. `krew` 플러그인 사용법, `stern`, `ksniff` 등 외부 CLI도 본 문서에 후속 섹션으로 확장.

