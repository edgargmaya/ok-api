variable "kubeconfig_path" {
  description = "Ruta al kubeconfig (el mismo archivo que usa kubectl, salvo que uses KUBECONFIG apuntando a otro). Por defecto ~/.kube/config."
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "Nombre del contexto de kubectl (equivalente a `kubectl config use-context`). Si es null, se usa el current-context del kubeconfig."
  type        = string
  default     = null
  nullable    = true
}

variable "keda_release_name" {
  description = "Nombre del Helm release de KEDA."
  type        = string
  default     = "keda"
}

variable "keda_namespace" {
  description = "Namespace donde se instala KEDA."
  type        = string
  default     = "keda"
}

variable "keda_chart_version" {
  description = "Versión del chart kedacore/keda a instalar."
  type        = string
  default     = "2.19.0"
}

variable "keda_create_namespace" {
  description = "Si es true, Helm crea el namespace indicado en keda_namespace."
  type        = bool
  default     = true
}

variable "metrics_server_enabled" {
  description = "Si es true, instala metrics-server con Helm (API metrics.k8s.io para kubectl top y triggers CPU de KEDA)."
  type        = bool
  default     = true
}

variable "metrics_server_release_name" {
  description = "Nombre del Helm release de metrics-server."
  type        = string
  default     = "metrics-server"
}

variable "metrics_server_namespace" {
  description = "Namespace de metrics-server (habitualmente kube-system)."
  type        = string
  default     = "kube-system"
}

variable "metrics_server_chart_version" {
  description = "Versión del chart metrics-server (kubernetes-sigs.github.io/metrics-server)."
  type        = string
  default     = "3.13.0"
}

variable "metrics_server_create_namespace" {
  description = "Si es true, Helm intenta crear el namespace (normalmente false para kube-system)."
  type        = bool
  default     = false
}
