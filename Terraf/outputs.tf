output "instance_id" {
  description = "ID de la instancia EC2."
  value       = aws_instance.this.id
}

output "private_ip" {
  description = "IP privada de la instancia."
  value       = aws_instance.this.private_ip
}

output "public_ip" {
  description = "IP pública (si aplica según subred y associate_public_ip_address)."
  value       = aws_instance.this.public_ip
}

output "vpc_id" {
  description = "VPC usada: la indicada en la variable o la inferida desde la subred."
  value       = local.vpc_id
}

output "ami_id" {
  description = "AMI efectiva (personalizada o Ubuntu LTS por defecto)."
  value       = local.ami_id
}

output "subnet_id" {
  description = "Subred donde está la instancia."
  value       = aws_instance.this.subnet_id
}

output "bootstrap_log_hint" {
  description = "Ruta en la instancia del log del script de instalación de herramientas (user_data)."
  value       = "/var/log/ec2-bootstrap-tools.log"
}
