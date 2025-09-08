# pages/5_Gestion_Carga.py

import streamlit as st
import sys
import os
import database
import pytz
from datetime import datetime

# --- BLOQUE DE CORRECCIÓN DE IMPORTPATH ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
# --- FIN DEL BLOQUE ---


# --- GUARDIÁN DE SEGURIDAD (Permite a TODOS los logueados) ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop()
# ------------------------------------

# --- Lógica de la Página ---
st.set_page_config(page_title="Gestión de Carga", layout="centered")
st.title("Módulo de Gestión de Carga 🚚")
st.info("Este módulo es solo informativo y no afecta el Cierre de Caja.")

# IDs de Sesión
usuario_id_actual = st.session_state['perfil']['id']
rol_usuario = st.session_state['perfil']['rol']

# 1. SELECCIÓN DE SUCURSAL (Similar al Cierre de Caja)
@st.cache_data(ttl=600)
def cargar_sucursales_data():
    sucursales_data, err = database.obtener_sucursales()
    if err:
        st.error(f"No se pudieron cargar sucursales: {err}")
        return {}
    # Mapa de Nombre -> ID
    opciones = {s['sucursal']: s['id'] for s in sucursales_data}
    return opciones

opciones_sucursal = cargar_sucursales_data()
lista_nombres_sucursales = ["--- Seleccione Sucursal ---"] + list(opciones_sucursal.keys())

sucursal_nombre_sel = st.selectbox(
    "Sucursal de Trabajo:",
    options=lista_nombres_sucursales,
    index=0 
)

if sucursal_nombre_sel == "--- Seleccione Sucursal ---":
    st.warning("Debe seleccionar una sucursal para registrar o ver la carga.")
    st.stop()

sucursal_id_sel = opciones_sucursal[sucursal_nombre_sel]

st.divider()

# 2. SELECCIÓN DE FECHA (CON PERMISOS DE ADMIN)
tz_panama = pytz.timezone('America/Panama')
fecha_hoy_str = datetime.now(tz_panama).strftime('%Y-%m-%d')

fecha_operacion_sel = None

if rol_usuario == 'admin':
    st.markdown("**(Admin)** Puede seleccionar una fecha pasada para editarla.")
    # El admin puede seleccionar cualquier fecha
    fecha_dt = st.date_input("Fecha de Operación a Gestionar:", datetime.now(tz_panama).date())
    fecha_operacion_sel = fecha_dt.strftime('%Y-%m-%d')
else:
    # El usuario normal solo puede gestionar HOY
    st.subheader(f"Registrando para Hoy: {fecha_hoy_str}")
    fecha_operacion_sel = fecha_hoy_str

# 3. CARGAR DATOS EXISTENTES (SI HAY)
datos_existentes = None
if fecha_operacion_sel and sucursal_id_sel:
    with st.spinner("Buscando registros existentes..."):
        datos_existentes, err_get = database.get_registro_carga(fecha_operacion_sel, sucursal_id_sel)
        if err_get:
            st.error(f"Error cargando datos: {err_get}")
            st.stop()

# Valores por defecto (si no hay datos, usa 0.0)
val_facturada = float(datos_existentes['carga_facturada']) if datos_existentes else 0.0
val_retirada = float(datos_existentes['carga_retirada']) if datos_existentes else 0.0
val_sin_retirar = float(datos_existentes['carga_sin_retirar']) if datos_existentes else 0.0


# 4. FORMULARIO DE INGRESO (UPSERT)
st.header("Formulario de Registro")
with st.form(key="form_carga"):
    
    col1, col2, col3 = st.columns(3)
    
    # Usamos los valores cargados (o 0.0) como 'value'
    input_facturada = col1.number_input("1. Carga Facturada ($):", min_value=0.0, value=val_facturada, step=0.01, format="%.2f")
    input_retirada = col2.number_input("2. Carga Retirada ($):", min_value=0.0, value=val_retirada, step=0.01, format="%.2f")
    input_sin_retirar = col3.number_input("3. Carga Sin Retirar ($):", min_value=0.0, value=val_sin_retirar, step=0.01, format="%.2f")
    
    submit_carga = st.form_submit_button("Guardar Registro del Día", type="primary")

if submit_carga:
    datos_para_db = {
        "carga_facturada": input_facturada,
        "carga_retirada": input_retirada,
        "carga_sin_retirar": input_sin_retirar
    }
    
    with st.spinner("Guardando datos (Insertando o Actualizando)..."):
        _, err_upsert = database.upsert_registro_carga(
            fecha_operacion=fecha_operacion_sel,
            sucursal_id=sucursal_id_sel,
            usuario_id=usuario_id_actual,
            datos_carga=datos_para_db
        )
    
    if err_upsert:
        st.error(f"Error al guardar: {err_upsert}")
    else:
        st.success(f"¡Registro para el {fecha_operacion_sel} en {sucursal_nombre_sel} guardado con éxito!")
        # Actualizamos los valores de los reportes para que coincidan con lo guardado
        val_facturada = input_facturada
        val_retirada = input_retirada
        val_sin_retirar = input_sin_retirar


# 5. REPORTES (Basados en los valores actuales/guardados)
st.divider()
st.header("Reporte del Día Seleccionado")

# Cálculo 1: Ganancia
ganancia = val_facturada - val_retirada
# Cálculo 2: Ganancia Actual
ganancia_actual = ganancia - val_sin_retirar

col_r1, col_r2 = st.columns(2)
col_r1.metric(
    label="Ganancia (Facturado - Retirado)",
    value=f"${ganancia:,.2f}",
    delta_color="normal" if ganancia >= 0 else "inverse"
)
col_r2.metric(
    label="Ganancia Actual (Ganancia - Sin Retirar)",
    value=f"${ganancia_actual:,.2f}",
    delta_color="normal" if ganancia_actual >= 0 else "inverse"
)
