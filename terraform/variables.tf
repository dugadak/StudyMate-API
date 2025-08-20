# Variables for TimeTree Event Creator Infrastructure

# General Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "timetree-creator"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

variable "availability_zone_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 2
  
  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "Availability zone count must be between 2 and 3."
  }
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# Domain Configuration
variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

# ECS Configuration
variable "container_port" {
  description = "Port exposed by the docker image to redirect traffic to"
  type        = number
  default     = 8000
}

variable "container_cpu" {
  description = "Fargate instance CPU units to provision (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "container_memory" {
  description = "Fargate instance memory to provision (in MiB)"
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Number of Fargate instances to run"
  type        = number
  default     = 2
}

variable "docker_image" {
  description = "Docker image to deploy"
  type        = string
  default     = "timetree-creator:latest"
}

# Database Configuration
variable "database_name" {
  description = "Name of the database"
  type        = string
  default     = "timetree_creator"
}

variable "database_username" {
  description = "Username for the database"
  type        = string
  default     = "app_user"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Amount of storage to allocate for RDS instance (GB)"
  type        = number
  default     = 20
}

variable "db_backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_clusters" {
  description = "Number of cache clusters (nodes) in the replication group"
  type        = number
  default     = 2
}

# API Keys and Secrets (should be set via environment variables or tfvars file)
variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic (Claude) API key"
  type        = string
  sensitive   = true
}

variable "together_api_key" {
  description = "Together AI API key"
  type        = string
  sensitive   = true
}

variable "timetree_client_id" {
  description = "TimeTree OAuth client ID"
  type        = string
  sensitive   = true
}

variable "timetree_client_secret" {
  description = "TimeTree OAuth client secret"
  type        = string
  sensitive   = true
}

variable "stripe_publishable_key" {
  description = "Stripe publishable key"
  type        = string
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe secret key"
  type        = string
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "JWT secret key for authentication"
  type        = string
  sensitive   = true
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable CloudWatch monitoring and alerting"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
}

variable "enable_xray" {
  description = "Enable AWS X-Ray tracing"
  type        = bool
  default     = false
}

# Backup Configuration
variable "enable_point_in_time_recovery" {
  description = "Enable point-in-time recovery for RDS"
  type        = bool
  default     = true
}

variable "backup_window" {
  description = "Daily time range for RDS backups"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Weekly time range for RDS maintenance"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# Security Configuration
variable "enable_waf" {
  description = "Enable AWS WAF for the load balancer"
  type        = bool
  default     = false
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the application"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# Auto Scaling Configuration
variable "enable_auto_scaling" {
  description = "Enable auto scaling for ECS service"
  type        = bool
  default     = true
}

variable "min_capacity" {
  description = "Minimum number of tasks for auto scaling"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of tasks for auto scaling"
  type        = number
  default     = 10
}

variable "cpu_target_value" {
  description = "Target CPU utilization for auto scaling"
  type        = number
  default     = 70.0
}

variable "memory_target_value" {
  description = "Target memory utilization for auto scaling"
  type        = number
  default     = 80.0
}

# Cost Optimization
variable "enable_spot_instances" {
  description = "Use Spot instances for Fargate (if supported in region)"
  type        = bool
  default     = false
}

variable "schedule_scaling" {
  description = "Enable scheduled scaling for predictable traffic patterns"
  type        = bool
  default     = false
}

# Development Configuration
variable "enable_debug_mode" {
  description = "Enable debug mode for development environments"
  type        = bool
  default     = false
}

variable "enable_ssh_access" {
  description = "Enable SSH access for debugging (dev environments only)"
  type        = bool
  default     = false
}

# Feature Flags
variable "enable_redis_cluster_mode" {
  description = "Enable Redis cluster mode for better performance"
  type        = bool
  default     = false
}

variable "enable_database_encryption" {
  description = "Enable encryption at rest for RDS"
  type        = bool
  default     = true
}

variable "enable_s3_versioning" {
  description = "Enable versioning for S3 buckets"
  type        = bool
  default     = true
}

# Local variables for computed values
locals {
  # Environment-specific configurations
  is_production = var.environment == "production"
  
  # Database configuration based on environment
  db_config = {
    dev = {
      instance_class = "db.t3.micro"
      allocated_storage = 20
      multi_az = false
    }
    staging = {
      instance_class = "db.t3.small"
      allocated_storage = 50
      multi_az = false
    }
    production = {
      instance_class = "db.r5.large"
      allocated_storage = 100
      multi_az = true
    }
  }
  
  # Redis configuration based on environment
  redis_config = {
    dev = {
      node_type = "cache.t3.micro"
      num_clusters = 1
    }
    staging = {
      node_type = "cache.t3.small"
      num_clusters = 2
    }
    production = {
      node_type = "cache.r5.large"
      num_clusters = 3
    }
  }
  
  # ECS configuration based on environment
  ecs_config = {
    dev = {
      cpu = 256
      memory = 512
      desired_count = 1
    }
    staging = {
      cpu = 512
      memory = 1024
      desired_count = 2
    }
    production = {
      cpu = 1024
      memory = 2048
      desired_count = 3
    }
  }
  
  # Common tags
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    CreatedBy   = "TimeTree Event Creator"
    
    # Cost tracking tags
    CostCenter = var.project_name
    Owner      = "Engineering Team"
  }
  
  # Security group rules based on environment
  security_rules = {
    allow_all_http = {
      type        = "ingress"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = var.allowed_cidr_blocks
    }
    allow_all_https = {
      type        = "ingress"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.allowed_cidr_blocks
    }
  }
}