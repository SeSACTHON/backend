# IAM Role for Kubernetes Nodes
# Grants EC2 instances permissions for ELB, ECR, CloudWatch

# IAM Role
resource "aws_iam_role" "k8s_node" {
  name = "k8s-node-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
    }]
  })

  tags = {
    Name        = "k8s-node-role"
    Environment = var.environment
  }
}

# Note: ALB Controller IAM Policy is defined in alb-controller-iam.tf
# to avoid duplication and maintain separation of concerns

# IAM Policy for ECR (Container Registry)
resource "aws_iam_policy" "ecr_read" {
  name        = "k8s-ecr-read-policy-${var.environment}"
  description = "Policy for reading from ECR"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetRepositoryPolicy",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy for S3 (Image Storage)
resource "aws_iam_policy" "s3_access" {
  name        = "k8s-s3-access-policy-${var.environment}"
  description = "Policy for S3 access"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::ecoeco-*",
          "arn:aws:s3:::ecoeco-*/*"
        ]
      }
    ]
  })
}

# IAM Policy for CloudWatch (Logging & Monitoring)
resource "aws_iam_policy" "cloudwatch" {
  name        = "k8s-cloudwatch-policy-${var.environment}"
  description = "Policy for CloudWatch logging"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach policies to the role
# Note: ALB Controller policy attachment is in alb-controller-iam.tf

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.k8s_node.name
  policy_arn = aws_iam_policy.ecr_read.arn
}

resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.k8s_node.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.k8s_node.name
  policy_arn = aws_iam_policy.cloudwatch.arn
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "k8s" {
  name = "k8s-instance-profile-${var.environment}"
  role = aws_iam_role.k8s_node.name

  tags = {
    Name        = "k8s-instance-profile"
    Environment = var.environment
  }
}

# Outputs
output "k8s_node_role_arn" {
  description = "ARN of the K8s node IAM role"
  value       = aws_iam_role.k8s_node.arn
}

output "k8s_instance_profile_name" {
  description = "Name of the K8s instance profile"
  value       = aws_iam_instance_profile.k8s.name
}
