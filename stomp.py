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
// ========= FUNCIONES DE VAULT ADAPTADAS PARA EJECUCIÓN LOCAL =========

import groovy.json.JsonSlurper
import java.nio.file.Files
import java.nio.file.Paths

// Función auxiliar para configurar el entorno de Vault
def setupVaultEnvironment(Map params = [:], String token) {
    def environment = [
        "VAULT_ADDR"    : "https://hcvdev.fiscloudservices.com",
        "VAULT_NAMESPACE": params.namespace,
        "VAULT_FORMAT"  : "json",
        "VAULT_TOKEN"   : token
    ]
    return environment
}

// Función para ejecutar comandos de shell de forma segura
def executeShell(Map env, String script, boolean throwOnError = true) {
    def process = script.execute(null, env)
    process.waitForProcessOutput(System.out, System.err)
    def exitCode = process.exitValue()

    if (throwOnError && exitCode != 0) {
        throw new RuntimeException("Comando fallido con código de salida ${exitCode}: ${script}")
    }
    return process.text
}

/**
 * Verifica si una política de Vault existe.
 *
 * @param params Mapa que contiene el nombre de la política (`name`) y el namespace (`namespace`).
 * @param token Token de Vault para autenticación.
 * @return `true` si la política existe, `false` en caso contrario.
 */
Boolean policyExists(Map params = [:], String token) {
    if (!params.name || !params.namespace || !token) {
        error "policyExists: Los parámetros 'name', 'namespace' y 'token' son obligatorios."
    }

    // Usar con withEnv() para establecer variables de entorno de forma segura
    withEnv([
        "VAULT_ADDR=https://hcvdev.fiscloudservices.com",
        "VAULT_NAMESPACE=${params.namespace}",
        "VAULT_FORMAT=json",
        "VAULT_TOKEN=${token}"
    ]) {
        try {
            // 'vault policy read' fallará si la política no existe.
            // Usamos 'returnStatus: true' para capturar el código de salida
            def result = sh(
                script: "vault policy read ${params.name}",
                returnStatus: true
            )

            // Si el código de salida es 0, el comando fue exitoso y la política existe.
            if (result == 0) {
                echo "La política '${params.name}' existe."
                return true
            } else {
                echo "La política '${params.name}' no existe."
                return false
            }
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
            // Este catch es para manejo de errores más complejos o interrupciones,
            // pero 'returnStatus' ya maneja la mayoría de los casos de "no existe".
            echo "La política '${params.name}' no existe (error al leer la política)."
            return false
        }
    }
}

// Función para crear una política de Vault (idempotente)
def createPolicy(Map params = [:], String policyContent, String token) {
    if (!params.name || !policyContent || !params.namespace || !token) {
        throw new IllegalArgumentException("createPolicy: Los parámetros 'name', 'policyContent', 'namespace' y 'token' son obligatorios.")
    }

    if (policyExists(name: params.name, namespace: params.namespace, token: token)) {
        println "La política '${params.name}' ya existe. No se hará nada."
        return
    }

    def env = setupVaultEnvironment(params, token)
    def tempFile = "${params.name}.hcl"

    try {
        // Crear archivo temporal con el contenido de la política
        Files.write(Paths.get(tempFile), policyContent.getBytes())

        def command = "vault policy write ${params.name} ${tempFile}"
        executeShell(env, command)
        println "Política '${params.name}' creada exitosamente."
    } catch (Exception e) {
        throw new RuntimeException("Error al crear la política '${params.name}': ${e.message}", e)
    } finally {
        // Limpiar el archivo temporal
        new File(tempFile).delete()
    }
}

// ========= CÓDIGO DE EJECUCIÓN =========

// Configura tus variables
def VAULT_TOKEN = "s.YOUR_VAULT_ROOT_TOKEN_OR_AN_APPROPRIATE_TOKEN" // <-- Reemplaza con tu token real
def VAULT_NAMESPACE = "admin" // <-- Reemplaza con tu namespace
def POLICY_NAME = "test-policy"
def POLICY_PATH = "secret/data/temporary-app/*" // Ruta del secreto KV v2

// Define el contenido de la política
def myPolicyContent = """
path "${POLICY_PATH}" {
  capabilities = ["read", "write", "create", "update", "delete", "list"]
}
"""

try {
    // Invoca la función para crear la política
    println "Iniciando la creación de la política '${POLICY_NAME}'..."
    createPolicy(name: POLICY_NAME, namespace: VAULT_NAMESPACE, policyContent: myPolicyContent, token: VAULT_TOKEN)
    println "Proceso completado."

} catch (Exception e) {
    System.err.println("¡ERROR! Algo salió mal durante la ejecución del script.")
    e.printStackTrace()
}



def command = "echo \"${policyContent.replaceAll('"', '\\"')}\" | vault policy write ${params.name} -"








def createSecret(Map params = [:], Map secretData, String token) {
    if (!params.path || !secretData || !params.namespace || !token) {
        error "createSecret: Los parámetros 'path', 'secretData', 'namespace' y 'token' son obligatorios."
    }

    def env = [
        "VAULT_ADDR=https://hcvdev.fiscloudservices.com",
        "VAULT_NAMESPACE=${params.namespace}",
        "VAULT_TOKEN=${token}"
    ]

    withEnv(env) {
        try {
            // Construir el string de datos para el comando
            def dataString = secretData.collect { key, value ->
                "${key}=\"${value.toString().replaceAll('"', '\\"')}\""
            }.join(' ')

            // Comando que inyecta los datos a través de stdin
            sh "echo \"${dataString}\" | vault kv put ${params.path}"
            
            echo "Secreto en la ruta '${params.path}' creado/actualizado exitosamente."
        } catch (Exception e) {
            error "Error al crear/actualizar el secreto en la ruta '${params.path}': ${e.message}"
        }
    }
}



def setSecretMetadata(Map params = [:], Map metadata, String token) {
    if (!params.path || !metadata || !params.namespace || !token) {
        error "setSecretMetadata: Los parámetros 'path', 'metadata', 'namespace' y 'token' son obligatorios."
    }

    // Se asume que el secreto ya existe. Si no, esta operación fallará.
    // Podrías añadir una verificación con 'secretExists' si lo deseas.

    def env = [
        "VAULT_ADDR=https://hcvdev.fiscloudservices.com",
        "VAULT_NAMESPACE=${params.namespace}",
        "VAULT_TOKEN=${token}"
    ]

    withEnv(env) {
        try {
            // Construir el string de metadatos
            def metadataString = metadata.collect { key, value ->
                "-add ${key}=\"${value.toString().replaceAll('"', '\\"')}\""
            }.join(' ')

            // Comando para agregar o actualizar metadatos
            sh "vault kv metadata put ${params.path} ${metadataString}"
            
            echo "Metadatos en la ruta '${params.path}' creados/actualizados exitosamente."
        } catch (Exception e) {
            error "Error al setear metadatos para el secreto en la ruta '${params.path}': ${e.message}"
        }
    }
}



def mySecretData = [
                        "username": "app_user",
                        "password": "strong-password-123",
                        "db_name": "production_db"
                    ]

https://10.237.x.x:1443/tasks/admin/library/jobconfig/LibraryJobConfigTasks/viewJobConfig?jobConfigId=508

https://x.x.x.com:8443/git/?p=A0006-CRM/ADA_BT_Backend.git
