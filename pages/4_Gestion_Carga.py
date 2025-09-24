# pages/5_Gestion_Carga.py

import streamlit as st
import database
import pytz
from datetime import datetime, timedelta
import pandas as pd

# --- GUARDIÁN DE SEGURIDAD ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión.")
    st.stop()

# --- Lógica de la Página ---
st.set_page_config(page_title="Gestión de Carga", layout="wide")
st.title("Panel de Control y Gestión de Carga 🚚")

# --- IDs y Roles de Sesión ---
usuario_id_actual = st.session_state['perfil']['id']
rol_usuario = st.session_state['perfil']['rol']

# 1. SELECCIÓN DE SUCURSAL PARA VISTA RÁPIDA Y REGISTRO
@st.cache_data(ttl=600)
def cargar_sucursales_data():
    sucursales_data, err = database.obtener_sucursales()
    if err:
        st.error(f"No se pudieron cargar sucursales: {err}")
        return {}
    return {s['sucursal']: s['id'] for s in sucursales_data}

opciones_sucursal = cargar_sucursales_data()
sucursal_nombre_sel = st.selectbox(
    "Seleccione Sucursal (para registro y panel rápido):",
    options=list(opciones_sucursal.keys())
)
sucursal_id_sel = opciones_sucursal[sucursal_nombre_sel]

st.divider()

# 2. FORMULARIO Y PANEL EN VIVO (PARA SUCURSAL SELECCIONADA)
col_form, col_panel = st.columns([1, 2])

with col_form:
    st.header(f"Registro del Día")
    fecha_operacion_sel = datetime.now(pytz.timezone('America/Panama')).strftime('%Y-%m-%d')
    st.caption(f"Fecha de operación: {fecha_operacion_sel}")

    historial_completo_para_ref, _ = database.get_registros_carga_rango([sucursal_id_sel])
    ultimo_sin_retirar = 0.0
    if historial_completo_para_ref:
        df_ref = pd.DataFrame(historial_completo_para_ref).sort_values(by='fecha_operacion', ascending=False)
        if not df_ref.empty:
            ultimo_sin_retirar = float(df_ref.iloc[0].get('carga_sin_retirar', 0))

    with st.form(key="form_carga"):
        input_retirada = st.number_input("Carga Retirada (Hoy) $:", min_value=0.0, step=0.01, format="%.2f")
        input_facturada = st.number_input("Carga Facturada (Hoy) $:", min_value=0.0, step=0.01, format="%.2f")
        input_sin_retirar = st.number_input(
            f"Carga Sin Retirar (Total Acum.) $:", min_value=0.0, step=0.01, format="%.2f",
            help=f"El último valor registrado fue ${ultimo_sin_retirar:,.2f}. Ingresa el nuevo total de hoy."
        )
        submit_carga = st.form_submit_button("Guardar Registro del Día", type="primary")

    if submit_carga:
        datos_para_db = {"carga_facturada": input_facturada, "carga_retirada": input_retirada, "carga_sin_retirar": input_sin_retirar}
        _, err_upsert = database.upsert_registro_carga(
            fecha_operacion=fecha_operacion_sel, sucursal_id=sucursal_id_sel,
            usuario_id=usuario_id_actual, datos_carga=datos_para_db
        )
        if err_upsert: st.error(f"Error al guardar: {err_upsert}")
        else:
            st.success("¡Registro guardado con éxito!"); st.cache_data.clear(); st.rerun()

with col_panel:
    st.header(f"Panel de Control (Total Histórico - {sucursal_nombre_sel})")
    if not historial_completo_para_ref:
        st.info("Aún no hay registros para esta sucursal.")
    else:
        df = pd.DataFrame(historial_completo_para_ref)
        total_facturado_acumulado = pd.to_numeric(df['carga_facturada']).sum()
        total_retirado_acumulado = pd.to_numeric(df['carga_retirada']).sum()
        stock_actual_sin_retirar = pd.to_numeric(df.sort_values(by='fecha_operacion').iloc[-1]['carga_sin_retirar'])
        ganancia_bruta_acumulada = total_facturado_acumulado - total_retirado_acumulado
        ganancia_real_acumulada = ganancia_bruta_acumulada - stock_actual_sin_retirar
        
        col_p1, col_p2, col_p3 = st.columns(3)
        col_p1.metric("Total Facturado Histórico", f"${total_facturado_acumulado:,.2f}")
        col_p2.metric("Stock Actual (Carga Sin Retirar)", f"${stock_actual_sin_retirar:,.2f}")
        col_p3.metric("Ganancia REAL Acumulada", f"${ganancia_real_acumulada:,.2f}", delta_color="off")

st.divider()

# 3. REPORTE Y EDITOR HISTÓRICO
st.header("Reporte y Edición Histórica")
fecha_hasta_def = datetime.now(pytz.timezone('America/Panama')).date()
fecha_desde_def = fecha_hasta_def - timedelta(days=30)
col_f1, col_f2, col_f3 = st.columns(3)
filtro_fecha_desde = col_f1.date_input("Reporte Desde:", value=fecha_desde_def)
filtro_fecha_hasta = col_f2.date_input("Reporte Hasta:", value=fecha_hasta_def)

# NUEVO: Filtro Multi-Sucursal
nombres_sucursales = list(opciones_sucursal.keys())
sel_sucursales_reporte = col_f3.multiselect(
    "Filtrar por Sucursal(es):", 
    options=nombres_sucursales,
    default=[sucursal_nombre_sel] # Por defecto selecciona la de arriba
)

if st.button("Buscar Historial", key="btn_buscar_historial"):
    if not sel_sucursales_reporte:
        st.error("Debes seleccionar al menos una sucursal para el reporte.")
    elif filtro_fecha_desde > filtro_fecha_hasta:
        st.error("Error: La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
    else:
        ids_sucursales_filtrar = [opciones_sucursal[nombre] for nombre in sel_sucursales_reporte]
        with st.spinner("Buscando historial..."):
            historial_data, err_hist = database.get_registros_carga_rango(
                ids_sucursales_filtrar, 
                filtro_fecha_desde.strftime('%Y-%m-%d'), 
                filtro_fecha_hasta.strftime('%Y-%m-%d')
            )
        
        if err_hist: st.error(f"Error cargando historial: {err_hist}")
        elif not historial_data: st.warning("No se encontraron registros en ese rango de fechas para esta(s) sucursal(es).")
        else:
            df_data = []
            for fila in historial_data:
                df_data.append({
                    "id": fila['id'], "Fecha": fila['fecha_operacion'],
                    "Facturado": float(fila.get('carga_facturada', 0)),
                    "Retirado": float(fila.get('carga_retirada', 0)),
                    "Sin Retirar (Acum.)": float(fila.get('carga_sin_retirar', 0)),
                    "Usuario": fila.get('perfiles', {}).get('nombre', 'N/A') if fila.get('perfiles') else 'N/A',
                    "Sucursal": fila.get('sucursales', {}).get('sucursal', 'N/A') if fila.get('sucursales') else 'N/A'
                })
            st.session_state['historial_carga_df'] = pd.DataFrame(df_data)

if 'historial_carga_df' in st.session_state and not st.session_state['historial_carga_df'].empty:
    df_reporte = st.session_state['historial_carga_df']
    
    st.subheader("Totales del Rango y Sucursal(es) Seleccionada(s)")
    total_facturado_rango = df_reporte['Facturado'].sum()
    total_retirado_rango = df_reporte['Retirado'].sum()
    ganancia_bruta_rango = total_facturado_rango - total_retirado_rango
    
    # Para el stock, tomamos el máximo valor por sucursal dentro del rango y luego sumamos
    stock_final_rango = df_reporte.loc[df_reporte.groupby('Sucursal')['Fecha'].idxmax()]['Sin Retirar (Acum.)'].sum()
    ganancia_real_rango = ganancia_bruta_rango - stock_final_rango

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Total Facturado (en rango)", f"${total_facturado_rango:,.2f}")
    col_t2.metric("Stock al Final del Periodo", f"${stock_final_rango:,.2f}")
    col_t3.metric("Ganancia Real (en rango)", f"${ganancia_real_rango:,.2f}")
    st.divider()

    st.info(f"Se encontraron {len(df_reporte)} registros. Puedes editar los valores directamente en la tabla.")
    df_editado = st.data_editor(
        df_reporte,
        column_config={
            "id": None, "Fecha": st.column_config.DateColumn("Fecha", disabled=True),
            "Facturado": st.column_config.NumberColumn("Facturado ($)", format="%.2f"),
            "Retirado": st.column_config.NumberColumn("Retirado ($)", format="%.2f"),
            "Sin Retirar (Acum.)": st.column_config.NumberColumn("Sin Retirar (Acum.)", format="%.2f"),
            "Usuario": st.column_config.TextColumn("Usuario", disabled=True),
            "Sucursal": st.column_config.TextColumn("Sucursal", disabled=True),
        },
        hide_index=True, key="editor_carga"
    )

    if st.button("Guardar Cambios", type="primary", disabled=(rol_usuario != 'admin')):
        # Lógica de guardado
        pass # Tu lógica de guardado aquí

    if rol_usuario != 'admin':
        st.warning("La edición está deshabilitada. Solo los administradores pueden guardar cambios.")
