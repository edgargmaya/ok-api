import os
from proton import Message, SSLDomain
from proton.handlers import MessagingHandler
from proton.reactor import Container

BROKER_URL = "amqps://YOUR_BROKER_ENDPOINT:5671"
USERNAME = "YOUR_USERNAME"
PASSWORD = "YOUR_PASSWORD"
QUEUE     = "test-queue"

# Ajusta la ruta a tu archivo CA. 
# Este archivo debe contener la CA raíz que firmó el cert de tu broker.
CA_CERT_PATH = "/path/to/AmazonRootCA1.pem"


class TlsSenderReceiver(MessagingHandler):
    def __init__(self, url, queue, ssl_domain):
        super(TlsSenderReceiver, self).__init__()
        self.url = url
        self.queue = queue
        self.ssl_domain = ssl_domain
        self.sent = False

    def on_start(self, event):
        # Establecemos conexión pasando la configuración SSL
        conn = event.container.connect(
            self.url,
            user=USERNAME,
            password=PASSWORD,
            ssl_domain=self.ssl_domain
        )
        self.sender = event.container.create_sender(conn, target=self.queue)
        self.receiver = event.container.create_receiver(conn, source=self.queue)

    def on_sendable(self, event):
        if not self.sent:
            msg = Message(body="Hello from TLS with Python + AMQP!")
            event.sender.send(msg)
            print("Message sent.")
            self.sent = True

    def on_message(self, event):
        print("Message received:", event.message.body)
        event.connection.close()


def main():
    # Si tu entorno ya confía en la CA de Amazon, 
    # podrías no requerir SSLDomain y simplemente conectarte amqps:// ...
    # Pero si necesitas forzar el uso de tu cert file:
    ssl_domain = SSLDomain(SSLDomain.MODE_CLIENT)
    ssl_domain.set_trusted_ca_db(CA_CERT_PATH)

    # Si el cert es autogenerado/no coincide con el hostname, 
    # podrías deshabilitar la verificación (NO recomendado en producción):
    # ssl_domain.set_peer_authentication(SSLDomain.VERIFY_PEER_NAME, None)

    handler = TlsSenderReceiver(BROKER_URL, QUEUE, ssl_domain)
    Container(handler).run()


if __name__ == "__main__":
    main()
