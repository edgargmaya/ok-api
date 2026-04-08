output "metrics_server_installed" {
  description = "Indica si el release de metrics-server está gestionado por este proyecto."
  value       = var.metrics_server_enabled
}

output "metrics_server_release_name" {
  description = "Nombre del release de Helm de metrics-server (si está habilitado)."
  value       = var.metrics_server_enabled ? helm_release.metrics_server[0].name : null
}

output "metrics_server_chart_version" {
  description = "Versión del chart metrics-server instalada (si está habilitado)."
  value       = var.metrics_server_enabled ? helm_release.metrics_server[0].version : null
}

output "metrics_server_status" {
  description = "Estado del release metrics-server (si está habilitado)."
  value       = var.metrics_server_enabled ? helm_release.metrics_server[0].status : null
}

output "keda_release_name" {
  description = "Nombre del release de Helm de KEDA."
  value       = helm_release.keda.name
}

output "keda_namespace" {
  description = "Namespace donde está instalado KEDA."
  value       = helm_release.keda.namespace
}

output "keda_chart_version" {
  description = "Versión del chart instalada."
  value       = helm_release.keda.version
}

output "keda_status" {
  description = "Estado del release (por ejemplo deployed)."
  value       = helm_release.keda.status
}
