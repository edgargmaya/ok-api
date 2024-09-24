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

