# Lista de registros privados permitidos
$privateRegistries = @("dkrmuseum", "myprivateregistry")

# Ejecuta kubectl para obtener las imágenes de todos los deployments en todos los namespaces
$deployments = kubectl get deployments --all-namespaces -o json | ConvertFrom-Json

# Filtra los deployments que usan imágenes que no provienen de los registros privados
$invalidDeployments = @()

foreach ($deployment in $deployments.items) {
    foreach ($container in $deployment.spec.template.spec.containers) {
        # Comprobar si la imagen contiene al menos uno de los registros permitidos
        $isValid = $false
        foreach ($registry in $privateRegistries) {
            if ($container.image -like "*$registry*") {
                $isValid = $true
                break
            }
        }

        # Si la imagen no contiene ninguno de los registros privados, se marca como inválida
        if (-not $isValid) {
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
    Write-Host "All deployments are using images from the private registries: $($privateRegistries -join ', ')."
}
