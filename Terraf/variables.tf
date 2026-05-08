variable "aws_region" {
  description = "Región de AWS donde se despliega la instancia. Si se omite, se usa us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "subnet_id" {
  description = "ID de la subred donde se lanza la EC2. La VPC se obtiene automáticamente de esta subred salvo que también indiques vpc_id."
  type        = string
  default     = "subnet-07ca3d27220df694e"
}

variable "vpc_id" {
  description = "ID de la VPC (opcional). Si es null, se usa la VPC asociada a subnet_id mediante una consulta a la subred."
  type        = string
  default     = null
  nullable    = true
}

variable "security_group_ids" {
  description = "Lista de IDs de security groups a asociar a la instancia. Obligatorio (al menos un SG)."
  type        = list(string)

  validation {
    condition     = length(var.security_group_ids) > 0
    error_message = "Debes indicar al menos un security group en security_group_ids."
  }

  default = ["sg-0ea644ab38d1eef80"]
}

variable "iam_instance_profile_name" {
  description = "Nombre del instance profile de IAM asociado a la EC2. El rol debe incluir permisos para SSM (p. ej. la política administrada AmazonSSMManagedInstanceCore) para acceder solo vía Session Manager."
  type        = string
  default     = "SSMRole"
}

variable "ami_id" {
  description = "AMI personalizada. Si es null, se usa la AMI oficial más reciente de Ubuntu Server 22.04 LTS (amd64) en la región."
  type        = string
  default     = null
  nullable    = true
}

variable "instance_type" {
  description = "Tipo de instancia EC2."
  type        = string
  default     = "t3.micro"
}

variable "instance_name" {
  description = "Nombre (tag Name) de la instancia."
  type        = string
  default     = "ubuntu-tools"
}

variable "associate_public_ip_address" {
  description = "Si true, asocia IP pública a la instancia (útil en subredes públicas)."
  type        = bool
  default     = true
}

variable "root_volume_size" {
  description = "Tamaño del volumen raíz en GiB."
  type        = number
  default     = 30
}

variable "additional_tags" {
  description = "Tags adicionales para la instancia."
  type        = map(string)
  default     = {}
}
