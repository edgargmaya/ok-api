import requests
import json

# Configuración
grafana_url = 'http://grafana-mydomain.com'
api_key = 'TU_CLAVE_DE_API'  # Clave de API con permisos de administrador
org_id = 1  # ID de la organización (usualmente 1)

# Encabezados para las solicitudes HTTP
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

# Lista de correos electrónicos
email_list = [
    "email1@example.com",
    "email2@example.com",
    # Agrega más correos electrónicos aquí
]

def get_users():
    url = f'{grafana_url}/api/orgs/{org_id}/users'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_folders():
    url = f'{grafana_url}/api/folders'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def create_folder(title):
    url = f'{grafana_url}/api/folders'
    data = {
        "title": title
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()
    return response.json()

def assign_folder_permissions(folder_uid, user_id):
    url = f'{grafana_url}/api/folders/{folder_uid}/permissions'
    data = {
        "items": [
            {
                "userId": user_id,
                "permission": 1  # 1 = View, 2 = Edit, 4 = Admin
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()
    return response.json()

def main():
    users = get_users()
    folders = get_folders()

    # Crear un diccionario para acceso rápido a los folders existentes
    existing_folders = {folder['title']: folder for folder in folders}

    for email in email_list:
        # Encontrar el usuario por correo electrónico
        user = next((u for u in users if u['email'] == email), None)
        if not user:
            print(f"Usuario con email {email} no encontrado.")
            continue

        # Verificar si el usuario ha iniciado sesión
        last_seen = user.get('lastSeenAtAge', '')
        if 'year' in last_seen:
            years = int(last_seen.split()[0])
            if years >= 8:
                print(f"El usuario {user['login']} nunca ha iniciado sesión. Saltando...")
                continue
        elif not user.get('lastSeenAt'):
            print(f"El usuario {user['login']} nunca ha iniciado sesión. Saltando...")
            continue

        # Formatear el nombre para el folder
        name_parts = user['name'].split(', ')
        if len(name_parts) == 2:
            folder_name = f"{name_parts[1]} {name_parts[0]}"
        else:
            folder_name = user['name']

        # Verificar si el folder existe
        if folder_name in existing_folders:
            print(f"El folder '{folder_name}' ya existe. Continuando con el siguiente usuario.")
            continue

        # Crear el folder
        print(f"Creando el folder '{folder_name}' para el usuario '{user['login']}'.")
        folder = create_folder(folder_name)
        folder_uid = folder['uid']

        # Asignar permisos al usuario
        print(f"Asignando permisos al usuario '{user['login']}' para el folder '{folder_name}'.")
        assign_folder_permissions(folder_uid, user['id'])

        # Actualizar la lista de folders existentes
        existing_folders[folder_name] = folder

    print("Proceso completado.")

if __name__ == '__main__':
    main()
