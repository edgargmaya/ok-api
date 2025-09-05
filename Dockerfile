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
  steps {
    sh '''
      set +e
      # Ejemplo IaC; ajusta --path / imagen, etc.
      fcs-cli iac scan \
        --path infra/terraform \
        --report-formats json,sarif,junit \
        --output-path fcs-out \
        --no-color
      RC=$?
      echo "FCS exit code: $RC"
      # Imprime un resumen si hay JSON
      if [ -f fcs-out/*.json ]; then
        echo "== FCS JSON summary (primeros 2000 chars) =="
        head -c 2000 fcs-out/*.json || true
        echo ""
      fi
      exit $RC
    '''
  }
  post {
    always {
      archiveArtifacts artifacts: 'fcs-out/**', allowEmptyArchive: true
    }
  }
}
