resource "aws_security_group" "master" {
  name        = "${var.environment}-k8s-master-sg"
  description = "Security group for Kubernetes Master node"
  vpc_id      = var.vpc_id
  
  # SSH
  ingress {
    description = "SSH from allowed CIDR"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }
  
  # Kubernetes API Server
  ingress {
    description = "Kubernetes API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # HTTP
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # HTTPS
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # etcd server client API
  ingress {
    description = "etcd"
    from_port   = 2379
    to_port     = 2380
    protocol    = "tcp"
    self        = true
  }
  
  # Kubelet API, kube-scheduler, kube-controller-manager
  # Worker SG는 별도 rule로 추가 (순환 참조 방지)
  
  # NodePort Services (선택)
  ingress {
    description = "NodePort Services"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # Egress all
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.environment}-k8s-master-sg"
  }
}

resource "aws_security_group" "worker" {
  name        = "${var.environment}-k8s-worker-sg"
  description = "Security group for Kubernetes Worker nodes"
  vpc_id      = var.vpc_id
  
  # SSH
  ingress {
    description = "SSH from allowed CIDR"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }
  
  # Kubelet API, NodePort
  # Master SG는 별도 rule로 추가 (순환 참조 방지)
  
  # Worker 간 통신 (Pod network)
  ingress {
    description = "Worker to worker communication"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }
  
  # Master to Worker (별도 rule로)
  
  # Egress all
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.environment}-k8s-worker-sg"
  }
}

# 순환 참조 방지를 위한 별도 Rule 생성

# Master -> Worker Rules
resource "aws_security_group_rule" "master_to_worker_kubelet" {
  type                     = "ingress"
  from_port                = 10250
  to_port                  = 10252
  protocol                 = "tcp"
  security_group_id        = aws_security_group.master.id
  source_security_group_id = aws_security_group.worker.id
  description              = "Kubelet API from worker"
}

# Worker -> Master Rules
resource "aws_security_group_rule" "worker_to_master_kubelet" {
  type                     = "ingress"
  from_port                = 10250
  to_port                  = 10250
  protocol                 = "tcp"
  security_group_id        = aws_security_group.worker.id
  source_security_group_id = aws_security_group.master.id
  description              = "Kubelet API from master"
}

resource "aws_security_group_rule" "worker_nodeport" {
  type                     = "ingress"
  from_port                = 30000
  to_port                  = 32767
  protocol                 = "tcp"
  security_group_id        = aws_security_group.worker.id
  source_security_group_id = aws_security_group.master.id
  description              = "NodePort from master"
}

resource "aws_security_group_rule" "master_to_worker_all" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.worker.id
  source_security_group_id = aws_security_group.master.id
  description              = "All traffic from master"
}

