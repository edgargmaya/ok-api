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
