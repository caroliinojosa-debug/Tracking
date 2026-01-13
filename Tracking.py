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
import ssl
app = FastAPI()

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "PedidosExt" 

MI_CORREO = "ciextrufan@gmail.com"
MI_PASSWORD = "axojrteyadfhqofs"
CORREO_VENTAS = "caroli.inojosa@gmail.com"

def conectar_hoja():
    creds_json = os.environ.get("GOOGLE_CREDS")
    try:
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", SCOPE)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        print(f"Error conexión: {e}")
        return None

def enviar_aviso_ventas(id_pedido, estados):
    try:
        resumen = "\n".join([f"- {d}: {'✅ LISTO' if v else '⏳ PENDIENTE'}" for d, v in estados.items()])
        msg = EmailMessage()
        msg.set_content(f"Saludos Equipo de Ventas,\n\nSe ha actualizado el seguimiento del pedido #{id_pedido}.\n\nESTADO ACTUAL:\n{resumen}\n\nEnlace: https://{os.getenv('RAILWAY_STATIC_URL', 'https://tracking-production-7a93.up.railway.app/')}")
        msg['Subject'] = f"ACTUALIZACIÓN PEDIDO #{id_pedido}"
        msg['From'] = MI_CORREO
        msg['To'] = CORREO_VENTAS
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(MI_CORREO, MI_PASSWORD)
            server.send_mail(MI_CORREO, CORREO_VENTAS, mensaje.as_string())
    except Exception as e: print(f"Error correo: {e}")

def cargar_desde_sheets():
    try:
        sheet = conectar_hoja()
        if not sheet: return []
        data = sheet.get_all_values()
        if len(data) < 2: return []
        encabezados = data[0]
        pedidos = []
        for fila in data[1:]:
            if not fila or not fila[0]: continue
            est = {encabezados[i]: (str(fila[i]).upper() == "TRUE") for i in range(1, len(encabezados))}
            pedidos.append({"id": str(fila[0]), "estados": est})
        return pedidos
    except: return []

def guardar_en_sheets(pedidos):
    try:
        sheet = conectar_hoja()
        if not sheet: return
        sheet.clear()
        encabezados = ["ID", "Materia_Prima", "Impresion", "Laminacion", "Corte", "Sellado", "Embalaje", "Despacho"]
        matriz = [encabezados]
        for p in pedidos:
            fila = [p["id"]] + ["TRUE" if p["estados"].get(d, False) else "FALSE" for d in encabezados[1:]]
            matriz.append(fila)
        sheet.update(f"A1:{chr(64 + len(encabezados))}{len(matriz)}", matriz)
    except Exception as e: print(f"Error guardado: {e}")

# --- APP FLET ---
CLAVE_ADMIN = "extrusora383"
DEPTOS = ["Materia_Prima", "Impresion", "Laminacion", "Corte", "Sellado", "Embalaje", "Despacho"]

async def main(page: ft.Page):
    page.title = "Tracking de Produccion"
    page.web_renderer = ft.WebRenderer.HTML
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F0F2F5"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.CrossAxisAlignment.CENTER

    def contenedor_principal(contenido):
        return ft.Container(
            content=ft.Column(contenido, horizontal_alignment="center", spacing=20),
            padding=30, bgcolor="white", border_radius=20, width=400,
            shadow=ft.BoxShadow(blur_radius=15, color="black12")
        )

    async def mostrar_menu_principal(e=None):
        await page.clean_async()
        async def ir_admin(e): await vista_login_admin()
        async def ir_visitante(e): await vista_visitante()
        await page.add_async(
            contenedor_principal([
                ft.Image(src="/logo.png", width=120),
                ft.Text("Tracking Pedidos", size=28, weight="bold", color="blue900"),
                ft.ElevatedButton("MODO ADMINISTRADOR", on_click=ir_admin, width=280),
                ft.ElevatedButton("CONSULTAR MI PEDIDO", on_click=ir_visitante, bgcolor="blue900", color="white", width=280),
            ])
        )

    async def vista_login_admin():
        await page.clean_async()
        txt_clave = ft.TextField(label="Contraseña", password=True, width=250, text_align="center")
        async def entrar(e):
            if txt_clave.value == CLAVE_ADMIN: await vista_panel_admin()
            else: txt_clave.error_text = "Incorrecta"; await page.update_async()
        async def volver(e): await mostrar_menu_principal()
        await page.add_async(contenedor_principal([
            ft.Image(src="/logo.png", width=120),
            ft.TextButton("< Volver", on_click=volver),
            ft.Text("Acceso Admin", size=24, weight="bold"),
            txt_clave,
            ft.ElevatedButton("ENTRAR", on_click=entrar)
        ]))

    async def vista_panel_admin():
        await page.clean_async()
        async def nuevo(e): await vista_accion_admin("nuevo")
        async def editar(e): await vista_accion_admin("editar")
        async def borrar(e): await vista_accion_admin("borrar")
        async def salir(e): await mostrar_menu_principal()
        await page.add_async(contenedor_principal([
            ft.Image(src="/logo.png", width=120),
            ft.Text("Panel de Control", size=24, weight="bold"),
            ft.ElevatedButton("REGISTRAR NUEVO", on_click=nuevo, width=250),
            ft.ElevatedButton("EDITAR PEDIDO", on_click=editar, width=250),
            ft.ElevatedButton("BORRAR PEDIDO", on_click=borrar, bgcolor="red100", color="red", width=250),
            ft.TextButton("Cerrar Sesión", on_click=salir)
        ]))

    async def vista_accion_admin(modo):
        await page.clean_async()
        txt_id = ft.TextField(label="ID del Pedido", width=250)
        checks = [ft.Checkbox(label=d) for d in DEPTOS]
        col_checks = ft.Column(checks)

        # 1. Función para GUARDAR
        async def ejecutar_guardado(e):
            page.splash = ft.ProgressBar()
            await page.update_async()
            try:
                def tarea_backend():
                    pedidos = cargar_desde_sheets()
                    nuevos = [p for p in pedidos if p["id"] != txt_id.value]
                    if modo != "borrar":
                        est = {c.label: c.value for c in checks}
                        nuevos.append({"id": txt_id.value, "estados": est})
                        try: enviar_aviso_ventas(txt_id.value, est)
                        except: pass
                    guardar_en_sheets(nuevos)
                
                await asyncio.to_thread(tarea_backend)
            except Exception as ex:
                print(f"Error: {ex}")
            
            page.splash = None
            await page.clean_async()
            await page.update_async()
            await vista_panel_admin()

        # 2. Función para CARGAR
        async def ejecutar_carga(e):
            pedidos = await asyncio.to_thread(cargar_desde_sheets)
            p = next((p for p in pedidos if p["id"] == txt_id.value), None)
            if p:
                for c in checks:
                    c.value = p["estados"].get(c.label, False)
                await page.update_async()

        # 3. Función para VOLVER
        async def volver_panel(e):
            await vista_panel_admin()

        # Armar la vista
        btns = [
            ft.TextButton("< Volver", on_click=volver_panel),
            ft.Text(modo.upper(), size=20, weight="bold"),
            txt_id
        ]
        if modo == "editar":
            btns.append(ft.ElevatedButton("Cargar Datos", on_click=ejecutar_carga))
        
        btns.append(col_checks)
        btns.append(ft.ElevatedButton("CONFIRMAR", on_click=ejecutar_guardado, 
                                     bgcolor="green" if modo != "borrar" else "red", 
                                     color="white", width=200))
        
        await page.add_async(contenedor_principal(btns))
    async def vista_visitante():
        await page.clean_async()
        txt_q = ft.TextField(label="Escriba su N° de Pedido", width=250, text_align="center")
        res = ft.Column()
        async def buscar(e):
            res.controls = [ft.ProgressBar()]; await page.update_async()
            loop = asyncio.get_event_loop()
            pedidos = await loop.run_in_executor(None, cargar_desde_sheets)
            p = next((p for p in pedidos if p["id"] == txt_q.value), None)
            res.controls.clear()
            if p:
                for d, v in p["estados"].items():
                    ic = ft.icons.CHECK_CIRCLE if v else ft.icons.RADIO_BUTTON_UNCHECKED
                    res.controls.append(ft.Row([ft.Icon(ic, color="green" if v else "red"), ft.Text(d)]))
            else: res.controls.append(ft.Text("No encontrado", color="red"))
            await page.update_async()
        async def volver(e): await mostrar_menu_principal()
        await page.add_async(contenedor_principal([
            ft.Image(src="/logo.png", width=120),
            ft.TextButton("< Volver", on_click=volver),
            ft.Text("Consultar Pedido", size=24, weight="bold"),
            txt_q, ft.ElevatedButton("BUSCAR", on_click=buscar, width=200), res
        ]))

    await mostrar_menu_principal()

# --- MONTAJE FINAL ---
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_assets = os.path.join(ruta_actual, "assets")
app_flet = flet_fastapi.app(main, assets_dir=ruta_assets, app_name="Tracking Dispromm")
app.mount("/", app_flet)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("Tracking:app", host="0.0.0.0", port=port, reload=False)




































