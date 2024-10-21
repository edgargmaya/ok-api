import requests
import json

# Configuration
grafana_url = 'http://grafana-mydomain.com'
api_key = 'YOUR_API_KEY'  # API key with admin permissions
org_id = 1  # Organization ID (usually 1)

# Headers for HTTP requests
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

# List of email addresses
email_list = [
    "email1@example.com",
    "email2@example.com",
    # Add more email addresses here
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

    # Create a dictionary for quick access to existing folders
    existing_folders = {folder['title']: folder for folder in folders}

    for email in email_list:
        # Find the user by email
        user = next((u for u in users if u['email'] == email), None)
        if not user:
            print(f"User with email {email} not found.")
            continue

        # Check if the user has logged in
        last_seen = user.get('lastSeenAtAge', '')
        if 'year' in last_seen:
            years = int(last_seen.split()[0])
            if years >= 8:
                print(f"User {user['login']} has never logged in. Skipping...")
                continue
        elif not user.get('lastSeenAt'):
            print(f"User {user['login']} has never logged in. Skipping...")
            continue

        # Format the user's name for the folder name
        name_parts = user['name'].split(', ')
        if len(name_parts) == 2:
            folder_name = f"{name_parts[1]} {name_parts[0]}"
        else:
            folder_name = user['name']

        # Check if the folder exists
        if folder_name in existing_folders:
            print(f"Folder '{folder_name}' already exists. Continuing to next user.")
            continue

        # Create the folder
        print(f"Creating folder '{folder_name}' for user '{user['login']}'.")
        folder = create_folder(folder_name)
        folder_uid = folder['uid']

        # Assign permissions to the user
        print(f"Assigning permissions to user '{user['login']}' for folder '{folder_name}'.")
        assign_folder_permissions(folder_uid, user['id'])

        # Update the existing folders list
        existing_folders[folder_name] = folder

    print("Process completed.")

if __name__ == '__main__':
    main()
