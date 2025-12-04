import streamlit as st
import requests
import time
import os
import json
import random
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

# --- AÑADIR ESTO PARA MODO LOCAL (PC) ---
try:
    from dotenv import load_dotenv
    load_dotenv() # Esto carga las claves del archivo .env
except ImportError:
    pass # Si da error es que no tienes la libreria instalada aun
# ----------------------------------------

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Shopify Auto-Pilot Pro", page_icon="🚀", layout="wide")