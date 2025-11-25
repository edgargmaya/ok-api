terraform {
  required_providers {
    consul = {
      source  = "hashicorp/consul"
      version = ">= 2.20.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.29.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.13.0"
    }
  }
}

provider "helm" {
  kubernetes = {
    config_path = "~/.kube/config"
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

locals {
  namespace = "vault"
}

resource "kubernetes_namespace_v1" "vault" {
  metadata { name = local.namespace }
}

resource "helm_release" "consul" {
  name       = "consul"
  namespace  = local.namespace
  repository = "https://helm.releases.hashicorp.com"
  chart      = "consul"
  version    = "1.7.2"

  values = [file("${path.module}/consul-values.yaml")]

  timeout = 600
  depends_on = [kubernetes_namespace_v1.vault]
}
---
data "kubernetes_secret" "consul_bootstrap" {
  metadata {
    name      = "consul-consul-bootstrap-acl-token"
    namespace = local.namespace
  }
  depends_on = [helm_release.consul]
}

locals {
  consul_bootstrap_raw = try(data.kubernetes_secret.consul_bootstrap.data["token"], "")
  consul_bootstrap_raw_nonsensitive = nonsensitive(local.consul_bootstrap_raw)
  consul_bootstrap_token = try(
    base64decode(local.consul_bootstrap_raw_nonsensitive),
    local.consul_bootstrap_raw_nonsensitive
  )
  consul_addr = "https://127.0.0.1:8501"
}

provider "consul" {
  address = local.consul_addr
  token   = local.consul_bootstrap_token
  insecure_https = true
  scheme = "https"
}

resource "consul_acl_policy" "vault" {
  name        = "vault"
  description = "Permisos para que Vault use Consul como storage y sesiones"
  rules = file("${path.module}/policies/vault.hcl")
}

resource "consul_acl_token" "vault_server" {
  description = "vault-server"
  policies    = [consul_acl_policy.vault.name]
}

resource "kubernetes_secret_v1" "consul_vault_token" {
  metadata {
    name      = "consul-vault-token"
    namespace = local.namespace
  }

  data = {
    token = ""
  }

  type = "Opaque"
}
---
key_prefix "vault/" {
  policy = "write"
}

session_prefix "" {
  policy = "write"
}

service "vault" {
  policy = "write"
}

node_prefix "" {
  policy = "read"
}

agent_prefix "" {
  policy = "read"
}
---
global:
  tls:
    enabled: true
  acls:
    manageSystemACLs: true

server:
  replicas: 3
  storageClass: "gp2"
  resources:
    requests:
      memory: "1Gi"
      cpu: "300m"
    limits:
      memory: "1Gi"
      cpu: "300m"
  storage: "30Gi"

client:
  enabled: false
  affinity: |
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchExpressions:
              - key: app
                operator: In
                values:
                  - consul
          topologyKey: "kubernetes.io/hostname"

ui:
  enabled: true
  service:
    type: LoadBalancer
    annotations:
      service.beta.kubernetes.io/aws-load-balancer-subnets: "subnet-54e0e7bafdb3240,subnet-45f56d1c2f19f1d,subnet-b130037cc84fd91"

connectInject:
  enabled: true

# helm upgrade --install consul hashicorp/consul --create-namespace --namespace vault -f consul-values.yaml
# helm show values hashicorp/consul

---
server:
  serviceAccount:
    create: true
    name: "$VAULT_KSA_NAME"
    # Como no usamos KMS, generalmente no necesitamos el IRSA aquí para el sello.
    # Si usas AWS Auth Method, podrías necesitar descomentarlo.
    # annotations:
    #   eks.amazonaws.com/role-arn: "$ROLE_ARN"

  affinity: |
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            match-expressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - vault
          topologyKey: "kubernetes.io/hostname"

  volumes:
  - name: consul-ca
    secret:
      secretName: consul-consul-ca-cert

  volumeMounts:
  - name: consul-ca
    mountPath: "/vault/userconfig/consul-ca"
    readOnly: true

  extraSecretEnvironmentVars:
    - envName: CONSUL_HTTP_TOKEN
      secretName: consul-vault-token
      secretKey: token

  ha:
    enabled: true
    replicas: 2
    config: |
      ui = true
      
      storage "consul" {
        address = "consul-consul-server:8501"
        path    = "vault/"
        scheme  = "https"
        tls_ca_file = "/vault/userconfig/consul-ca/tls.crt"
      }

      # BLOQUE KMS ELIMINADO PARA USAR SHAMIR (MANUAL)
      
      listener "tcp" {
        address = "0.0.0.0:8200"
        cluster_address = "0.0.0.0:8201"
        tls_disable = "true"
      }
      
      disable_mlock = true
      service_registration "kubernetes" {}

ui:
  enabled: true
  serviceType: "LoadBalancer"
