# Network: one VPC across 3 availability zones.
# Worker nodes live in private subnets; one NAT gateway (cheaper, fine for a lab) gives them internet access.
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.16"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"
  azs  = local.azs

  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  # Tags so Kubernetes knows where it may create load balancers
  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}

# Kubernetes: an EKS control plane (run by AWS) plus a managed group of worker nodes spread over the 3 zones.
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name = var.cluster_name
  # cluster_version left unset: AWS picks its current default Kubernetes version
  # (pinning an old one can drop into paid "extended support").

  cluster_endpoint_public_access           = true # so kubectl on your laptop can reach the API
  enable_cluster_creator_admin_permissions = true # your AWS user becomes cluster admin

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_addons = {
    coredns                = { most_recent = true }
    kube-proxy             = { most_recent = true }
    vpc-cni                = { most_recent = true }
    eks-pod-identity-agent = { most_recent = true }
    aws-ebs-csi-driver     = { most_recent = true } # creates EBS disks for Elasticsearch data
  }

  eks_managed_node_groups = {
    workers = {
      instance_types = [var.node_instance_type]
      min_size       = var.node_count
      max_size       = var.node_count + 1
      desired_size   = var.node_count

      # Lets the EBS CSI driver (running on the nodes) create and attach volumes
      iam_role_additional_policies = {
        ebs = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
      }
    }
  }
}
