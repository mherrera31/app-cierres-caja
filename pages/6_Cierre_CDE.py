# pages/6_Cierre_CDE.py
# VERSIÓN 2 (Con flujo de "Abrir Cierre" y reporte de métodos No-CDE)

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

# --- Constantes de Denominación (Copiadas) ---
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
# (Cargamos esto una vez, independientemente del estado del cierre)
@st.cache_data(ttl=60) 
def cargar_totales_sistema(fecha, sucursal_nombre):
    totales_metodos, total_efectivo, err = database.calcular_totales_pagos_dia_sucursal(fecha, sucursal_nombre)
    if err:
        st.error(f"Error fatal al calcular totales de pagos: {err}")
        st.stop()
    return totales_metodos, total_efectivo

totales_sistema_metodos_dict, total_sistema_efectivo = cargar_totales_sistema(fecha_hoy_str, sucursal_nombre_sel)

# --- 3. BUSCAR ESTADO DEL CIERRE CDE (NUEVO FLUJO) ---
cierre_cde_actual, err_busqueda = database.buscar_cierre_cde_existente_hoy(fecha_hoy_str, sucursal_id_actual)

if err_busqueda:
    st.error(f"Error fatal al buscar cierre: {err_busqueda}")
    st.stop()

# --- 4. LÓGICA DE ESTADO ---

# CASO 1: Cierre ya está CERRADO
if cierre_cde_actual and cierre_cde_actual.get('estado') == 'CERRADO':
    st.success(f"El Cierre CDE para hoy ya fue FINALIZADO.")
    if cierre_cde_actual.get('discrepancia'):
        st.warning("Este cierre fue forzado por un Admin y presenta discrepancia.")
    # (Aquí puedes añadir un expander para mostrar los datos guardados si lo deseas)
    st.stop()

# CASO 2: NO existe cierre. Mostrar botón para CREAR.
if not cierre_cde_actual:
    st.warning("No se ha iniciado el Cierre CDE para esta sucursal hoy.")
    st.subheader("Totales de Sistema Detectados (Tabla Pagos):")
    st.metric("Total Efectivo (Sistema)", f"${Decimal(total_sistema_efectivo):,.2f}")
    
    if st.button("▶️ Abrir Cierre de Verificación CDE", type="primary"):
        with st.spinner("Creando nuevo cierre CDE..."):
            _, err_crear = database.crear_nuevo_cierre_cde(fecha_hoy_str, sucursal_id_actual, usuario_id_actual)
        if err_crear:
            st.error(f"Error al crear cierre: {err_crear}")
        else:
            st.success("¡Cierre CDE creado! Recargando...")
            cargar_totales_sistema.clear() # Limpiar caché de totales
            st.rerun()
    st.stop() # Detener el script hasta que abran el cierre

# CASO 3: El cierre está ABIERTO (cierre_cde_actual existe). Continuamos con la app.
cierre_cde_id = cierre_cde_actual['id']
    # --- AÑADIR ESTE BLOQUE NUEVO ---
if st.button("🔄 Refrescar Totales del Sistema (Pagos)", help="Haga clic aquí si han entrado nuevos pagos (Yappy, Tarjeta, etc.) después de que abrió esta página."):
    # Limpiamos el caché de la función que lee la tabla 'pagos'
    cargar_totales_sistema.clear()
    st.success("Totales del sistema refrescados.")
    st.rerun()
# --- FIN DEL BLOQUE NUEVO ---

# --- 5. CARGAR MÉTODOS CDE (PARA EL FORMULARIO) ---
@st.cache_data(ttl=600)
def cargar_metodos_cde_activos():
    metodos, err = database.obtener_metodos_pago_cde() # Esta función ya excluye 'Efectivo'
    if err:
        st.error(f"Error cargando métodos CDE: {err}")
        return []
    return metodos

@st.cache_data(ttl=600)
def cargar_metodos_NO_cde(totales_sistema_dict):
    metodos_no_cde, err = database.obtener_metodos_pago_NO_cde(totales_sistema_dict)
    if err:
        st.error(f"Error cargando métodos NO-CDE: {err}")
    return metodos_no_cde

metodos_pago_cde_lista = cargar_metodos_cde_activos()
metodos_informativos_lista = cargar_metodos_NO_cde(totales_sistema_metodos_dict)

# Cargar conteos guardados previamente (si existen)
conteo_efectivo_guardado = cierre_cde_actual.get('detalle_conteo_efectivo') or {}
detalle_efectivo_guardado = conteo_efectivo_guardado.get('detalle', {})
verificacion_metodos_guardado = cierre_cde_actual.get('verificacion_metodos') or {}


# --- 6. INTERFAZ DE CONTEO Y VERIFICACIÓN ---
st.subheader("Formulario de Conteo y Verificación Manual")
all_match_ok = True # Flag global de discrepancia

with st.form(key="form_conteo_cde"):

    tab_efectivo, tab_metodos_match, tab_metodos_info = st.tabs([
        "💵 Conteo de Efectivo", 
        "💳 Verificación CDE (Match)", 
        "ℹ️ Métodos Informativos (No-CDE)"
    ])

    with tab_efectivo:
        st.subheader("1. Conteo Físico de Efectivo")
        # El total de sistema ahora lo leemos desde el cierre guardado (se capturó al ABRIR)
        total_efectivo_sistema_guardado = cierre_cde_actual.get('total_efectivo_sistema', 0.0)
        st.metric("Total Efectivo del Sistema (Capturado al Abrir)", f"${Decimal(total_efectivo_sistema_guardado):,.2f}")
        
        inputs_conteo = {}
        total_calculado_fisico = Decimal('0.00')
        
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_efectivo_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(f"Input_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1, value=cantidad_guardada, key=f"den_final_cde_{den['nombre']}")
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.markdown("**Billetes**")
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_efectivo_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(f"Input_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1, value=cantidad_guardada, key=f"den_final_cde_{den['nombre']}")
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.divider()
        st.header(f"Total Contado Físico: ${total_calculado_fisico:,.2f}")

        # Cálculo de diferencia de efectivo
        diferencia_efectivo = total_calculado_fisico - Decimal(str(total_efectivo_sistema_guardado))
        cash_match_ok = abs(diferencia_efectivo) < Decimal('0.01')
        if not cash_match_ok:
            all_match_ok = False # Marcamos discrepancia global

        st.metric(
            label="DIFERENCIA DE EFECTIVO (Físico vs. Sistema)",
            value=f"${diferencia_efectivo:,.2f}",
            delta="CUADRADO" if cash_match_ok else "DESCUADRE",
            delta_color="normal" if cash_match_ok else "inverse"
        )
        

    with tab_metodos_match:
        st.subheader("2. Verificación Manual de Métodos CDE (Requerido para Match)")
        
        verificacion_json_output = {} # Para guardar los inputs manuales
        
        if not metodos_pago_cde_lista:
            st.info("No hay métodos de pago configurados como 'is_cde = true' (excluyendo Efectivo).")
            
        for metodo in metodos_pago_cde_lista:
            nombre_metodo = metodo['nombre']
            # Obtener el total del sistema que calculamos AL INICIO de la página
            total_sistema = totales_sistema_metodos_dict.get(nombre_metodo, 0.0)
            
            st.markdown(f"**Verificando: {nombre_metodo}**")
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
            
            verificacion_json_output[nombre_metodo] = valor_manual # Guardamos el input manual
            st.divider()

    with tab_metodos_info:
        st.subheader("3. Métodos Informativos (No-CDE que SÍ recibieron pagos hoy)")
        st.caption("Estos métodos no requieren 'Match' y no bloquean el cierre, solo se muestran para control.")
        
        if not metodos_informativos_lista:
            st.info("No se detectaron pagos en otros métodos (que no sean Efectivo ni CDE).")
        else:
            for metodo_info in metodos_informativos_lista:
                nombre = metodo_info['nombre']
                total = metodo_info['total']
                st.metric(f"{nombre} (Sistema)", f"${Decimal(str(total)):,.2f}")
                # Guardamos esto también en el JSON para el reporte
                verificacion_json_output[f"INFO_{nombre}"] = float(total)

    
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
                verificacion_json_output # Esto ahora contiene los manuales CDE Y los informativos
            )
            
        if err_save:
            st.error(f"Error al guardar: {err_save}")
        else:
            st.success("Conteos guardados con éxito.")
            cargar_totales_sistema.clear()
            st.rerun()

st.divider()

# --- 7. LÓGICA DE FINALIZACIÓN ---
st.header("Finalización del Cierre CDE")

if all_match_ok:
    st.info("Todo cuadrado. El cierre puede ser finalizado.")
else:
    st.error("Existen discrepancias en Efectivo o en Métodos CDE. Revisa los conteos.")

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
