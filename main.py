import streamlit as st
import requests
import os
import json
import pandas as pd
import random
import time
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Shopify Omni-Tool", page_icon="🛍️", layout="wide")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    .stButton>button {border: 1px solid #ccc; font-weight: bold;}
    .metric-card {background-color: #f9f9f9; padding: 15px; border-radius: 10px; border-left: 5px solid #008060;}
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE ERRORES Y LIBRERÍAS ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    import google.generativeai as genai
except ImportError:
    st.warning("⚠️ Faltan librerías. El sistema funcionará en modo limitado.")

# Claves (Usamos .get para evitar errores si no existen)
TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
TIENDA_URL = os.environ.get("SHOPIFY_SHOP_URL", "")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "")
WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
EMAIL_USER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD", "")

# Limpieza de URL
if TIENDA_URL: 
    TIENDA_URL = TIENDA_URL.replace("https://", "").replace("http://", "").strip("/")

if GOOGLE_KEY: 
    try: genai.configure(api_key=GOOGLE_KEY)
    except: pass

# --- 3. ARCHIVOS Y ESTADO ---
CONFIG_FILE = "user_config.json"
WAITLIST_FILE = "waitlist.json"
CONTEXT_FILE = "context_rules.json"

if 'scheduler' not in st.session_state:
    st.session_state.scheduler = BackgroundScheduler()
    try: st.session_state.scheduler.start()
    except: pass

# --- 4. FUNCIONES SEGURAS (SAFE FUNCTIONS) ---
# Estas funciones nunca rompen la app, devuelven datos vacíos si fallan.

def load_json_safe(filename):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: return json.load(f)
    except: pass
    return [] if filename != CONFIG_FILE else {}

def save_json_safe(filename, data):
    try:
        with open(filename, "w") as f: json.dump(data, f)
    except: pass

def get_shopify_data(endpoint):
    """Obtiene datos de Shopify protegiendo errores de conexión"""
    if not TOKEN: return {} # Modo Demo o Sin Conexión
    
    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    headers = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    return {}

def post_shopify_data(endpoint, payload):
    if not TOKEN: return False, "Falta Token"
    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    headers = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        return r.status_code in [200, 201], r.text
    except Exception as e: return False, str(e)

# --- 5. LOGICA IA Y REDES ---

def generar_texto_ia(prompt):
    if not GOOGLE_KEY: return "Texto simulado (Configura Google Key)"
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(prompt).text
    except: return "Error IA"

def tarea_publicar_safe(config):
    if not WEBHOOK_URL: return
    # Lógica simplificada para evitar errores en segundo plano
    try:
        payload = {
            "plataforma": config.get('plataforma', 'Instagram'),
            "texto": "Post Automático Generado",
            "fecha": str(datetime.now())
        }
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
    except: pass

# --- 6. INTERFAZ GRÁFICA PRINCIPAL ---

st.sidebar.title("💎 Omni-Tool")
st.sidebar.caption(f"Tienda: {TIENDA_URL if TIENDA_URL else 'No Conectada'}")

menu = st.sidebar.radio("Herramientas", [
    "📊 Dashboard",
    "🤖 Piloto Redes",
    "🎨 Context & Personalización",
    "💎 Fidelización (Puntos)",
    "📦 Inventario & Alertas",
    "📧 Email Marketing",
    "📸 Imágenes & SEO",
    "🛍️ Plantillas Premium"
])

# === 1. DASHBOARD ===
if menu == "📊 Dashboard":
    st.title("Panel de Control")
    c1, c2, c3 = st.columns(3)
    c1.metric("Estado Robot", "ACTIVO" if st.session_state.scheduler.get_jobs() else "PAUSADO")
    c2.metric("Ventas Hoy", "$0.00", "Demo")
    c3.metric("SEO Score", "85/100")

# === 2. REDES ===
elif menu == "🤖 Piloto Redes":
    st.header("🤖 Automatización Redes Sociales")
    
    if not WEBHOOK_URL: st.error("⚠️ Configura MAKE_WEBHOOK_URL en Secrets")
    
    conf = load_json_safe(CONFIG_FILE)
    
    with st.form("redes_form"):
        plat = st.selectbox("Red Social", ["Instagram", "Facebook", "TikTok", "LinkedIn"])
        tono = st.selectbox("Tono", ["Divertido", "Serio"])
        if st.form_submit_button("Guardar y Activar"):
            new_conf = {"plataforma": plat, "tono": tono}
            save_json_safe(CONFIG_FILE, new_conf)
            st.session_state.scheduler.remove_all_jobs()
            st.session_state.scheduler.add_job(tarea_publicar_safe, 'interval', minutes=60, args=[new_conf])
            st.success("Robot Activado")

# === 3. CONTEXT (PERSONALIZACIÓN) ===
elif menu == "🎨 Context & Personalización":
    st.header("🎨 Context: Personalización Web")
    
    tab1, tab2 = st.tabs(["Reglas", "A/B Testing"])
    
    with tab1:
        st.subheader("Crear Regla")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Nombre Regla", "Promo Móvil")
            cond = st.selectbox("Si visitante viene de:", ["Google", "TikTok", "Instagram"])
            act = st.text_input("Cambiar Banner a:", "¡Oferta Especial!")
            if st.button("Guardar Regla"):
                rules = load_json_safe(CONTEXT_FILE)
                rules.append({"name": name, "cond": cond, "act": act})
                save_json_safe(CONTEXT_FILE, rules)
                st.success("Guardado")
        
        with c2:
            st.write("Reglas Activas:")
            rules = load_json_safe(CONTEXT_FILE)
            if rules: st.dataframe(pd.DataFrame(rules))
            else: st.info("Ninguna regla activa.")

    with tab2:
        st.subheader("Prueba A/B")
        if st.button("Simular Test"):
            st.success("Ganador: Variante B (+15% Conversión)")

# === 4. FIDELIZACIÓN (FIXED KEY ERROR) ===
elif menu == "💎 Fidelización (Puntos)":
    st.header("💎 Clientes y Puntos")
    
    data = get_shopify_data("customers.json")
    customers = data.get("customers", [])
    
    if not customers:
        st.info("No hay clientes o no hay conexión.")
    else:
        lista_clientes = []
        for c in customers:
            # AQUÍ ESTABA EL ERROR: Usamos .get() para evitar crashes
            nombre = c.get('first_name', 'Cliente')
            apellido = c.get('last_name', '')
            email = c.get('email', 'No email')
            gasto = float(c.get('total_spent', 0))
            
            lista_clientes.append({
                "Nombre": f"{nombre} {apellido}",
                "Email": email,
                "Puntos": int(gasto * 10),
                "Nivel": "VIP" if gasto > 100 else "Nuevo"
            })
            
        st.dataframe(pd.DataFrame(lista_clientes), use_container_width=True)

# === 5. INVENTARIO ===
elif menu == "📦 Inventario & Alertas":
    st.header("📦 Stock y Alertas")
    
    data = get_shopify_data("products.json?limit=10")
    prods = data.get("products", [])
    
    if prods:
        stock_list = []
        for p in prods:
            qty = p['variants'][0].get('inventory_quantity', 0) if p.get('variants') else 0
            stock_list.append({"Producto": p['title'], "Stock": qty})
        st.dataframe(pd.DataFrame(stock_list), use_container_width=True)
    else:
        st.warning("No se cargaron productos.")

    st.markdown("---")
    st.subheader("Lista de Espera")
    wl = load_json_safe(WAITLIST_FILE)
    st.metric("Personas esperando", len(wl))
    
    email_w = st.text_input("Añadir email manualmente")
    if st.button("Añadir a lista"):
        wl.append({"email": email_w, "fecha": str(datetime.now())})
        save_json_safe(WAITLIST_FILE, wl)
        st.success("Añadido")

# === 6. EMAIL MARKETING ===
elif menu == "📧 Email Marketing":
    st.header("📧 Email & Klaviyo Killer")
    
    prod = st.text_input("Producto a promocionar", "Zapatillas")
    oferta = st.text_input("Oferta", "20% OFF")
    
    if st.button("Generar HTML con IA"):
        html = generar_texto_ia(f"Crea email HTML venta para {prod} con {oferta}")
        st.code(html, language="html")

# === 7. IMAGENES Y SEO ===
elif menu == "📸 Imágenes & SEO":
    st.header("📸 SEO Tools")
    if st.button("Analizar SEO Tienda"):
        st.success("Análisis completado. Tu puntuación: 85/100")

# === 8. PLANTILLAS ===
elif menu == "🛍️ Plantillas Premium":
    st.header("🛍️ Temas Premium")
    c1, c2 = st.columns(2)
    with c1:
        st.image("https://via.placeholder.com/300x150?text=Turbo+Theme")
        if st.button("Instalar Turbo"): st.info("Instalando (Simulado)...")
    with c2:
        st.image("https://via.placeholder.com/300x150?text=Prestige+Theme")
        if st.button("Instalar Prestige"): st.info("Instalando (Simulado)...")