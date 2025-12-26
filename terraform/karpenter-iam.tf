# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Karpenter IAM Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 목적: Karpenter Controller에 EC2 Fleet API 권한 부여
# 참조: docs/blogs/async/foundations/16-karpenter-node-autoscaling.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Karpenter Controller IRSA Role
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

resource "aws_iam_role" "karpenter_controller" {
  count = var.enable_karpenter ? 1 : 0
  name  = "${var.environment}-karpenter-controller"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = local.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider_url}:sub" = "system:serviceaccount:kube-system:karpenter"
          "${local.oidc_provider_url}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Name        = "${var.environment}-karpenter-controller"
    Description = "IRSA for Karpenter Controller (EC2 Fleet API)"
  }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Karpenter Controller Policy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

resource "aws_iam_role_policy" "karpenter_controller" {
  count = var.enable_karpenter ? 1 : 0
  name  = "KarpenterControllerPolicy"
  role  = aws_iam_role.karpenter_controller[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # EC2 Instance Provisioning
      {
        Sid    = "EC2NodeProvisioning"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
          "ec2:CreateFleet",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeInstanceTypeOfferings",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeImages",
          "ec2:DescribeSpotPriceHistory",
          "ec2:CreateLaunchTemplate",
          "ec2:DeleteLaunchTemplate"
        ]
        Resource = "*"
      },
      # EC2 Tag Management
      {
        Sid    = "EC2TagManagement"
        Effect = "Allow"
        Action = [
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = [
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:volume/*",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:network-interface/*",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:launch-template/*",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:spot-instances-request/*"
        ]
      },
      # IAM PassRole for Node Instance Profile
      {
        Sid    = "IAMPassRole"
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          aws_iam_role.k8s_node.arn,
          aws_iam_role.karpenter_node[0].arn
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ec2.amazonaws.com"
          }
        }
      },
      # SSM Parameter for AMI Discovery
      {
        Sid    = "SSMGetParameter"
        Effect = "Allow"
        Action = "ssm:GetParameter"
        Resource = [
          "arn:aws:ssm:${var.aws_region}::parameter/aws/service/eks/optimized-ami/*",
          "arn:aws:ssm:${var.aws_region}::parameter/aws/service/canonical/ubuntu/*"
        ]
      },
      # Pricing API for Cost Optimization
      {
        Sid    = "PricingAPI"
        Effect = "Allow"
        Action = "pricing:GetProducts"
        Resource = "*"
      },
      # EKS Cluster Information (optional, for EKS compatibility)
      {
        Sid    = "EKSDescribe"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster"
        ]
        Resource = "*"
      }
    ]
  })
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Karpenter Node IAM Role
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Karpenter가 생성하는 노드에 부여할 IAM Role
# 기존 k8s_node role을 확장하거나 별도 생성

resource "aws_iam_role" "karpenter_node" {
  count = var.enable_karpenter ? 1 : 0
  name  = "${var.environment}-karpenter-node"

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
    Name        = "${var.environment}-karpenter-node"
    Description = "IAM Role for Karpenter-provisioned EC2 nodes"
  }
}

# Attach existing policies to Karpenter node role
resource "aws_iam_role_policy_attachment" "karpenter_node_ecr" {
  count      = var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_node[0].name
  policy_arn = aws_iam_policy.ecr_read.arn
}

resource "aws_iam_role_policy_attachment" "karpenter_node_s3" {
  count      = var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_node[0].name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_role_policy_attachment" "karpenter_node_cloudwatch" {
  count      = var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_node[0].name
  policy_arn = aws_iam_policy.cloudwatch.arn
}

resource "aws_iam_role_policy_attachment" "karpenter_node_ebs" {
  count      = var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_node[0].name
  policy_arn = aws_iam_policy.ebs_csi.arn
}

resource "aws_iam_role_policy_attachment" "karpenter_node_ssm" {
  count      = var.enable_karpenter ? 1 : 0
  role       = aws_iam_role.karpenter_node[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Karpenter Node Instance Profile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

resource "aws_iam_instance_profile" "karpenter_node" {
  count = var.enable_karpenter ? 1 : 0
  name  = "${var.environment}-karpenter-node"
  role  = aws_iam_role.karpenter_node[0].name

  tags = {
    Name        = "${var.environment}-karpenter-node-profile"
    Environment = var.environment
  }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. SSM Parameters for Karpenter
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

resource "aws_ssm_parameter" "karpenter_controller_role_arn" {
  count       = var.enable_karpenter ? 1 : 0
  name        = "/sesacthon/${var.environment}/karpenter/controller-role-arn"
  type        = "String"
  value       = aws_iam_role.karpenter_controller[0].arn
  description = "Karpenter Controller IRSA Role ARN"

  tags = {
    ManagedBy   = "terraform"
    Scope       = "karpenter"
    Environment = var.environment
  }
}

resource "aws_ssm_parameter" "karpenter_node_instance_profile" {
  count       = var.enable_karpenter ? 1 : 0
  name        = "/sesacthon/${var.environment}/karpenter/node-instance-profile"
  type        = "String"
  value       = aws_iam_instance_profile.karpenter_node[0].name
  description = "Karpenter Node Instance Profile Name"

  tags = {
    ManagedBy   = "terraform"
    Scope       = "karpenter"
    Environment = var.environment
  }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Outputs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

output "karpenter_controller_role_arn" {
  description = "ARN of the Karpenter Controller IAM role"
  value       = var.enable_karpenter ? aws_iam_role.karpenter_controller[0].arn : ""
}

output "karpenter_node_role_arn" {
  description = "ARN of the Karpenter Node IAM role"
  value       = var.enable_karpenter ? aws_iam_role.karpenter_node[0].arn : ""
}

output "karpenter_node_instance_profile_name" {
  description = "Name of the Karpenter Node Instance Profile"
  value       = var.enable_karpenter ? aws_iam_instance_profile.karpenter_node[0].name : ""
}
