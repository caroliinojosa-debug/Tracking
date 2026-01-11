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
SHEET_NAME = "PedidosExt" # Nombre de tu Excel

MI_CORREO = "caroli.inojosa@gmail.com"
MI_PASSWORD = "axojrteyadfhqofs"
CORREO_VENTAS = "rhextrufan@gmail.com"

def conectar_hoja():
    # Intenta leer de variable de entorno (Railway) o de archivo local (PC)
    creds_json = os.environ.get("GOOGLE_CREDS")
    try:
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            # Si estás en local busca el archivo
            creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", SCOPE)
        
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        print(f"Error en conexión: {e}")
        return None

def enviar_aviso_ventas(id_pedido, estados):
    try:
        resumen = "\n".join([f"- {depto}: {'✅ LISTO' if listo else '⏳ PENDIENTE'}" for depto, listo in estados.items()])
        msg = EmailMessage()
        msg.set_content(f"Saludos Equipo de Ventas,\n\nSe ha actualizado el seguimiento del pedido #{id_pedido}.\n\nESTADO ACTUAL:\n{resumen}\n\nEnlace: https://{os.getenv('RAILWAY_STATIC_URL', 'seguimiento-de-producción-7a93.up.railway.app')}")
        msg['Subject'] = f"ACTUALIZACIÓN PEDIDO #{id_pedido}"
        msg['From'] = MI_CORREO
        msg['To'] = CORREO_VENTAS

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(MI_CORREO, MI_PASSWORD) 
            server.send_message(msg)
    except Exception as e:
        print(f"Error correo: {e}")

def cargar_desde_sheets():
    try:
        sheet = conectar_hoja()
        if not sheet: return []
        lista_completa = sheet.get_all_values()
        if not lista_completa or len(lista_completa) < 2: return []
        encabezados = lista_completa[0]
        pedidos = []
        for fila in lista_completa[1:]:
            if not fila or not fila[0]: continue
            estado_dict = {}
            for i in range(1, len(encabezados)):
                estado_dict[encabezados[i]] = (str(fila[i]).upper() == "TRUE")
            pedidos.append({"id": str(fila[0]), "estados": estado_dict})
        return pedidos
    except Exception as e:
        print(f"Error carga: {e}"); return []

def guardar_en_sheets(pedidos):
    try:
        sheet = conectar_hoja()
        if not sheet: return
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
        print(f"Error guardado: {e}")

# --- APP FLET ---
CLAVE_ADMIN = "extrusora383"
DEPTOS = ["Materia_Prima", "Impresion", "Laminacion", "Corte", "Sellado", "Embalaje", "Despacho"]

async def main(page: ft.Page):
    page.web_renderer = ft.WebRenderer.HTML
    page.title = "Tracking de Produccion"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F0F2F5"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.CrossAxisAlignment.CENTER

    def contenedor_principal(contenido):
        return ft.Container(
            content=ft.Column(contenido, horizontal_alignment="center", spacing=20),
            padding=30, bgcolor="white", border_radius=20,
            shadow=ft.BoxShadow(blur_radius=15, color="black12"), width=400
        )

   async def mostrar_menu_principal(e=None):
        await page.clean_async()

        # --- AQUÍ ESTÁ EL TRUCO ---
        # Definimos estas dos funciones cortitas antes de los botones
        async def ir_a_admin(e):
            await vista_login_admin()

        async def ir_a_visitante(e):
            await vista_visitante()

        # Ahora el menú con los botones corregidos
        await page.add_async(
            contenedor_principal([
                ft.Image(src="/logo.png", width=120), 
                ft.Text("Tracking Pedidos", size=28, weight="bold", color="blue900"),
                
                # Mira cómo cambiamos el on_click: ya no hay lambda
                ft.ElevatedButton("MODO ADMINISTRADOR", on_click=ir_a_admin, width=280),
                ft.ElevatedButton("CONSULTAR MI PEDIDO", on_click=ir_a_visitante, bgcolor="blue900", color="white", width=280),
            ])
        )

    async def vista_login_admin():
        await page.clean_async()
        
        # 1. Definimos el campo de texto
        txt_clave = ft.TextField(label="Contraseña", password=True, width=250, text_align="center")
        
        # 2. Función interna para entrar (ya es async, está bien)
        async def entrar(e):
            if txt_clave.value == CLAVE_ADMIN: 
                await vista_panel_admin()
            else: 
                txt_clave.error_text = "Incorrecta"
                await page.update_async()

        # 3. Función interna para volver (necesita await)
        async def volver(e):
            await mostrar_menu_principal()
        
        # 4. Agregamos los controles
        await page.add_async(
            contenedor_principal([
                # IMPORTANTE: Cambiamos el on_click para que use 'volver' con await
                ft.TextButton("< Volver", on_click=volver),
                ft.Text("Acceso Admin", size=24, weight="bold"),
                txt_clave,
                ft.ElevatedButton("ENTRAR", on_click=entrar)
            ])
        )

    async def vista_panel_admin():
        await page.clean_async()

        # --- FUNCIONES PARA QUE LOS BOTONES REACCIONEN ---
        async def ir_a_nuevo(e):
            await vista_accion_admin("nuevo")

        async def ir_a_editar(e):
            await vista_accion_admin("editar")

        async def ir_a_borrar(e):
            await vista_accion_admin("borrar")

        async def salir(e):
            await mostrar_menu_principal()

        # --- LA INTERFAZ ---
        await page.add_async(
            contenedor_principal([
                ft.Text("Panel de Control", size=24, weight="bold"),
                
                # Usamos las funciones que acabamos de crear arriba
                ft.ElevatedButton("REGISTRAR NUEVO", on_click=ir_a_nuevo, width=250),
                ft.ElevatedButton("EDITAR PEDIDO", on_click=ir_a_editar, width=250),
                ft.ElevatedButton("BORRAR PEDIDO", on_click=ir_a_borrar, bgcolor="red100", color="red", width=250),
                
                ft.TextButton("Cerrar Sesión", on_click=salir)
            ])
        )

    async def vista_accion_admin(modo):
        await page.clean_async()
        txt_id = ft.TextField(label="ID del Pedido", width=250)
        col_checks = ft.Column([ft.Checkbox(label=d) for d in DEPTOS])
        
        # Esta función ya la tienes bien, mantenla así
        async def guardar(e):
            page.splash = ft.ProgressBar(); await page.update_async()
            loop = asyncio.get_event_loop()
            pedidos = await loop.run_in_executor(None, cargar_desde_sheets)
            
            estados = {ck.label: ck.value for ck in col_checks.controls}
            nuevos_pedidos = [p for p in pedidos if p["id"] != txt_id.value]
            
            if modo != "borrar":
                nuevos_pedidos.append({"id": txt_id.value, "estados": estados})
            
            await loop.run_in_executor(None, guardar_en_sheets, nuevos_pedidos)
            if modo != "borrar":
                await loop.run_in_executor(None, enviar_aviso_ventas, txt_id.value, estados)
            
            page.splash = None
            await vista_panel_admin()

        # Esta también está bien
        async def cargar_datos(e):
            loop = asyncio.get_event_loop()
            pedidos = await loop.run_in_executor(None, cargar_desde_sheets)
            p = next((p for p in pedidos if p["id"] == txt_id.value), None)
            if p:
                for ck in col_checks.controls:
                    ck.value = p["estados"].get(ck.label, False)
                await page.update_async()

        # --- EL CAMBIO: Función para volver ---
        async def volver(e):
            await vista_panel_admin()

        btn_confirmar = ft.ElevatedButton(
            "CONFIRMAR", 
            on_click=guardar, # Aquí NO lleva paréntesis porque Flet lo llama solo
            bgcolor="green" if modo != "borrar" else "red", 
            color="white", width=200
        )

        controles = [
            # Primero define la función para volver
        async def volver_al_panel(e):
            await vista_panel_admin()

        # Ahora arma la lista de controles sin el lambda
        controles = [
            ft.TextButton("< Volver", on_click=volver_al_panel), 
            ft.Text(modo.upper(), size=20, weight="bold"), 
            txt_id
        ]
        
        if modo == "editar": 
            controles.append(ft.ElevatedButton("Cargar Datos", on_click=cargar_datos))
        
        controles.append(col_checks)
        controles.append(btn_confirmar)
        
        await page.add_async(contenedor_principal(controles))
        )

        async def vista_visitante():
        await page.clean_async()
        txt_q = ft.TextField(label="Escriba su N° de Pedido", width=250, text_align="center")
        res = ft.Column()

        # Función para que el botón de volver funcione en la web
        async def volver_inicio(e):
            await mostrar_menu_principal()

        # Tu función buscar (que ya está muy bien)
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
                        ft.Icon(ft.icons.CHECK_CIRCLE if listo else ft.icons.RADIO_BUTTON_UNCHECKED, 
                                color="green" if listo else "red"),
                        ft.Text(d, size=16)
                    ]))
            else:
                res.controls.append(ft.Text("ID no encontrado", color="red"))
            await page.update_async()

        # Agregamos todo al contenedor principal
        await page.add_async(
            contenedor_principal([
                ft.TextButton("< Volver al Inicio", on_click=volver_inicio), # <--- CORREGIDO
                ft.Text("Consultar Pedido", size=24, weight="bold"),
                txt_q,
                ft.ElevatedButton("BUSCAR ESTADO", on_click=buscar, width=200, bgcolor="blue900", color="white"),
                res
            ])
        )

       # 1. Definimos la función para que el botón de volver responda
        async def volver_inicio(e):
            await mostrar_menu_principal()

        # 2. Ahora agregamos los controles usando esa función
        await page.add_async(
            contenedor_principal([
                # CAMBIO: Usamos volver_inicio en lugar de mostrar_menu_principal directamente
                ft.TextButton("< Volver", on_click=volver_inicio), 
                ft.Text("Consultar Estado", size=24, weight="bold"),
                txt_q,
                ft.ElevatedButton("BUSCAR", on_click=buscar, width=200),
                res
            ])
        )

    # 3. Este es el arranque de la app, está perfecto:
    await mostrar_menu_principal()

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_assets = os.path.join(ruta_actual, "assets")

# En lugar de montar con FastAPI, usamos el cargador directo de flet_fastapi
app = flet_fastapi.app(
    main, 
    assets_dir=ruta_assets,
    app_name="Tracking Dispromm",
    # Esto fuerza a que la conexión sea más fuerte
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("Tracking:app", host="0.0.0.0", port=port, reload=False)

























