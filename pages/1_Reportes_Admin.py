# pages/1_Reportes_Admin.py

import streamlit as st
import sys
import os
import database  # Esta importación ahora funcionará
import pandas as pd
from datetime import datetime

# --- BLOQUE DE CORRECCIÓN DE IMPORTPATH (VITAL) ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
# --- FIN DEL BLOQUE ---

# --- GUARDIÁN DE SEGURIDAD (AÑADIDO) ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop() 

if st.session_state.get("perfil", {}).get("rol") != 'admin':
    st.error("Acceso denegado. Esta sección es solo para administradores. 🔒")
    st.stop()
# ------------------------------------


# --- Configuración de la Página ---
st.set_page_config(page_title="Reportes de Cierre", layout="wide")
st.title("Panel de Reportes de Cierres Administrativos")

# --- Funciones Auxiliares para Renderizar Reportes ---

def mostrar_reporte_denominaciones(titulo, data_dict):
    st.subheader(titulo)
    if not data_dict or not data_dict.get('detalle'):
        st.info("No hay datos de conteo registrados para este paso.")
        return

    detalle = data_dict.get('detalle', {})
    total = data_dict.get('total', 0)
    
    try:
        df = pd.DataFrame.from_dict(detalle, orient='index').reset_index()
        column_names = ["Denominación", "Cantidad", "Subtotal"]
        df.columns = column_names[:len(df.columns)]
        # --- CORRECCIÓN DE ADVERTENCIA (width='stretch') ---
        st.dataframe(df, width='stretch', hide_index=True)
    except Exception as e:
        st.json(detalle)
        st.error(f"Error al renderizar dataframe: {e}")
        
    st.metric(label=f"TOTAL CONTADO ({titulo})", value=f"${float(total):,.2f}")

def mostrar_reporte_verificacion(data_dict):
    st.subheader("Reporte de Verificación de Pagos")
    if not data_dict or (not data_dict.get('verificacion_con_match') and not data_dict.get('registros_informativos')):
        st.info("No hay datos de verificación guardados para este cierre.")
        return

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

        url_foto = item.get('url_foto')
        if url_foto:
            st.markdown(f"**[Ver Foto Adjunta]({url_foto})**", unsafe_allow_html=True)
        st.divider()

    st.markdown("**Pagos Informativos (Sin Match)**")
    informativos = data_dict.get('registros_informativos', [])
    if not informativos:
        st.markdown("*N/A*")
    
    for item in informativos:
        st.markdown(f"**{item.get('metodo')}** (Fuente: *{item.get('fuente')}*)")
        st.metric(label=f"{item.get('metodo')} (Informativo)", value=f"${item.get('total_sistema', 0):,.2f}")
        st.divider()

def mostrar_reporte_gastos(cierre_id):
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
        
        # --- CORRECCIÓN DE ADVERTENCIA (width='stretch') ---
        st.dataframe(df_data, width='stretch')
        st.metric("TOTAL GASTOS", f"${total_gastos:,.2f}")

def comando_reabrir(cierre_id):
    _, error = database.reabrir_cierre(cierre_id)
    if error:
        st.error(f"No se pudo reabrir el cierre: {error}")
    else:
        st.success(f"¡Cierre {cierre_id} reabierto con éxito!")
        cargar_filtros_data.clear()
        st.rerun() 

@st.cache_data(ttl=600) 
def cargar_filtros_data():
    sucursales_data, _ = database.obtener_sucursales()
    usuarios_data, _ = database.admin_get_lista_usuarios()
    return sucursales_data, usuarios_data

sucursales_db, usuarios_db = cargar_filtros_data()

opciones_sucursal = {"TODAS": None}
if sucursales_db:
    for s in sucursales_db:
        opciones_sucursal[s['sucursal']] = s['id'] 

opciones_usuario = {"TODOS": None}
if usuarios_db:
    for u in usuarios_db:
        opciones_usuario[u['nombre']] = u['id'] 


st.header("Filtros de Búsqueda")
col_filtros1, col_filtros2 = st.columns(2)

with col_filtros1:
    fecha_ini = st.date_input("Fecha Desde", value=None)
    sel_sucursal_nombre = st.selectbox("Sucursal", options=opciones_sucursal.keys())

with col_filtros2:
    fecha_fin = st.date_input("Fecha Hasta", value=None)
    sel_usuario_nombre = st.selectbox("Usuario", options=opciones_usuario.keys())

solo_disc = st.checkbox("Mostrar solo cierres con discrepancia inicial")

sucursal_id_filtrar = opciones_sucursal[sel_sucursal_nombre]
usuario_id_filtrar = opciones_usuario[sel_usuario_nombre]

if st.button("Buscar Cierres", type="primary"):
    
    if fecha_ini and not fecha_fin:
        fecha_fin = datetime.now().date() 
    if not fecha_ini and fecha_fin:
         st.error("Debe seleccionar una fecha de INICIO si selecciona una fecha de FIN.")
    else:
        str_ini = fecha_ini.strftime("%Y-%m-%d") if fecha_ini else None
        str_fin = fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None
        
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
            
            for cierre in cierres:
                user_nombre = cierre.get('perfiles', {}).get('nombre', 'N/A') if cierre.get('perfiles') else 'Usuario N/A'
                suc_nombre = cierre.get('sucursales', {}).get('sucursal', 'N/A') if cierre.get('sucursales') else 'Sucursal N/A'
                titulo_expander = f"📅 {cierre['fecha_operacion']}  |  👤 {user_nombre}  |  🏠 {suc_nombre}  |  ({cierre['estado']})"
                
                with st.expander(titulo_expander):
                    
                    tab_resumen, tab_inicial, tab_final, tab_verif, tab_gastos = st.tabs([
                        "Resumen", "Caja Inicial", "Caja Final", "Verificación", "Gastos"
                    ])
                    
                    with tab_resumen:
                        st.subheader("Resumen del Cierre")
                        if cierre.get('estado') == 'CERRADO':
                            st.button(
                                "Reabrir este Cierre (Admin)", 
                                key=f"reabrir_{cierre['id']}", 
                                on_click=comando_reabrir, 
                                args=(cierre['id'],),
                                type="secondary"
                            )
                        st.markdown(f"**Discrepancia Inicial Detectada:** {'Sí' if cierre['discrepancia_saldo_inicial'] else 'No'}")
                        
                        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
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
