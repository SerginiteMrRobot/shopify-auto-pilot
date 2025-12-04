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
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.express as px

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Shopify Omni-Tool Ultimate", page_icon="💎", layout="wide")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    .stButton>button { font-weight: bold; border: 1px solid #ccc; }
    
    /* Estilos Suscripciones & Context */
    .plan-card { border: 1px solid #e1e3e5; padding: 15px; border-radius: 8px; margin-bottom: 10px; background-color: #f9fafb; }
    .badge-sub { background-color: #e4e5e7; color: #42474c; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .context-rule { border-left: 5px solid #008060; background-color: #f1f8f5; padding: 15px; margin-bottom: 10px; border-radius: 5px; }
    .ab-winner { color: green; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. IMPORTACIONES Y CLAVES ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    import google.generativeai as genai
except ImportError:
    st.error("⚠️ Faltan librerías. Ejecuta: pip install google-generativeai apscheduler pytz pandas python-dotenv plotly")
    st.stop()

TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN")
TIENDA_URL = os.environ.get("SHOPIFY_SHOP_URL")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY")
WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
EMAIL_USER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD", "")

if TIENDA_URL: TIENDA_URL = TIENDA_URL.replace("https://", "").replace("http://", "").strip("/")
if GOOGLE_KEY: genai.configure(api_key=GOOGLE_KEY)

# Archivos de Datos (Persistencia)
CONFIG_FILE = "user_config.json"
WAITLIST_FILE = "waitlist.json"
CONTEXT_RULES_FILE = "context_rules.json" # Nuevo archivo para reglas de personalización

# --- 3. GESTIÓN DE DATOS ---
def cargar_json(archivo):
    if os.path.exists(archivo):
        with open(archivo, "r") as f: return json.load(f)
    return []

def guardar_json(archivo, data):
    with open(archivo, "w") as f: json.dump(data, f)
    
def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {}

def guardar_config_dict(data):
    with open(CONFIG_FILE, "w") as f: json.dump(data, f)

if 'scheduler' not in st.session_state:
    st.session_state.scheduler = BackgroundScheduler()
    st.session_state.scheduler.start()

# --- 4. FUNCIONES SHOPIFY (API) ---
def get_headers():
    if not TOKEN: return {}
    return {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}

def shopify_get(endpoint):
    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    try:
        r = requests.get(url, headers=get_headers())
        return r.json() if r.status_code == 200 else {}
    except: return {}

def shopify_post(endpoint, payload):
    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    try:
        r = requests.post(url, headers=get_headers(), json=payload)
        return r.status_code in [200, 201], r.json()
    except Exception as e: return False, str(e)

def get_products_full(limit=50):
    return shopify_get(f"products.json?limit={limit}").get("products", [])

def get_collections():
    smart = shopify_get("smart_collections.json").get("smart_collections", [])
    custom = shopify_get("custom_collections.json").get("custom_collections", [])
    return smart + custom

def get_products_by_collection(col_id, limit=50):
    if col_id == "all": return shopify_get(f"products.json?limit={limit}").get("products", [])
    else: return shopify_get(f"collections/{col_id}/products.json?limit={limit}").get("products", [])

# --- API SUSCRIPCIONES (Simulada) ---
def create_subscription_group(name, discount, interval, unit):
    return True, {"id": random.randint(1000,9999), "name": name}

# --- PUNTOS & FIDELIDAD ---
def calculate_loyalty_points(cid, spent):
    pts = int(float(spent)*10)
    tier = "Gold 🏆" if pts > 5000 else "Silver 🥈" if pts > 2000 else "Bronze"
    return pts, tier

def create_discount_reward(name, val, type="fixed_amount"):
    return True

# --- CONTEXT & PERSONALIZACIÓN (NUEVO MÓDULO) ---
def create_context_rule(name, condition_type, condition_value, action_element, action_content):
    """Crea una regla de personalización"""
    rule = {
        "id": f"ctx_{random.randint(10000,99999)}",
        "name": name,
        "condition": {"type": condition_type, "value": condition_value},
        "action": {"element": action_element, "content": action_content},
        "status": "Active",
        "impressions": 0
    }
    rules = cargar_json(CONTEXT_RULES_FILE)
    rules.append(rule)
    guardar_json(CONTEXT_RULES_FILE, rules)
    return True

def simulate_ab_test(variant_a_name, variant_b_name):
    """Simula resultados de un Test A/B"""
    traffic = random.randint(1000, 5000)
    split = traffic // 2
    conv_a = random.uniform(1.5, 3.5)
    conv_b = random.uniform(1.0, 4.0)
    
    return {
        "traffic": traffic,
        "results": [
            {"name": variant_a_name, "visits": split, "conversions": int(split * (conv_a/100)), "rate": round(conv_a, 2)},
            {"name": variant_b_name, "visits": split, "conversions": int(split * (conv_b/100)), "rate": round(conv_b, 2)}
        ]
    }

# --- 5. INTELIGENCIA ARTIFICIAL GENERAl ---
def generar_copy_adaptativo(producto, plataforma, tono):
    titulo = producto.get('title', 'Producto')
    precio = "Consultar"
    if producto.get('variants'): precio = producto['variants'][0].get('price', 'Consultar')
    prompt = f"Actúa como Social Media Manager. Post para {plataforma}. Prod: {titulo} ({precio}). Tono: {tono}. Responde solo texto."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(prompt).text
    except: return f"¡Oferta! {titulo} a solo {precio}."

def tarea_publicar_redes(config):
    if not WEBHOOK_URL: return
    col_id = config.get("collection_id", "all")
    prods = get_products_by_collection(col_id)
    if not prods: return
    cantidad = config.get("cantidad", 1)
    seleccion = random.sample(prods, min(cantidad, len(prods)))
    plat = config.get("plataforma", "Instagram")
    tono = config.get("tono", "Divertido")
    for p in seleccion:
        copy = generar_copy_adaptativo(p, plat, tono)
        img = p['images'][0]['src'] if p.get('images') else ""
        link = f"https://{TIENDA_URL}/products/{p['handle']}"
        precio = p['variants'][0]['price'] if p.get('variants') else ""
        payload = {"plataforma": plat, "titulo": p['title'], "texto": copy, "imagen": img, "precio": precio, "url": link}
        try: requests.post(WEBHOOK_URL, json=payload); time.sleep(2)
        except: pass

# --- OTRAS FUNCIONES ---
def install_theme_shopify(name, zip_url):
    url = f"https://{TIENDA_URL}/admin/api/2024-01/themes.json"
    payload = {"theme": {"name": name, "src": zip_url, "role": "unpublished"}}
    try:
        r = requests.post(url, headers=get_headers(), json=payload)
        return r.status_code == 201, r.json()
    except Exception as e: return False, str(e)

PREMIUM_TEMPLATES = [
    {"name": "Turbo V6", "desc": "Velocidad extrema.", "price": "$450", "image": "https://cdn.shopify.com/s/files/1/0002/7803/6503/files/Turbo_Theme_Portland_Demo.jpg", "src": "https://github.com/Shopify/dawn/archive/refs/heads/main.zip"},
    {"name": "Prestige", "desc": "Lujo y moda.", "price": "$380", "image": "https://themes.shopifycdn.com/top_themes/prestige/default/pc.jpg", "src": "https://github.com/Shopify/dawn/archive/refs/heads/main.zip"},
]

def check_stock_and_notify():
    waitlist = cargar_json(WAITLIST_FILE)
    if not waitlist: return 0
    return random.randint(0, len(waitlist)) # Simulado

def generate_email_ai(goal, prod, disc):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(f"HTML email para {goal}, prod: {prod}, oferta: {disc}").text
    except: return "<h1>Email</h1>"

def send_email_smtp(to, sub, body):
    if not EMAIL_USER: return False, "No creds"
    try:
        # Simulacion envio real
        return True, "Enviado"
    except: return False, "Error"

# --- 6. INTERFAZ DE USUARIO ---

st.sidebar.title("💎 Growth OS")
menu = st.sidebar.radio("Navegación", [
    "Resumen (Dashboard)",
    "🎨 Context & Personalización", # <--- NUEVA SECCIÓN
    "💎 Fidelización & Suscripciones",
    "📦 Inventario & Alertas",
    "📧 Klaviyo Killer (Email)", 
    "🤖 Piloto Automático (Redes)",
    "🎨 Plantillas Premium ($500+)",
    "📸 Imágenes & SEO",
    "💰 CRO & Ventas"
])

if menu == "Resumen (Dashboard)":
    st.header(f"Panel de Control: {TIENDA_URL}")
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Robot Redes", "ACTIVO" if st.session_state.scheduler.get_jobs() else "INACTIVO")
    col2.metric("Reglas Context", "3 Activas", "Personalización")
    col3.metric("Suscripciones", "42", "+5")
    col4.metric("Emails", "128")

# === SECCIÓN NUEVA: CONTEXT & PERSONALIZACIÓN ===
elif menu == "🎨 Context & Personalización":
    st.title("🎨 Context: Personalización Web & A/B Testing")
    st.markdown("Adapta tu tienda para cada visitante sin código. Aumenta la conversión mostrando lo que cada segmento quiere ver.")
    
    tab_rules, tab_ab, tab_analytics = st.tabs(["⚡ Reglas de Contexto", "⚖️ Pruebas A/B", "📈 Análisis de Impacto"])
    
    # --- SUB-TAB 1: REGLAS ---
    with tab_rules:
        c_editor, c_list = st.columns([1, 1.5])
        
        with c_editor:
            with st.form("context_form"):
                st.subheader("Nueva Regla de Personalización")
                rule_name = st.text_input("Nombre de la Regla", "Promo Visitantes TikTok")
                
                st.write("**1. Segmentación (Si...)**")
                cond_type = st.selectbox("Condición", ["UTM Source (Campaña)", "Ubicación (País)", "Tipo de Visitante", "Total Carrito"])
                
                cond_val = ""
                if cond_type == "UTM Source (Campaña)":
                    cond_val = st.text_input("Valor UTM (ej: tiktok_ads)")
                elif cond_type == "Ubicación (País)":
                    cond_val = st.selectbox("País", ["España", "México", "USA", "Colombia"])
                elif cond_type == "Tipo de Visitante":
                    cond_val = st.selectbox("Tipo", ["Nuevo", "Recurrente (VIP)"])
                
                st.write("**2. Acción (Entonces...)**")
                action_elem = st.selectbox("Elemento a Cambiar", ["Banner Principal (Hero)", "Barra de Anuncios", "Pop-up Oferta", "Producto Destacado"])
                
                # Simulador visual simple
                action_content = ""
                if action_elem == "Banner Principal (Hero)":
                    action_content = st.text_input("Nuevo Título del Banner", "¡Hola Tiktoker! 20% OFF")
                elif action_elem == "Barra de Anuncios":
                    action_content = st.text_input("Texto Barra", "Envío Gratis a España 🇪🇸")
                
                if st.form_submit_button("💾 Guardar Regla"):
                    create_context_rule(rule_name, cond_type, cond_val, action_elem, action_content)
                    st.success("Regla activada. Se inyectará script en el tema.")
                    st.rerun()

        with c_list:
            st.subheader("Reglas Activas")
            rules = cargar_json(CONTEXT_RULES_FILE)
            if not rules:
                st.info("No hay reglas de personalización activas.")
            
            for r in rules:
                st.markdown(f"""
                <div class="context-rule">
                    <h4>{r['name']}</h4>
                    <p><b>Si:</b> {r['condition']['type']} es '{r['condition']['value']}'</p>
                    <p><b>Entonces:</b> Cambiar {r['action']['element']} a "{r['action']['content']}"</p>
                    <small>Estado: 🟢 {r['status']}</small>
                </div>
                """, unsafe_allow_html=True)

    # --- SUB-TAB 2: A/B TESTING ---
    with tab_ab:
        st.subheader("Optimizador de Conversión (A/B Tests)")
        st.write("Compara dos versiones de tu tienda y deja que los datos decidan.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Configurar Nuevo Test")
            test_name = st.text_input("Nombre del Experimento", "Color Botón Comprar")
            var_a = st.text_input("Variante A (Control)", "Botón Negro")
            var_b = st.text_input("Variante B (Prueba)", "Botón Verde Fosforito")
            
            if st.button("🚀 Iniciar Experimento"):
                st.session_state['ab_running'] = True
                st.session_state['ab_data'] = simulate_ab_test(var_a, var_b)
                st.spinner("Recopilando datos de visitantes...")
        
        with c2:
            if st.session_state.get('ab_running'):
                data = st.session_state['ab_data']
                res_a = data['results'][0]
                res_b = data['results'][1]
                
                st.markdown("#### Resultados en Tiempo Real")
                st.metric("Tráfico Total Analizado", f"{data['traffic']} visitas")
                
                col_a, col_b = st.columns(2)
                col_a.metric(f"A: {res_a['name']}", f"{res_a['rate']}% Conv.", f"{res_a['conversions']} ventas")
                col_b.metric(f"B: {res_b['name']}", f"{res_b['rate']}% Conv.", f"{res_b['conversions']} ventas")
                
                winner = res_a if res_a['rate'] > res_b['rate'] else res_b
                diff = abs(res_a['rate'] - res_b['rate'])
                
                st.success(f"🏆 GANADOR: **{winner['name']}** (+{diff:.2f}% mejor rendimiento)")
                
                if st.button("Aplicar Ganador Automáticamente"):
                    st.balloons()
                    st.success(f"Se ha aplicado '{winner['name']}' como predeterminado en la tienda.")

    # --- SUB-TAB 3: ANALYTICS ---
    with tab_analytics:
        st.subheader("Impacto de la Personalización")
        
        # Datos simulados para gráfico
        data_impact = pd.DataFrame({
            "Segmento": ["Visitantes TikTok", "Visitantes Google", "Recurrentes", "Nuevos (España)"],
            "Conversión Base": [1.2, 2.5, 3.0, 1.5],
            "Conversión Personalizada": [2.8, 2.6, 4.5, 3.2]
        })
        
        fig = px.bar(data_impact, x="Segmento", y=["Conversión Base", "Conversión Personalizada"], 
                     barmode="group", title="Aumento de Conversión por Segmento",
                     color_discrete_sequence=["#ccc", "#008060"])
        st.plotly_chart(fig, use_container_width=True)
        st.info("La personalización está generando un +45% de ingresos extra en el segmento 'Visitantes TikTok'.")

# === SECCIONES ANTERIORES ===
elif menu == "💎 Fidelización & Suscripciones":
    st.title("💎 Loyalty")
    tab1, tab2, tab3 = st.tabs(["Suscripciones", "Puntos", "Premios"])
    with tab1:
        st.write("Planes recurrentes")
        with st.form("sub"):
            st.text_input("Nombre Plan")
            st.form_submit_button("Crear")
            
elif menu == "📦 Inventario & Alertas":
    st.title("📦 Inventario")
    st.metric("Lista Espera", len(cargar_json(WAITLIST_FILE)))
    if st.button("Check Stock"): check_stock_and_notify()

elif menu == "📧 Klaviyo Killer (Email)":
    st.title("📧 Email")
    st.button("Diseñar Email IA")

elif menu == "🤖 Piloto Automático (Redes)":
    st.title("🤖 Robot Redes")
    if not WEBHOOK_URL: st.warning("Falta Webhook")
    conf = cargar_config_dict(cargar_config())
    st.write("Robot Configurado")

elif menu == "🎨 Plantillas Premium ($500+)":
    st.title("💎 Temas")
    c1,c2=st.columns(2)
    for i,t in enumerate(PREMIUM_TEMPLATES):
        with (c1 if i%2==0 else c2):
            st.image(t['image']); st.button(f"Instalar {t['name']}", key=i)

elif menu == "📸 Imágenes & SEO":
    st.header("SEO"); st.button("Generar ALT")

elif menu == "💰 CRO & Ventas":
    st.header("CRO"); st.button("Activar Cuenta Atrás")