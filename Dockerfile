# Usar una imagen base oficial de Node.js
FROM node:18

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /usr/src/app

# Copiar los archivos de dependencias
COPY package*.json ./

# Instalar las dependencias
RUN npm install

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto 3000
EXPOSE 3000

# Comando para ejecutar la aplicación
CMD ["node", "app.js"]

$pods = kubectl get pods --all-namespaces --field-selector=status.phase=Succeeded -o json | ConvertFrom-Json

foreach ($pod in $pods.items) {
    $namespace = $pod.metadata.namespace
    $podName = $pod.metadata.name
    kubectl delete pod $podName -n $namespace
}

https://github.com/CrowdStrike/fcs-action/blob/main/README.md

stage('FCS scan') {
  def rc = 0
  try {
    rc = sh(script: '''
      set +e
      fcs-cli iac scan \
        --path infra/terraform \
        --report-formats json,sarif,junit \
        --output-path fcs-report \
        --no-color
      RC=$?
      echo "FCS exit code: $RC"
      if ls fcs-report/*.json >/dev/null 2>&1; then
        echo "== FCS JSON summary (first 5000 chars) =="
        head -c 5000 fcs-report/*.json || true
        echo ""
      fi
      exit $RC
    ''', returnStatus: true)

    if (rc != 0) { error "FCS scan returned exit code ${rc}" }
  } finally {
    archiveArtifacts artifacts: 'fcs-report/**', allowEmptyArchive: true
  }
}
