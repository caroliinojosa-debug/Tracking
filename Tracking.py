import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import smtplib
from email.message import EmailMessage
from fastapi import FastAPI
import flet_fastapi
import json

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
ruta_carpeta = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(ruta_carpeta, "credenciales.json") 
SHEET_NAME = "PedidosExt" 

MI_CORREO="caroli.inojosa@gmail.com"
MI_PASSWORD="axojrteyadfhqofs"
CORREO_VENTAS="rhextrufan@gmail.com"

def conectar_hoja():
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def enviar_aviso_ventas(id_pedido, estados):
    try:
        resumen="\n".join([f"- {depto}: {'? LISTO' if listo else '? PENDIENTE'}" for depto, listo in estados.items()])

        msg=EmailMessage()
        msg.set_content(f"Saludos Equipo de Ventas,\n\nSe ha actualizado el seguimiento del pedido #{id_pedido}.\n\nESTADO ACTUAL:\n{resumen}\n\nEnlace de seguimiento: https://huggingface.co/spaces/carolinita007/tracking")
        msg['From']=MI_CORREO
        msg['To']=CORREO_VENTAS

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
        print(f"Error: {e}")
        return []

def guardar_en_sheets(pedidos):
    try:
        sheet = conectar_hoja()
        sheet.clear()
        encabezados = ["ID", "Materia_Prima", "Impresion", "Laminacion", "Corte", "Sellado", "Embalaje", "Despacho"]
        matriz = [encabezados]
        for p in pedidos:
            fila = [p["id"]]
            for depto in encabezados[1:]:
                fila.append("TRUE" if p["estados"].get(depto, False) else "FALSE")
            matriz.append(fila)
        sheet.update(f"A1:{chr(64 + len(encabezados))}{len(matriz)}", matriz)
    except Exception as e:
        print(f"Error: {e}")

# --- APP ---
CLAVE_ADMIN = "extrusora383"

async def main(page: ft.Page):
    page.title = "Tracking de Produccion"
    page.window_icon_header="assets/logo.png"
    page.theme_mode = "light"
    page.window_width = 450
    page.bgcolor = "#F0F2F5"
    page.horizontal_alignment = "center"
    page.vertical_alignment = "center"

    DEPTOS = ["Materia_Prima", "Impresion", "Laminacion", "Corte", "Sellado", "Embalaje", "Despacho"]

    def titulo(texto):
        return ft.Text(texto, size=28, weight="bold", color="blue900")

    def contenedor_principal(contenido):
        return ft.Container(
            content=ft.Column(contenido, horizontal_alignment="center", spacing=20),
            padding=30,
            bgcolor="white",
            border_radius=20,
            shadow=ft.BoxShadow(blur_radius=15, color="black12"),
            width=400
        )

    def mostrar_menu_principal(e=None):
        page.clean()
        botones = [
            ft.Image(src="logo.png", width=100, height=100),
            titulo("Tracking Pedidos"),
            ft.Text("Control de Produccion", size=16, color="grey"),
            ft.ElevatedButton("MODO ADMINISTRADOR", on_click=vista_admin, width=280, height=50),
            ft.ElevatedButton("CONSULTAR MI PEDIDO", on_click=vista_visitante, 
                              bgcolor="blue900", color="white", width=280, height=50),
        ]
        page.add(contenedor_principal(botones))

    def vista_admin(e=None):
        page.clean()
        txt_clave = ft.TextField(label="Contraseña", password=True, width=250, text_align="center")
        def entrar(e):
            if txt_clave.value == CLAVE_ADMIN: vista_panel_admin()
            else: txt_clave.error_text = "Incorrecta"; page.update()
        
        page.add(contenedor_principal([
            ft.Image(src="logo.png", width=80),
            ft.TextButton("< Volver al Inicio", on_click=mostrar_menu_principal),
            titulo("Acceso Admin"), 
            txt_clave, 
            ft.ElevatedButton("ENTRAR", on_click=entrar, width=150)
        ]))

    def vista_panel_admin():
        page.clean()
        page.add(contenedor_principal([
            ft.Image(src="logo.png", width=80),
            titulo("Panel Control"),
            ft.ElevatedButton("REGISTRAR NUEVO", on_click=lambda _: vista_accion_admin("nuevo"), width=250),
            ft.ElevatedButton("EDITAR / BORRAR", on_click=lambda _: vista_accion_admin("editar"), width=250),
            ft.TextButton("Cerrar Sesion", on_click=mostrar_menu_principal)
        ]))

    def vista_accion_admin(modo):
        page.clean()
        txt_id = ft.TextField(label="ID del Pedido", width=250)
        col_checks = ft.Column([ft.Checkbox(label=d) for d in DEPTOS])
        
        def guardar(e):
            pedidos = cargar_desde_sheets()
            estados = {ck.label: ck.value for ck in col_checks.controls}
            nuevos_pedidos = [p for p in pedidos if p["id"] != txt_id.value]
            if modo != "borrar": nuevos_pedidos.append({"id": txt_id.value, "estados": estados})
            guardar_en_sheets(nuevos_pedidos)
            vista_panel_admin()

        def cargar_datos(e):
            pedidos = cargar_desde_sheets()
            p = next((p for p in pedidos if p["id"] == txt_id.value), None)
            if p:
                for ck in col_checks.controls: ck.value = p["estados"].get(ck.label, False)
                page.update()

        controles = [ft.TextButton("< Volver al Panel", on_click=lambda _: vista_panel_admin()), titulo(modo.upper()), txt_id]
        if modo == "editar": controles.append(ft.ElevatedButton("Cargar Datos", on_click=cargar_datos))
        controles.append(col_checks)
        controles.append(ft.ElevatedButton("CONFIRMAR ACCION", on_click=guardar, bgcolor="green" if modo != "borrar" else "red", color="white", width=200))
        
        page.add(contenedor_principal(controles))

    def vista_visitante(e=None):
        page.clean()
        txt_q = ft.TextField(label="Escriba su N° de Pedido", width=250, text_align="center")
        res = ft.Column()
        def buscar(e):
            res.controls.clear()
            p = next((p for p in cargar_desde_sheets() if p["id"] == txt_q.value), None)
            if p:
                for d, listo in p["estados"].items():
                    res.controls.append(ft.Row([
                        ft.Text(" [OK] " if listo else " [..] ", color="green" if listo else "red", weight="bold"), 
                        ft.Text(d, size=16)
                    ]))
            else: res.controls.append(ft.Text("ID no encontrado", color="red"))
            page.update()

        page.add(contenedor_principal([
            ft.Image(src="logo.png", width=80),
            ft.TextButton("< Volver al Inicio", on_click=mostrar_menu_principal), 
            titulo("Consultar"), 
            txt_q, 
            ft.ElevatedButton("BUSCAR ESTADO", on_click=buscar, width=200), 
            res
        ]))

    mostrar_menu_principal()




app = FastAPI()



# La línea que ya tienes
app.mount("/", flet_fastapi.app(main, assets_dir="assets"))






