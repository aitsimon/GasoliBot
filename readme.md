# ⛽ GasoliBot - Asistente Inteligente de Repostaje en Telegram

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

## 🔐 Compromiso con la Privacidad (Privacy by Design)
Este bot está diseñado asumiendo que el servidor puede ser comprometido. Los datos geográficos y personales son ilegibles sin la clave de entorno. Además, incluye un flujo de confirmación estricta para que los usuarios puedan aplicar el "Derecho al Olvido" (RGPD), eliminando todo su rastro de la base de datos de forma irreversible con un solo botón.

## 📄 Licencia
Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo `LICENSE` para más detalles.
