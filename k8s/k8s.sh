#!/usr/bin/env bash
set -euo pipefail

K8S_MINOR="${K8S_MINOR:-v1.36}"
POD_CIDR="${POD_CIDR:-10.244.0.0/16}"
NODE_NAME="${NODE_NAME:-k8s-node01}"

log() {
  echo -e "\n[INFO] $(date '+%F %T') - $*\n"
}

ok() {
  echo -e "[OK] $*"
}

fail() {
  echo -e "[ERROR] $*" >&2
  exit 1
}

require_root() {
  if [[ "$EUID" -ne 0 ]]; then
    fail "Ejecuta con sudo: sudo bash $0"
  fi
}

show_status() {
  echo "----- STATUS: $1 -----"
  systemctl --no-pager --full status "$1" || true
  echo "----------------------"
}

require_root

log "Configurando hostname: ${NODE_NAME}"
hostnamectl set-hostname "${NODE_NAME}"

log "Actualizando sistema"
apt-get update -y
apt-get install -y apt-transport-https ca-certificates curl gpg lsb-release software-properties-common

log "Desactivando swap"
swapoff -a
sed -i.bak '/ swap / s/^/#/' /etc/fstab
swapon --show || true

log "Configurando módulos de kernel para Kubernetes"
cat >/etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF

modprobe overlay
modprobe br_netfilter

log "Configurando sysctl"
cat >/etc/sysctl.d/k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables=1
net.bridge.bridge-nf-call-ip6tables=1
net.ipv4.ip_forward=1
vm.swappiness=0
fs.inotify.max_user_watches=1048576
fs.inotify.max_user_instances=8192
EOF

sysctl --system

log "Instalando containerd"
apt-get install -y containerd

mkdir -p /etc/containerd
containerd config default >/etc/containerd/config.toml

log "Configurando containerd con SystemdCgroup=true"
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

systemctl restart containerd
systemctl enable containerd
show_status containerd

log "Agregando repo oficial de Kubernetes ${K8S_MINOR}"
mkdir -p /etc/apt/keyrings

curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

cat >/etc/apt/sources.list.d/kubernetes.list <<EOF
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /
EOF

apt-get update -y

log "Instalando kubelet, kubeadm y kubectl"
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl

systemctl enable kubelet

log "Verificando versiones"
containerd --version
kubeadm version
kubectl version --client=true

if [[ -f /etc/kubernetes/admin.conf ]]; then
  log "El cluster ya parece estar inicializado. Saltando kubeadm init."
else
  log "Inicializando cluster Kubernetes single-node con kubeadm"
  kubeadm init --pod-network-cidr="${POD_CIDR}"
fi

REAL_USER="${SUDO_USER:-root}"
REAL_HOME="$(eval echo ~${REAL_USER})"

log "Configurando kubeconfig para usuario ${REAL_USER}"
mkdir -p "${REAL_HOME}/.kube"
cp -f /etc/kubernetes/admin.conf "${REAL_HOME}/.kube/config"
chown "${REAL_USER}:${REAL_USER}" "${REAL_HOME}/.kube/config"

export KUBECONFIG=/etc/kubernetes/admin.conf

log "Instalando Flannel como CNI"
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml

log "Permitiendo workloads en el nodo control-plane single-node"
kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true

log "Esperando estado del nodo"
sleep 15

kubectl get nodes -o wide
kubectl get pods -A

ok "Instalación terminada."
echo
echo "Prueba ahora con:"
echo "  kubectl get nodes"
echo "  kubectl get pods -A"
