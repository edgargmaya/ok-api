output "metrics_server_installed" {
  description = "Whether metrics-server is managed by this project."
  value       = var.metrics_server_enabled
}

output "metrics_server_release_name" {
  description = "Helm release name for metrics-server (when enabled)."
  value       = var.metrics_server_enabled ? helm_release.metrics_server[0].name : null
}

output "metrics_server_chart_version" {
  description = "Installed metrics-server chart version (when enabled)."
  value       = var.metrics_server_enabled ? helm_release.metrics_server[0].version : null
}

output "metrics_server_status" {
  description = "metrics-server release status (when enabled)."
  value       = var.metrics_server_enabled ? helm_release.metrics_server[0].status : null
}

output "keda_release_name" {
  description = "Helm release name for KEDA."
  value       = helm_release.keda.name
}

output "keda_namespace" {
  description = "Namespace where KEDA is installed."
  value       = helm_release.keda.namespace
}

output "keda_chart_version" {
  description = "Installed KEDA chart version."
  value       = helm_release.keda.version
}

output "keda_status" {
  description = "KEDA release status (e.g. deployed)."
  value       = helm_release.keda.status
}
