# pages/6_Cierre_CDE.py

import streamlit as st
import sys
import os
import database
import pytz
from datetime import datetime
from decimal import Decimal

# --- BLOQUE DE CORRECCIÓN DE IMPORTPATH ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
# --- FIN DEL BLOQUE ---

# --- GUARDIÁN DE SEGURIDAD (NUEVO ROL) ---
rol_usuario = st.session_state.get("perfil", {}).get("rol")
if rol_usuario not in ['admin', 'cde']:
    st.error("Acceso denegado. 🚫 Esta sección es solo para roles CDE y Administradores.")
    st.stop() 
# ------------------------------------

# --- Constantes de Denominación (Copiadas de 4_Cierre_de_Caja.py) ---
DENOMINACIONES = [
    {'nombre': 'Monedas de $0.01', 'valor': 0.01},
    {'nombre': 'Monedas de $0.05', 'valor': 0.05},
    {'nombre': 'Monedas de $0.10', 'valor': 0.10},
    {'nombre': 'Monedas de $0.25', 'valor': 0.25},
    {'nombre': 'Monedas de $0.50', 'valor': 0.50},
    {'nombre': 'Monedas de $1', 'valor': 1.00},
    {'nombre': 'Billetes de $1', 'valor': 1.00},
    {'nombre': 'Billetes de $5', 'valor': 5.00},
    {'nombre': 'Billetes de $10', 'valor': 10.00},
    {'nombre': 'Billetes de $20', 'valor': 20.00},
    {'nombre': 'Billetes de $50', 'valor': 50.00},
    {'nombre': 'Billetes de $100', 'valor': 100.00},
]
# ------------------------------------

st.set_page_config(page_title="Cierre CDE", layout="wide")
st.title("Módulo de Verificación de Cierre CDE 🏦")

# --- 1. SELECCIÓN DE SUCURSAL CDE ---
@st.cache_data(ttl=600)
def cargar_sucursales_cde_data():
    sucursales_data, err = database.obtener_sucursales_cde()
    if err:
        st.error(f"No se pudieron cargar sucursales CDE: {err}")
        return {}
    opciones = {s['sucursal']: s['id'] for s in sucursales_data}
    return opciones

opciones_sucursal_cde = cargar_sucursales_cde_data()
if not opciones_sucursal_cde:
    st.error("No se encontraron sucursales configuradas que terminen en 'CDE'.")
    st.stop()

lista_nombres_sucursales = ["--- Seleccione Sucursal CDE ---"] + list(opciones_sucursal_cde.keys())
sucursal_nombre_sel = st.selectbox(
    "Sucursal CDE:",
    options=lista_nombres_sucursales,
    index=0 
)

if sucursal_nombre_sel == "--- Seleccione Sucursal CDE ---":
    st.info("Debe seleccionar una sucursal CDE para continuar.")
    st.stop()

sucursal_id_actual = opciones_sucursal_cde[sucursal_nombre_sel]
usuario_id_actual = st.session_state['perfil']['id']
tz_panama = pytz.timezone('America/Panama')
fecha_hoy_str = datetime.now(tz_panama).strftime('%Y-%m-%d')

st.header(f"Verificación para: {sucursal_nombre_sel} | Fecha: {fecha_hoy_str}")
st.divider()

# --- 2. CARGAR TOTALES DEL SISTEMA (DE LA TABLA PAGOS) ---
@st.cache_data(ttl=60) # TTL corto (60 seg) para obtener datos casi en vivo
def cargar_totales_sistema(fecha, sucursal_nombre):
    totales_metodos, total_efectivo, err = database.calcular_totales_pagos_dia_sucursal(fecha, sucursal_nombre)
    if err:
        st.error(f"Error fatal al calcular totales de pagos: {err}")
        st.stop()
    return totales_metodos, total_efectivo

totales_sistema_metodos, total_sistema_efectivo = cargar_totales_sistema(fecha_hoy_str, sucursal_nombre_sel)

# --- 3. CARGAR O CREAR EL CIERRE CDE DE HOY ---
cierre_cde_actual, err_cierre = database.buscar_o_crear_cierre_cde(
    fecha_hoy_str, sucursal_id_actual, usuario_id_actual, total_sistema_efectivo
)

if err_cierre and err_cierre == "EXISTE_CERRADO":
    st.success(f"El Cierre CDE para {sucursal_nombre_sel} en la fecha {fecha_hoy_str} ya fue FINALIZADO.")
    st.subheader("Datos del Cierre Finalizado:")
    if cierre_cde_actual.get('discrepancia'):
        st.warning("Este cierre fue forzado por un Admin y presenta discrepancia.")
    # (Aquí puedes añadir más lógica para mostrar el reporte del día si lo deseas)
    st.stop()
elif err_cierre:
    st.error(f"Error fatal: {err_cierre}")
    st.stop()


cierre_cde_id = cierre_cde_actual['id']

# --- 4. CARGAR MÉTODOS CDE (PARA EL FORMULARIO) ---
@st.cache_data(ttl=600)
def cargar_metodos_cde_activos():
    metodos, err = database.obtener_metodos_pago_cde() # Esta función ya excluye 'Efectivo'
    if err:
        st.error(f"Error cargando métodos CDE: {err}")
        return []
    return metodos

metodos_pago_cde_lista = cargar_metodos_cde_activos()

# Cargar conteos guardados previamente (si existen)
conteo_efectivo_guardado = cierre_cde_actual.get('detalle_conteo_efectivo') or {}
detalle_efectivo_guardado = conteo_efectivo_guardado.get('detalle', {})
verificacion_metodos_guardado = cierre_cde_actual.get('verificacion_metodos') or {}


# --- 5. INTERFAZ DE CONTEO Y VERIFICACIÓN ---
st.subheader("Formulario de Conteo y Verificación Manual")

all_match_ok = True # Flag global de discrepancia

with st.form(key="form_conteo_cde"):

    tab_efectivo, tab_metodos = st.tabs(["💵 Conteo de Efectivo", "💳 Verificación de Métodos"])

    with tab_efectivo:
        st.subheader("1. Conteo Físico de Efectivo")
        st.metric("Total Efectivo del Sistema (Tabla Pagos)", f"${Decimal(total_sistema_efectivo):,.2f}")
        
        inputs_conteo = {}
        total_calculado_fisico = Decimal('0.00')
        
        st.markdown("**Monedas**")
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_efectivo_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(
                    label=f"Input_Final_{den['nombre']}", label_visibility="collapsed", 
                    min_value=0, step=1, value=cantidad_guardada, key=f"den_final_cde_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.markdown("**Billetes**")
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_efectivo_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(
                    label=f"Input_Final_{den['nombre']}", label_visibility="collapsed", 
                    min_value=0, step=1, value=cantidad_guardada, key=f"den_final_cde_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.divider()
        st.header(f"Total Contado Físico: ${total_calculado_fisico:,.2f}")

        # Cálculo de diferencia de efectivo
        diferencia_efectivo = total_calculado_fisico - Decimal(str(total_sistema_efectivo))
        cash_match_ok = abs(diferencia_efectivo) < Decimal('0.01')
        if not cash_match_ok:
            all_match_ok = False # Marcamos discrepancia global

        st.metric(
            label="DIFERENCIA DE EFECTIVO (Físico vs. Sistema)",
            value=f"${diferencia_efectivo:,.2f}",
            delta="CUADRADO" if cash_match_ok else "DESCUADRE",
            delta_color="normal" if cash_match_ok else "inverse"
        )
        

    with tab_metodos:
        st.subheader("2. Verificación Manual de Métodos CDE")
        
        verificacion_json_output = {} # Para guardar los inputs manuales
        
        if not metodos_pago_cde_lista:
            st.info("No hay métodos de pago configurados como 'is_cde = true' (excluyendo Efectivo).")
            
        for metodo in metodos_pago_cde_lista:
            nombre_metodo = metodo['nombre']
            # Obtener el total del sistema que calculamos antes
            total_sistema = totales_sistema_metodos.get(nombre_metodo, 0.0)
            
            st.markdown(f"**Verificando: {nombre_metodo}**")
            
            # Obtener el valor manual guardado (si existe)
            valor_manual_guardado = verificacion_metodos_guardado.get(nombre_metodo, 0.0)
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Sistema (Pagos)", f"${Decimal(str(total_sistema)):,.2f}")
            
            valor_manual = col_m2.number_input(
                f"Total Manual Reportado ({nombre_metodo})", 
                min_value=0.0, step=0.01, format="%.2f", 
                value=float(valor_manual_guardado),
                key=f"manual_{metodo['id']}"
            )
            
            diferencia_metodo = Decimal(str(valor_manual)) - Decimal(str(total_sistema))
            metodo_match_ok = abs(diferencia_metodo) < Decimal('0.01')
            
            if not metodo_match_ok:
                all_match_ok = False # Marcamos discrepancia global

            col_m3.metric(
                "Diferencia",
                f"${diferencia_metodo:,.2f}",
                delta="OK" if metodo_match_ok else "FALLO",
                delta_color="normal" if metodo_match_ok else "inverse"
            )
            
            # Guardamos el input manual para la DB
            verificacion_json_output[nombre_metodo] = valor_manual
            st.divider()

    
    submitted = st.form_submit_button("Guardar Conteos", type="secondary")

    if submitted:
        # Preparar el JSON de conteo de efectivo
        datos_conteo_efectivo_dict = {"total": float(total_calculado_fisico), "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                datos_conteo_efectivo_dict["detalle"][nombre] = {
                    "cantidad": data['cantidad'], 
                    "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                }
        
        with st.spinner("Guardando datos..."):
            _, err_save = database.guardar_conteo_cde(
                cierre_cde_id,
                float(total_calculado_fisico),
                datos_conteo_efectivo_dict,
                verificacion_json_output
            )
            
        if err_save:
            st.error(f"Error al guardar: {err_save}")
        else:
            st.success("Conteos guardados con éxito.")
            # Refrescamos el caché de los totales de sistema y recargamos
            cargar_totales_sistema.clear()
            st.rerun()

st.divider()

# --- 6. LÓGICA DE FINALIZACIÓN ---
st.header("Finalización del Cierre CDE")

if all_match_ok:
    st.info("Todo cuadrado. El cierre puede ser finalizado.")
else:
    st.error("Existen discrepancias en Efectivo o en Métodos de Pago. Revisa los conteos.")

# Botón de Finalizar (para todos, pero deshabilitado si hay discrepancia)
if st.button("FINALIZAR CIERRE CDE", type="primary", disabled=not all_match_ok):
    with st.spinner("Finalizando..."):
        _, err_final = database.finalizar_cierre_cde(cierre_cde_id, con_discrepancia=False)
    if err_final:
        st.error(f"Error: {err_final}")
    else:
        st.success("¡Cierre CDE Finalizado con Éxito!")
        st.balloons()
        cargar_totales_sistema.clear()
        st.rerun()

# Botón de Admin (solo visible para Admin, y solo si hay discrepancia)
if not all_match_ok and rol_usuario == 'admin':
    st.warning("ADMIN: El cierre presenta un DESCUADRE. Puedes forzar la finalización.")
    if st.button("Forzar Cierre con Discrepancia (Admin)"):
        with st.spinner("Forzando finalización..."):
            _, err_final = database.finalizar_cierre_cde(cierre_cde_id, con_discrepancia=True)
        if err_final:
            st.error(f"Error: {err_final}")
        else:
            st.success("¡Cierre CDE Finalizado (Forzado) con Éxito!")
            cargar_totales_sistema.clear()
            st.rerun()
