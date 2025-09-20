import stomp

# Configuración de la conexión
host = "tu_host_activemq"
port = 61612  # Puerto TLS por defecto
user = "tu_usuario"
password = "tu_contraseña"
topic = "/topic/tu_topic"  # Reemplaza con tu topic
message = "Hola desde Python con TLS!"

# Configuración TLS
key_file = "ruta/a/tu/archivo.key"  # Reemplaza con la ruta a tu archivo de clave privada
cert_file = "ruta/a/tu/archivo.crt"  # Reemplaza con la ruta a tu archivo de certificado

# Crea la conexión
conn = stomp.Connection12([(host, port)], use_ssl=True, ssl_key_file=key_file, ssl_cert_file=cert_file)

# Establece el listener (opcional, para recibir mensajes)
class MyListener(stomp.ConnectionListener):
    def on_error(self, headers, message):
        print(f"Error recibido: {message}")

    def on_message(self, headers, message):
        print(f"Mensaje recibido: {message}")

conn.set_listener('', MyListener())

# Conecta al broker
conn.start()
conn.connect(user, password, wait=True)

# Envía el mensaje
conn.send(topic, message)

# Desconecta
conn.disconnect()

print("Mensaje enviado correctamente.")
---
graph TD
    subgraph "Phase 1: Start & Orchestration"
        A("1. Service Start")
        A --> B("Launch Listener/Processing Goroutine")
        A --> C("Launch Deletion Goroutine")
    end

    subgraph "Phase 2: Message Processing Cycle"
        B --> D{"Listen from the<br/>SQS Queue in Batches"}
        D --> E[Internal Channel `messageStream`]
        E --> F("Central Processor<br/>(HandleMessages)")
        F --> G{"Switch by Message Type<br/>(handleMessage)"}

        G -- Event: CaaSOrder --> H["Handler: handleOrderCreated"]
        H --> I{"Validation:<br/>Does the record already exist in DB?"}
        I -- No (New) --> J["Write new<br/>record to DB"]
        I -- Yes (Idempotency) --> K["Skip Write"]
        J --> L[Send to Deletion Channel]
        K --> L

        G -- Event: JenkinsJobCompleted --> M["Handler: handleCaaSCIOnboardingCompleted"]
        M --> N{"Validation:<br/>Does the record exist in DB?"}
        N -- Yes --> O["Update<br/>record in DB"]
        N -- No (Error) --> P["End of Flow<br/>(Return Nil)"]
        O --> Q["Send Notification Email"]
        Q --> L[Send to Deletion Channel]

        G -- Event: Vault --> U["Handler: syncAndTriggerOnboarding"]
        U --> V{"Validation"}
        V -- Yes --> W["Update<br/>record in DB"]
        V -- No (Error) --> X["End of Flow<br/>(Return Nil)"]
        X --> Q["Send Notification Email"]
        W --> L[Send to Deletion Channel]

        G -- Unknown Event --> L
    end

    subgraph "Phase 3: Deletion Cycle"
        L --> R["Channel: deleteStream"]
        C --> S("Deletion Consumer")
        R --> S
        S --> T("Delete Message<br/>from the SQS Queue")
    end

    %% --- Styles for Clarity ---
    style A fill:#cde4f9,stroke:#0b5ed7
    style T fill:#f8d7da,stroke:#721c24
    style S fill:#fff3cd,stroke:#856404
    style C fill:#fff3cd,stroke:#856404
    style F fill:#d1ecf1,stroke:#0c5460
---
// Función auxiliar para configurar el entorno de Vault
def setupVaultEnvironment(Map params = [:], String token) {
    def environment = [
        "VAULT_ADDR=https://hcvdev.fiscloudservices.com", // Puedes parametrizar esto si es necesario
        "VAULT_NAMESPACE=${params.namespace}",
        "VAULT_FORMAT=json",
        "VAULT_TOKEN=${token}"
    ]
    return environment
}

// Función para verificar si una política existe
// Params:
//   - name: Nombre de la política a verificar
//   - namespace: Namespace de Vault
//   - token: Token de Vault para autenticación
Boolean policyExists(Map params = [:], String token) {
    if (!params.name || !params.namespace || !token) {
        error "policyExists: Los parámetros 'name', 'namespace' y 'token' son obligatorios."
    }
    def env = setupVaultEnvironment(params, token)
    withEnv(env) {
        try {
            // Intenta listar la política específica. Si no existe, el comando fallará con un código de salida distinto de 0.
            // La salida JSON para una política existente es un objeto con la política.
            // Para una inexistente, la salida es vacía o un error de la CLI.
            String output = sh(script: "vault policy read ${params.name}", returnStdout: true, returnStatus: true)
            // Si el comando no lanza un error y devuelve algo, la política probablemente existe
            // Un read exitoso devuelve un JSON con la política
            if (output.trim()) {
                // Intenta parsear como JSON para confirmar que es una respuesta válida
                try {
                    readJSON(text: output)
                    echo "La política '${params.name}' existe."
                    return true
                } catch (JSONException e) {
                    echo "vault policy read no devolvió un JSON válido para '${params.name}'. Posiblemente no existe o hubo un error inesperado."
                    return false
                }
            }
            echo "La política '${params.name}' no existe."
            return false
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
            // Esto ocurre si sh() falla (código de salida != 0)
            echo "La política '${params.name}' no existe (error al leer la política)."
            return false
        }
    }
}

// Función para verificar si un rol existe (asumiendo un engine como Kubernetes, AWS, etc.)
// Para este ejemplo, asumiremos un rol de Kubernetes.
// Adapta la ruta si utilizas otro engine (e.g., /auth/aws/role/your-role-name)
// Params:
//   - name: Nombre del rol a verificar
//   - namespace: Namespace de Vault
//   - token: Token de Vault para autenticación
//   - authMountPath: La ruta de montaje del método de autenticación (e.g., 'kubernetes')
Boolean roleExists(Map params = [:], String token, String authMountPath) {
    if (!params.name || !params.namespace || !token || !authMountPath) {
        error "roleExists: Los parámetros 'name', 'namespace', 'token' y 'authMountPath' son obligatorios."
    }
    def env = setupVaultEnvironment(params, token)
    withEnv(env) {
        try {
            // Intenta leer la configuración del rol. Si no existe, fallará.
            String output = sh(script: "vault read ${authMountPath}/role/${params.name}", returnStdout: true, returnStatus: true)
            if (output.trim()) {
                try {
                    readJSON(text: output)
                    echo "El rol '${params.name}' en '${authMountPath}' existe."
                    return true
                } catch (JSONException e) {
                    echo "vault read de rol no devolvió un JSON válido para '${params.name}'. Posiblemente no existe o hubo un error inesperado."
                    return false
                }
            }
            echo "El rol '${params.name}' en '${authMountPath}' no existe."
            return false
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
            echo "El rol '${params.name}' en '${authMountPath}' no existe (error al leer el rol)."
            return false
        }
    }
}

// Función para verificar si un secreto existe en un KV engine v2
// Params:
//   - path: Ruta completa del secreto (e.g., 'secret/data/myapp/config')
//   - namespace: Namespace de Vault
//   - token: Token de Vault para autenticación
Boolean secretExists(Map params = [:], String token) {
    if (!params.path || !params.namespace || !token) {
        error "secretExists: Los parámetros 'path', 'namespace' y 'token' son obligatorios."
    }
    def env = setupVaultEnvironment(params, token)
    withEnv(env) {
        try {
            // Para KV v2, 'vault kv get' devuelve un error si el secreto no existe.
            // Si el secreto existe pero no tiene datos, devolverá la metadata.
            // Queremos verificar si la ruta existe.
            String output = sh(script: "vault kv get -format=json ${params.path}", returnStdout: true, returnStatus: true)
            if (output.trim()) {
                try {
                    def secretData = readJSON(text: output)
                    // Verifica si hay datos en el secreto o si solo es metadata vacía
                    if (secretData?.data?.data || secretData?.data?.metadata) {
                        echo "El secreto en la ruta '${params.path}' existe."
                        return true
                    }
                } catch (JSONException e) {
                    echo "vault kv get no devolvió un JSON válido para '${params.path}'. Posiblemente no existe o hubo un error inesperado."
                    return false
                }
            }
            echo "El secreto en la ruta '${params.path}' no existe."
            return false
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
            echo "El secreto en la ruta '${params.path}' no existe (error al leer el secreto)."
            return false
        }
    }
}

// Función para crear o actualizar una política de Vault (idempotente)
// Params:
//   - name: Nombre de la política
//   - policyContent: Contenido HCL de la política
//   - namespace: Namespace de Vault
//   - token: Token de Vault para autenticación
def createPolicy(Map params = [:], String policyContent, String token) {
    if (!params.name || !policyContent || !params.namespace || !token) {
        error "createPolicy: Los parámetros 'name', 'policyContent', 'namespace' y 'token' son obligatorios."
    }

    if (policyExists(name: params.name, namespace: params.namespace, token: token)) {
        echo "La política '${params.name}' ya existe. No se hará nada."
        return
    }

    def env = setupVaultEnvironment(params, token)
    withEnv(env) {
        try {
            // Crea un archivo temporal para el contenido de la política
            writeFile(file: "${params.name}.hcl", text: policyContent)
            sh "vault policy write ${params.name} ${params.name}.hcl"
            echo "Política '${params.name}' creada exitosamente."
        } catch (Exception e) {
            error "Error al crear la política '${params.name}': ${e.message}"
        } finally {
            // Limpia el archivo temporal
            deleteDir() // O un cleanup más específico si no es un workspace dedicado
        }
    }
}

// Función para crear o actualizar un rol de Vault (idempotente)
// Para este ejemplo, asumimos un rol de Kubernetes.
// Adapta el comando `vault write` según el tipo de rol y sus parámetros.
// Params:
//   - name: Nombre del rol
//   - authMountPath: La ruta de montaje del método de autenticación (e.g., 'kubernetes')
//   - roleParameters: Un mapa con los parámetros específicos del rol (e.g., { "bound_service_account_names": "my-sa", "bound_service_account_namespaces": "default", "ttl": "24h" })
//   - namespace: Namespace de Vault
//   - token: Token de Vault para autenticación
def createRole(Map params = [:], String authMountPath, Map roleParameters, String token) {
    if (!params.name || !authMountPath || !roleParameters || !params.namespace || !token) {
        error "createRole: Los parámetros 'name', 'authMountPath', 'roleParameters', 'namespace' y 'token' son obligatorios."
    }

    if (roleExists(name: params.name, namespace: params.namespace, token: token, authMountPath: authMountPath)) {
        echo "El rol '${params.name}' en '${authMountPath}' ya existe. No se hará nada."
        return
    }

    def env = setupVaultEnvironment(params, token)
    withEnv(env) {
        try {
            // Construye el comando `vault write` con los parámetros del rol
            def roleCmd = "vault write ${authMountPath}/role/${params.name}"
            roleParameters.each { key, value ->
                roleCmd += " ${key}=\"${value}\""
            }
            sh roleCmd
            echo "Rol '${params.name}' en '${authMountPath}' creado exitosamente."
        } catch (Exception e) {
            error "Error al crear el rol '${params.name}' en '${authMountPath}': ${e.message}"
        }
    }
}

// Función para crear o actualizar un secreto en un KV engine v2 (idempotente)
// Params:
//   - path: Ruta completa del secreto (e.g., 'secret/data/myapp/config')
//   - secretData: Un mapa con los datos del secreto (e.g., { "username": "admin", "password": "supersecret" })
//   - namespace: Namespace de Vault
//   - token: Token de Vault para autenticación
def createSecret(Map params = [:], Map secretData, String token) {
    if (!params.path || !secretData || !params.namespace || !token) {
        error "createSecret: Los parámetros 'path', 'secretData', 'namespace' y 'token' son obligatorios."
    }

    // No hacemos una verificación de existencia estricta aquí porque 'vault kv put'
    // automáticamente actualiza si ya existe, lo cual es idempotente por naturaleza.
    // Sin embargo, si quieres una verificación más explícita para evitar operaciones innecesarias,
    // podrías comparar el contenido del secreto si existe. Por simplicidad, un 'put' es suficiente para la idempotencia básica.

    def env = setupVaultEnvironment(params, token)
    withEnv(env) {
        try {
            def secretCmd = "vault kv put ${params.path}"
            secretData.each { key, value ->
                secretCmd += " ${key}=\"${value}\""
            }
            sh secretCmd
            echo "Secreto en la ruta '${params.path}' creado/actualizado exitosamente."
        } catch (Exception e) {
            error "Error al crear/actualizar el secreto en la ruta '${params.path}': ${e.message}"
        }
    }
}

// Ejemplo de uso en un pipeline de Jenkins
// pipeline {
//     agent any
//     stages {
//         stage('Configurar Vault') {
//             steps {
//                 script {
//                     def vaultToken = "s.YOUR_VAULT_ROOT_TOKEN_OR_AN_APPROPRIATE_TOKEN" // ¡Cuidado con esto en producción! Usa credenciales de Jenkins.
//                     def vaultNamespace = "admin" // Reemplaza con tu namespace

//                     // Verificar y crear política
//                     def myPolicyContent = """
// path "secret/data/myapp/*" {
//   capabilities = ["read", "list"]
// }
// """
//                     createPolicy(name: "myapp-read-policy", namespace: vaultNamespace, policyContent: myPolicyContent, token: vaultToken)

//                     // Verificar y crear rol (ejemplo de Kubernetes)
//                     def myRoleParameters = [
//                         "bound_service_account_names": "my-app-sa",
//                         "bound_service_account_namespaces": "default",
//                         "policies": "myapp-read-policy",
//                         "ttl": "24h"
//                     ]
//                     createRole(name: "my-app-role", authMountPath: "auth/kubernetes", roleParameters: myRoleParameters, namespace: vaultNamespace, token: vaultToken)

//                     // Verificar y crear secreto KV v2
//                     def mySecretData = [
//                         "username": "appuser",
//                         "password": "apppassword123",
//                         "api_key": "xyz123abc"
//                     ]
//                     createSecret(path: "secret/data/myapp/config", secretData: mySecretData, namespace: vaultNamespace, token: vaultToken)

//                     // Puedes agregar más llamadas a las funciones aquí
//                 }
//             }
//         }
//     }
// }
