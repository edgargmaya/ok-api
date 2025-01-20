# Define el nombre del registry privado
$privateRegistry = "dkrmuseum"

# Ejecuta kubectl para obtener las imágenes de todos los deployments en todos los namespaces
$deployments = kubectl get deployments --all-namespaces -o json | ConvertFrom-Json

# Filtra los deployments que usan imágenes que no provienen del registry privado
$invalidDeployments = @()

foreach ($deployment in $deployments.items) {
    foreach ($container in $deployment.spec.template.spec.containers) {
        if ($container.image -notmatch "^$privateRegistry/") {
            $invalidDeployments += [PSCustomObject]@{
                Namespace  = $deployment.metadata.namespace
                Deployment = $deployment.metadata.name
                Image      = $container.image
            }
        }
    }
}

# Mostrar resultados si hay deployments que no cumplen la regla
if ($invalidDeployments.Count -gt 0) {
    Write-Host "Deployments with unauthorized images:"
    $invalidDeployments | Format-Table -AutoSize
} else {
    Write-Host "All deployments are using images from the private registry ($privateRegistry)."
}
