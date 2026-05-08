#!/bin/bash
# Cloud-init lo invoca con: runcmd -> [ /bin/bash, este_script ] (no pasa por ShellScriptPartHandler).

exec > >(tee -a /var/log/ec2-bootstrap-tools.log) 2>&1
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

wait_for_apt() {
  local max=200
  local n=0
  while true; do
    if ! pgrep -x apt-get >/dev/null 2>&1 \
      && ! pgrep -x dpkg >/dev/null 2>&1 \
      && ! pgrep -x unattended-upgrade >/dev/null 2>&1; then
      break
    fi
    n=$((n + 1))
    if [[ "$n" -ge "$max" ]]; then
      echo "Timeout esperando locks de apt/dpkg"
      exit 1
    fi
    echo "Esperando apt/dpkg/unattended-upgrade ($n)..."
    sleep 3
  done
}

wait_for_network_https() {
  local max=60
  local n=0
  until curl -fsI --connect-timeout 5 https://archive.ubuntu.com >/dev/null 2>&1; do
    n=$((n + 1))
    if [[ "$n" -ge "$max" ]]; then
      echo "Timeout esperando salida HTTPS (¿NAT o endpoints VPC?)."
      exit 1
    fi
    echo "Esperando red saliente ($n)..."
    sleep 5
  done
}

echo "=== ec2-bootstrap-tools inicio $(date -Iseconds) ==="

wait_for_network_https
wait_for_apt
sleep 10

apt-get update -y
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  nano \
  git \
  unzip \
  wget \
  net-tools \
  iputils-ping \
  dnsutils \
  traceroute \
  telnet \
  netcat-openbsd \
  jq

wait_for_apt

# AWS CLI v2
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip

# kubectl (también en /usr/bin por compatibilidad con PATH mínimos)
KUBECTL_VERSION="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
curl -fsSLO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
ln -sf /usr/local/bin/kubectl /usr/bin/kubectl
rm -f kubectl

# Helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Terraform (repositorio HashiCorp)
wget -qO- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" >/etc/apt/sources.list.d/hashicorp.list
wait_for_apt
apt-get update -y
apt-get install -y terraform

# GitHub CLI (gh)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg status=none
chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" >/etc/apt/sources.list.d/github-cli.list
wait_for_apt
apt-get update -y
apt-get install -y gh

command -v kubectl && kubectl version --client
command -v terraform && terraform version
command -v helm && helm version
command -v aws && aws --version

echo "=== ec2-bootstrap-tools fin $(date -Iseconds) ==="
