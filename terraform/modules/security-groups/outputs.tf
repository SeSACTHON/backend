output "cluster_sg_id" {
  description = "클러스터 보안 그룹 ID (master & worker 통합)"
  value       = aws_security_group.k8s_cluster.id
}

output "alb_sg_id" {
  description = "ALB 보안 그룹 ID"
  value       = aws_security_group.alb.id
}

# 하위 호환성을 위한 별칭 (deprecated)
output "master_sg_id" {
  description = "[DEPRECATED] Use cluster_sg_id instead"
  value       = aws_security_group.k8s_cluster.id
}

output "worker_sg_id" {
  description = "[DEPRECATED] Use cluster_sg_id instead"
  value       = aws_security_group.k8s_cluster.id
}
