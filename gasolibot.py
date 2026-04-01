import logging, sqlite3, datetime, os, re, math, requests, urllib3, asyncio, csv, json, random
from io import BytesIO, StringIO
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from cryptography.fernet import Fernet

# --- IMPORTANTE PARA GRÁFICAS EN SERVIDORES SIN PANTALLA ---
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN DE RUTAS DINÁMICAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "basededatos.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
IMAGEN_BIENVENIDA = os.path.join(BASE_DIR, "medios", "imagen_bienvenida.png")

# --- CARGAR CONFIGURACIÓN JSON ---
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# --- MODO DEBUG PARA LOGS LECTURA DINÁMICA ---
DEBUG_MODE = CONFIG.get("debug", False) 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                    level=logging.INFO if DEBUG_MODE else logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 

if not DEBUG_MODE:
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)

BTN = CONFIG["botones"]
TIPOS_VEHICULOS = CONFIG["vehiculos"]
EMOJIS_TIPOS = {v: k for k, v in TIPOS_VEHICULOS.items()} 
CAMPOS_API = CONFIG["combustibles"]

load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
TOKEN = os.getenv('BOTFATHER_TOKEN')
DOMAIN = os.getenv('BOT_DOMAIN', 'https://tu-dominio-ejemplo.com')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
SECRET = os.getenv('WEB_SECRET')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if not ENCRYPTION_KEY:
    logger.error("🚨 FALTA ENCRYPTION_KEY EN EL ARCHIVO .ENV 🚨")
    cipher_suite = None
else:
    cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def encrypt_data(data):
    if data is None or not cipher_suite: return None
    return cipher_suite.encrypt(str(data).encode('utf-8')).decode('utf-8')

def decrypt_data(data, tipo=str):
    if data is None or not cipher_suite: return None
    try:
        descifrado = cipher_suite.decrypt(str(data).encode('utf-8')).decode('utf-8')
        if descifrado == "None": return None
        return tipo(descifrado)
    except:
        try: return tipo(data)
        except: return None

# --- VARIABLES DE CACHÉ EN MEMORIA ---
CACHE_API = None
CACHE_TIME = None
TIEMPO_CACHE_MINUTOS = 0 

async def obtener_datos_ministerio():
    global CACHE_API, CACHE_TIME, TIEMPO_CACHE_MINUTOS
    ahora = datetime.datetime.now()
    if CACHE_API and CACHE_TIME and (ahora - CACHE_TIME).total_seconds() < (TIEMPO_CACHE_MINUTOS * 60):
        return CACHE_API
    try:
        url = "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"
        res = await asyncio.to_thread(requests.get, url, timeout=30, verify=False)
        datos_brutos = res.json().get('ListaEESSPrecio', [])
        
        datos_limpios = []
        for e in datos_brutos:
            try:
                e['lat_num'] = float(e['Latitud'].replace(',', '.'))
                e['lon_num'] = float(e['Longitud (WGS84)'].replace(',', '.'))
                datos_limpios.append(e)
            except:
                continue
                
        CACHE_API = datos_limpios
        CACHE_TIME = ahora
        TIEMPO_CACHE_MINUTOS = random.randint(25, 40)
        logger.info(f"🔄 Caché actualizada. Procesadas {len(datos_limpios)} gasolineras. Caduca en {TIEMPO_CACHE_MINUTOS} mins.")
        return CACHE_API
    except Exception as e:
        logger.error(f"🚨 Error API Ministerio: {e}")
        return CACHE_API if CACHE_API else []

# Estados de Conversación
ESPERANDO_UBICACION, PREGUNTAR_COMBUSTIBLE, PREGUNTAR_FAVORITA, ESPERANDO_HORA, ESPERANDO_RADIO, ESPERANDO_LIMITE, ESPERANDO_VEHICULO, ESPERANDO_EMOJI, ESPERANDO_NOMBRE_VEHICULO, ESPERANDO_COMBUSTIBLE_REPOSTAJE, ESPERANDO_LITROS, ESPERANDO_PRECIO_LITRO, ESPERANDO_KM, CONFIRMAR_BORRADO = range(14)

# --- TECLADOS DINÁMICOS ---
MENU_PRINCIPAL = ReplyKeyboardMarkup([
    [BTN["precios"]], 
    [BTN["repostaje"], BTN["garaje"]], 
    [BTN["estadisticas"], BTN["ubicacion"]], 
    [BTN["ayuda"], BTN["config"]],          
    [BTN["borrar"]]
], resize_keyboard=True)

MENU_ESTADISTICAS = ReplyKeyboardMarkup([[BTN["excel"]], [BTN["volver"]]], resize_keyboard=True)
MENU_CONFIGURACION = ReplyKeyboardMarkup([[BTN["combustible"], BTN["radio"]], [BTN["hora"], BTN["cantidad"]], [BTN["volver"]]], resize_keyboard=True)

TECLADO_VOLVER = ReplyKeyboardMarkup([[BTN["volver"]]], resize_keyboard=True)
TECLADO_CANCELAR = ReplyKeyboardMarkup([[BTN["cancelar"]]], resize_keyboard=True)
TECLADO_CONFIRMAR_BORRADO = ReplyKeyboardMarkup([["⚠️ SÍ, BORRAR MIS DATOS"], [BTN["cancelar"]]], resize_keyboard=True, one_time_keyboard=True)

TECLADO_COMBUSTIBLE = ReplyKeyboardMarkup([["Gasolina 95", "Diésel"], ["Gasolina 98", "GLP"]], resize_keyboard=True, one_time_keyboard=True)
TECLADO_COMBUSTIBLE_VOLVER = ReplyKeyboardMarkup([["Gasolina 95", "Diésel"], ["Gasolina 98", "GLP"], [BTN["volver"]]], resize_keyboard=True, one_time_keyboard=True)
TECLADO_COMBUSTIBLE_CANCELAR = ReplyKeyboardMarkup([["Gasolina 95", "Diésel"], ["Gasolina 98", "GLP"], [BTN["cancelar"]]], resize_keyboard=True, one_time_keyboard=True)

TECLADO_CONFIRMACION = ReplyKeyboardMarkup([[BTN["guardar"], BTN["no_guardar"]]], resize_keyboard=True, one_time_keyboard=True)
TECLADO_HORA_CANCELAR = ReplyKeyboardMarkup([["09:00", "14:00", "20:00"], [BTN["cancelar"]]], resize_keyboard=True, one_time_keyboard=True)
TECLADO_HORA_VOLVER = ReplyKeyboardMarkup([["09:00", "14:00", "20:00"], [BTN["volver"]]], resize_keyboard=True, one_time_keyboard=True)

lista_emojis = list(TIPOS_VEHICULOS.values())
TECLADO_EMOJIS = ReplyKeyboardMarkup([lista_emojis[i:i+4] for i in range(0, len(lista_emojis), 4)] + [[BTN["cancelar"]]], resize_keyboard=True, one_time_keyboard=True)

# --- DB LIMPIA ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, lat REAL, lon REAL, hora INTEGER, minutos INTEGER, combustible TEXT, radio INTEGER DEFAULT 15, limite INTEGER DEFAULT 5, nombre TEXT, username TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_precios (id INTEGER PRIMARY KEY AUTOINCREMENT, rotulo TEXT, direccion TEXT, lat REAL, lon REAL, combustible TEXT, precio REAL, fecha TEXT, UNIQUE(rotulo, direccion, combustible, fecha))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS consumos (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, vehiculo TEXT, litros REAL, precio_litro REAL, total REAL, km REAL, l_100km REAL, combustible TEXT, fecha TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS vehiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tipo TEXT, nombre TEXT)''')
    conn.commit()
    conn.close()

def obtener_usuario_db(user_id):
    conn = sqlite3.connect(DB_PATH)
    user = conn.execute('SELECT lat, lon, combustible, radio, limite FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user: return (decrypt_data(user[0], float), decrypt_data(user[1], float), user[2], user[3], user[4])
    return None

def calcular_distancia(lat1, lon1, lat2, lon2):
    rad = math.pi / 180
    dlat, dlon = (lat2 - lat1) * rad, (lon2 - lon1) * rad
    a = math.sin(dlat/2)**2 + math.cos(lat1*rad) * math.cos(lat2*rad) * math.sin(dlon/2)**2
    return 2 * 6371 * math.atan2(math.sqrt(a), math.sqrt(1-a))

async def calcular_media_zona(lat, lon, pref_user, radio=15):
    try:
        todas = await obtener_datos_ministerio()
        campo_fav = CAMPOS_API.get(pref_user, "Precio Gasolina 95 E5")
        precios = []
        margen_grados = radio / 80.0 
        for e in todas:
            e_lat, e_lon = e['lat_num'], e['lon_num']
            if abs(e_lat - lat) > margen_grados or abs(e_lon - lon) > margen_grados:
                continue
            if calcular_distancia(lat, lon, e_lat, e_lon) <= radio:
                p_str = e.get(campo_fav, "")
                if p_str: precios.append(float(p_str.replace(',', '.')))
        if precios: return sum(precios) / len(precios)
    except: pass
    return None

async def generar_mensaje_precios(lat, lon, pref_user, radio=15, limite=5):
    try:
        todas = await obtener_datos_ministerio()
        campo_fav = CAMPOS_API.get(pref_user, "Precio Gasolina 95 E5")
        en_radio, vistos = [], set()
        margen_grados = radio / 80.0 
        for e in todas:
            try:
                identificador = (e['Rótulo'], e['Dirección'])
                if identificador in vistos: continue
                e_lat, e_lon = e['lat_num'], e['lon_num']
                if abs(e_lat - lat) > margen_grados or abs(e_lon - lon) > margen_grados:
                    continue
                dist = calcular_distancia(lat, lon, e_lat, e_lon)
                if dist <= radio:
                    p_str = e.get(campo_fav, "")
                    if p_str:
                        p_num = float(p_str.replace(',', '.'))
                        vistos.add(identificador)
                        txt_p = [f"⭐️ *{pref_user}: {p_str} €/L*"]
                        for n, c in CAMPOS_API.items():
                            if n != pref_user and e.get(c): txt_p.append(f"🔹 {n}: {e.get(c)} €/L")
                        en_radio.append({'n': e['Rótulo'], 'd': dist, 'p_num': p_num, 'txt': "\n".join(txt_p), 'dir': e['Dirección'], 'l': f"http://maps.google.com/?q={e_lat},{e_lon}", 'e_lat': e_lat, 'e_lon': e_lon})
            except: continue
        res_filtrado = sorted(en_radio, key=lambda x: x['p_num'])[:limite]
        if not res_filtrado: return None
        try:
            fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
            datos_insertar = [(g['n'], g['dir'], g['e_lat'], g['e_lon'], pref_user, g['p_num'], fecha_hoy) for g in res_filtrado]
            conn = sqlite3.connect(DB_PATH)
            conn.executemany('''INSERT INTO historico_precios (rotulo, direccion, lat, lon, combustible, precio, fecha) 
                                VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(rotulo, direccion, combustible, fecha) DO UPDATE SET precio=excluded.precio''', datos_insertar)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando histórico: {e}")
        txt = f"⛽ **TOP {limite} MÁS BARATAS ({radio}km)**\n\n"
        for g in res_filtrado: txt += f"🏢 *{g['n']}*\n{g['txt']}\n📏 {round(g['d'], 1)} km | [MAPA]({g['l']})\n📍 {g['dir']}\n───\n"
        return txt
    except: return "⚠️ Error procesando los datos de las gasolineras."

async def revisar_alarmas(context: ContextTypes.DEFAULT_TYPE):
    h, m = datetime.datetime.now().hour, datetime.datetime.now().minute
    conn = sqlite3.connect(DB_PATH)
    usuarios = conn.execute('SELECT id, lat, lon, combustible, radio, limite FROM usuarios WHERE hora = ? AND minutos = ?', (h, m)).fetchall()
    conn.close()
    if usuarios:
        logger.info(f"⏰ Lanzando aviso diario a {len(usuarios)} usuario(s) configurado(s) a las {h:02d}:{m:02d}...")
        for u in usuarios:
            user_id, lat_cifrada, lon_cifrada, comb, radio, limite = u
            txt = await generar_mensaje_precios(decrypt_data(lat_cifrada, float), decrypt_data(lon_cifrada, float), comb, radio if radio else 15, limite if limite else 5)
            if txt:
                try: await context.bot.send_message(chat_id=user_id, text=f"⏰ **¡TU AVISO DIARIO!**\n\n{txt}", parse_mode=ParseMode.MARKDOWN)
                except: pass

async def comando_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not obtener_usuario_db(update.effective_user.id): return await inicio(update, context)
    await update.message.reply_text("🎛️ Aquí tienes el menú principal:", reply_markup=MENU_PRINCIPAL)
    return ConversationHandler.END

async def comando_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not obtener_usuario_db(update.effective_user.id): return await inicio(update, context)
    texto = update.message.text if update.message else ""
    msg = "🏠 Volviendo al menú principal..." if texto == BTN["volver"] else "🛑 Operación cancelada. Volviendo al menú principal."
    await update.message.reply_text(msg, reply_markup=MENU_PRINCIPAL)
    return ConversationHandler.END

async def mostrar_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "ℹ️ **GUÍA RÁPIDA DE GASOLIBOT**\n\n"
        "Este bot te ayuda a encontrar gasolina barata y a controlar tus gastos.\n\n"
        "🔧 **Comandos Disponibles:**\n"
        "🔹 /start - Crear cuenta o actualizar tu ubicación principal.\n"
        "🔹 /menu - Muestra el teclado de botones principal.\n"
        "🔹 /cancel - Cancela cualquier operación a medias.\n"
        "🔹 /help - Muestra este panel de ayuda.\n\n"
        "👇 **Uso de los Botones Principales:**\n"
        "• **Ver precios:** Muestra el Top gasolineras al instante.\n"
        "• **Anotar Repostaje:** Registra tus consumos y ahorros.\n"
        "• **Mis Estadísticas:** Tu resumen visual y exportación a Excel.\n"
        "• **Mi Configuración:** Ajusta tus preferencias de búsqueda y avisos.\n\n"
        "🔒 *Tus datos están protegidos. Lee nuestra* [Política de Privacidad](https://gasolinabot.me/privacidad.html)\n\n"
        "*(Usa el menú inferior para navegar)*"
    )
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_PRINCIPAL, disable_web_page_preview=True)
    return ConversationHandler.END

async def ver_garaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    vehiculos = conn.execute('SELECT tipo, nombre FROM vehiculos WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    if not vehiculos:
        await update.message.reply_text("🚘 **Tu Garaje está vacío.**\n\nTu primer vehículo se creará automáticamente la próxima vez que anotes un repostaje.", parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    txt = "🚘 **TU GARAJE**\n\nEstos son los vehículos que tienes guardados:\n"
    for v in vehiculos:
        emoji_visual = TIPOS_VEHICULOS.get(v[0], TIPOS_VEHICULOS["coche"])
        txt += f"└ {emoji_visual} {v[1]}\n"
    txt += f"\n*(Para añadir más vehículos, pulsa en {BTN['repostaje']})*"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_PRINCIPAL)
    return ConversationHandler.END

async def iniciar_repostaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not obtener_usuario_db(user_id):
        await update.message.reply_text("❌ Primero debes configurar tu ubicación con /start", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    conn = sqlite3.connect(DB_PATH)
    vehiculos = conn.execute('SELECT tipo, nombre FROM vehiculos WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    if not vehiculos:
        await update.message.reply_text("📝 **Anotar Repostaje**\n\nAún no tienes ningún vehículo en tu garaje. Vamos a crearlo.\n\nElige un icono que lo represente:", reply_markup=TECLADO_EMOJIS)
        return ESPERANDO_EMOJI
    botones = [[f"{TIPOS_VEHICULOS.get(v[0], TIPOS_VEHICULOS['coche'])} {v[1]}"] for v in vehiculos]
    botones.append([BTN["nuevo_vehiculo"], BTN["cancelar"]])
    teclado_pers = ReplyKeyboardMarkup(botones, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("📝 **Anotar Repostaje**\n\n¿A qué vehículo le estás echando gasolina?", reply_markup=teclado_pers)
    return ESPERANDO_VEHICULO

async def recibir_vehiculo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    if texto == BTN["nuevo_vehiculo"]:
        await update.message.reply_text("Elige un icono para tu nuevo vehículo:", reply_markup=TECLADO_EMOJIS)
        return ESPERANDO_EMOJI
    partes = texto.split(" ", 1)
    nombre_limpio = partes[1] if len(partes) > 1 and partes[0] in EMOJIS_TIPOS else texto
    context.user_data['repostaje_vehiculo'] = nombre_limpio
    await update.message.reply_text(f"Seleccionado: **{nombre_limpio}**\n\n⛽ ¿Qué combustible le has echado?", parse_mode=ParseMode.MARKDOWN, reply_markup=TECLADO_COMBUSTIBLE_CANCELAR)
    return ESPERANDO_COMBUSTIBLE_REPOSTAJE

async def recibir_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    emoji = texto.split()[0]
    tipo = EMOJIS_TIPOS.get(emoji, 'coche')
    context.user_data['temp_tipo'] = tipo
    await update.message.reply_text(f"Icono {emoji} guardado.\n\n¿Qué **nombre** le quieres poner? (Ej: Ibiza, Ninja, Furgo del trabajo):", reply_markup=TECLADO_CANCELAR)
    return ESPERANDO_NOMBRE_VEHICULO

async def recibir_nombre_vehiculo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text
    if nombre in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    tipo = context.user_data.get('temp_tipo', 'coche')
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO vehiculos (user_id, tipo, nombre) VALUES (?, ?, ?)', (update.effective_user.id, tipo, nombre))
    conn.commit()
    conn.close()
    context.user_data['repostaje_vehiculo'] = nombre
    emoji_visual = TIPOS_VEHICULOS.get(tipo, TIPOS_VEHICULOS["coche"])
    await update.message.reply_text(f"✅ ¡Añadido a tu garaje: **{emoji_visual} {nombre}**!\n\n⛽ ¿Qué combustible le has echado?", parse_mode=ParseMode.MARKDOWN, reply_markup=TECLADO_COMBUSTIBLE_CANCELAR)
    return ESPERANDO_COMBUSTIBLE_REPOSTAJE

async def recibir_combustible_repostaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    combustible = update.message.text
    if combustible in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    if combustible not in CAMPOS_API:
        await update.message.reply_text("⚠️ Por favor, usa los botones del menú para elegir el combustible:", reply_markup=TECLADO_COMBUSTIBLE_CANCELAR)
        return ESPERANDO_COMBUSTIBLE_REPOSTAJE
    context.user_data['repostaje_combustible'] = combustible
    await update.message.reply_text(f"✅ Combustible: {combustible}.\n\n¿Cuántos **litros** has echado? (Ej: 40 o 45.5):", reply_markup=TECLADO_CANCELAR)
    return ESPERANDO_LITROS

async def recibir_litros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    try:
        context.user_data['repostaje_litros'] = float(update.message.text.replace(',', '.'))
        await update.message.reply_text(f"✅ Anotados {context.user_data['repostaje_litros']} L.\n\n¿A qué **precio por litro** lo has pagado? (Ej: 1.54):", reply_markup=TECLADO_CANCELAR)
        return ESPERANDO_PRECIO_LITRO
    except ValueError:
        await update.message.reply_text("⚠️ Escribe un número válido (ej: 40). Inténtalo de nuevo:", reply_markup=TECLADO_CANCELAR)
        return ESPERANDO_LITROS

async def recibir_precio_litro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    try:
        context.user_data['repostaje_precio'] = float(update.message.text.replace(',', '.'))
        await update.message.reply_text(f"✅ Anotado {context.user_data['repostaje_precio']} €/L.\n\n¿Cuántos **kilómetros** has recorrido desde el último repostaje? (Ej: 520.5):", reply_markup=TECLADO_CANCELAR)
        return ESPERANDO_KM
    except ValueError:
        await update.message.reply_text("⚠️ Escribe un precio válido (ej: 1.54). Inténtalo de nuevo:", reply_markup=TECLADO_CANCELAR)
        return ESPERANDO_PRECIO_LITRO

async def guardar_repostaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    try:
        km = float(update.message.text.replace(',', '.'))
        litros = context.user_data.get('repostaje_litros', 0)
        precio_litro = context.user_data.get('repostaje_precio', 0)
        vehiculo = context.user_data.get('repostaje_vehiculo', 'Mi Vehículo')
        combustible_repostado = context.user_data.get('repostaje_combustible', 'Gasolina 95')
        total = round(litros * precio_litro, 2)
        l_100km = round((litros / km) * 100, 2) if km > 0 else 0
        user_id = update.effective_user.id
        user_reg = obtener_usuario_db(user_id)
        if not user_reg: return ConversationHandler.END
        lat, lon, radio = user_reg[0], user_reg[1], user_reg[3] if user_reg[3] else 15
        media_zona = await calcular_media_zona(lat, lon, combustible_repostado, radio)
        msg_ahorro = ""
        if media_zona and precio_litro < media_zona:
            ahorro_total = round((media_zona - precio_litro) * litros, 2)
            msg_ahorro = f"\n💡 *¡Buena jugada!* La media en tu zona hoy es {round(media_zona, 3)}€/L.\nAl repostar aquí **te has ahorrado {ahorro_total}€** 👏\n"
        conn = sqlite3.connect(DB_PATH)
        conn.execute('INSERT INTO consumos (user_id, vehiculo, litros, precio_litro, total, km, l_100km, combustible, fecha) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     (user_id, vehiculo, litros, precio_litro, total, km, l_100km, combustible_repostado, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        msg = f"💾 **¡Repostaje de {vehiculo} guardado!**\n\n⛽ {litros} L x {precio_litro} €/L ({combustible_repostado})\n🛣️ {km} km\n📉 **Consumo:** {l_100km} L/100km\n💰 **Total pagado: {total} €**\n{msg_ahorro}"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ Escribe un kilometraje válido (ej: 500). Inténtalo de nuevo:", reply_markup=TECLADO_CANCELAR)
        return ESPERANDO_KM

async def descargar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    consumos = conn.execute('SELECT fecha, vehiculo, combustible, litros, precio_litro, total, km, l_100km FROM consumos WHERE user_id = ? ORDER BY fecha DESC', (user_id,)).fetchall()
    conn.close()
    if not consumos:
        await update.message.reply_text("📉 Aún no tienes datos para exportar. ¡Anota un repostaje primero!", reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    f = StringIO()
    writer = csv.writer(f, delimiter=';') 
    writer.writerow(['Fecha', 'Vehiculo', 'Combustible', 'Litros', 'Precio/L (€)', 'Total Pagado (€)', 'Km Recorridos', 'Consumo (L/100km)'])
    for c in consumos: writer.writerow(c)
    f.seek(0)
    await context.bot.send_document(
        chat_id=user_id, document=f.getvalue().encode('utf-8'), 
        filename=f"Mis_Consumos_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
        caption="📊 Aquí tienes tus datos listos para abrir en Excel o Google Sheets.", reply_markup=MENU_ESTADISTICAS
    )
    return ConversationHandler.END

async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mensaje_bienvenida = (
        "¡Bienvenido a *GasoliBot*! ⛽📉\n\n"
        "Tu asistente personal para que dejes de pagar de más por la gasolina. Hecho con ❤️ para ayudarte a ahorrar.\n\n"
        "Echa un vistazo a la imagen para descubrir todo lo que puedo hacer por ti. "
        "Para empezar, solo necesitas enviarme tu ubicación pulsando el botón de abajo. 👇"
    )
    teclado = ReplyKeyboardMarkup([[KeyboardButton("📍 Enviar Ubicación", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    if os.path.exists(IMAGEN_BIENVENIDA):
        try:
            with open(IMAGEN_BIENVENIDA, 'rb') as photo:
                await context.bot.send_photo(chat_id=user_id, photo=photo, caption=mensaje_bienvenida, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado)
        except Exception as e:
            logger.error(f"Error enviando la foto de bienvenida: {e}")
            await update.message.reply_text(mensaje_bienvenida, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado)
    else:
        await update.message.reply_text(mensaje_bienvenida, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado)
    return ESPERANDO_UBICACION

async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['lat'], context.user_data['lon'] = update.message.location.latitude, update.message.location.longitude
    user_reg = obtener_usuario_db(update.effective_user.id)
    teclado = TECLADO_COMBUSTIBLE_VOLVER if user_reg else TECLADO_COMBUSTIBLE
    await update.message.reply_text("✅ Ubicación recibida.\n\n⛽ ¿Qué combustible usas?", reply_markup=teclado)
    return PREGUNTAR_COMBUSTIBLE

async def cambiar_ubicacion_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = ReplyKeyboardMarkup([[KeyboardButton("📍 Enviar Ubicación", request_location=True)], [BTN["volver"]]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("📍 Envía tu nueva ubicación:", reply_markup=teclado)
    return ESPERANDO_UBICACION

async def recibir_combustible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comb = update.message.text
    if comb in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    context.user_data['combustible'] = comb
    user_id = update.effective_user.id
    await update.message.reply_text("🔎 Buscando los mejores precios...", reply_markup=ReplyKeyboardRemove())
    user_reg = obtener_usuario_db(user_id)
    txt = await generar_mensaje_precios(context.user_data['lat'], context.user_data['lon'], comb, user_reg[3] if user_reg and user_reg[3] else 15, user_reg[4] if user_reg and user_reg[4] else 5)
    if not txt:
        await update.message.reply_text("📍 No hay gasolineras en tu radio actual. Escribe uno mayor:")
        return ESPERANDO_RADIO
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
    if user_reg:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('UPDATE usuarios SET combustible=?, lat=?, lon=?, nombre=?, username=? WHERE id=?', 
                     (comb, encrypt_data(context.user_data.get('lat')), encrypt_data(context.user_data.get('lon')), encrypt_data(update.effective_user.first_name), encrypt_data(update.effective_user.username), user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Datos actualizados de forma segura.", reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    else:
        await update.message.reply_text("¿Quieres recibir este TOP automáticamente cada día?", reply_markup=TECLADO_CONFIRMACION)
        return PREGUNTAR_FAVORITA

async def decidir_favorita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    if BTN["guardar"] in update.message.text:
        await update.message.reply_text("🕒 ¿A qué hora te envío el aviso?", reply_markup=TECLADO_HORA_CANCELAR)
        return ESPERANDO_HORA
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''INSERT OR REPLACE INTO usuarios (id, lat, lon, combustible, radio, limite, nombre, username) VALUES (?, ?, ?, ?, COALESCE((SELECT radio FROM usuarios WHERE id = ?), 15), COALESCE((SELECT limite FROM usuarios WHERE id = ?), 5), ?, ?)''', 
                 (user_id, encrypt_data(context.user_data['lat']), encrypt_data(context.user_data['lon']), context.user_data['combustible'], user_id, user_id, encrypt_data(update.effective_user.first_name), encrypt_data(update.effective_user.username)))
    conn.commit()
    conn.close()
    await update.message.reply_text("Entendido. Tus datos han sido guardados.", reply_markup=MENU_PRINCIPAL)
    return ConversationHandler.END

async def guardar_todo_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    match = re.search(r'(\d{1,2}):(\d{2})', update.message.text)
    if match:
        h, m = map(int, match.groups())
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''INSERT OR REPLACE INTO usuarios (id, lat, lon, hora, minutos, combustible, radio, limite, nombre, username) VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT radio FROM usuarios WHERE id = ?), 15), COALESCE((SELECT limite FROM usuarios WHERE id = ?), 5), ?, ?)''', 
                     (user_id, encrypt_data(context.user_data['lat']), encrypt_data(context.user_data['lon']), h, m, context.user_data['combustible'], user_id, user_id, encrypt_data(update.effective_user.first_name), encrypt_data(update.effective_user.username)))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Guardado. Te avisaré a las {h:02d}:{m:02d}.", reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    return ESPERANDO_HORA

async def boton_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = obtener_usuario_db(update.effective_user.id)
    if user:
        await update.message.reply_text(f"🔎 Buscando TOP {user[4] if user[4] else 5} en {user[3] if user[3] else 15}km...", reply_markup=ReplyKeyboardRemove())
        txt = await generar_mensaje_precios(user[0], user[1], user[2], user[3] if user[3] else 15, user[4] if user[4] else 5)
        if txt:
            await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_PRINCIPAL)
            return ConversationHandler.END
        else:
            await update.message.reply_text(f"📍 No hay gasolineras cerca. Escribe un radio mayor:")
            return ESPERANDO_RADIO
    else: return await inicio(update, context)

async def cambiar_combustible_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = obtener_usuario_db(update.effective_user.id)
    if not user: return await inicio(update, context)
    context.user_data['lat'], context.user_data['lon'] = user[0], user[1]
    await update.message.reply_text("⛽ Elige combustible:", reply_markup=TECLADO_COMBUSTIBLE_VOLVER)
    return PREGUNTAR_COMBUSTIBLE

async def cambiar_hora_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = obtener_usuario_db(update.effective_user.id)
    if not user: return await inicio(update, context)
    context.user_data['lat'], context.user_data['lon'], context.user_data['combustible'] = user[0], user[1], user[2]
    await update.message.reply_text("🕒 Nueva hora:", reply_markup=TECLADO_HORA_VOLVER)
    return ESPERANDO_HORA

async def preguntar_radio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📏 Escribe el nuevo radio en km (ejemplo: 20):", reply_markup=TECLADO_VOLVER)
    return ESPERANDO_RADIO

async def guardar_radio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    try:
        nuevo_radio = int(update.message.text.strip())
        conn = sqlite3.connect(DB_PATH)
        conn.execute('UPDATE usuarios SET radio = ? WHERE id = ?', (nuevo_radio, update.effective_user.id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Radio actualizado a {nuevo_radio} km.", reply_markup=MENU_CONFIGURACION)
        return ConversationHandler.END
    except:
        await update.message.reply_text("⚠️ Escribe solo un número.", reply_markup=TECLADO_VOLVER)
        return ESPERANDO_RADIO

async def preguntar_limite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔢 ¿Cuántas gasolineras quieres ver? (ej: 5):", reply_markup=TECLADO_VOLVER)
    return ESPERANDO_LIMITE

async def guardar_limite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in [BTN["cancelar"], BTN["volver"]]: return await comando_cancelar(update, context)
    try:
        nuevo_limite = int(update.message.text.strip())
        conn = sqlite3.connect(DB_PATH)
        conn.execute('UPDATE usuarios SET limite = ? WHERE id = ?', (nuevo_limite, update.effective_user.id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Verás {nuevo_limite} resultados.", reply_markup=MENU_CONFIGURACION)
        return ConversationHandler.END
    except:
        await update.message.reply_text("⚠️ Escribe solo un número.", reply_markup=TECLADO_VOLVER)
        return ESPERANDO_LIMITE

async def mostrar_configuracion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    user = conn.execute('SELECT lat, lon, hora, minutos, combustible, radio, nombre, username, limite FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if not user: return await inicio(update, context)
    texto = f"⚙️ **TU CONFIGURACIÓN**\n🆔 `{user_id}`\n⛽ **Combustible:** {user[4]}\n📏 **Radio:** {user[5] if user[5] else 15} km\n🔢 **Resultados:** {user[8] if user[8] else 5}\n"
    texto += f"⏰ **Aviso:** {user[2]:02d}:{user[3]:02d}\n" if user[2] is not None else "⏰ **Aviso:** Desactivado\n"
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_CONFIGURACION)
    return ConversationHandler.END

async def mostrar_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    consumos_all = conn.execute('SELECT litros, precio_litro, total, fecha, combustible, km, l_100km, vehiculo FROM consumos WHERE user_id = ? ORDER BY fecha DESC', (user_id,)).fetchall()
    vehiculos_db = conn.execute('SELECT tipo, nombre FROM vehiculos WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    if not consumos_all:
        await update.message.reply_text("📉 Aún no tienes repostajes anotados.", reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    emoji_dict = {v[1]: TIPOS_VEHICULOS.get(v[0], '🚗') for v in vehiculos_db}
    consumos_por_vehiculo = defaultdict(list)
    for c in consumos_all:
        vehiculo_nombre = c[7]
        consumos_por_vehiculo[vehiculo_nombre].append(c)
    for vehiculo_nombre, consumos in consumos_por_vehiculo.items():
        total_gastado = sum(c[2] for c in consumos)
        total_litros = sum(c[0] for c in consumos)
        total_km = sum(c[5] if c[5] else 0 for c in consumos)
        emoji_v = emoji_dict.get(vehiculo_nombre, '🚗')
        texto = f"📈 **ESTADÍSTICAS: {emoji_v} {vehiculo_nombre}**\n\n🗓️ **Total repostajes:** {len(consumos)}\n🛣️ **Kilómetros:** {round(total_km, 1)} km\n💧 **Litros:** {round(total_litros, 2)} L\n💸 **Gasto:** {round(total_gastado, 2)} €\n"
        if total_km > 0: 
            texto += f"📉 **Consumo medio:** {round((total_litros/total_km)*100, 2)} L/100km\n"
        ultimo = consumos[0]
        texto += f"\n⏱️ **Último repostaje ({ultimo[3][:10]}):**\n└ {ultimo[0]}L a {ultimo[1]}€/L -> {ultimo[2]}€"
        if len(consumos) >= 2:
            try:
                fechas = [c[3][:10] for c in consumos][::-1] 
                gastos = [c[2] for c in consumos][::-1]
                plt.figure(figsize=(9, 5))
                plt.plot(fechas, gastos, marker='o', color='#007BFF', linewidth=2.5, markersize=8, markerfacecolor='white', markeredgewidth=2)
                plt.fill_between(fechas, gastos, color='#007BFF', alpha=0.15) 
                plt.title(f'Evolución del Gasto - {vehiculo_nombre}', fontsize=16, pad=20, fontweight='bold', color='#333333')
                plt.ylabel('Euros (€)', fontsize=12, fontweight='bold', color='#555555')
                plt.grid(True, linestyle='--', alpha=0.6, color='#CCCCCC')
                plt.xticks(rotation=45, ha='right', color='#555555')
                plt.yticks(color='#555555')
                for i, txt in enumerate(gastos):
                    plt.annotate(f"{txt}€", (fechas[i], gastos[i]), textcoords="offset points", xytext=(0,10), ha='center', fontsize=9, fontweight='bold', color='#333333')
                ax = plt.gca()
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('#DDDDDD')
                ax.spines['bottom'].set_color('#DDDDDD')
                plt.tight_layout()
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
                buf.seek(0)
                plt.close()
                await context.bot.send_photo(chat_id=user_id, photo=buf, caption=texto, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Error generando la gráfica HD: {e}")
                await context.bot.send_message(chat_id=user_id, text=texto, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id=user_id, text=texto, parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("📥 Si lo deseas, puedes descargar tu histórico completo en Excel:", reply_markup=MENU_ESTADISTICAS)
    return ConversationHandler.END

async def pedir_confirmacion_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_alerta = (
        "🚨 *¡ATENCIÓN: BORRADO DE DATOS!* 🚨\n\n"
        "Estás a punto de borrar **TODOS** tus datos para siempre. Esto incluye:\n"
        "• Tu ubicación y alarmas programadas.\n"
        "• Tu garaje de vehículos.\n"
        "• Todo tu historial de repostajes y estadísticas.\n\n"
        "⚠️ _Esta acción es irreversible y no se puede deshacer._\n\n"
        "¿Estás completamente seguro de que quieres borrar tu cuenta?"
    )
    await update.message.reply_text(texto_alerta, parse_mode=ParseMode.MARKDOWN, reply_markup=TECLADO_CONFIRMAR_BORRADO)
    return CONFIRMAR_BORRADO

async def ejecutar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto in [BTN["cancelar"], BTN["volver"]]:
        await update.message.reply_text("🛑 Borrado cancelado. Tus datos están a salvo.", reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    if texto == "⚠️ SÍ, BORRAR MIS DATOS":
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
        conn.execute('DELETE FROM consumos WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM vehiculos WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("🗑️ Se han eliminado todos tus datos permanentemente.", reply_markup=ReplyKeyboardRemove())
        return await inicio(update, context)
    await update.message.reply_text("Usa los botones de abajo para confirmar o cancelar el borrado:", reply_markup=TECLADO_CONFIRMAR_BORRADO)
    return CONFIRMAR_BORRADO

async def mensaje_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if obtener_usuario_db(update.effective_user.id):
        await update.message.reply_text("No he entendido eso 😅. Usa el menú de abajo o escribe /menu:", reply_markup=MENU_PRINCIPAL)
        return ConversationHandler.END
    return await inicio(update, context)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.job_queue.run_repeating(revisar_alarmas, interval=60)
    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', inicio),
            CommandHandler('menu', comando_menu),      
            CommandHandler('cancel', comando_cancelar), 
            CommandHandler('help', mostrar_ayuda),
            MessageHandler(filters.Regex(f'^{BTN["precios"]}$'), boton_precios),
            MessageHandler(filters.Regex(f'^{BTN["ubicacion"]}$'), cambiar_ubicacion_directo),
            MessageHandler(filters.Regex(f'^{BTN["combustible"]}$'), cambiar_combustible_directo),
            MessageHandler(filters.Regex(f'^{BTN["hora"]}$'), cambiar_hora_directo),
            MessageHandler(filters.Regex(f'^{BTN["radio"]}$'), preguntar_radio),
            MessageHandler(filters.Regex(f'^{BTN["cantidad"]}$'), preguntar_limite),
            MessageHandler(filters.Regex(f'^{BTN["config"]}$'), mostrar_configuracion),
            MessageHandler(filters.Regex(f'^{BTN["repostaje"]}$'), iniciar_repostaje),
            MessageHandler(filters.Regex(f'^{BTN["garaje"]}$'), ver_garaje), 
            MessageHandler(filters.Regex(f'^{BTN["estadisticas"]}$'), mostrar_estadisticas),
            MessageHandler(filters.Regex(f'^{BTN["excel"]}$'), descargar_excel),
            MessageHandler(filters.Regex(f'^{BTN["ayuda"]}$'), mostrar_ayuda),  
            MessageHandler(filters.Regex(f'^{BTN["volver"]}$'), comando_cancelar),    
            MessageHandler(filters.Regex(f'^{BTN["borrar"]}$'), pedir_confirmacion_borrado),
            MessageHandler(filters.LOCATION, recibir_ubicacion),
            MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_desconocido)
        ],
        states={
            ESPERANDO_UBICACION: [MessageHandler(filters.LOCATION, recibir_ubicacion)],
            PREGUNTAR_COMBUSTIBLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_combustible)],
            PREGUNTAR_FAVORITA: [MessageHandler(filters.TEXT & ~filters.COMMAND, decidir_favorita)],
            ESPERANDO_HORA: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_todo_final)],
            ESPERANDO_RADIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_radio)],
            ESPERANDO_LIMITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_limite)],
            ESPERANDO_VEHICULO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_vehiculo)],
            ESPERANDO_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_emoji)],
            ESPERANDO_NOMBRE_VEHICULO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_vehiculo)],
            ESPERANDO_COMBUSTIBLE_REPOSTAJE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_combustible_repostaje)],
            ESPERANDO_LITROS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_litros)],
            ESPERANDO_PRECIO_LITRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio_litro)],
            ESPERANDO_KM: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_repostaje)],
            CONFIRMAR_BORRADO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ejecutar_borrado)]
        },
        fallbacks=[
            CommandHandler('start', inicio),
            CommandHandler('cancel', comando_cancelar), 
            CommandHandler('menu', comando_menu),
            MessageHandler(filters.Regex(f'^({BTN["volver"]}|{BTN["cancelar"]})$'), comando_cancelar)        
        ]
    )
    app.add_handler(conv)
    app.run_webhook(
        listen="127.0.0.1", 
        port=8000, 
        url_path="webhook", 
        webhook_url=f"{DOMAIN}/webhook",
        secret_token=SECRET
    )

if __name__ == '__main__':
    main()
