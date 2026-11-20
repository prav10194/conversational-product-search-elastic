variable "region" {
  description = "AWS region for the lab"
  type        = string
  default     = "us-east-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "eck-lab"
}

variable "node_instance_type" {
  description = "EC2 type for the worker nodes (m7i-flex.large = 2 vCPU, 8 GiB, free-tier eligible)"
  type        = string
  default     = "m7i-flex.large"
}

variable "node_count" {
  description = "Worker nodes (one per availability zone)"
  type        = number
  default     = 3
}
