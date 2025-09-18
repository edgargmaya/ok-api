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

