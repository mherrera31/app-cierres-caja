# pages/6_Cierre_CDE.py
# VERSIÓN 7 (Lógica de Resumen y Verificación adaptada de 5_Cierre_de_Caja.py)

import streamlit as st
import sys
import os
import database
import pytz
from datetime import datetime
from decimal import Decimal
import tempfile 
import json

# --- BLOQUE DE CORRECCIÓN DE IMPORTPATH ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
# --- FIN DEL BLOQUE ---

# --- GUARDIÁN DE SEGURIDAD (ROL CDE / ADMIN) ---
rol_usuario = st.session_state.get("perfil", {}).get("rol")
if rol_usuario not in ['admin', 'cde']:
    st.error("Acceso denegado. 🚫 Esta sección es solo para roles CDE y Administradores.")
    st.stop() 
# ------------------------------------

# --- Constantes de Denominación ---
DENOMINACIONES = [
    {'nombre': 'Monedas de $0.01', 'valor': 0.01}, {'nombre': 'Monedas de $0.05', 'valor': 0.05},
    {'nombre': 'Monedas de $0.10', 'valor': 0.10}, {'nombre': 'Monedas de $0.25', 'valor': 0.25},
    {'nombre': 'Monedas de $0.50', 'valor': 0.50}, {'nombre': 'Monedas de $1', 'valor': 1.00},
    {'nombre': 'Billetes de $1', 'valor': 1.00}, {'nombre': 'Billetes de $5', 'valor': 5.00},
    {'nombre': 'Billetes de $10', 'valor': 10.00}, {'nombre': 'Billetes de $20', 'valor': 20.00},
    {'nombre': 'Billetes de $50', 'valor': 50.00}, {'nombre': 'Billetes de $100', 'valor': 100.00},
]
# ------------------------------------

st.set_page_config(page_title="Cierre CDE", layout="wide")
st.title("Módulo de Verificación de Cierre CDE 🏦")

# --- 1. SELECCIÓN DE SUCURSAL ---
@st.cache_data(ttl=600)
def cargar_sucursales_cde_data():
    sucursales_data, err = database.obtener_sucursales_cde()
    if err:
        st.error(f"No se pudieron cargar sucursales CDE: {err}")
        return {}
    return {s['sucursal']: s['id'] for s in sucursales_data}

opciones_sucursal_cde = cargar_sucursales_cde_data()
if not opciones_sucursal_cde:
    st.error("No se encontraron sucursales configuradas que terminen en 'CDE'.")
    st.stop()

lista_nombres_sucursales = ["--- Seleccione Sucursal CDE ---"] + list(opciones_sucursal_cde.keys())
sucursal_nombre_sel = st.selectbox("Sucursal CDE:", options=lista_nombres_sucursales)

if sucursal_nombre_sel == "--- Seleccione Sucursal CDE ---":
    st.info("Debe seleccionar una sucursal CDE para continuar.")
    st.stop()

sucursal_id_actual = opciones_sucursal_cde[sucursal_nombre_sel]
usuario_id_actual = st.session_state['perfil']['id']
tz_panama = pytz.timezone('America/Panama')
fecha_hoy_str = datetime.now(tz_panama).strftime('%Y-%m-%d')

st.header(f"Verificación para: {sucursal_nombre_sel} | Fecha: {fecha_hoy_str}")

if st.button("🔄 Refrescar Totales del Sistema (Pagos)"):
    cargar_totales_sistema.clear()
    st.success("Totales del sistema refrescados.")
    st.rerun()
st.divider()

# --- 2. CARGAR TOTALES DEL SISTEMA ---
@st.cache_data(ttl=60) 
def cargar_totales_sistema(fecha, sucursal_nombre):
    totales_metodos, total_efectivo, err = database.calcular_totales_pagos_dia_sucursal(fecha, sucursal_nombre)
    if err:
        st.error(f"Error fatal al calcular totales de pagos: {err}")
        st.stop()
    return totales_metodos, total_efectivo

totales_sistema_metodos_dict, total_sistema_efectivo = cargar_totales_sistema(fecha_hoy_str, sucursal_nombre_sel)

# --- 3. BUSCAR/CREAR CIERRE CDE ---
cierre_cde_actual, err_busqueda = database.buscar_cierre_cde_existente_hoy(fecha_hoy_str, sucursal_id_actual)
if err_busqueda:
    st.error(f"Error fatal al buscar cierre: {err_busqueda}")
    st.stop()

# --- 4. LÓGICA DE ESTADO ---
if cierre_cde_actual and cierre_cde_actual.get('estado') == 'CERRADO':
    st.success(f"El Cierre CDE para hoy ya fue FINALIZADO.")
    st.stop()

if not cierre_cde_actual:
    st.warning("No se ha iniciado el Cierre CDE para esta sucursal hoy.")
    st.metric("Total Efectivo (Sistema detectado)", f"${Decimal(total_sistema_efectivo):,.2f}")
    if st.button("▶️ Abrir Cierre de Verificación CDE", type="primary"):
        with st.spinner("Creando nuevo cierre CDE..."):
            _, err_crear = database.crear_nuevo_cierre_cde(fecha_hoy_str, sucursal_id_actual, usuario_id_actual)
        if err_crear:
            st.error(f"Error al crear cierre: {err_crear}")
        else:
            st.success("¡Cierre CDE creado! Recargando...")
            cargar_totales_sistema.clear() 
            st.rerun()
    st.stop() 

cierre_cde_id = cierre_cde_actual['id']

# --- 5. CARGAR DEPENDENCIAS DEL FORMULARIO ---
@st.cache_data(ttl=600)
def cargar_metodos_cde_activos():
    metodos, err = database.obtener_metodos_pago_cde()
    if err:
        st.error(f"Error cargando métodos CDE: {err}")
        return []
    return metodos

metodos_pago_cde_lista = cargar_metodos_cde_activos()
conteo_efectivo_guardado = cierre_cde_actual.get('detalle_conteo_efectivo') or {}
detalle_efectivo_guardado = conteo_efectivo_guardado.get('detalle', {})
verificacion_metodos_guardado = cierre_cde_actual.get('verificacion_metodos') or {}

# --- 6. FORMULARIO PRINCIPAL ---
st.subheader("Formulario de Conteo y Verificación Manual")
all_match_ok = True 
widget_data_files = {}

with st.form(key="form_conteo_cde"):
    tab_efectivo, tab_verificacion = st.tabs(["💵 Conteo de Efectivo", "💳 Verificación y Reportes"])

    with tab_efectivo:
        st.subheader("1. Conteo Físico de Efectivo")
        total_efectivo_sistema_guardado = Decimal(str(cierre_cde_actual.get('total_efectivo_sistema', 0.0)))
        st.metric("Total Efectivo del Sistema (Capturado al Abrir)", f"${total_efectivo_sistema_guardado:,.2f}")
        
        total_calculado_fisico = Decimal('0.00')
        inputs_conteo = {}
        for den in DENOMINACIONES:
            nombre = den['nombre']
            cantidad_guardada = detalle_efectivo_guardado.get(nombre, {}).get('cantidad', 0)
            cantidad = st.number_input(f"{nombre}:", min_value=0, step=1, value=cantidad_guardada, key=f"den_cde_{nombre}")
            inputs_conteo[nombre] = {"cantidad": cantidad, "valor": den['valor']}
            total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.header(f"Total Contado Físico: ${total_calculado_fisico:,.2f}")
        diferencia_efectivo = total_calculado_fisico - total_efectivo_sistema_guardado
        cash_match_ok = abs(diferencia_efectivo) < Decimal('0.01')
        if not cash_match_ok: all_match_ok = False 
        st.metric("DIFERENCIA DE EFECTIVO", f"${diferencia_efectivo:,.2f}", delta="CUADRADO" if cash_match_ok else "DESCUADRE", delta_color="normal" if cash_match_ok else "inverse")

    with tab_verificacion:
        st.subheader("2. Verificación Manual de Métodos")
        verificacion_json_output = {} 
        
        if not metodos_pago_cde_lista:
            st.warning("No hay métodos de pago configurados como 'is_cde = true' (excluyendo Efectivo).", icon="⚠️")
        
        for metodo in metodos_pago_cde_lista:
            nombre_metodo = metodo['nombre']
            total_sistema = Decimal(str(totales_sistema_metodos_dict.get(nombre_metodo, 0.0)))
            metodo_guardado_obj = verificacion_metodos_guardado.get(nombre_metodo, {})
            valor_manual_guardado = float(metodo_guardado_obj.get('total_manual', 0.0))
            url_foto_guardada = metodo_guardado_obj.get('url_foto')
            
            st.markdown(f"**Verificando: {nombre_metodo}**")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Sistema (Pagos)", f"${total_sistema:,.2f}")
            valor_manual = col_m2.number_input(f"Total Manual Reportado", min_value=0.0, step=0.01, format="%.2f", value=valor_manual_guardado, key=f"manual_{metodo['id']}")
            
            diferencia_metodo = Decimal(str(valor_manual)) - total_sistema
            metodo_match_ok = abs(diferencia_metodo) < Decimal('0.01')
            if not metodo_match_ok: all_match_ok = False 
            col_m3.metric("Diferencia", f"${diferencia_metodo:,.2f}", delta="OK" if metodo_match_ok else "FALLO", delta_color="normal" if metodo_match_ok else "inverse")
            
            if url_foto_guardada: st.markdown(f"✅ Foto Guardada: **[Ver Foto]({url_foto_guardada})**")
            file_uploader = st.file_uploader(f"Subir foto voucher {nombre_metodo} (Opcional)", type=["jpg", "jpeg", "png"], key=f"file_cde_{metodo['id']}")
            
            widget_data_files[nombre_metodo] = {"widget_obj": file_uploader, "url_guardada_previa": url_foto_guardada}
            verificacion_json_output[nombre_metodo] = {"total_manual": float(valor_manual), "total_sistema": float(total_sistema), "match_ok": metodo_match_ok, "url_foto": url_foto_guardada}
            st.divider()

    submitted = st.form_submit_button("Guardar Conteos y Fotos (Sin Finalizar)", type="secondary")

if submitted:
    datos_conteo_efectivo_dict = {"total": float(total_calculado_fisico), "detalle": {}}
    for nombre, data in inputs_conteo.items():
        if data['cantidad'] > 0:
            datos_conteo_efectivo_dict["detalle"][nombre] = {"cantidad": data['cantidad'], "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))}
    
    with st.spinner("Guardando datos y subiendo fotos..."):
        for nombre_metodo, data_widget in widget_data_files.items():
            archivo_subido = data_widget["widget_obj"]
            if archivo_subido:
                with tempfile.NamedTemporaryFile(delete=False, suffix=archivo_subido.name) as tmp_file:
                    tmp_file.write(archivo_subido.getvalue())
                    ruta_temporal = tmp_file.name
                url_publica, err_subida = database.subir_archivo_storage(cierre_cde_id, nombre_metodo, ruta_temporal)
                os.remove(ruta_temporal) 
                if err_subida: st.error(f"FALLO AL SUBIR FOTO para {nombre_metodo}: {err_subida}")
                else: verificacion_json_output[nombre_metodo]['url_foto'] = url_publica
        
        _, err_save = database.guardar_conteo_cde(cierre_cde_id, float(total_calculado_fisico), datos_conteo_efectivo_dict, verificacion_json_output)
        
    if err_save: st.error(f"Error al guardar: {err_save}")
    else:
        st.success("Conteos y fotos guardados con éxito.")
        cargar_totales_sistema.clear()
        st.rerun()
st.divider()

# --- 7. RESUMEN DE INGRESOS (ADAPTADO DEL REPORTE ADMIN) ---
st.subheader("Resumen de Ingresos del Día (Según lo guardado)")

total_efectivo_contado = Decimal(str(cierre_cde_actual.get('total_efectivo_contado', 0) or 0))
total_yappy = Decimal('0.0')
total_tarjeta_credito = Decimal('0.0')
total_tarjeta_debito = Decimal('0.0')

if verificacion_metodos_guardado:
    for metodo, data in verificacion_metodos_guardado.items():
        if isinstance(data, dict):
            m_lower = metodo.lower()
            total_manual = Decimal(str(data.get("total_manual", 0) or 0))
            if "yappy" in m_lower: total_yappy += total_manual
            elif "credito" in m_lower: total_tarjeta_credito += total_manual
            elif "debito" in m_lower or "clave" in m_lower: total_tarjeta_debito += total_manual

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Efectivo Contado", f"${total_efectivo_contado:,.2f}")
col2.metric("Total Yappy (Verificado)", f"${total_yappy:,.2f}")
col3.metric("Total Tarjeta Crédito (Verificado)", f"${total_tarjeta_credito:,.2f}")
col4.metric("Total Tarjeta Débito/Clave (Verificado)", f"${total_tarjeta_debito:,.2f}")
st.divider()

# --- 8. SECCIÓN DE FINALIZACIÓN ---
st.header("Finalización del Cierre CDE")
if all_match_ok: st.info("Todo cuadrado. El cierre puede ser finalizado.")
else: st.error("Existen discrepancias en Efectivo o en Métodos CDE. Revisa los conteos.")

if st.button("FINALIZAR CIERRE CDE", type="primary", disabled=not all_match_ok, key="btn_finalizar"):
    with st.spinner("Finalizando..."):
        _, err_final = database.finalizar_cierre_cde(cierre_cde_id, con_discrepancia=False)
    if err_final: st.error(f"Error: {err_final}")
    else:
        st.success("¡Cierre CDE Finalizado con Éxito!")
        st.balloons()
        cargar_totales_sistema.clear()
        st.rerun()

if not all_match_ok and rol_usuario == 'admin':
    st.warning("ADMIN: El cierre presenta un DESCUADRE. Puedes forzar la finalización.")
    if st.button("Forzar Cierre con Discrepancia (Admin)", key="btn_forzar"):
        with st.spinner("Forzando finalización..."):
            _, err_final = database.finalizar_cierre_cde(cierre_cde_id, con_discrepancia=True)
        if err_final: st.error(f"Error: {err_final}")
        else:
            st.success("¡Cierre CDE Finalizado (Forzado) con Éxito!")
            cargar_totales_sistema.clear()
            st.rerun()
