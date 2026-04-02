# ⛽ GasoliBot - Asistente Inteligente de Repostaje en Telegram

<p align="center">
  <a href="https://gasolinabot.me">
    <img src="https://gasolinabot.me/logo.jpg" alt="GasoliBot Logo" width="200" style="border-radius: 50%;">
  </a>
</p>

<p align="center">
  <strong>🌐 Bot en funcionamiento: <a href="https://gasolinabot.me">gasolinabot.me</a></strong><br>
  <em>Ahorra tiempo, dinero y gestiona tu consumo desde una sola interfaz.</em>
</p>

---

GasoliBot es un bot de Telegram avanzado escrito en Python diseñado para ayudar a los usuarios a encontrar las gasolineras más baratas de España en tiempo real, gestionar su garaje virtual y llevar un control exhaustivo de sus gastos de combustible.

El proyecto destaca por su enfoque estricto en la privacidad del usuario, empleando encriptación de grado industrial para los datos sensibles, y por su alta optimización de recursos en el servidor mediante algoritmos de filtrado espacial (Bounding Box) y caché en memoria RAM.

## ✨ Características Principales

* **📍 Búsqueda Geoespacial Optimizada:** Encuentra los mejores precios en un radio personalizado. Utiliza un filtro de Bounding Box matemático para descartar coordenadas lejanas antes de calcular distancias reales, ahorrando ciclos de CPU.
* **🧠 Caché Dinámica en RAM:** Integra un sistema de caché inteligente con tiempos de caducidad aleatorios (25-40 min) para minimizar las peticiones a la API del Ministerio y garantizar respuestas en milisegundos.
* **🛡️ Privacidad y Cifrado (Fernet):** Las ubicaciones de los usuarios (latitud/longitud) y sus nombres de usuario se cifran en la base de datos SQLite mediante criptografía simétrica.
* **⏰ Automatización y Alertas:** Sistema de trabajos programados (Cron) para enviar el Top de gasolineras baratas diariamente a la hora configurada por cada usuario.
* **📈 Garaje Virtual y Estadísticas:** Registro de repostajes (litros, precio, kilómetros). Generación nativa de gráficas de consumo usando `matplotlib` y exportación de datos a formato `.csv`.
* **🔧 Panel de Administración CLI:** Incluye una herramienta independiente (`admin.py`) para gestionar usuarios, revisar el estado de la caché en tiempo real y alternar modos de depuración sin reiniciar el servidor manualmente.

## 🛠️ Stack Tecnológico

* **Lenguaje:** Python 3.9+
* **Librerías Core:** `python-telegram-bot` (v20+), `cryptography`, `matplotlib`, `requests`
* **Base de Datos:** SQLite3
* **Arquitectura:** Webhooks (Apto para despliegue tras Reverse Proxy con Nginx)

## 🚀 Instalación y Despliegue

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/TuUsuario/GasoliBot.git](https://github.com/TuUsuario/GasoliBot.git)
   cd GasoliBot
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Variables de Entorno (.env):**
   Crea un archivo `.env` en la raíz del proyecto con tus credenciales:
   ```env
   BOTFATHER_TOKEN=tu_token_de_telegram
   ENCRYPTION_KEY=tu_clave_generada_con_fernet
   BOT_DOMAIN=[https://tu-dominio.com](https://tu-dominio.com)
   ```

4. **Configuración:**
   Edita el archivo `config.json` para personalizar los botones, tipos de combustible y vehículos disponibles en la interfaz.

5. **Ejecución:**
   ```bash
   python gasolibot.py
   ```
   *(Para entornos de producción, se recomienda gestionar el proceso con PM2 o Systemd).*

## 🌐 Arquitectura de Despliegue (Real World Case)

Este proyecto no es solo un script local; está desplegado y operando en un entorno de producción real con la siguiente infraestructura:

* **Hosting:** VPS en **DigitalOcean** (Droplet) con Ubuntu Server.
* **Gestión de Procesos:** Utiliza **PM2** para garantizar que el bot esté online 24/7, con reinicio automático en caso de fallos del sistema o del servidor.
* **Seguridad de Red:** Protegido mediante un **Reverse Proxy con Nginx**, gestionando certificados **SSL (HTTPS)** para una comunicación segura con los servidores de Telegram.
* **Webhooks:** A diferencia del método tradicional de *polling*, este bot utiliza *webhooks* para una respuesta instantánea y un consumo de CPU mínimo, optimizando los recursos del VPS.
* **CI/CD Manual:** Flujo de trabajo basado en **Git** para actualizaciones rápidas desde el entorno de desarrollo al de producción.


## 🔐 Compromiso con la Privacidad (Privacy by Design)

GasoliBot integra capas de seguridad nativas para garantizar que la información del usuario no sea vulnerable, incluso en entornos de producción:

* [cite_start]**Cifrado de Datos Sensibles:** Las coordenadas geográficas (latitud/longitud) y los nombres de usuario se almacenan cifrados en la base de datos mediante criptografía simétrica (Fernet/AES-256). [cite: 1]
* [cite_start]**Ilegibilidad de la Base de Datos:** En caso de acceso no autorizado al archivo SQLite, los datos personales resultan indescifrables sin la clave correspondiente cargada en memoria. [cite: 1]
* [cite_start]**Derecho al Olvido (RGPD):** El sistema incluye una función de purga que permite al usuario eliminar de forma irreversible toda su información y registros de repostaje con un solo comando. [cite: 1]
* [cite_start]**Gestión de Sesiones:** No se almacenan historiales de ubicación en texto plano; el bot solo procesa la posición actual para el cálculo de distancias y la descarta tras la respuesta o el cifrado. [cite: 1]

## 📄 Licencia
Este proyecto se distribuye bajo una Licencia de Uso Personal y No Comercial. Consulta el archivo `LICENSE` para más detalles.
