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

# 1. SELECCIÓN DE SUCURSAL
@st.cache_data(ttl=600)
def cargar_sucursales_data():
    sucursales_data, err = database.obtener_sucursales()
    if err:
        st.error(f"No se pudieron cargar sucursales: {err}")
        return {}
    return {s['sucursal']: s['id'] for s in sucursales_data}

opciones_sucursal = cargar_sucursales_data()
sucursal_nombre_sel = st.selectbox("Seleccione Sucursal:", options=list(opciones_sucursal.keys()))
sucursal_id_sel = opciones_sucursal[sucursal_nombre_sel]

st.divider()

# 2. FORMULARIO DE REGISTRO DIARIO (CON DISEÑO ORIGINAL)
st.header("Formulario de Registro")
fecha_operacion_sel = datetime.now(pytz.timezone('America/Panama')).strftime('%Y-%m-%d')

# Cargar último valor de 'Carga sin retirar' para referencia
historial_completo_para_ref, _ = database.get_registros_carga_rango(sucursal_id_sel)
ultimo_sin_retirar = 0.0
if historial_completo_para_ref:
    # Aseguramos que el historial esté ordenado por fecha para tomar el más reciente
    df_ref = pd.DataFrame(historial_completo_para_ref).sort_values(by='fecha_operacion', ascending=False)
    if not df_ref.empty:
        ultimo_sin_retirar = float(df_ref.iloc[0].get('carga_sin_retirar', 0))

with st.form(key="form_carga"):
    col1, col2, col3 = st.columns(3)
    input_retirada = col1.number_input("1. Carga Retirada ($):", min_value=0.0, step=0.01, format="%.2f")
    input_facturada = col2.number_input("2. Carga Facturada ($):", min_value=0.0, step=0.01, format="%.2f")
    input_sin_retirar = col3.number_input(
        "3. Carga Sin Retirar (Total Acum.) $:",
        min_value=0.0, step=0.01, format="%.2f",
        help=f"El último valor registrado fue ${ultimo_sin_retirar:,.2f}. Ingresa el nuevo total de hoy."
    )
    submit_carga = st.form_submit_button("Guardar Registro del Día", type="primary")

if submit_carga:
    datos_para_db = {
        "carga_facturada": input_facturada,
        "carga_retirada": input_retirada,
        "carga_sin_retirar": input_sin_retirar
    }
    _, err_upsert = database.upsert_registro_carga(
        fecha_operacion=fecha_operacion_sel,
        sucursal_id=sucursal_id_sel,
        usuario_id=usuario_id_actual,
        datos_carga=datos_para_db
    )
    if err_upsert:
        st.error(f"Error al guardar: {err_upsert}")
    else:
        st.success("¡Registro guardado con éxito!")
        st.cache_data.clear()
        st.rerun()

st.divider()

# 3. PANEL DE CONTROL EN VIVO
st.header("Panel de Control Acumulado (En Vivo)")
if not historial_completo_para_ref:
    st.info("Aún no hay registros históricos para esta sucursal.")
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
col_f1, col_f2 = st.columns(2)
filtro_fecha_desde = col_f1.date_input("Reporte Desde:", value=fecha_desde_def)
filtro_fecha_hasta = col_f2.date_input("Reporte Hasta:", value=fecha_hasta_def)

if st.button("Buscar Historial", key="btn_buscar_historial"):
    if filtro_fecha_desde > filtro_fecha_hasta:
        st.error("Error: La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
    else:
        historial_data, _ = database.get_registros_carga_rango(sucursal_id_sel, filtro_fecha_desde, filtro_fecha_hasta)
        st.session_state['historial_carga_df'] = pd.DataFrame(historial_data)

if 'historial_carga_df' in st.session_state and not st.session_state['historial_carga_df'].empty:
    df_original = st.session_state['historial_carga_df']
    st.info(f"Se encontraron {len(df_original)} registros. Puedes editar los valores directamente en la tabla.")

    df_editado = st.data_editor(
        df_original,
        column_config={
            "id": None, # Ocultar columna ID
            "fecha_operacion": st.column_config.DateColumn("Fecha", disabled=True),
            "carga_facturada": st.column_config.NumberColumn("Facturado ($)", format="%.2f"),
            "carga_retirada": st.column_config.NumberColumn("Retirado ($)", format="%.2f"),
            "carga_sin_retirar": st.column_config.NumberColumn("Sin Retirar (Acum.)", format="%.2f"),
            "perfiles": st.column_config.TextColumn("Usuario", disabled=True)
        },
        hide_index=True,
        key="editor_carga"
    )

    if st.button("Guardar Cambios", type="primary", disabled=(rol_usuario != 'admin')):
        cambios = []
        for index, row in df_editado.iterrows():
            original_row = df_original.iloc[index]
            if not row.equals(original_row):
                cambios.append((row['id'], {
                    'carga_facturada': row['carga_facturada'],
                    'carga_retirada': row['carga_retirada'],
                    'carga_sin_retirar': row['carga_sin_retirar']
                }))
        
        if not cambios:
            st.info("No se detectaron cambios para guardar.")
        else:
            with st.spinner(f"Guardando {len(cambios)} cambio(s)..."):
                errores = []
                for registro_id, datos in cambios:
                    _, err = database.admin_actualizar_registro_carga(registro_id, datos)
                    if err: errores.append(f"ID {registro_id}: {err}")
            
            if errores:
                st.error("Ocurrieron errores al guardar:")
                st.json(errores)
            else:
                st.success("¡Cambios guardados con éxito!")
                st.cache_data.clear()
                del st.session_state['historial_carga_df']
                st.rerun()

    if rol_usuario != 'admin':
        st.warning("La edición de registros históricos está deshabilitada. Solo los administradores pueden guardar cambios.")
