import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import smtplib
import json
from email.message import EmailMessage
from fastapi import FastAPI
import flet_fastapi

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "PedidosExt" 

MI_CORREO = "caroli.inojosa@gmail.com"
MI_PASSWORD = "axojrteyadfhqofs"
CORREO_VENTAS = "rhextrufan@gmail.com"

def conectar_hoja():
    # Leemos la variable de entorno que configuramos en Railway
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("No se encontró la variable GOOGLE_CREDS en Railway")
    
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# ... (Aquí van tus funciones de enviar_aviso, cargar_desde_sheets y guardar_en_sheets) ...
# Asegúrate de que usen 'conectar_hoja()' como está arriba.

CLAVE_ADMIN = "extrusora383"

async def main(page: ft.Page):
    page.title = "Tracking de Produccion"
    page.theme_mode = "light"
    page.horizontal_alignment = "center"
    page.vertical_alignment = "center"

    # --- Aquí va toda tu lógica de vistas (mostrar_menu_principal, etc.) ---
    
    def mostrar_menu_principal(e=None):
        page.clean()
        page.add(ft.Text("App de Tracking Lista", size=30))
        # Agrega aquí tus botones originales...

    mostrar_menu_principal()

# --- ESTA PARTE ES CRÍTICA: FUERA DE CUALQUIER FUNCIÓN ---
app = FastAPI()
app.mount("/", flet_fastapi.app(main, assets_dir="assets"))
