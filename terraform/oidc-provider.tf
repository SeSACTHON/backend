locals {
  service_account_oidc_issuer_url = var.service_account_oidc_issuer_url != "" ? var.service_account_oidc_issuer_url : format("https://oidc.sesacthon.io/%s", var.environment)
}

data "tls_certificate" "service_account_oidc" {
  url = local.service_account_oidc_issuer_url
}

resource "aws_iam_openid_connect_provider" "cluster" {
  url = local.service_account_oidc_issuer_url

  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    data.tls_certificate.service_account_oidc.certificates[length(data.tls_certificate.service_account_oidc.certificates) - 1].sha1_fingerprint
  ]

  tags = {
    Name        = "${var.environment}-self-managed-oidc"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

