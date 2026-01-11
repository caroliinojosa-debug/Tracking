import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import smtplib
from email.message import EmailMessage
from fastapi import FastAPI
import flet_fastapi
import json
import uvicorn
import asyncio

app = FastAPI()

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "PedidosExt"

MI_CORREO = "caroli.inojosa@gmail.com"
MI_PASSWORD = "axojrteyadfhqofs"
CORREO_VENTAS = "rhextrufan@gmail.com"

def conectar_hoja():
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        return None # Evitamos que explote si no hay credenciales todavía
    
    try:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        print(f"Error en conexión: {e}")
        return None

def cargar_desde_sheets():
    try:
        sheet = conectar_hoja()
        if not sheet: return []
        lista_completa = sheet.get_all_values()
        if not lista_completa or len(lista_completa) < 2: return []
        encabezados = lista_completa[0]
        datos = lista_completa[1:]
        pedidos = []
        for fila in datos:
            if not fila or not fila[0]: continue
            estado_dict = {}
            for i in range(1, len(encabezados)):
                nombre_col = encabezados[i]
                estado_dict[nombre_col] = (str(fila[i]).upper() == "TRUE")
            pedidos.append({"id": str(fila[0]), "estados": estado_dict})
        return pedidos
    except Exception as e:
        print(f"Error cargando: {e}")
        return []

# --- APP FLET ---
CLAVE_ADMIN = "extrusora383"
DEPTOS = ["Materia_Prima", "Impresion", "Laminacion", "Corte", "Sellado", "Embalaje", "Despacho"]

async def main(page: ft.Page):
    page.title = "Tracking de Produccion"
    page.theme_mode = "light"
    page.bgcolor = "#F0F2F5"
    page.horizontal_alignment = "center"
    page.vertical_alignment = "center"

    async def mostrar_menu_principal(e=None):
        await page.clean_async()
        await page.add_async(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.TRACK_CHANGES, size=50, color="blue900"),
                    ft.Text("Tracking Pedidos", size=28, weight="bold", color="blue900"),
                    ft.ElevatedButton("MODO ADMINISTRADOR", on_click=lambda _: page.show_snack_bar_async(ft.SnackBar(ft.Text("Próximamente"))), width=280),
                    ft.ElevatedButton("CONSULTAR MI PEDIDO", on_click=vista_visitante, bgcolor="blue900", color="white", width=280),
                ], horizontal_alignment="center", spacing=20),
                padding=30, bgcolor="white", border_radius=20, width=400
            )
        )

    async def vista_visitante(e=None):
        await page.clean_async()
        txt_q = ft.TextField(label="N° de Pedido", width=250, text_align="center")
        res = ft.Column()

        async def buscar(e):
            res.controls.clear()
            res.controls.append(ft.ProgressBar())
            await page.update_async()
            
            loop = asyncio.get_event_loop()
            pedidos = await loop.run_in_executor(None, cargar_desde_sheets)
            
            res.controls.clear()
            p = next((p for p in pedidos if p["id"] == txt_q.value), None)
            if p:
                for d, listo in p["estados"].items():
                    res.controls.append(ft.Row([
                        ft.icon(ft.Icons.CHECK_CIRCLE if listo else ft.Icons.RADIO_BUTTON_UNCHECKED, color="green" if listo else "red"),
                        ft.Text(d, size=16)
                    ]))
            else:
                res.controls.append(ft.Text("No encontrado", color="red"))
            await page.update_async()

        await page.add_async(
            ft.Container(
                content=ft.Column([
                    ft.TextButton("< Volver", on_click=mostrar_menu_principal),
                    ft.Text("Consultar Pedido", size=24, weight="bold"),
                    txt_q,
                    ft.ElevatedButton("BUSCAR", on_click=buscar, width=200),
                    res
                ], horizontal_alignment="center"),
                padding=30, bgcolor="white", border_radius=20
            )
        )

    await mostrar_menu_principal()

# --- MONTAJE FINAL (CORREGIDO) ---
app.mount("/", flet_fastapi.app(main))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)























