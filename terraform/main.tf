resource "helm_release" "metrics_server" {
  count = var.metrics_server_enabled ? 1 : 0

  name             = var.metrics_server_release_name
  repository       = "https://kubernetes-sigs.github.io/metrics-server/"
  chart            = "metrics-server"
  version          = var.metrics_server_chart_version
  namespace        = var.metrics_server_namespace
  create_namespace = var.metrics_server_create_namespace

  values = [
    file("${path.module}/helm-values/metrics-server-values.yaml")
  ]
}

resource "helm_release" "keda" {
  name             = var.keda_release_name
  repository       = "https://kedacore.github.io/charts"
  chart            = "keda"
  version          = var.keda_chart_version
  namespace        = var.keda_namespace
  create_namespace = var.keda_create_namespace

  values = [
    file("${path.module}/helm-values/values.yaml")
  ]

  depends_on = [helm_release.metrics_server]
}
