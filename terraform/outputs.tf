output "master_public_ip" {
  description = "Master 노드 Public IP (Elastic IP)"
  value       = aws_eip.master.public_ip
}

output "master_private_ip" {
  description = "Master 노드 Private IP"
  value       = module.master.private_ip
}

output "worker_1_public_ip" {
  description = "Worker 1 Public IP"
  value       = module.worker_1.public_ip
}

output "worker_1_private_ip" {
  description = "Worker 1 Private IP"
  value       = module.worker_1.private_ip
}

output "worker_2_public_ip" {
  description = "Worker 2 Public IP"
  value       = module.worker_2.public_ip
}

output "worker_2_private_ip" {
  description = "Worker 2 Private IP"
  value       = module.worker_2.private_ip
}

output "ansible_inventory" {
  description = "Ansible Inventory 내용"
  value = templatefile("${path.module}/templates/hosts.tpl", {
    master_public_ip       = aws_eip.master.public_ip
    master_private_ip      = module.master.private_ip
    worker_1_public_ip     = module.worker_1.public_ip
    worker_1_private_ip    = module.worker_1.private_ip
    worker_2_public_ip     = module.worker_2.public_ip
    worker_2_private_ip    = module.worker_2.private_ip
    rabbitmq_public_ip     = module.rabbitmq.public_ip
    rabbitmq_private_ip    = module.rabbitmq.private_ip
    postgresql_public_ip   = module.postgresql.public_ip
    postgresql_private_ip  = module.postgresql.private_ip
    redis_public_ip        = module.redis.public_ip
    redis_private_ip       = module.redis.private_ip
    monitoring_public_ip   = module.monitoring.public_ip
    monitoring_private_ip  = module.monitoring.private_ip
  })
}

output "ssh_commands" {
  description = "SSH 접속 명령어"
  value = {
    master     = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${aws_eip.master.public_ip}"
    worker_1   = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${module.worker_1.public_ip}"
    worker_2   = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${module.worker_2.public_ip}"
    rabbitmq   = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${module.rabbitmq.public_ip}"
    postgresql = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${module.postgresql.public_ip}"
    redis      = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${module.redis.public_ip}"
    monitoring = "ssh -i ~/.ssh/sesacthon.pem ubuntu@${module.monitoring.public_ip}"
  }
}

output "rabbitmq_public_ip" {
  description = "RabbitMQ 노드 Public IP"
  value       = module.rabbitmq.public_ip
}

output "rabbitmq_private_ip" {
  description = "RabbitMQ 노드 Private IP"
  value       = module.rabbitmq.private_ip
}

output "postgresql_public_ip" {
  description = "PostgreSQL 노드 Public IP"
  value       = module.postgresql.public_ip
}

output "postgresql_private_ip" {
  description = "PostgreSQL 노드 Private IP"
  value       = module.postgresql.private_ip
}

output "redis_public_ip" {
  description = "Redis 노드 Public IP"
  value       = module.redis.public_ip
}

output "redis_private_ip" {
  description = "Redis 노드 Private IP"
  value       = module.redis.private_ip
}

output "monitoring_public_ip" {
  description = "Monitoring 노드 Public IP"
  value       = module.monitoring.public_ip
}

output "monitoring_private_ip" {
  description = "Monitoring 노드 Private IP"
  value       = module.monitoring.private_ip
}

output "cluster_info" {
  description = "클러스터 정보 요약"
  value = {
    vpc_id             = module.vpc.vpc_id
    master_ip          = aws_eip.master.public_ip
    worker_ips         = [module.worker_1.public_ip, module.worker_2.public_ip]
    rabbitmq_ip        = module.rabbitmq.public_ip
    postgresql_ip      = module.postgresql.public_ip
    redis_ip           = module.redis.public_ip
    monitoring_ip      = module.monitoring.public_ip
    total_nodes        = 7
    total_vcpu         = 11  # 2+2+2+1+1+1+2
    total_memory_gb    = 22  # 8+4+4+2+2+2+4
    estimated_cost_usd = 214  # t3.large*1 + t3.medium*3 + t3.small*3
  }
}

output "node_roles" {
  description = "노드별 역할"
  value = {
    master     = "Control Plane (t3.large, 8GB)"
    worker_1   = "Application Pods (t3.medium, 4GB)"
    worker_2   = "Celery Workers (t3.medium, 4GB)"
    rabbitmq   = "RabbitMQ only (t3.small, 2GB)"
    postgresql = "PostgreSQL only (t3.small, 2GB)"
    redis      = "Redis only (t3.small, 2GB)"
    monitoring = "Prometheus + Grafana (t3.medium, 4GB)"
  }
}

output "dns_records" {
  description = "생성된 DNS 레코드 (domain_name 설정 시)"
  value = var.domain_name != "" ? {
    apex_domain = "https://${var.domain_name}"
    www_url     = "https://www.${var.domain_name}"
    api_url     = "https://api.${var.domain_name}"
    argocd_url  = "https://argocd.${var.domain_name}"
    grafana_url = "https://grafana.${var.domain_name}"
    wildcard    = var.create_wildcard_record ? "https://*.${var.domain_name}" : "disabled"
    nameservers = try(data.aws_route53_zone.main[0].name_servers, [])
  } : null
}


output "s3_bucket_info" {
  description = "S3 이미지 버킷 정보"
  value = {
    bucket_name = aws_s3_bucket.images.id
    bucket_arn  = aws_s3_bucket.images.arn
    region      = var.aws_region
  }
}

# ALB Controller 및 Ansible에서 필요한 Output
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "aws_region" {
  description = "AWS Region"
  value       = var.aws_region
}

output "acm_certificate_arn" {
  description = "ACM Certificate ARN (domain_name이 설정된 경우)"
  value       = var.domain_name != "" ? try(aws_acm_certificate_validation.main[0].certificate_arn, aws_acm_certificate.main[0].arn, "") : ""
}
