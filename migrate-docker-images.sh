#!/bin/bash
set -eo pipefail

# Ubicación del listado de imágenes
IMAGES_FILE="${IMAGES_FILE:-/scripts/images.txt}"
# Repositorio de destino (lo puedes inyectar por variable de entorno)
TARGET_REPO="${TARGET_REPO:-myregistry.example.com/my-namespace}"

while read -r IMAGE; do
  # Saltar líneas vacías
  if [ -z "$IMAGE" ]; then
    continue
  fi

  echo "=== Pulling $IMAGE ==="
  docker pull "$IMAGE"

  # Tomamos todo lo que venga tras la primera '/'
  # Por ejemplo: "docker.io/library/nginx:latest" -> "library/nginx:latest"
  # Y le anteponemos $TARGET_REPO para el tag final
  NEW_IMAGE="${TARGET_REPO}/${IMAGE#*/}"

  echo "=== Tagging $IMAGE -> $NEW_IMAGE ==="
  docker tag "$IMAGE" "$NEW_IMAGE"

  echo "=== Pushing $NEW_IMAGE ==="
  docker push "$NEW_IMAGE"

done < "$IMAGES_FILE"
