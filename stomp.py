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
    subgraph "Fase 1: Inicio y Orquestación"
        A("1. Inicio del Servicio")
        A --> B("Lanza Goroutine de Escucha/Procesamiento")
        A --> C("Lanza Goroutine de Borrado")
    end

    subgraph "Fase 2: Ciclo de Procesamiento de Mensajes"
        B --> D{"Escuchar desde la<br/>Cola SQS en Lotes"}
        D --> E[Canal Interno `messageStream`]
        E --> F("Procesador Central<br/>(HandleMessages)")
        F --> G{"Switch por Tipo de Mensaje<br/>(handleMessage)"}

        G -- Evento: CaaSOrder --> H["Handler: handleOrderCreated"]
        H --> I{"Validación:<br/>¿Registro ya existe en BD?"}
        I -- No (Es nuevo) --> J["Escribir nuevo<br/>registro en BD"]
        I -- Sí (Idempotencia) --> K["Omitir Escritura"]
        J --> L[Enviar a Canal de Borrado]
        K --> L

        G -- Evento: JenkinsJobCompleted --> M["Handler: handleCaaSCIOnboardingCompleted"]
        M --> N{"Validación:<br/>¿Registro existe en BD?"}
        N -- Si --> O["Actualizar<br/>registro en BD"]
        N -- No (Error) --> P["Fin del Flujo<br/>(Return Nil)"]
        O --> Q["Enviar Email de Notificación"]
        Q --> L[Enviar a Canal de Borrado]

        G -- Evento: Vault --> U["Handler: syncAndTriggerOnboarding"]
        U --> V{"Validación"}
        V -- Si --> W["Actualizar<br/>registro en BD"]
        V -- No (Error) --> X["Fin del Flujo<br/>(Return Nil)"]
        X --> Q["Enviar Email de Notificación"]
        W --> L[Enviar a Canal de Borrado]

        G -- Evento Desconocido --> L
    end

    subgraph "Fase 3: Ciclo de Eliminación"
        L --> R["Canal: deleteStream"]
        C --> S("Consumidor de Borrado")
        R --> S
        S --> T("Eliminar Mensaje<br/>de la Cola SQS")
    end

    %% --- Estilos para Claridad ---
    style A fill:#cde4f9,stroke:#0b5ed7
    style T fill:#f8d7da,stroke:#721c24
    style S fill:#fff3cd,stroke:#856404
    style C fill:#fff3cd,stroke:#856404
    style F fill:#d1ecf1,stroke:#0c5460
