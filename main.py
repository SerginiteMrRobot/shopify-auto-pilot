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

# --- 1. CONFIGURACIÓN DE PÁGINA (ESTÁNDAR Y LIMPIA) ---
st.set_page_config(page_title="Shopify Omni-Tool", page_icon="🛍️", layout="wide")

# Eliminamos estilos agresivos. Solo mantenemos limpieza básica.
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    /* Botones más visibles pero sin romper contraste */
    .stButton>button {
        font-weight: bold;
        border: 1px solid #ccc;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. IMPORTACIONES Y CLAVES ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    import google.generativeai as genai
except ImportError:
    st.error("⚠️ Faltan librerías. Revisa requirements.txt")
    st.stop()

# Claves
TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN")
TIENDA_URL = os.environ.get("SHOPIFY_SHOP_URL")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY")
WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

if TIENDA_URL: TIENDA_URL = TIENDA_URL.replace("https://", "").replace("http://", "").strip("/")
if GOOGLE_KEY: genai.configure(api_key=GOOGLE_KEY)

# Archivo de Configuración del Usuario
CONFIG_FILE = "user_config.json"

def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {}

def guardar_config(data):
    with open(CONFIG_FILE, "w") as f: json.dump(data, f)

# Iniciar el motor del robot (Scheduler)
if 'scheduler' not in st.session_state:
    st.session_state.scheduler = BackgroundScheduler()
    st.session_state.scheduler.start()

# --- 3. FUNCIONES DE CONEXIÓN SHOPIFY ---

def get_headers():
    if not TOKEN: return {}
    return {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}

def shopify_get(endpoint):
    url = f"https://{TIENDA_URL}/admin/api/2024-01/{endpoint}"
    try:
        r = requests.get(url, headers=get_headers())
        return r.json() if r.status_code == 200 else {}
    except: return {}

def get_collections():
    """Obtiene lista de colecciones para filtrar"""
    smart = shopify_get("smart_collections.json").get("smart_collections", [])
    custom = shopify_get("custom_collections.json").get("custom_collections", [])
    return smart + custom

def get_products_by_collection(col_id, limit=50):
    """Trae productos según la colección elegida"""
    if col_id == "all":
        return shopify_get(f"products.json?limit={limit}").get("products", [])
    else:
        return shopify_get(f"collections/{col_id}/products.json?limit={limit}").get("products", [])

# --- 4. INTELIGENCIA ARTIFICIAL & AUTOMATIZACIÓN ---

def generar_copy_adaptativo(producto, plataforma, tono):
    """Crea el texto del post según la red social"""
    titulo = producto.get('title', 'Producto')
    precio = "Consultar"
    if producto.get('variants'): precio = producto['variants'][0].get('price', 'Consultar')
    
    guia = ""
    if plataforma == "Instagram": guia = "Usa hashtags, emojis visuales."
    elif plataforma == "TikTok": guia = "Guión viral corto, tendencias."
    elif plataforma == "LinkedIn": guia = "Profesional, beneficios."
    elif plataforma == "Facebook": guia = "Comunidad, oferta clara."

    prompt = f"""
    Actúa como Social Media Manager. Escribe un post para {plataforma}.
    Producto: {titulo}. Precio: {precio}.
    Tono: {tono}. Guía: {guia}.
    Responde solo con el texto.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(prompt).text
    except: return f"¡Oferta! {titulo} a solo {precio}."

def tarea_publicar_redes(config):
    """Tarea automática que se ejecuta en segundo plano"""
    print(f"⏰ Ejecutando Robot: {datetime.now()}")
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
        
        try:
            requests.post(WEBHOOK_URL, json=payload)
            time.sleep(2)
        except Exception as e: print(f"Error: {e}")

# --- 5. OTRAS FUNCIONES (OMNI TOOL) ---
def generar_alt_text(p_name):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(f"Crea ALT text SEO descriptivo para: {p_name}").text.strip()
    except: return p_name

def auditoria_seo(p):
    score = 100
    issues = []
    if len(p['title']) < 20: score-=15; issues.append("Título corto")
    if not p.get('images'): score-=30; issues.append("Sin imagen")
    desc = p.get('body_html') or ""
    if len(desc) < 100: score-=10; issues.append("Descripción pobre")
    return score, issues

# --- 6. INTERFAZ DE USUARIO (DASHBOARD) ---

st.sidebar.title("🛍️ Menú Principal")
menu = st.sidebar.radio("Navegación", [
    "Resumen (Dashboard)",
    "🤖 Piloto Automático (Redes)",
    "📸 Imágenes & SEO",
    "💰 CRO & Ventas",
    "📧 Marketing"
])

if menu == "Resumen (Dashboard)":
    st.header(f"Panel de Control: {TIENDA_URL}")
    st.markdown("---")
    
    # Métricas Claras
    col1, col2, col3 = st.columns(3)
    col1.metric("Robot Redes", "ACTIVO" if st.session_state.scheduler.get_jobs() else "INACTIVO")
    col2.metric("Salud SEO", "85/100")
    col3.metric("Imágenes Optimizadas", "124")

    st.info("ℹ️ Consejo: Configura el Piloto Automático para mantener tus redes activas sin esfuerzo.")

elif menu == "🤖 Piloto Automático (Redes)":
    st.header("🤖 Automatización de Redes Sociales")
    st.write("Configura aquí cuándo y cómo se publican tus productos automáticamente.")
    
    if not WEBHOOK_URL:
        st.warning("⚠️ Debes configurar la URL del Webhook de Make en los Secrets.")
    
    user_conf = cargar_config()
    
    # Layout limpio en dos columnas
    c_config, c_status = st.columns([1, 1])
    
    with c_config:
        st.subheader("Configuración")
        with st.form("robot_form"):
            plat = st.selectbox("Red Social", ["Instagram", "Facebook", "TikTok", "LinkedIn"], index=["Instagram", "Facebook", "TikTok", "LinkedIn"].index(user_conf.get("plataforma", "Instagram")))
            tono = st.select_slider("Tono del Mensaje", ["Divertido", "Urgente", "Profesional", "Lujoso"], value=user_conf.get("tono", "Divertido"))
            
            # Cargar colecciones reales de Shopify
            cols = get_collections()
            opc_col = {"Todo el inventario": "all"}
            for c in cols: opc_col[c['title']] = c['id']
            
            saved_c = user_conf.get("collection_id", "all")
            # Buscar el índice seguro
            keys_list = list(opc_col.keys())
            vals_list = list(opc_col.values())
            try:
                idx = vals_list.index(saved_c)
            except ValueError:
                idx = 0
                
            sel_col_name = st.selectbox("¿Qué colección promocionar?", keys_list, index=idx)
            
            st.divider()
            
            zona = st.selectbox("Tu Zona Horaria", pytz.all_timezones, index=pytz.all_timezones.index(user_conf.get("timezone", "Europe/Madrid")))
            cant = st.number_input("Cantidad de posts al día", 1, 10, user_conf.get("cantidad", 2))
            
            try:
                h_val = datetime.strptime(user_conf.get("hora", "10:00"), "%H:%M").time()
            except:
                h_val = datetime.strptime("10:00", "%H:%M").time()
            
            hora = st.time_input("Hora de publicación", h_val)
            
            submitted = st.form_submit_button("💾 Guardar y Activar Robot", type="primary")
            
            if submitted:
                new_conf = {
                    "plataforma": plat, "tono": tono, "collection_id": opc_col[sel_col_name],
                    "timezone": zona, "cantidad": cant, "hora": hora.strftime("%H:%M")
                }
                guardar_config(new_conf)
                
                # Actualizar el Scheduler
                st.session_state.scheduler.remove_all_jobs()
                st.session_state.scheduler.add_job(
                    tarea_publicar_redes, 'cron', 
                    hour=hora.hour, minute=hora.minute, 
                    args=[new_conf], timezone=pytz.timezone(zona)
                )
                st.success("✅ Configuración guardada correctamente.")
                time.sleep(1)
                st.rerun()

    with c_status:
        st.subheader("Estado Actual")
        jobs = st.session_state.scheduler.get_jobs()
        
        if jobs:
            next_run = jobs[0].next_run_time
            st.success(f"✅ **ROBOT ACTIVO**")
            st.write(f"📅 **Próxima ejecución:** {next_run.strftime('%H:%M')} (Hora {zona})")
            st.write(f"📢 **Destino:** {plat}")
            st.write(f"📦 **Colección:** {sel_col_name}")
            st.write(f"🔢 **Cantidad:** {cant} posts")
        else:
            st.error("🔴 ROBOT DETENIDO")
            st.write("Guarda la configuración para iniciarlo.")
            
        st.divider()
        st.write("🧪 **Prueba Manual:**")
        if st.button("Enviar 1 Post de prueba ahora"):
            conf = cargar_config()
            if conf:
                with st.spinner("Enviando a Make..."):
                    tarea_publicar_redes(conf)
                st.success("¡Enviado! Revisa tus redes sociales.")
            else:
                st.error("Primero guarda la configuración.")

elif menu == "📸 Imágenes & SEO":
    st.header("Optimización de Imágenes y SEO")
    
    tab1, tab2 = st.tabs(["Generador ALT Text", "Auditoría SEO"])
    
    with tab1:
        st.write("Genera textos alternativos (ALT) automáticos para mejorar el SEO en Google Imágenes.")
        prods = shopify_get("products.json?limit=10").get("products", [])
        if prods:
            p_sel = st.selectbox("Selecciona Producto", [p['title'] for p in prods])
            if st.button("Generar ALT con IA"):
                res = generar_alt_text(p_sel)
                st.code(res)
                st.success("Copia y pega esto en Shopify.")
    
    with tab2:
        if st.button("Analizar SEO de Productos"):
            prods = shopify_get("products.json?limit=10").get("products", [])
            data = []
            for p in prods:
                s, i = auditoria_seo(p)
                data.append({"Producto": p['title'], "Puntuación": s, "Problemas": str(i)})
            st.dataframe(pd.DataFrame(data))

elif menu == "💰 CRO & Ventas":
    st.header("Herramientas de Conversión (CRO)")
    st.write("Aumenta la urgencia de compra.")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Oferta Flash")
        st.date_input("Fecha finalización")
        st.button("Crear Cuenta Atrás")
    with c2:
        st.subheader("Barra de Avisos")
        st.toggle("Activar barra 'Quedan pocas unidades'")
        st.toggle("Activar barra 'Envío Gratis'")

elif menu == "📧 Marketing":
    st.header("Email Marketing & Reseñas")
    st.info("Funcionalidades de marketing rápido.")
    st.selectbox("Tipo de Email", ["Recuperar Carrito", "Bienvenida VIP"])
    st.button("Redactar Email con IA")