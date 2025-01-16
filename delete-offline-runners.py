import requests
import os

# Configuración
GITHUB_API_URL = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")  # Carga el token desde la variable de entorno
ORG_NAME = "your-org-name"  # Cambia esto por tu organización (o repositorio si es necesario)
IS_ORG_LEVEL = True  # Cambia a False si los runners son para un repositorio específico
REPO_NAME = "your-repo-name"  # Solo necesario si IS_ORG_LEVEL es False

# Headers para autenticación
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Función para obtener la lista de runners
def get_runners():
    if IS_ORG_LEVEL:
        url = f"{GITHUB_API_URL}/orgs/{ORG_NAME}/actions/runners"
    else:
        url = f"{GITHUB_API_URL}/repos/{ORG_NAME}/{REPO_NAME}/actions/runners"
    
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("runners", [])
    else:
        print(f"Error obteniendo runners: {response.status_code} {response.text}")
        return []

# Función para eliminar un runner
def delete_runner(runner_id):
    if IS_ORG_LEVEL:
        url = f"{GITHUB_API_URL}/orgs/{ORG_NAME}/actions/runners/{runner_id}"
    else:
        url = f"{GITHUB_API_URL}/repos/{ORG_NAME}/{REPO_NAME}/actions/runners/{runner_id}"
    
    response = requests.delete(url, headers=HEADERS)
    if response.status_code == 204:
        print(f"Runner con ID {runner_id} eliminado exitosamente.")
    else:
        print(f"Error eliminando runner con ID {runner_id}: {response.status_code} {response.text}")

# Función principal
def main():
    runners = get_runners()
    if not runners:
        print("No se encontraron runners.")
        return

    for runner in runners:
        if runner["status"] == "offline":
            print(f"Eliminando runner offline: {runner['name']} (ID: {runner['id']})")
            delete_runner(runner["id"])
        else:
            print(f"Runner en línea: {runner['name']} (Estado: {runner['status']})")

if __name__ == "__main__":
    if not TOKEN:
        print("Por favor, define la variable de entorno GITHUB_TOKEN con un token válido.")
    else:
        main()
