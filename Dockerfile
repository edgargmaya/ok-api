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


-------------
stage('FCS IaC scan') {
  container('crowdstrike') {
    // Parametriza para no hardcodear políticas
    env.FCS_SEVERITIES = (params.FCS_SEVERITIES ?: 'critical,high,medium')
    env.FCS_FAIL_ON    = (params.FCS_FAIL_ON    ?: 'critical=1,high=1')
    env.FCS_OUT        = "fcs-results-${env.BUILD_NUMBER}"

    // Manejo robusto de errores y publicación de reportes
    int rc = 0
    try {
      sh """
        set -euxo pipefail
        mkdir -p "${FCS_OUT}"
        echo "FCS CLI version:" || true
        fcs version || fcs --version || true

        # (Opcional) muestra qué Terraform cambió en el PR para contexto
        git --no-pager diff --name-only "${env.GIT_PREVIOUS_SUCCESSFUL_COMMIT}" "${env.GIT_COMMIT}" | grep -E '\\.tf$' || true

        # Ejecuta el scan con timeout y reintento por si hay fluke de red
      """
      retry(2) {
        timeout(time: 10, unit: 'MINUTES') {
          rc = sh(returnStatus: true, script: """
            set +e
            fcs iac scan \\
              --path . \\
              --severities "${FCS_SEVERITIES}" \\
              --fail-on "${FCS_FAIL_ON}" \\
              --report-formats json,sarif,junit \\
              --output-path "${FCS_OUT}"
            exit \$?
          """)
        }
      }

      // Resumen legible en consola (sin depender del esquema del JSON)
      sh """
        if ls "${FCS_OUT}"/*.json >/dev/null 2>&1; then
          echo "================ FCS resumen (conteo por severidad) ================"
          CRIT=\$(grep -oh '"severity":"critical"' "${FCS_OUT}"/*.json | wc -l || true)
          HIGH=\$(grep -oh '"severity":"high"'     "${FCS_OUT}"/*.json | wc -l || true)
          MED=\$(grep -oh '"severity":"medium"'   "${FCS_OUT}"/*.json | wc -l || true)
          LOW=\$(grep -oh '"severity":"low"'      "${FCS_OUT}"/*.json | wc -l || true)
          echo "critical=\$CRIT | high=\$HIGH | medium=\$MED | low=\$LOW"
          echo "===================================================================="

          echo "== Primeras 20 coincidencias (regla / archivo:línea / recurso) =="
          # Esto intenta construir una línea útil por hallazgo; es genérico y tolerante
          paste -d' ' \
            <(grep -hoE '"rule_id":"[^"]+' "${FCS_OUT}"/*.json | head -20 | sed -E 's/^"rule_id":"//') \
            <(grep -hoE '"file":"[^"]+","line":[0-9]+' "${FCS_OUT}"/*.json | head -20 | sed -E 's/^"file":"//; s/","line":/ : /') \
            <(grep -hoE '"resource":"[^"]+' "${FCS_OUT}"/*.json | head -20 | sed -E 's/^"resource":"/ — /') \
            || true
          echo ""
        fi
      """

      // Publicar reportes en la UI de Jenkins
      // SARIF -> Warnings NG: vista con tendencias y navegación por archivo/línea
      recordIssues enabledForFailure: true, tools: [sarif(pattern: "${FCS_OUT}/*.sarif")]

      // JUnit -> barra de tendencias + “test suite” por hallazgos
      junit allowEmptyResults: true, testResults: "${FCS_OUT}/*.junit.xml"

      // Archivar todo y hacer fingerprint (para trazabilidad)
      archiveArtifacts artifacts: "${FCS_OUT}/*", fingerprint: true, allowEmptyArchive: true

      // Política de resultado del build según código de FCS
      if (rc == 0) {
        echo "FCS: sin violaciones por encima de los umbrales."
      } else if (rc == 20) {
        // Hallazgos por encima de --fail-on: marca UNSTABLE para no cortar el resto del pipeline
        currentBuild.result = 'UNSTABLE'
        echo "FCS encontró violaciones de política (exit 20). Marcando como UNSTABLE."
      } else {
        error "FCS falló con código ${rc}"
      }
    } finally {
      // En caso de error temprano, intenta archivar lo que haya
      archiveArtifacts artifacts: "${FCS_OUT}/*", fingerprint: true, allowEmptyArchive: true
    }
  }
}
