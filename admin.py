import sqlite3
import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# --- CONFIGURACIÓN DE RUTAS DINÁMICAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "basededatos.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
load_dotenv(os.path.join(BASE_DIR, ".env"))
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

if ENCRYPTION_KEY:
    cipher_suite = Fernet(ENCRYPTION_KEY.encode())
else:
    cipher_suite = None

def decrypt_data(data, tipo=str):
    if data is None or not cipher_suite: return None
    try:
        descifrado = cipher_suite.decrypt(str(data).encode('utf-8')).decode('utf-8')
        if descifrado == "None": return None
        return tipo(descifrado)
    except:
        try: return tipo(data)
        except: return None

def encrypt_data(data):
    if data is None or not cipher_suite: return None
    return cipher_suite.encrypt(str(data).encode('utf-8')).decode('utf-8')

# --- FUNCIONES DE ADMINISTRACIÓN ---

def ver_usuario(uid):
    conn = sqlite3.connect(DB_PATH)
    user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (uid,)).fetchone()
    conn.close()
    if user:
        print(f"\n--- DATOS DEL USUARIO {uid} ---")
        print(f"Latitud: {decrypt_data(user[1], float)}")
        print(f"Longitud: {decrypt_data(user[2], float)}")
        print(f"Hora de aviso: {user[3]}:{user[4] if user[4] is not None else '00'}")
        print(f"Combustible: {user[5]}")
        print(f"Radio: {user[6]} km")
        print(f"Límite: {user[7]}")
        print(f"Nombre: {decrypt_data(user[8], str)}")
        print(f"Username: {decrypt_data(user[9], str)}")
    else:
        print("❌ Usuario no encontrado en la base de datos.")

def cambiar_ubicacion(uid, lat, lon):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE usuarios SET lat = ?, lon = ? WHERE id = ?', (encrypt_data(lat), encrypt_data(lon), uid))
    conn.commit()
    conn.close()
    print(f"✅ Ubicación actualizada con éxito para el usuario {uid}.")

def ver_repostajes(uid):
    conn = sqlite3.connect(DB_PATH)
    repostajes = conn.execute('SELECT id, vehiculo, litros, precio_litro, total, fecha FROM consumos WHERE user_id = ? ORDER BY fecha DESC', (uid,)).fetchall()
    conn.close()
    if repostajes:
        print(f"\n--- REPOSTAJES DEL USUARIO {uid} ---")
        for r in repostajes:
            print(f"ID: {r[0]} | Fecha: {r[5]} | Vehículo: {r[1]} | Litros: {r[2]} | Precio: {r[3]}€ | Total: {r[4]}€")
    else:
        print("❌ No hay repostajes registrados para este usuario.")

def borrar_repostaje(rid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM consumos WHERE id = ?', (rid,))
    conn.commit()
    conn.close()
    print(f"✅ Repostaje {rid} borrado correctamente.")

def ver_estado_cache():
    print("\n" + "="*50)
    print("🧠 HISTORIAL DE LA CACHÉ DEL MINISTERIO (Últimas 5)")
    print("="*50)
    try:
        comando_linux = 'cat ~/.pm2/logs/gasolibot-out.log ~/.pm2/logs/gasolibot-error.log 2>/dev/null | grep "Caché actualizada" | tail -n 5'
        resultado = os.popen(comando_linux).read().strip()
        
        if resultado:
            lineas = resultado.split('\n')
            ultima_fecha_str = None
            caducidad_mins = 0
            
            for linea in lineas:
                if " - INFO - " in linea:
                    partes = linea.split(' - INFO - ')
                    fecha_hora = partes[0].split(',')[0]
                    mensaje = partes[1]
                    print(f"🕒 {fecha_hora} -> {mensaje}")
                    
                    ultima_fecha_str = fecha_hora
                    match = re.search(r'(?:Caduca|caducidad) en (\d+) mins', mensaje)
                    if match:
                        caducidad_mins = int(match.group(1))
                else:
                    print(f"👉 {linea}")
            
            # --- ANÁLISIS DEL ESTADO ACTUAL ---
            if ultima_fecha_str and caducidad_mins > 0:
                print("-" * 50)
                try:
                    ultima_fecha = datetime.strptime(ultima_fecha_str, '%Y-%m-%d %H:%M:%S')
                    ahora = datetime.now()
                    
                    minutos_pasados = (ahora - ultima_fecha).total_seconds() / 60.0
                    
                    if minutos_pasados < caducidad_mins:
                        minutos_restantes = int(caducidad_mins - minutos_pasados)
                        print(f"✅ ESTADO ACTUAL: ACTIVA")
                        print(f"⏳ Tiempo restante: Quedan {minutos_restantes} minutos para que caduque.")
                    else:
                        print(f"❌ ESTADO ACTUAL: CADUCADA")
                        print("🔄 El bot descargará precios nuevos la próxima vez que un usuario los pida.")
                except Exception as e:
                    print(f"⚠️ No se pudo calcular el tiempo exacto: {e}")
        else:
            print("⚠️ La caché está vacía o los logs se acaban de limpiar. Se llenará cuando alguien pida precios.")
    except Exception as e:
        print(f"❌ Error leyendo los logs: {e}")
    print("="*50 + "\n")

def alternar_debug():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        estado_actual = config.get("debug", False)
        nuevo_estado = not estado_actual
        config["debug"] = nuevo_estado
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        if nuevo_estado:
            print("\n🟢 MODO DEBUG: ACTIVADO (Verás todo el tráfico en PM2)")
        else:
            print("\n🔴 MODO DEBUG: DESACTIVADO (Logs limpios y silenciosos)")
            
        print("🔄 Reiniciando GasoliBot para aplicar los cambios...")
        os.system("pm2 restart gasolibot > /dev/null")
        print("✅ ¡Bot reiniciado con éxito!")
    except Exception as e:
        print(f"❌ Error al cambiar el modo debug: {e}")

# --- MENÚ PRINCIPAL ---

def menu():
    while True:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                debug_on = json.load(f).get("debug", False)
            debug_status = "🟢 ON" if debug_on else "🔴 OFF"
        except:
            debug_status = "❓"

        print(f"\n🔧 --- PANEL DE ADMINISTRACIÓN GASOLIBOT --- 🔧")
        print("1. Ver datos de un usuario (Descifrados)")
        print("2. Cambiar ubicación manual de un usuario")
        print("3. Ver repostajes de un usuario")
        print("4. Borrar un repostaje específico")
        print("5. Ver estado de la Caché RAM")
        print(f"6. Alternar MODO DEBUG (Actual: {debug_status})")
        print("7. Salir")
        
        opcion = input("\nElige una opción (1-7): ")
        
        if opcion == '1':
            uid = input("Introduce el ID de Telegram del usuario: ")
            ver_usuario(uid)
        elif opcion == '2':
            uid = input("Introduce el ID del usuario: ")
            lat = input("Nueva Latitud (ej: 42.4666): ")
            lon = input("Nueva Longitud (ej: -2.4499): ")
            try:
                cambiar_ubicacion(uid, float(lat), float(lon))
            except ValueError:
                print("❌ Error: Las coordenadas deben ser números.")
        elif opcion == '3':
            uid = input("Introduce el ID de Telegram del usuario: ")
            ver_repostajes(uid)
        elif opcion == '4':
            rid = input("Introduce el ID del REPOSTAJE que quieres borrar: ")
            borrar_repostaje(rid)
        elif opcion == '5':
            ver_estado_cache()
        elif opcion == '6':
            alternar_debug()
        elif opcion == '7':
            print("👋 Saliendo del panel de administración...")
            break
        else:
            print("❌ Opción no válida.")

if __name__ == '__main__':
    menu()
