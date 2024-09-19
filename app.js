const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();

// Middleware para parsear cuerpos JSON
app.use(express.json({ limit: '8mb' }));

app.post('/ok', (req, res) => {
    // Respuesta y log en consola
    const responseMessage = { response: 'OK' };
    console.log(JSON.stringify(responseMessage));
    res.json(responseMessage);

    // Obtener el cuerpo de la solicitud
    const requestBody = req.body;

    // Generar timestamp para el nombre del archivo
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `request-${timestamp}.json`;
    const filepath = path.join(__dirname, filename);

    // Guardar el cuerpo en un archivo JSON
    fs.writeFile(filepath, JSON.stringify(requestBody, null, 2), (err) => {
        if (err) {
            console.error('Error al escribir el archivo:', err);
        } else {
            console.log(`Archivo guardado como ${filename}`);
        }
    });
});

// Iniciar el servidor
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Servidor escuchando en http://localhost:${PORT}`);
});
