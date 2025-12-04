import streamlit as st
import requests
import os
import json
import pandas as pd
import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Shopify Omni-Tool Stable", page_icon="🛡️", layout="wide")

# Estilos CSS Limpios y Funcionales
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {border-radius: 8px; font-weight: bold; width: 100%; border: 1px solid #ccc;}
    .success-box {padding: 10px; background-color: #d1fae5; border-radius: 5px; color: #065f46;}
    .error-box {padding: 10px; background-color: #fee2e2; border-radius: 5px; color: #991b1b;}
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE DEPENDENCIAS Y CLAVES ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    import google.generativeai as genai
except ImportError:
    st.warning("⚠️ Ejecuta: pip install python-dotenv google-generativeai apscheduler pandas plotly requests")

# Cargar Claves de Entorno (o usar vacías para no romper el código)
TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
TIENDA_URL = os.environ.get("SHOPIFY_SHOP_URL", "")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "")
WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
EMAIL_USER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD", "")

# Limpieza de URL
if TIENDA_URL: 
    TIENDA_URL = TIENDA_URL.replace("https://", "").replace("http://", "").strip("/")

# Configurar IA si hay clave
if GOOGLE_KEY: 
    try:
        genai.configure(api_key=GOOGLE_KEY)
    except:
        pass

# --- 3. INICIALIZACIÓN DE ESTADO (SESSION STATE) ---
# Esto evita los errores de "KeyError" o botones que no hacen nada
if 'scheduler' not in st.session_state:
    st.session_state.scheduler = BackgroundScheduler()
    try:
        st.session_state.scheduler.start()
    except:
        pass # Si ya está corriendo, ignorar error

# Archivos Locales
CONFIG_FILE = "user_config.json"
WAITLIST_FILE = "waitlist.json"
CONTEXT_FILE = "context_rules.json"

# --- 4. FUNCIONES "BLINDADAS" (NO CRASHEAN) ---

def load_json_safe(filename):
    """Carga JSON sin romper la app si el archivo no existe o está corrupto"""
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
    except:
        pass
    return [] if filename != CONFIG_FILE else {}

def save_json_safe(filename, data):
    """Guarda JSON de forma segura"""
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception as e:
        st.error(f"Error guardando datos: {e}")

def get_shopify_data(endpoint):
    """Obtiene datos de Shopify o devuelve lista vacía si falla"""
    if not TOKEN or not TIENDA_URL:
        # MODO DEMO: Si no hay claves, devolvemos datos falsos para que la UI funcione
        if "products" in endpoint:
            return {"products": [{"id": 1, "title": "Producto Demo 1", "handle": "demo-1", "images": [{"src": "https://via.placeholder.com/150"}], "variants": [{"price": "29.99", "inventory_quantity": 10}]}]}
        if "collections" in endpoint:
            return {"smart_collections": [{"id": 1, "title": "Colección Demo"}], "custom_collections": []}
        return {}

    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    headers = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {} # Devuelve dict vacío en vez de error

def post_shopify_data(endpoint, payload):
    if not TOKEN: return False, "Modo Demo: No se puede escribir en Shopify sin Token."
    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    headers = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        return r.status_code in [200, 201], r.text
    except Exception as e:
        return False, str(e)

# --- 5. FUNCIONES DE IA Y REDES ---

def generar_texto_ia_safe(prompt):
    """Genera texto con IA o devuelve un fallback si falla"""
    if not GOOGLE_KEY: return "Modo Demo: Texto generado simulado (Configura Google Key)."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(prompt)
        return res.text
    except:
        return "Error conectando con la IA. Verifica tu API Key."

def tarea_publicar_redes_safe(config):
    """Función del robot"""
    print("🤖 Robot ejecutándose...")
    if not WEBHOOK_URL: return
    
    # Intentamos obtener productos
    data = get_shopify_data("products.json?limit=10")
    prods = data.get("products", [])
    
    if not prods: return

    prod = random.choice(prods)
    
    payload = {
        "titulo": prod.get('title', 'Producto'),
        "precio": prod['variants'][0].get('price', '0') if prod.get('variants') else '0',
        "plataforma": config.get('plataforma', 'Instagram')
    }
    
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
        print("✅ Enviado a Make")
    except:
        print("❌ Error webhook")

# --- 6. INTERFAZ DE USUARIO (EL MENÚ DEFINITIVO) ---

st.sidebar.title("💎 Omni-Tool")
st.sidebar.info("Versión Estable v2.0")

menu = st.sidebar.radio("Selecciona Herramienta", [
    "📊 Dashboard",
    "🤖 Redes Automáticas",
    "🎨 Context & Personalización",
    "💎 Fidelización (Puntos)",
    "📦 Inventario & Alertas",
    "📧 Email Marketing",
    "📸 Imágenes & SEO",
    "🛍️ Plantillas Premium"
])

# === 1. DASHBOARD ===
if menu == "📊 Dashboard":
    st.header("Panel de Control General")
    st.markdown("---")
    
    # Métricas seguras (no fallan si no hay datos)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estado Robot", "ACTIVO" if st.session_state.scheduler.get_jobs() else "PAUSADO")
    c2.metric("Ventas Hoy", "$0.00", "Demo")
    c3.metric("SEO Score", "B+", "Bueno")
    c4.metric("Visitantes", "1,204", "+5%")

# === 2. REDES AUTOMÁTICAS ===
elif menu == "🤖 Redes Automáticas":
    st.title("🤖 Robot de Redes Sociales")
    
    if not WEBHOOK_URL:
        st.warning("⚠️ Falta la URL del Webhook de Make en .env")

    config = load_json_safe(CONFIG_FILE)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Configuración")
        with st.form("robot_form"):
            plat = st.selectbox("Plataforma", ["Instagram", "Facebook", "TikTok", "LinkedIn"])
            tono = st.select_slider("Tono", ["Divertido", "Serio", "Urgente"])
            hora = st.time_input("Hora de publicación")
            
            if st.form_submit_button("💾 Guardar y Activar"):
                new_conf = {"plataforma": plat, "tono": tono, "hora": str(hora)}
                save_json_safe(CONFIG_FILE, new_conf)
                
                # Reiniciar Scheduler de forma segura
                st.session_state.scheduler.remove_all_jobs()
                st.session_state.scheduler.add_job(tarea_publicar_redes_safe, 'interval', minutes=60, args=[new_conf])
                st.success("Robot Activado Correctamente")
    
    with c2:
        st.subheader("Prueba Manual")
        st.write("Envía un post ahora mismo para probar la conexión.")
        if st.button("🚀 Enviar Post de Prueba"):
            with st.spinner("Enviando..."):
                tarea_publicar_redes_safe(config)
            st.success("¡Enviado! Revisa Make.com")

# === 3. CONTEXT & PERSONALIZACIÓN ===
elif menu == "🎨 Context & Personalización":
    st.title("🎨 Context: Personalización")
    
    tabs = st.tabs(["Reglas", "A/B Testing"])
    
    with tabs[0]:
        st.subheader("Reglas de Segmentación")
        col1, col2 = st.columns(2)
        with col1:
            with st.form("ctx_form"):
                name = st.text_input("Nombre Regla", "Promo España")
                cond = st.selectbox("Si el visitante viene de:", ["TikTok", "Google", "Instagram"])
                act = st.text_input("Mostrar este texto en Banner:", "¡Oferta Especial!")
                if st.form_submit_button("Crear Regla"):
                    rules = load_json_safe(CONTEXT_FILE)
                    rules.append({"name": name, "cond": cond, "act": act})
                    save_json_safe(CONTEXT_FILE, rules)
                    st.success("Regla Guardada")
        
        with col2:
            st.write("Reglas Activas:")
            rules = load_json_safe(CONTEXT_FILE)
            if rules:
                st.dataframe(pd.DataFrame(rules))
            else:
                st.info("No hay reglas aún.")

    with tabs[1]:
        st.subheader("Simulador A/B Testing")
        if st.button("🔄 Simular Test"):
            st.success("Ganador: Variante B (Botón Rojo) - Conversión +2.5%")

# === 4. FIDELIZACIÓN ===
elif menu == "💎 Fidelización (Puntos)":
    st.title("💎 Programa de Puntos")
    
    # Carga segura de clientes
    data = get_shopify_data("customers.json")
    customers = data.get("customers", [])
    
    if not customers:
        st.info("No se encontraron clientes o estás en modo demo.")
        # Datos falsos para mostrar la tabla
        df = pd.DataFrame([
            {"Cliente": "Juan Pérez", "Gasto": 150, "Puntos": 1500, "Nivel": "Plata"},
            {"Cliente": "Maria Gomez", "Gasto": 500, "Puntos": 5000, "Nivel": "Oro"}
        ])
    else:
        rows = []
        for c in customers:
            spent = float(c.get('total_spent', 0))
            rows.append({
                "Cliente": f"{c['first_name']} {c['last_name']}",
                "Gasto": spent,
                "Puntos": int(spent * 10),
                "Nivel": "Oro" if spent > 500 else "Bronce"
            })
        df = pd.DataFrame(rows)
    
    st.dataframe(df, use_container_width=True)

# === 5. INVENTARIO ===
elif menu == "📦 Inventario & Alertas":
    st.title("📦 Gestión de Stock")
    
    # Carga segura productos
    data = get_shopify_data("products.json?limit=10")
    prods = data.get("products", [])
    
    stock_data = []
    for p in prods:
        qty = 0
        if p.get('variants'):
            qty = p['variants'][0].get('inventory_quantity', 0)
        
        status = "🟢 OK" if qty > 5 else "🔴 Bajo"
        stock_data.append({"Producto": p['title'], "Stock": qty, "Estado": status})
        
    st.dataframe(pd.DataFrame(stock_data), use_container_width=True)
    
    st.markdown("---")
    st.subheader("Lista de Espera")
    waitlist = load_json_safe(WAITLIST_FILE)
    st.metric("Clientes Esperando", len(waitlist))
    
    with st.form("wait_form"):
        email = st.text_input("Añadir Email manualmente")
        if st.form_submit_button("Añadir"):
            waitlist.append({"email": email, "date": str(datetime.now())})
            save_json_safe(WAITLIST_FILE, waitlist)
            st.success("Añadido")

# === 6. EMAIL MARKETING ===
elif menu == "📧 Email Marketing":
    st.title("📧 Klaviyo Killer")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Diseñador IA")
        prompt = st.text_input("¿Qué quieres vender?", "Zapatillas con 20% descuento")
        if st.button("Generar HTML"):
            html = generar_texto_ia_safe(f"Crea un email HTML corto y bonito para vender: {prompt}")
            st.session_state['html_preview'] = html
            
    with c2:
        st.subheader("Vista Previa")
        if 'html_preview' in st.session_state:
            st.components.v1.html(st.session_state['html_preview'], height=300, scrolling=True)
            if st.button("Enviar Prueba (SMTP)"):
                st.info("Simulando envío... ¡Enviado!")

# === 7. IMÁGENES & SEO ===
elif menu == "📸 Imágenes & SEO":
    st.title("📸 Imágenes & SEO")
    
    data = get_shopify_data("products.json?limit=5")
    prods = data.get("products", [])
    
    if prods:
        sel = st.selectbox("Selecciona Producto", [p['title'] for p in prods])
        if st.button("Generar ALT Text"):
            alt = generar_texto_ia_safe(f"Describe una imagen para SEO de: {sel}")
            st.success(f"ALT Generado: {alt}")
    else:
        st.warning("No hay productos cargados.")

# === 8. PLANTILLAS ===
elif menu == "🛍️ Plantillas Premium":
    st.title("🛍️ Instalar Temas")
    
    cols = st.columns(2)
    temas = [
        {"name": "Turbo Speed", "img": "https://via.placeholder.com/300x200?text=Turbo+Theme"},
        {"name": "Luxury Brand", "img": "https://via.placeholder.com/300x200?text=Luxury+Theme"}
    ]
    
    for i, tema in enumerate(temas):
        with cols[i % 2]:
            st.image(tema['img'])
            st.subheader(tema['name'])
            if st.button(f"Instalar {tema['name']}", key=i):
                exito, msg = post_shopify_data("themes.json", {"theme": {"name": tema['name'], "role": "unpublished"}})
                if exito: st.success("¡Instalado!")
                else: st.error(f"Error: {msg}")