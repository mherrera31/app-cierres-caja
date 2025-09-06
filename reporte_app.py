# reporte_app.py
# Para ejecutar esta app, corre en tu terminal: streamlit run reporte_app.py

import streamlit as st
import database  # Reutilizamos el 100% de nuestro archivo de base de datos
import pandas as pd
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Reportes de Cierre", layout="wide")
st.title("Panel de Reportes de Cierres Administrativos")

# --- Funciones Auxiliares para Renderizar Reportes ---
# Estas reemplazan la lógica de "poblar_tabs" de nuestro archivo Tkinter

def mostrar_reporte_denominaciones(titulo, data_dict):
    """Muestra la tabla de conteo de dinero (usado para Caja Inicial y Final)"""
    st.subheader(titulo)
    if not data_dict or not data_dict.get('detalle'):
        st.info("No hay datos de conteo registrados para este paso.")
        return

    detalle = data_dict.get('detalle', {})
    total = data_dict.get('total', 0)
    
    # Convertimos el dict en un DataFrame de Pandas para una vista bonita
    try:
        df = pd.DataFrame.from_dict(detalle, orient='index').reset_index()
        # Aseguramos el orden correcto de las columnas si existen
        column_names = ["Denominación", "Cantidad", "Subtotal"]
        df.columns = column_names[:len(df.columns)]
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        # Si falla el dataframe (ej. datos extraños), solo muestra el JSON
        st.json(detalle)
        st.error(f"Error al renderizar dataframe: {e}")
        
    st.metric(label=f"TOTAL CONTADO ({titulo})", value=f"${float(total):,.2f}")

def mostrar_reporte_verificacion(data_dict):
    """Muestra el reporte formateado de Verificación de Pagos"""
    st.subheader("Reporte de Verificación de Pagos")
    if not data_dict or (not data_dict.get('verificacion_con_match') and not data_dict.get('registros_informativos')):
        st.info("No hay datos de verificación guardados para este cierre.")
        return

    # Sección 1: Verificados con Match
    st.markdown("---")
    st.markdown("**Pagos Verificados (Match)**")
    verificados = data_dict.get('verificacion_con_match', [])
    if not verificados:
        st.markdown("*N/A*")
    
    for item in verificados:
        match_texto = "OK ✔️" if item.get('match_ok') else "FALLO ❌"
        
        st.markdown(f"**{item.get('metodo')}** (Fuente: *{item.get('fuente')}*)")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sistema", f"${item.get('total_sistema', 0):,.2f}")
        col2.metric("Total Reportado", f"${item.get('total_reportado', 0):,.2f}")
        col3.metric("Estado Match", f"{match_texto}")

        # Aquí manejamos el enlace de la foto (reemplaza a webbrowser.open)
        url_foto = item.get('url_foto')
        if url_foto:
            # st.markdown genera un hipervínculo HTML clickeable
            st.markdown(f"**[Ver Foto Adjunta]({url_foto})**", unsafe_allow_html=True)
        st.divider()


    # Sección 2: Informativos
    st.markdown("**Pagos Informativos (Sin Match)**")
    informativos = data_dict.get('registros_informativos', [])
    if not informativos:
        st.markdown("*N/A*")
    
    for item in informativos:
        st.markdown(f"**{item.get('metodo')}** (Fuente: *{item.get('fuente')}*)")
        st.metric("Total Sistema", f"${item.get('total_sistema', 0):,.2f}")
        st.divider()

def mostrar_reporte_gastos(cierre_id):
    """Obtiene y muestra la lista de gastos"""
    st.subheader("Reporte de Gastos")
    gastos_lista, err_g = database.obtener_gastos_del_cierre(cierre_id)
    
    if err_g:
        st.error(f"Error al cargar gastos: {err_g}")
    elif not gastos_lista:
        st.info("No se registraron gastos para este cierre.")
    else:
        total_gastos = 0
        df_data = []
        for gasto in gastos_lista:
            nombre_cat = gasto.get('gastos_categorias', {}).get('nombre', 'N/A') if gasto.get('gastos_categorias') else 'N/A'
            monto = gasto.get('monto', 0)
            total_gastos += monto
            df_data.append({
                "Categoría": nombre_cat,
                "Monto": monto,
                "Notas": gasto.get('notas')
            })
        
        st.dataframe(df_data, use_container_width=True)
        st.metric("TOTAL GASTOS", f"${total_gastos:,.2f}")

def comando_reabrir(cierre_id):
    """Llama a la DB para reabrir un cierre y refresca la app"""
    _, error = database.reabrir_cierre(cierre_id)
    if error:
        st.error(f"No se pudo reabrir el cierre: {error}")
    else:
        st.success(f"¡Cierre {cierre_id} reabierto con éxito!")
        # Limpia el caché para forzar la recarga de datos
        cargar_filtros_data.clear()
        st.rerun() # Refresca la página completa en Streamlit 8


# --- CARGA DE DATOS PARA FILTROS ---
# (Usamos @st.cache_data para que no cargue esto cada vez)

@st.cache_data(ttl=600) # Cache por 10 minutos
def cargar_filtros_data():
    sucursales_data, _ = database.obtener_sucursales()
    usuarios_data, _ = database.admin_get_lista_usuarios()
    return sucursales_data, usuarios_data

sucursales_db, usuarios_db = cargar_filtros_data()

# Formatear opciones para los selectbox
opciones_sucursal = {"TODAS": None}
for s in sucursales_db:
    opciones_sucursal[s['sucursal']] = s['id'] # Guardamos ID

opciones_usuario = {"TODOS": None}
for u in usuarios_db:
    opciones_usuario[u['nombre']] = u['id'] # Guardamos ID


# --- RENDERIZADO DE LA UI DE FILTROS ---
st.header("Filtros de Búsqueda")
col_filtros1, col_filtros2 = st.columns(2)

with col_filtros1:
    # Este es el reemplazo de los Entry de fecha. Es un calendario gráfico.
    # Si se dejan vacíos (None), la lógica de DB los ignora (como arreglamos).
    fecha_ini = st.date_input("Fecha Desde", value=None)
    sel_sucursal_nombre = st.selectbox("Sucursal", options=opciones_sucursal.keys())

with col_filtros2:
    fecha_fin = st.date_input("Fecha Hasta", value=None)
    sel_usuario_nombre = st.selectbox("Usuario", options=opciones_usuario.keys())

solo_disc = st.checkbox("Mostrar solo cierres con discrepancia inicial")

# Convertir de vuelta a IDs
sucursal_id_filtrar = opciones_sucursal[sel_sucursal_nombre]
usuario_id_filtrar = opciones_usuario[sel_usuario_nombre]


# --- LÓGICA DE BÚSQUEDA Y VISUALIZACIÓN DE RESULTADOS ---

if st.button("Buscar Cierres", type="primary"):
    
    # Validación de fechas (Streamlit usa objetos 'date', la DB espera 'YYYY-MM-DD' string)
    if fecha_ini and not fecha_fin:
        fecha_fin = datetime.now().date() # Default hasta hoy si solo ponen inicio
    if not fecha_ini and fecha_fin:
         st.error("Debe seleccionar una fecha de INICIO si selecciona una fecha de FIN.")
    else:
        # Convertir fechas a string si existen
        str_ini = fecha_ini.strftime("%Y-%m-%d") if fecha_ini else None
        str_fin = fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None
        
        # Llamar a nuestra función de DB existente
        cierres, error = database.admin_buscar_cierres_filtrados(
            fecha_inicio=str_ini,
            fecha_fin=str_fin,
            sucursal_id=sucursal_id_filtrar,
            usuario_id=usuario_id_filtrar,
            solo_discrepancia=solo_disc
        )
        
        if error:
            st.error(f"Error de Base de Datos: {error}")
        elif not cierres:
            st.warning("No se encontraron cierres que coincidan con esos filtros.")
        else:
            st.success(f"Se encontraron {len(cierres)} cierres.")
            
            # --- Mostrar Resultados ---
            # Usamos un "Expander" (acordeón) para cada cierre encontrado
            for cierre in cierres:
                user_nombre = cierre.get('perfiles', {}).get('nombre', 'N/A') if cierre.get('perfiles') else 'Usuario N/A'
                suc_nombre = cierre.get('sucursales', {}).get('sucursal', 'N/A') if cierre.get('sucursales') else 'Sucursal N/A'
                titulo_expander = f"📅 {cierre['fecha_operacion']}  |  👤 {user_nombre}  |  🏠 {suc_nombre}  |  ({cierre['estado']})"
                
                with st.expander(titulo_expander):
                    
                    # Crear las pestañas (Tabs) dentro del expander
                    tab_resumen, tab_inicial, tab_final, tab_verif, tab_gastos = st.tabs([
                        "Resumen", "Caja Inicial", "Caja Final", "Verificación", "Gastos"
                    ])

                    # --- Poblar Pestañas ---
                    
                    with tab_resumen:
                        st.subheader("Resumen del Cierre")
                        
                        # Botón para Reabrir (solo si está cerrado)
                        if cierre.get('estado') == 'CERRADO':
                            st.button(
                                "Reabrir este Cierre (Admin)", 
                                key=f"reabrir_{cierre['id']}", # Key única para el botón
                                on_click=comando_reabrir, 
                                args=(cierre['id'],),
                                type="secondary"
                            )
                        
                        st.markdown(f"**Discrepancia Inicial Detectada:** {'Sí' if cierre['discrepancia_saldo_inicial'] else 'No'}")
                        
                        # Usamos st.metric para mostrar los números clave
                        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                        # Nos aseguramos de convertir a float y manejar Nones
                        col_r1.metric("Saldo Inicial (Contado)", f"${float(cierre.get('saldo_inicial_efectivo') or 0):,.2f}")
                        col_r2.metric("Saldo Final (Contado)", f"${float(cierre.get('saldo_final_efectivo') or 0):,.2f}")
                        col_r3.metric("Total a Depositar", f"${float(cierre.get('total_a_depositar') or 0):,.2f}")
                        col_r4.metric("Saldo Día Siguiente", f"${float(cierre.get('saldo_para_siguiente_dia') or 0):,.2f}")

                    with tab_inicial:
                        mostrar_reporte_denominaciones("Detalle de Caja Inicial", cierre.get('saldo_inicial_detalle'))

                    with tab_final:
                        mostrar_reporte_denominaciones("Detalle de Caja Final", cierre.get('saldo_final_detalle'))

                    with tab_verif:
                        mostrar_reporte_verificacion(cierre.get('verificacion_pagos_detalle'))

                    with tab_gastos:
                        mostrar_reporte_gastos(cierre['id'])