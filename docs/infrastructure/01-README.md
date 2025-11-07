# 🏗️ Infrastructure 문서

> **13-Node Kubernetes 클러스터 인프라**  
> **Terraform + Ansible + AWS**  
> **최적화 버전 (v0.6.0): 15 vCPU, $238/월**

## 📚 문서 목록

### 네트워크 설계

1. **[VPC 네트워크 설계](03-vpc-network-design.md)** ⭐⭐⭐⭐⭐
   - VPC (10.0.0.0/16)
   - 3 Public Subnets
   - Security Groups 전체
   - 포트 목록 상세

### Kubernetes 구축

2. **[IaC 구성 (Terraform + Ansible)](04-iac-terraform-ansible.md)** ⭐⭐⭐⭐⭐
   - 자동화 스크립트
   - Terraform 구조
   - Ansible Playbook
   - 40-50분 자동 배포

### CNI

3. [CNI 비교 (Calico vs Flannel)](06-cni-comparison.md)
   - Flannel → Calico 전환
   - VXLAN vs BGP
   - 성능 비교

---

## 🎯 빠른 참조

```
자동 배포:
./scripts/cluster/auto-rebuild.sh

구성 (최적화):
- 13 nodes
- 15 vCPU (16 한도 내)
- 38GB RAM
- $238/월

노드 상세:
- Master: 1 × t3.large (2 vCPU)
- API: 6 × t3.micro/small (6 vCPU)
- Worker: 2 × t3.small (2 vCPU)
- Infrastructure: 4 × t3.small/medium (5 vCPU)
```

---

**최종 업데이트**: 2025-11-07  
**상태**: 프로덕션 준비 완료  
**버전**: v0.6.0 (13-Node + WAL 최적화)
