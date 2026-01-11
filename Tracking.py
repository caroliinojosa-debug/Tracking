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
        raise ValueError("Error: No se encontró la variable GOOGLE_CREDS en Railway")
    
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def enviar_aviso_ventas(id_pedido, estados):
    try:
        resumen = "\n".join([f"- {depto}: {'✅ LISTO' if listo else '⏳ PENDIENTE'}" for depto, listo in estados.items()])
        msg = EmailMessage()
        msg.set_content(f"Saludos Equipo de Ventas,\n\nSe ha actualizado el seguimiento del pedido #{id_pedido}.\n\nESTADO ACTUAL:\n{resumen}\n\nEnlace: https://tracking-production-7a93.up.railway.app")
        msg['From'] = MI_CORREO
        msg['To'] = CORREO_VENTAS
        msg['Subject'] = f"Actualización Pedido #{id_pedido}"

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(MI_CORREO, MI_PASSWORD) 
            server.send_message(msg)
    except Exception as e:
        print(f"Error al enviar correo: {e}") 

def cargar_desde_sheets():
    try:
        sheet = conectar_hoja()
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
        print(f"Error cargando sheets: {e}")
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
    
    # Helpers visuales
    def titulo(texto):
        return ft.Text(texto, size=28, weight="bold", color="blue900")

    def contenedor_principal(contenido):
        return ft.Container(
            content=ft.Column(contenido, horizontal_alignment="center", spacing=20),
            padding=30, bgcolor="white", border_radius=20,
            shadow=ft.BoxShadow(blur_radius=15, color="black12"), width=400
        )

    # Vistas
    async def mostrar_menu_principal(e=None):
        await page.clean_async()
        botones = [
            ft.Image(src="/logo.png", width=100, height=100), 
            titulo("Tracking Pedidos"),
            ft.Text("Control de Produccion", size=16, color="grey"),
            ft.ElevatedButton("MODO ADMINISTRADOR", on_click=vista_admin, width=280, height=50),
            ft.ElevatedButton("CONSULTAR MI PEDIDO", on_click=vista_visitante, 
                             bgcolor="blue900", color="white", width=280, height=50),
        ]
        await page.add_async(contenedor_principal(botones))

    async def vista_admin(e=None):
        await page.clean_async()
        txt_clave = ft.TextField(label="Contraseña", password=True, width=250, text_align="center")

        async def entrar(e):
            if txt_clave.value == CLAVE_ADMIN: 
                await vista_panel_admin()
            else: 
                txt_clave.error_text = "Incorrecta"
                await page.update_async()

        await page.add_async(contenedor_principal([
            ft.Image(src="/logo.png", width=80), 
            ft.TextButton("< Volver al Inicio", on_click=mostrar_menu_principal),
            titulo("Acceso Admin"), 
            txt_clave, 
            ft.ElevatedButton("ENTRAR", on_click=entrar, width=150)
        ]))

    async def vista_panel_admin(e=None):
        await page.clean_async()
        await page.add_async(contenedor_principal([
            ft.Image(src="/logo.png", width=80),
            titulo("Panel Control"),
            ft.ElevatedButton("REGISTRAR NUEVO", on_click=lambda _: page.run_task(vista_accion_admin, "nuevo"), width=250),
            ft.ElevatedButton("EDITAR / BORRAR", on_click=lambda _: page.run_task(vista_accion_admin, "editar"), width=250),
            ft.TextButton("Cerrar Sesion", on_click=mostrar_menu_principal)
        ]))

    async def vista_accion_admin(modo):
        await page.clean_async()
        txt_id = ft.TextField(label="ID del Pedido", width=250)
        # Diccionario para guardar referencia a los checkboxes
        checks = {d: ft.Checkbox(label=d) for d in DEPTOS}
        col_checks = ft.Column(list(checks.values()))

        async def guardar(e):
            # Aquí iría la lógica de guardar_en_sheets
            # Por ahora simplificado para que no de error
            await page.show_snack_bar_async(ft.SnackBar(ft.Text("Procesando...")))
            await mostrar_menu_principal()

        controles = [
            ft.TextButton("< Volver", on_click=mostrar_menu_principal),
            titulo(modo.upper()),
            txt_id,
            col_checks,
            ft.ElevatedButton("CONFIRMAR", on_click=guardar, bgcolor="blue900", color="white", width=200)
        ]
        await page.add_async(contenedor_principal(controles))

    async def vista_visitante(e=None):
        await page.clean_async()
        txt_q = ft.TextField(label="N° de Pedido", width=250, text_align="center")
        res = ft.Column()

        async def buscar(e):
            res.controls.clear()
            res.controls.append(ft.ProgressBar())
            await page.update_async()
            
            # Ejecutar en hilo aparte para no bloquear
            loop = asyncio.get_event_loop()
            pedidos = await loop.run_in_executor(None, cargar_desde_sheets)
            
            res.controls.clear()
            p = next((p for p in pedidos if p["id"] == txt_q.value), None)
            if p:
                for d, listo in p["estados"].items():
                    res.controls.append(ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE if listo else ft.Icons.RADIO_BUTTON_UNCHECKED, 
                                color="green" if listo else "red"),
                        ft.Text(d, size=16)
                    ]))
            else:
                res.controls.append(ft.Text("No encontrado", color="red"))
            await page.update_async()

        await page.add_async(contenedor_principal([
            ft.Image(src="/logo.png", width=80),
            ft.TextButton("< Volver", on_click=mostrar_menu_principal),
            titulo("Consultar"),
            txt_q,
            ft.ElevatedButton("BUSCAR", on_click=buscar, width=200),
            res
        ]))

    await mostrar_menu_principal()

# --- MONTAJE DE LA APP ---
app.mount("/", flet_fastapi.app(main, assets_dir="assets"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)






















