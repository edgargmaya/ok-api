variable "kubeconfig_path" {
  description = "Path to the kubeconfig file (same file kubectl uses unless KUBECONFIG points elsewhere). Defaults to ~/.kube/config."
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "Kubeconfig context name (same as `kubectl config use-context`). If null, the kubeconfig current-context is used."
  type        = string
  default     = null
  nullable    = true
}

variable "keda_release_name" {
  description = "Helm release name for KEDA."
  type        = string
  default     = "keda"
}

variable "keda_namespace" {
  description = "Namespace where KEDA is installed."
  type        = string
  default     = "keda"
}

variable "keda_chart_version" {
  description = "kedacore/keda Helm chart version to install."
  type        = string
  default     = "2.19.0"
}

variable "keda_create_namespace" {
  description = "If true, Helm creates the namespace set in keda_namespace."
  type        = bool
  default     = true
}

variable "metrics_server_enabled" {
  description = "If true, installs metrics-server with Helm (metrics.k8s.io API for kubectl top and KEDA CPU triggers)."
  type        = bool
  default     = true
}

variable "metrics_server_release_name" {
  description = "Helm release name for metrics-server."
  type        = string
  default     = "metrics-server"
}

variable "metrics_server_namespace" {
  description = "Namespace for metrics-server (typically kube-system)."
  type        = string
  default     = "kube-system"
}

variable "metrics_server_chart_version" {
  description = "metrics-server Helm chart version (kubernetes-sigs.github.io/metrics-server)."
  type        = string
  default     = "3.13.0"
}

variable "metrics_server_create_namespace" {
  description = "If true, Helm will try to create the namespace (usually false for kube-system)."
  type        = bool
  default     = false
}
