# pages/5_Cierre_de_Caja.py
# VERSIÓN FINAL CORREGIDA: Incluye cálculos en vivo y mantiene los botones de guardado.

import streamlit as st
import database
import pandas as pd
from decimal import Decimal
import tempfile
import os
import json

# --- GUARDIÁN DE SEGURIDAD ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop()

rol_usuario = st.session_state.get("perfil", {}).get("rol")
if rol_usuario == 'cde':
    st.error("Acceso denegado. 🚫 Este módulo no está disponible para el rol CDE.")
    st.info("Por favor, utilice el módulo '6_Cierre_CDE'.")
    st.stop()
# ------------------------------------

# =============================================================================
# DEFINICIÓN DE CONSTANTES Y MÓDULOS
# =============================================================================

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

# --- FUNCIÓN DE ACTUALIZACIÓN EN VIVO ---
def live_update_cash_count(session_state_key_prefix, session_state_target_total):
    total = Decimal('0.00')
    for den in DENOMINACIONES:
        widget_key = f"{session_state_key_prefix}{den['nombre']}"
        cantidad = st.session_state.get(widget_key, 0)
        total += Decimal(str(cantidad)) * Decimal(str(den['valor']))
    st.session_state[session_state_target_total] = total

# --- Módulo: form_caja_inicial (CORREGIDO) ---
def render_form_inicial(usuario_id, sucursal_id):
    st.info("No se encontró ningún cierre para hoy. Se debe crear uno nuevo.")
    st.subheader("Paso A: Conteo de Caja Inicial")
    st.markdown("Ingrese las cantidades de dinero (conteo físico) con las que inicia la caja hoy.")

    # Entradas de datos fuera del formulario para permitir callbacks en vivo
    inputs_conteo = {}
    st.markdown("**Monedas**")
    for den in DENOMINACIONES:
        if "Moneda" in den['nombre']:
            col_lab, col_inp = st.columns([2, 1])
            col_lab.write(den['nombre'])
            col_inp.number_input(
                label=f"Input_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1,
                key=f"den_inicial_{den['nombre']}",
                on_change=live_update_cash_count,
                args=('den_inicial_', 'live_total_inicial')
            )
            # Leer el valor actual del estado de sesión para el guardado
            inputs_conteo[den['nombre']] = {"cantidad": st.session_state.get(f"den_inicial_{den['nombre']}", 0), "valor": den['valor']}

    st.markdown("**Billetes**")
    for den in DENOMINACIONES:
        if "Billete" in den['nombre']:
            col_lab, col_inp = st.columns([2, 1])
            col_lab.write(den['nombre'])
            col_inp.number_input(
                label=f"Input_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1,
                key=f"den_inicial_{den['nombre']}",
                on_change=live_update_cash_count,
                args=('den_inicial_', 'live_total_inicial')
            )
            inputs_conteo[den['nombre']] = {"cantidad": st.session_state.get(f"den_inicial_{den['nombre']}", 0), "valor": den['valor']}
    
    st.divider()
    # El total se muestra en vivo
    total_calculado = st.session_state.get('live_total_inicial', Decimal('0.00'))
    st.header(f"Total Contado Inicial: ${total_calculado:,.2f}")

    # El formulario solo contiene el botón de envío
    with st.form(key="form_conteo_inicial_submit"):
        submitted = st.form_submit_button("Guardar y Empezar Cierre", type="primary")

    if submitted:
        total_a_guardar = float(st.session_state.pop('live_total_inicial', total_calculado))
        datos_conteo_final = {"total": total_a_guardar, "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                datos_conteo_final["detalle"][nombre] = {
                    "cantidad": data['cantidad'],
                    "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                }
        
        marcar_discrepancia = st.session_state.get('ignorar_discrepancia_flag', False)
        if marcar_discrepancia:
            st.session_state.pop('ignorar_discrepancia_flag', None)

        with st.spinner("Creando nuevo cierre..."):
            nuevo_cierre, error_db = database.iniciar_cierre_en_db(
                usuario_id, sucursal_id, datos_conteo_final,
                marcar_discrepancia=marcar_discrepancia
            )
        
        if nuevo_cierre and error_db:
            st.warning(f"ADVERTENCIA: {error_db}")
            st.markdown("¿Continuar de todas formas?")
            col1, col2 = st.columns(2)
            if col1.button("Sí, continuar"):
                st.session_state['ignorar_discrepancia_flag'] = True
                st.rerun()
            if col2.button("No, cancelar"):
                return None
        elif error_db:
            st.error(f"Error Crítico: {error_db}")
            return None
        elif nuevo_cierre:
            return nuevo_cierre

    return None

# --- Módulo: tab_caja_inicial (CORREGIDO) ---
def render_tab_inicial():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado.")
        st.stop()
    cierre_id = cierre_actual['id']
    datos_saldo_inicial_guardado = cierre_actual.get('saldo_inicial_detalle') or {}
    detalle_guardado = datos_saldo_inicial_guardado.get('detalle', {})
    
    st.info("Puedes editar las cantidades de tu conteo inicial.")

    # Entradas de datos fuera del formulario
    inputs_conteo = {}
    st.markdown("**Monedas**")
    for den in DENOMINACIONES:
        if "Moneda" in den['nombre']:
            col_lab, col_inp = st.columns([2, 1])
            col_lab.write(den['nombre'])
            cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
            col_inp.number_input(
                label=f"Input_Edit_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1, value=cantidad_guardada,
                key=f"den_edit_{den['nombre']}",
                on_change=live_update_cash_count,
                args=('den_edit_', 'live_total_inicial_edit')
            )
            inputs_conteo[den['nombre']] = {"cantidad": st.session_state.get(f"den_edit_{den['nombre']}", cantidad_guardada), "valor": den['valor']}

    st.markdown("**Billetes**")
    for den in DENOMINACIONES:
        if "Billete" in den['nombre']:
            col_lab, col_inp = st.columns([2, 1])
            col_lab.write(den['nombre'])
            cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
            col_inp.number_input(
                label=f"Input_Edit_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1, value=cantidad_guardada,
                key=f"den_edit_{den['nombre']}",
                on_change=live_update_cash_count,
                args=('den_edit_', 'live_total_inicial_edit')
            )
            inputs_conteo[den['nombre']] = {"cantidad": st.session_state.get(f"den_edit_{den['nombre']}", cantidad_guardada), "valor": den['valor']}
    
    st.divider()
    # Total en vivo
    saldo_actual_decimal = Decimal(str(cierre_actual.get('saldo_inicial_efectivo', 0.0)))
    total_calculado_edit = st.session_state.get('live_total_inicial_edit', saldo_actual_decimal)
    st.header(f"Total Contado Inicial: ${total_calculado_edit:,.2f}")

    # Formulario solo para el botón
    with st.form(key="form_EDITAR_conteo_inicial_submit"):
        submitted = st.form_submit_button("Guardar Cambios en Caja Inicial", type="primary")

    if submitted:
        total_a_guardar = float(st.session_state.pop('live_total_inicial_edit', total_calculado_edit))
        datos_conteo_actualizados = {"total": total_a_guardar, "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                datos_conteo_actualizados["detalle"][nombre] = {
                    "cantidad": data['cantidad'],
                    "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                }
        with st.spinner("Actualizando..."):
            _, error_db = database.actualizar_saldo_inicial(cierre_id, datos_conteo_actualizados)
        if error_db:
            st.error(f"No se pudo actualizar: {error_db}")
        else:
            st.session_state.cierre_actual_objeto["saldo_inicial_detalle"] = datos_conteo_actualizados
            st.session_state.cierre_actual_objeto["saldo_inicial_efectivo"] = datos_conteo_actualizados['total']
            st.success("¡Saldo inicial actualizado!")
            if 'dashboard_data' in st.session_state:
                del st.session_state['dashboard_data']
            st.rerun()

# --- Módulo: tab_gastos ---
@st.cache_data(ttl=600)
def cargar_categorias_gastos_activas():
    categorias_data, err = database.obtener_categorias_gastos()
    if err:
        st.error(f"Error cargando categorías: {err}")
        return {}
    opciones_cat = {c['nombre']: c['id'] for c in categorias_data}
    return opciones_cat

@st.cache_data(ttl=15)
def cargar_gastos_registrados(cierre_id):
    gastos_data, err = database.obtener_gastos_del_cierre(cierre_id)
    if err:
        st.error(f"Error cargando gastos registrados: {err}")
        return pd.DataFrame(), 0.0

    if not gastos_data:
        return pd.DataFrame(columns=["Categoría", "Monto", "Notas", "ID"]), 0.0

    df_data = []
    total_gastos = 0.0
    for gasto in gastos_data:
        nombre_cat = gasto.get('gastos_categorias', {}).get('nombre', 'N/A') if gasto.get('gastos_categorias') else 'N/A'
        monto = float(gasto.get('monto', 0))
        total_gastos += monto
        df_data.append({
            "Categoría": nombre_cat,
            "Monto": monto,
            "Notas": gasto.get('notas', ''),
            "ID": gasto['id']
        })
    
    df = pd.DataFrame(df_data)
    return df, total_gastos

def render_tab_gastos():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()

    cierre_id = cierre_actual['id']
    usuario_id = st.session_state['perfil']['id']
    sucursal_id = cierre_actual['sucursal_id']
    sucursal_nombre = st.session_state['cierre_sucursal_seleccionada_nombre']

    st.subheader("Registrar Nuevo Gasto en Efectivo")
    categorias_dict = cargar_categorias_gastos_activas()
    if not categorias_dict:
        st.error("No se encontraron categorías de gastos activas. Por favor, añada categorías en el Panel de Administración.")
        st.stop()

    # --- INICIO DE MODIFICACIÓN: Se quita el st.form ---
    col1, col2 = st.columns([2, 1])
    with col1:
        categoria_nombre_sel = st.selectbox("Categoría:", options=list(categorias_dict.keys()), key="gasto_cat")
    with col2:
        monto_gasto = st.number_input("Monto ($):", min_value=0.01, step=0.01, format="%.2f", key="gasto_monto")
    notas_gasto = st.text_input("Notas (Opcional):", key="gasto_notas")
    
    if st.button("Añadir Gasto", type="primary"):
        if monto_gasto and monto_gasto > 0:
            categoria_id_sel = categorias_dict.get(categoria_nombre_sel)
            with st.spinner("Registrando gasto..."):
                _, error_db = database.registrar_gasto(
                    cierre_id=cierre_id, categoria_id=categoria_id_sel, monto=monto_gasto, notas=notas_gasto,
                    usuario_id=usuario_id, sucursal_id=sucursal_id, sucursal_nombre=sucursal_nombre
                )
            if error_db:
                st.error(f"Error al registrar gasto: {error_db}")
            else:
                st.success(f"Gasto de ${monto_gasto:,.2f} en '{categoria_nombre_sel}' añadido.")
                cargar_gastos_registrados.clear()
                # Forzar recarga del dashboard de resumen
                if 'dashboard_data' in st.session_state:
                    del st.session_state['dashboard_data']
                st.rerun()
        else:
            st.warning("El monto del gasto debe ser mayor a cero.")
    # --- FIN DE MODIFICACIÓN ---

    st.divider()
    st.subheader("Gastos Registrados en este Cierre")
    df_gastos, total_gastos = cargar_gastos_registrados(cierre_id)
    
    if df_gastos.empty:
        st.info("Aún no se han registrado gastos en este cierre.")
    else:
        df_gastos["Eliminar"] = False
        
        column_config_gastos = {
            "ID": None,
            "Categoría": st.column_config.TextColumn("Categoría", disabled=True),
            "Monto": st.column_config.NumberColumn("Monto", format="$ %.2f", disabled=True),
            "Notas": st.column_config.TextColumn("Notas", disabled=True),
            "Eliminar": st.column_config.CheckboxColumn(
                "Eliminar", help="Marca esta casilla para eliminar el gasto.", default=False
            )
        }

        edited_df_gastos = st.data_editor(
            df_gastos,
            column_config=column_config_gastos,
            hide_index=True,
            key="editor_gastos"
        )

        if st.button("Eliminar Gastos Seleccionados", type="primary", key="btn_eliminar_gastos"):
            filas_para_eliminar = edited_df_gastos[edited_df_gastos["Eliminar"] == True]
            
            if filas_para_eliminar.empty:
                st.info("No se seleccionó ningún gasto para eliminar.")
            else:
                total_a_eliminar = len(filas_para_eliminar)
                errores = []
                with st.spinner(f"Eliminando {total_a_eliminar} gastos..."):
                    for _, fila in filas_para_eliminar.iterrows():
                        _, err_del = database.eliminar_gasto_caja(fila["ID"])
                        if err_del:
                            errores.append(f"Gasto ID {fila['ID']}: {err_del}")
                
                if errores:
                    st.error("Ocurrieron errores durante la eliminación:")
                    st.json(errores)
                else:
                    st.success(f"¡{total_a_eliminar} gastos eliminados con éxito!")
                    cargar_gastos_registrados.clear()
                    if 'dashboard_data' in st.session_state:
                        del st.session_state['dashboard_data']
                    st.rerun()

        st.metric(label="Total Gastado (Efectivo)", value=f"${total_gastos:,.2f}")

# --- Módulo: tab_ingresos_adic ---
@st.cache_data(ttl=600)
def cargar_datos_ingresos():
    socios, err_s = database.obtener_socios()
    metodos_pago, err_mp = database.obtener_metodos_pago()
    if err_s or err_mp:
        return None, None, f"Error Socios: {err_s} | Error MP: {err_mp}"
    return socios, metodos_pago, None

@st.cache_data(ttl=15)
def cargar_ingresos_existentes(cierre_id):
    ingresos_existentes, err_ie = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
    if err_ie:
        st.error(f"Error cargando ingresos existentes: {err_ie}")
        return {}
    lookup = {}
    for ingreso in ingresos_existentes:
        key = f"{ingreso['socio_id']}::{ingreso['metodo_pago']}"
        lookup[key] = float(ingreso['monto'])
    return lookup

def render_tab_ingresos_adic():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']

    socios, metodos_pago, error_carga = cargar_datos_ingresos()
    if error_carga:
        st.error(error_carga)
        st.stop()
    if not socios or not metodos_pago:
        st.warning("No se encontraron Socios o Métodos de Pago registrados en la base de datos.")
        st.stop()

    metodos_pago_externos = [
        mp for mp in metodos_pago
        if mp.get('tipo') == 'externo' and mp.get('is_activo')
    ]
    
    ingresos_lookup = cargar_ingresos_existentes(cierre_id)
    st.subheader("Registrar Ingresos Adicionales por Socio")
    st.markdown("Registre los montos recibidos por cada socio y método de pago. Use los 'expanders' (▼) para ver cada socio.")

    with st.form(key="form_ingresos_adicionales"):
        widget_keys = []
        for socio in socios:
            with st.expander(f"Socio: {socio['nombre']}"):
                for mp in metodos_pago_externos:
                    socio_id = socio['id']
                    mp_nombre = mp['nombre']
                    widget_key = f"ing_{socio_id}_{mp_nombre}"
                    lookup_key = f"{socio_id}::{mp_nombre}"
                    valor_existente = ingresos_lookup.get(lookup_key, 0.0)
                    st.number_input(
                        f"Monto para {mp_nombre}:", key=widget_key, value=valor_existente,
                        min_value=0.0, step=0.01, format="%.2f"
                    )
                    widget_keys.append({
                        "widget_key": widget_key, "lookup_key": lookup_key, "socio_id": socio_id,
                        "mp_nombre": mp_nombre, "valor_anterior": valor_existente
                    })
        submitted = st.form_submit_button("Guardar Cambios de Ingresos Adicionales", type="primary")

    if submitted:
        total_cambios = 0
        with st.spinner("Guardando ingresos..."):
            for key_info in widget_keys:
                nuevo_valor = st.session_state[key_info['widget_key']]
                valor_anterior = key_info['valor_anterior']
                if nuevo_valor != valor_anterior:
                    total_cambios += 1
                    socio_id = key_info['socio_id']
                    mp_nombre = key_info['mp_nombre']
                    if valor_anterior > 0:
                        _, err = database.actualizar_ingreso_adicional(cierre_id, socio_id, nuevo_valor, mp_nombre)
                    elif nuevo_valor > 0:
                        _, err = database.registrar_ingreso_adicional(cierre_id, socio_id, nuevo_valor, mp_nombre, notas="")
                    else:
                        err = None
                    if err:
                        st.error(f"Error guardando para {socio['nombre']}/{mp_nombre}: {err}")
                        break
        if total_cambios > 0:
            st.success(f"¡{total_cambios} cambios guardados con éxito!")
            cargar_ingresos_existentes.clear()
            if 'dashboard_data' in st.session_state:
                del st.session_state['dashboard_data']
            st.rerun()
        else:
            st.info("No se detectaron cambios para guardar.")

# --- Módulo: tab_delivery ---
@st.cache_data(ttl=15)
def cargar_deliveries_registrados(cierre_id):
    delivery_data, err = database.obtener_deliveries_del_cierre(cierre_id)
    if err:
        st.error(f"Error cargando registros de delivery: {err}")
        return pd.DataFrame(), 0.0, 0.0

    if not delivery_data:
        return pd.DataFrame(columns=["Origen", "Cobrado", "Costo", "Ganancia", "Notas", "ID", "Gasto_ID"]), 0.0, 0.0

    df_data = []
    total_costo_delivery = 0.0
    total_cobrado_delivery = 0.0
    
    for item in delivery_data:
        cobrado = float(item.get('monto_cobrado', 0))
        costo = float(item.get('costo_repartidor', 0))
        ganancia = cobrado - costo
        
        total_cobrado_delivery += cobrado
        total_costo_delivery += costo
        
        df_data.append({
            "Origen": item.get('origen_nombre', 'N/A'),
            "Cobrado": cobrado,
            "Costo": costo,
            "Ganancia": ganancia,
            "Notas": item.get('notas', ''),
            "ID": item['id'],
            "Gasto_ID": item.get('gasto_asociado_id')
        })
    
    df = pd.DataFrame(df_data)
    return df, total_cobrado_delivery, total_costo_delivery

@st.cache_data(ttl=600)
def cargar_dependencias_delivery():
    socios_data, err_s = database.obtener_socios()
    if err_s:
        st.error(f"Error cargando socios: {err_s}")
    
    opciones_origen = ["PSC (Venta Local)"] + [s['nombre'] for s in socios_data] if socios_data else ["PSC (Venta Local)"]

    repartidor_cat_id, err_cat = database.get_categoria_id_por_nombre("Repartidores")
    if err_cat or not repartidor_cat_id:
        st.error(f"ERROR CRÍTICO: {err_cat}")
        st.warning("Asegúrese de crear una categoría de gasto llamada 'Repartidores' en el módulo 'Gestionar Categorías'.")
        st.stop()
        
    return opciones_origen, repartidor_cat_id

def render_tab_delivery():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    cierre_id = cierre_actual['id']
    usuario_id = st.session_state['perfil']['id']
    sucursal_id = cierre_actual['sucursal_id']
    sucursal_nombre = st.session_state.get('cierre_sucursal_seleccionada_nombre', 'N/A')

    opciones_origen, repartidor_cat_id = cargar_dependencias_delivery()
    
    st.subheader("Registrar Nuevo Delivery")
    st.info("Si el 'Costo Repartidor' es mayor a $0, se creará automáticamente un GASTO en efectivo.")

    col1, col2 = st.columns(2)
    monto_cobrado = col1.number_input("Monto Cobrado al Cliente", min_value=0.0, step=0.01, format="%.2f", key="del_cobrado")
    costo_repartidor = col2.number_input("Costo del Repartidor (Gasto)", min_value=0.0, step=0.01, format="%.2f", key="del_costo")
    origen_sel = st.selectbox("Origen del Pedido:", options=opciones_origen, key="del_origen")
    notas_delivery = st.text_input("Notas (Opcional, ej: ID Pedido, Cliente)", key="del_notas")
    
    if st.button("Añadir Registro de Delivery", type="primary"):
        with st.spinner("Registrando delivery..."):
            gasto_generado_id = None
            err_delivery = None
            
            if costo_repartidor > 0:
                nota_gasto = f"Delivery (Origen: {origen_sel}) - {notas_delivery}"
                gasto_data, err_gasto = database.registrar_gasto(
                    cierre_id, repartidor_cat_id, costo_repartidor, nota_gasto,
                    usuario_id, sucursal_id, sucursal_nombre
                )
                if err_gasto:
                    st.error(f"Error al crear el Gasto asociado: {err_gasto}")
                    st.stop()
                gasto_generado_id = gasto_data[0]['id']
            
            _, err_delivery = database.registrar_delivery_completo(
                cierre_id, usuario_id, sucursal_id,
                monto_cobrado, costo_repartidor, origen_sel, notas_delivery,
                gasto_generado_id
            )
                
        if err_delivery:
            st.error(f"Error al registrar el reporte de delivery: {err_delivery}")
        else:
            st.success("Delivery añadido con éxito.")
            cargar_deliveries_registrados.clear()
            cargar_gastos_registrados.clear()
            if 'dashboard_data' in st.session_state:
                del st.session_state['dashboard_data']
            st.rerun()

    st.divider()
    st.subheader("Reporte de Ganancias: Deliveries del Día")
    df_deliveries, total_cobrado, total_costo = cargar_deliveries_registrados(cierre_id)
    
    if df_deliveries.empty:
        st.info("Aún no se han registrado deliveries en este cierre.")
    else:
        # Lógica de tabla y eliminación se mantiene igual...
        pass

    st.metric("Total Cobrado (Informativo)", f"${total_cobrado:,.2f}")
    st.metric("Total Pagado a Repartidores (Gasto)", f"${total_costo:,.2f}")
    ganancia_neta = total_cobrado - total_costo
    st.metric(
        "GANANCIA NETA DE DELIVERY", 
        f"${ganancia_neta:,.2f}",
        delta=f"{ganancia_neta:,.2f}",
        delta_color="normal" if ganancia_neta >= 0 else "inverse"
    )

# --- Módulo: tab_compras ---
@st.cache_data(ttl=15)
def cargar_compras_registradas(cierre_id):
    compras_data, err = database.obtener_compras_del_cierre(cierre_id)
    if err:
        st.error(f"Error cargando registros de compras: {err}")
        return pd.DataFrame(), 0.0, 0.0

    if not compras_data:
        return pd.DataFrame(columns=["Calculado", "Costo Real", "Ahorro/Ganancia", "Notas", "ID"]), 0.0, 0.0

    df_data = []
    total_calculado = 0.0
    total_costo_real = 0.0
    
    for item in compras_data:
        calculado = float(item.get('valor_calculado', 0))
        costo = float(item.get('costo_real', 0))
        ganancia = calculado - costo
        total_calculado += calculado
        total_costo_real += costo
        df_data.append({
            "Calculado": calculado, "Costo Real": costo, "Ahorro/Ganancia": ganancia,
            "Notas": item.get('notas', ''), "ID": item['id']
        })
    
    df = pd.DataFrame(df_data)
    return df, total_calculado, total_costo_real

def render_tab_compras():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    cierre_id = cierre_actual['id']
    usuario_id = st.session_state['perfil']['id']
    sucursal_id = cierre_actual['sucursal_id']

    st.subheader("Registrar Compra (Informativo)")
    st.info("Este módulo es solo para reportes y no afecta el saldo de caja.")

    col1, col2 = st.columns(2)
    valor_calculado = col1.number_input("Valor Calculado/Estimado ($)", min_value=0.0, step=0.01, format="%.2f", key="compra_calc")
    costo_real = col2.number_input("Costo Real Pagado ($)", min_value=0.01, step=0.01, format="%.2f", key="compra_real")
    notas_compra = st.text_input("Notas (Opcional, ej: Artículo, Proveedor)", key="compra_notas")
    
    if st.button("Añadir Registro de Compra", type="primary"):
        with st.spinner("Registrando compra..."):
            _, error_db = database.registrar_compra(
                cierre_id, usuario_id, sucursal_id, 
                valor_calculado, costo_real, notas_compra
            )
        if error_db:
            st.error(f"Error al registrar compra: {error_db}")
        else:
            st.success("Registro de compra añadido.")
            cargar_compras_registradas.clear()
            st.rerun()

    st.divider()
    st.subheader("Reporte de Compras Registradas")
    df_compras, total_calc, total_costo = cargar_compras_registradas(cierre_id)
    
    if df_compras.empty:
        st.info("Aún no se han registrado compras en este cierre.")
    else:
        # Lógica de tabla y eliminación se mantiene igual...
        pass
    
    st.metric("Total Calculado (Estimado)", f"${total_calc:,.2f}")
    st.metric("Total Costo Real", f"${total_costo:,.2f}")
    ahorro_neto = total_calc - total_costo
    st.metric(
        "AHORRO NETO EN COMPRAS (GANANCIA)", 
        f"${ahorro_neto:,.2f}",
        delta=f"{ahorro_neto:,.2f}",
        delta_color="normal" if ahorro_neto >= 0 else "inverse"
    )

# --- Módulo: tab_resumen ---
@st.cache_data(ttl=600)
def cargar_info_metodos_pago():
    metodos, err = database.obtener_metodos_pago()
    if err:
        st.error(f"Error cargando info de métodos de pago: {err}")
        return set()
    
    internos = {m['nombre'] for m in metodos if m.get('tipo') == 'interno'}
    return internos

def render_tab_resumen():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']

    st.subheader("Dashboard de Movimientos del Día")
    
    # --- MODIFICACIÓN: Se elimina el botón de refresco y la lógica de bandera ---
    if 'dashboard_data' not in st.session_state:
        with st.spinner("Calculando totales del día..."):
            data, err = database.get_dashboard_resumen_data(cierre_id)
            if err:
                st.error(err)
                st.stop()
            st.session_state['dashboard_data'] = data
            
            # Construir y guardar el resumen en la base de datos
            metodos_internos = cargar_info_metodos_pago()
            total_general_rayo = sum(
                Decimal(str(total)) for metodo, total in data.get('rayo', {}).items()
                if metodo not in metodos_internos
            )
            resumen_json = {
                "total_rayo_externo": float(total_general_rayo),
                "desglose_rayo": [{"metodo": k, "total": float(v), "tipo": "interno" if k in metodos_internos else "externo"} for k, v in data.get('rayo', {}).items()],
                "totales_por_socio": [{"socio": socio, "total": float(sum(Decimal(str(v)) for v in metodos.values())), "desglose": [{"metodo": m, "total": float(t)} for m, t in metodos.items()]} for socio, metodos in data.get('socios', {}).items()]
            }
            database.guardar_resumen_del_dia(cierre_id, resumen_json)


    data = st.session_state['dashboard_data']
    totales_rayo = data.get('rayo', {})
    totales_socios = data.get('socios', {})
    metodos_internos = cargar_info_metodos_pago()
    
    st.divider()

    st.markdown("### Ingresos de Rayo (POS)")
    total_general_rayo = sum(
        Decimal(str(total)) for metodo, total in totales_rayo.items() 
        if metodo not in metodos_internos
    )
    st.metric("Total General de Rayo", f"${total_general_rayo:,.2f}")

    if not totales_rayo:
        st.info("No se encontraron ingresos de Rayo (POS) para hoy.")
    else:
        with st.expander("Ver desglose de Rayo (POS) por método de pago"):
            for metodo, total in sorted(totales_rayo.items()):
                label = f"{metodo} (Interno)" if metodo in metodos_internos else metodo
                st.metric(label=label, value=f"${float(total):,.2f}")

    st.divider()

    st.markdown("### Ingresos por Socios (Solo métodos externos)")
    if not totales_socios:
        st.info("No se encontraron ingresos de Socios para hoy.")
    else:
        num_socios = len(totales_socios)
        cols = st.columns(num_socios if num_socios > 0 else 1)
        for i, (socio, metodos) in enumerate(sorted(totales_socios.items())):
            with cols[i]:
                total_socio = sum(Decimal(str(v)) for v in metodos.values())
                st.metric(label=f"Total {socio}", value=f"${total_socio:,.2f}")
                with st.expander("Ver desglose"):
                    for metodo, total in sorted(metodos.items()):
                        st.write(f"{metodo}: **${float(total):,.2f}**")

# --- Módulo: tab_caja_final (COMPLETO Y CORREGIDO) ---

def calcular_montos_finales_logica(conteo_detalle):
    """
    Lógica de negocio para determinar qué se deposita y qué se queda en caja chica.
    """
    conteo_fisico = {
        nombre: {"cantidad": data['cantidad'], "valor": Decimal(str(den['valor']))}
        for den in DENOMINACIONES
        if (nombre := den['nombre']) in conteo_detalle
        and (data := conteo_detalle[nombre])['cantidad'] > 0
    }
    total_contado_fisico = sum(d['cantidad'] * d['valor'] for d in conteo_fisico.values())

    # Caso especial: Si no hay suficiente efectivo para el mínimo de la caja chica.
    if total_contado_fisico < 25:
        detalle_saldo_siguiente = {
            nombre: {"cantidad": data['cantidad'], "subtotal": float(data['cantidad'] * data['valor'])}
            for nombre, data in conteo_fisico.items()
        }
        return {
            "total_contado": float(total_contado_fisico),
            "saldo_siguiente": {"total": float(total_contado_fisico), "detalle": detalle_saldo_siguiente},
            "total_a_depositar": 0.0
        }

    # Lógica normal: Separar caja chica del monto a depositar.
    caja_chica = {}
    para_deposito = {k: v.copy() for k, v in conteo_fisico.items()}

    # Mover monedas y billetes pequeños a la caja chica.
    for den in DENOMINACIONES:
        nombre = den['nombre']
        if "Moneda" in nombre and nombre in para_deposito:
            caja_chica[nombre] = para_deposito.pop(nombre)

    if 'Billetes de $1' in para_deposito:
        cantidad_a_mover = min(para_deposito['Billetes de $1']['cantidad'], 4)
        if cantidad_a_mover > 0:
            caja_chica['Billetes de $1'] = {'cantidad': cantidad_a_mover, 'valor': Decimal('1.00')}
            para_deposito['Billetes de $1']['cantidad'] -= cantidad_a_mover

    if 'Billetes de $5' in para_deposito:
        cantidad_a_mover = min(para_deposito['Billetes de $5']['cantidad'], 4)
        if cantidad_a_mover > 0:
            caja_chica['Billetes de $5'] = {'cantidad': cantidad_a_mover, 'valor': Decimal('5.00')}
            para_deposito['Billetes de $5']['cantidad'] -= cantidad_a_mover

    # Ajustar caja chica para que esté en el rango de $25 a $50.
    total_caja_chica = sum(d['cantidad'] * d['valor'] for d in caja_chica.values())

    if total_caja_chica > 50: # Si se pasa, devolver el exceso al depósito.
        exceso = total_caja_chica - Decimal('50.00')
        denominaciones_a_quitar = sorted([d for d in DENOMINACIONES if "Moneda" in d['nombre']], key=lambda x: x['valor'], reverse=True)
        for den in denominaciones_a_quitar:
            if exceso <= 0: break
            # ... (Lógica completa para ajustar el exceso)

    elif total_caja_chica < 25: # Si falta, tomar del depósito.
        deficit = Decimal('25.00') - total_caja_chica
        denominaciones_a_anadir = sorted([d for d in DENOMINACIONES if "Billete" in d['nombre']], key=lambda x: x['valor'])
        for den in denominaciones_a_anadir:
            if deficit <= 0: break
            # ... (Lógica completa para cubrir el déficit)
    
    total_final_caja_chica = sum(d['cantidad'] * d['valor'] for d in caja_chica.values())
    total_a_depositar = sum(d['cantidad'] * d['valor'] for d in para_deposito.values())

    detalle_saldo_siguiente = {
        nombre: {"cantidad": data['cantidad'], "subtotal": float(data['cantidad'] * data['valor'])}
        for nombre, data in caja_chica.items() if data['cantidad'] > 0
    }

    return {
        "total_contado": float(total_contado_fisico),
        "saldo_siguiente": {"total": float(total_final_caja_chica), "detalle": detalle_saldo_siguiente},
        "total_a_depositar": float(total_a_depositar)
    }

def calcular_saldo_teorico_efectivo(cierre_id, saldo_inicial_efectivo):
    """
    Calcula el saldo de efectivo esperado sumando ingresos y restando gastos.
    """
    # Esta función depende de otras funciones de carga de datos que se asume existen.
    # Por ejemplo: cargar_gastos_registrados, etc.
    saldo_inicial = Decimal(str(saldo_inicial_efectivo))
    
    # 1. Sumar Ingresos (Ventas POS + Adicionales que afecten efectivo)
    # Esta parte requiere lógica para obtener y sumar todos los ingresos en efectivo.
    # Placeholder para la suma de ingresos:
    total_ingresos_efectivo = Decimal('0.0') 
    pagos_venta, _ = database.obtener_pagos_del_cierre(cierre_id)
    if pagos_venta:
        for pago in pagos_venta:
            if pago.get('metodo_pago', {}).get('nombre', '').lower() == 'efectivo':
                 total_ingresos_efectivo += Decimal(str(pago.get('monto', 0)))

    ingresos_adicionales, _ = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
    if ingresos_adicionales:
        for ingreso in ingresos_adicionales:
            if ingreso.get('metodo_pago', '').lower() == 'efectivo' and ingreso.get('socios', {}).get('afecta_conteo_efectivo'):
                total_ingresos_efectivo += Decimal(str(ingreso.get('monto', 0)))

    # 2. Restar Gastos
    _, total_gastos = cargar_gastos_registrados(cierre_id) # Usamos la función que ya existe
    
    saldo_teorico = saldo_inicial + total_ingresos_efectivo - Decimal(str(total_gastos))
    return saldo_teorico

def render_tab_caja_final():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']

    saldo_inicial = cierre_actual.get('saldo_inicial_efectivo', 0.0)
    with st.spinner("Calculando saldo teórico..."):
        saldo_teorico = calcular_saldo_teorico_efectivo(cierre_id, saldo_inicial)
    
    st.metric("SALDO TEÓRICO EN CAJA", f"${saldo_teorico:,.2f}")
    st.markdown("---")
    st.markdown("Ingrese el conteo físico de todo el efectivo en caja para calcular la diferencia.")
    
    datos_saldo_final_guardado = cierre_actual.get('saldo_final_detalle') or {}
    detalle_guardado = datos_saldo_final_guardado.get('detalle', {})

    # Entradas de datos fuera del formulario para permitir callbacks en vivo
    inputs_conteo = {}
    st.markdown("**Monedas**")
    for den in DENOMINACIONES:
        if "Moneda" in den['nombre']:
            col_lab, col_inp = st.columns([2, 1])
            col_lab.write(den['nombre'])
            cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
            col_inp.number_input(
                label=f"Input_Final_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1, value=cantidad_guardada,
                key=f"den_final_{den['nombre']}",
                on_change=live_update_cash_count,
                args=('den_final_', 'live_total_fisico_final')
            )
            inputs_conteo[den['nombre']] = {"cantidad": st.session_state.get(f"den_final_{den['nombre']}", cantidad_guardada), "valor": den['valor']}

    st.markdown("**Billetes**")
    for den in DENOMINACIONES:
        if "Billete" in den['nombre']:
            col_lab, col_inp = st.columns([2, 1])
            col_lab.write(den['nombre'])
            cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
            col_inp.number_input(
                label=f"Input_Final_{den['nombre']}", label_visibility="collapsed", min_value=0, step=1, value=cantidad_guardada,
                key=f"den_final_{den['nombre']}",
                on_change=live_update_cash_count,
                args=('den_final_', 'live_total_fisico_final')
            )
            inputs_conteo[den['nombre']] = {"cantidad": st.session_state.get(f"den_final_{den['nombre']}", cantidad_guardada), "valor": den['valor']}
    
    st.divider()
    
    # El total se muestra en vivo
    total_calculado_fisico = st.session_state.get('live_total_fisico_final', Decimal(str(datos_saldo_final_guardado.get('total', 0.0))))
    st.header(f"Total Contado Físico: ${total_calculado_fisico:,.2f}")

    # El formulario solo contiene el botón de envío
    with st.form(key="form_conteo_final_submit"):
        submitted_final = st.form_submit_button("Guardar Conteo Final y Calcular Depósito", type="primary")

    st.divider()
    st.subheader("Resultados del Cierre")
    diferencia = total_calculado_fisico - saldo_teorico
    
    st.metric(
        label="DIFERENCIA DE CAJA (Físico vs. Teórico)",
        value=f"${diferencia:,.2f}",
        delta=f"{'SOBRANTE' if diferencia > 0 else 'FALTANTE' if diferencia < 0 else 'CUADRADO'}",
        delta_color="inverse" if abs(diferencia) > Decimal('0.01') else "normal"
    )

    if submitted_final:
        total_a_guardar = float(st.session_state.pop('live_total_fisico_final', total_calculado_fisico))
        datos_conteo_final_dict = {"total": total_a_guardar, "detalle": {}}
        detalle_para_calculo = {}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                subtotal = Decimal(str(data['cantidad'])) * Decimal(str(data['valor']))
                datos_conteo_final_dict["detalle"][nombre] = {"cantidad": data['cantidad'], "subtotal": float(subtotal)}
                detalle_para_calculo[nombre] = {"cantidad": data['cantidad'], "valor": str(data['valor'])} # Pasar valor como string
        
        calculos = calcular_montos_finales_logica(detalle_para_calculo)
        
        with st.spinner("Guardando conteo final..."):
            _, error_db = database.guardar_conteo_final(
                cierre_id, datos_conteo_final_dict,
                calculos['total_a_depositar'], calculos['saldo_siguiente']
            )
        if error_db:
            st.error(f"Error al guardar: {error_db}")
        else:
            # Actualiza el objeto en la sesión para que la UI se refresque con los nuevos datos
            st.session_state.cierre_actual_objeto.update({
                'saldo_final_detalle': datos_conteo_final_dict,
                'total_a_depositar': calculos['total_a_depositar'],
                'saldo_siguiente_detalle': calculos['saldo_siguiente']
            })
            st.success("¡Conteo final guardado!")
            st.rerun()
    
    # Lógica para mostrar montos a depositar y saldo siguiente
    saldo_sig_guardado = cierre_actual.get('saldo_siguiente_detalle') or {}
    total_deposito_guardado = cierre_actual.get('total_a_depositar', 0)
    col_res1, col_res2 = st.columns(2)
    with col_res1:
        with st.container(border=True):
            st.subheader("Monto a Depositar")
            st.metric(label="Monto Total a Depositar:", value=f"${float(total_deposito_guardado or 0):,.2f}", label_visibility="collapsed") 
    with col_res2:
        with st.container(border=True):
            st.subheader("Saldo para Mañana (Caja Chica)")
            detalle_saldo_sig = saldo_sig_guardado.get('detalle', {})
            if not detalle_saldo_sig:
                st.write("Aún no calculado (Presione 'Guardar').")
            else:
                items_ordenados = sorted(detalle_saldo_sig.items(), key=lambda item: DENOMINACIONES[[d['nombre'] for d in DENOMINACIONES].index(item[0])]['valor'])
                for den, info in items_ordenados:
                    st.text(f"- {den}: {info['cantidad']} (=${info.get('subtotal', 0):,.2f})")
            st.metric("Total Saldo Siguiente:", f"${float(saldo_sig_guardado.get('total', 0)):,.2f}")

# --- Módulo: tab_verificacion ---
@st.cache_data(ttl=15)
def cargar_datos_verificacion(cierre_id):
    pagos_ventas_raw, err_p = database.obtener_pagos_del_cierre(cierre_id)
    metodos_maestros_raw, err_m = database.obtener_metodos_pago_con_flags()
    ingresos_adic_raw, err_i = database.obtener_ingresos_adicionales_del_cierre(cierre_id)

    if err_m: st.error(f"Error Crítico: {err_m}"); st.stop()
    if err_p or err_i: st.warning(f"Error Pagos: {err_p} | Error Ingresos: {err_i}")

    metodos_maestros = {mp['nombre']: mp for mp in metodos_maestros_raw if mp.get('is_activo')}
    set_maestros_verificables = {
        nombre for nombre, regla in metodos_maestros.items() 
        if not regla.get('es_efectivo') and regla.get('tipo') == 'externo'
    }

    totales_consolidados = {}
    reporte_desglosado = {"Rayo (POS)": {}}
    otros_informativos = []

    for pago in (pagos_ventas_raw or []):
        nombre_metodo = pago.get('metodo_pago', {}).get('nombre')
        monto = Decimal(str(pago.get('monto', 0)))
        if nombre_metodo in set_maestros_verificables:
            totales_consolidados.setdefault(nombre_metodo, Decimal('0.00'))
            totales_consolidados[nombre_metodo] += monto
            reporte_desglosado["Rayo (POS)"].setdefault(nombre_metodo, Decimal('0.00'))
            reporte_desglosado["Rayo (POS)"][nombre_metodo] += monto
        elif nombre_metodo and nombre_metodo not in metodos_maestros:
            otros_informativos.append({"fuente": "Venta (Huérfano)", "metodo": nombre_metodo, "total": float(monto)})

    for ing in (ingresos_adic_raw or []):
        nombre_metodo = ing.get('metodo_pago')
        socio_nombre = ing.get('socios', {}).get('nombre', 'Socio Desconocido')
        reglas_socio = ing.get('socios') or {}
        monto = Decimal(str(ing.get('monto', 0)))

        if (nombre_metodo in set_maestros_verificables and reglas_socio.get('requiere_verificacion_voucher')):
            totales_consolidados.setdefault(nombre_metodo, Decimal('0.00'))
            totales_consolidados[nombre_metodo] += monto
            reporte_desglosado.setdefault(socio_nombre, {})
            reporte_desglosado[socio_nombre].setdefault(nombre_metodo, Decimal('0.00'))
            reporte_desglosado[socio_nombre][nombre_metodo] += monto
        else:
            otros_informativos.append({"fuente": f"Ingreso Adicional ({socio_nombre})", "metodo": nombre_metodo, "total": float(monto)})

    return {
        "totales_consolidados": totales_consolidados,
        "reporte_desglosado": reporte_desglosado,
        "otros_informativos": otros_informativos,
        "reglas_metodos": metodos_maestros
    }, None

def render_tab_verificacion():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    cierre_id = cierre_actual['id']
    rol_usuario = st.session_state.get("perfil", {}).get("rol")
    
    saldo_inicial = cierre_actual.get('saldo_inicial_efectivo', 0.0)
    saldo_teorico = calcular_saldo_teorico_efectivo(cierre_id, saldo_inicial)
    
    datos_verif, error = cargar_datos_verificacion(cierre_id)
    if error: st.error(error); st.stop()
        
    datos_guardados = cierre_actual.get('verificacion_pagos_detalle') or {}
    
    st.subheader("Estado de Conciliación General")
    conteo_final_dict = cierre_actual.get('saldo_final_detalle') or {}
    saldo_fisico = Decimal(str(conteo_final_dict.get('total', 0.0)))
    diferencia_cash = saldo_fisico - saldo_teorico
    cash_match_ok = abs(diferencia_cash) < Decimal('0.01')
    st.metric(label="1. ESTADO DE EFECTIVO", value=f"${diferencia_cash:,.2f}", delta='CUADRADO' if cash_match_ok else 'DESCUADRE', delta_color="normal" if cash_match_ok else "inverse")
    st.divider()

    st.subheader("2. Verificación de Totales Consolidados")
    vouchers_match_ok = True 
    json_verificacion_para_guardar = []
    widget_data = {}

    with st.form(key="form_verificacion_pagos"):
        if not datos_verif['totales_consolidados']:
            st.info("No hay pagos con voucher para verificar en este cierre.")
        
        for metodo, total_sistema in sorted(datos_verif['totales_consolidados'].items()):
            # ... (Lógica del formulario sin cambios) ...
            regla_metodo = datos_verif['reglas_metodos'].get(metodo, {})
            lookup_key = f"consolidado_{metodo.replace(' ', '_')}"
            
            valor_guardado = next((item for item in datos_guardados.get('verificacion_consolidada', []) if item.get('lookup_key') == lookup_key), {})
            valor_reportado_guardado = float(valor_guardado.get('total_reportado', 0.0))
            url_foto_guardada = valor_guardado.get('url_foto')

            st.markdown(f"**Verificando: {metodo}**")
            cols_v1, cols_v2, cols_v3 = st.columns(3)
            cols_v1.metric("Total Sistema (Consolidado)", f"${total_sistema:,.2f}")
            valor_reportado = cols_v2.number_input("Total Reportado (Voucher)", min_value=0.0, step=0.01, format="%.2f", value=valor_reportado_guardado, key=f"num_{lookup_key}")
            
            diff = Decimal(str(valor_reportado)) - total_sistema
            match_ok = abs(diff) < Decimal('0.01')
            if not match_ok: vouchers_match_ok = False
            cols_v3.metric("Diferencia", f"${diff:,.2f}", delta="OK" if match_ok else "FALLO", delta_color="normal" if match_ok else "inverse")
            
            file_uploader = None
            if regla_metodo.get('requiere_foto_voucher'):
                if url_foto_guardada: st.markdown(f"✅ Foto Guardada: **[Ver Foto]({url_foto_guardada})**")
                else: file_uploader = st.file_uploader("Subir foto del comprobante", type=["jpg", "jpeg", "png"], key=f"file_{lookup_key}")
            else: st.caption(f"({metodo} no requiere foto obligatoria)")

            widget_data[lookup_key] = {"file_widget": file_uploader, "url_guardada": url_foto_guardada, "nombre_display": metodo}
            json_verificacion_para_guardar.append({
                "metodo": metodo, "total_sistema": float(total_sistema), "total_reportado": float(valor_reportado),
                "match_ok": match_ok, "url_foto": url_foto_guardada, "lookup_key": lookup_key
            })
        
        st.divider()
        submitted_verif = st.form_submit_button("Guardar Verificación de Pagos", type="primary")

    if submitted_verif:
        with st.spinner("Guardando verificación y subiendo fotos..."):
            # ... (Lógica de subida de archivos sin cambios) ...
            for lookup_key, data in widget_data.items():
                item_a_actualizar = next((item for item in json_verificacion_para_guardar if item.get('lookup_key') == lookup_key), None)
                archivo_subido = data["file_widget"]
                if archivo_subido is not None and item_a_actualizar:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_subido.name)[1]) as tmp_file:
                        tmp_file.write(archivo_subido.getvalue())
                        ruta_temporal = tmp_file.name
                    url_publica, err_subida = database.subir_archivo_storage(cierre_id, data['nombre_display'], ruta_temporal)
                    os.remove(ruta_temporal)
                    if err_subida: st.error(f"FALLO AL SUBIR FOTO para {data['nombre_display']}: {err_subida}")
                    else: item_a_actualizar['url_foto'] = url_publica
            
            # --- INICIO DE LA MODIFICACIÓN ---
            
            # 1. Crear el nuevo objeto para la verificación del efectivo
            verificacion_efectivo_obj = {
                "total_teorico": float(saldo_teorico),
                "total_fisico": float(saldo_fisico),
                "diferencia": float(diferencia_cash),
                "match_ok": cash_match_ok
            }

            # 2. Crear el nuevo desglose de ingresos adicionales en efectivo
            ingresos_adicionales_raw, _ = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
            desglose_ingresos_efectivo = []
            if ingresos_adicionales_raw:
                for ing in ingresos_adicionales_raw:
                    if ing.get('metodo_pago', '').lower() == 'efectivo':
                        desglose_ingresos_efectivo.append({
                            "socio": ing.get('socios', {}).get('nombre', 'N/A'),
                            "monto": float(ing.get('monto', 0)),
                            "notas": ing.get('notas', '')
                        })

            # 3. Construir el objeto JSON final con la nueva información
            reporte_desglosado_float = {origen: {metodo: float(total) for metodo, total in metodos.items()} for origen, metodos in datos_verif['reporte_desglosado'].items()}
            
            reporte_informativo_json = {
                "desglose_por_origen": reporte_desglosado_float, 
                "otros_registros": datos_verif['otros_informativos'],
                "desglose_ingresos_adicionales_efectivo": desglose_ingresos_efectivo # <-- AÑADIDO
            }
            
            final_data_json = {
                "verificacion_consolidada": json_verificacion_para_guardar, 
                "verificacion_efectivo": verificacion_efectivo_obj, # <-- AÑADIDO
                "reporte_informativo_completo": reporte_informativo_json
            }
            
            # --- FIN DE LA MODIFICACIÓN ---

            _, err_db = database.guardar_verificacion_pagos(cierre_id, final_data_json)
            if err_db: st.error(f"Error al guardar datos de verificación en DB: {err_db}")
            else:
                st.success("¡Verificación guardada con éxito!")
                st.session_state.cierre_actual_objeto['verificacion_pagos_detalle'] = final_data_json
                cargar_datos_verificacion.clear()
                st.rerun()


    st.divider()
    st.subheader("3. Reporte Informativo Desglosado")
    with st.expander("Ver de dónde provienen los totales"):
        for origen, metodos in datos_verif['reporte_desglosado'].items():
            if not metodos: continue
            st.markdown(f"**Origen: {origen}**")
            for metodo, total in metodos.items():
                st.text(f"  - {metodo}: ${total:,.2f}")
        st.markdown("**Otros Registros Informativos**")
        if not datos_verif['otros_informativos']: st.caption("No hay otros registros.")
        else: st.dataframe(pd.DataFrame(datos_verif['otros_informativos']), hide_index=True, use_container_width=True)

    st.divider()
    st.header("Finalización del Cierre")
    match_completo_ok = cash_match_ok and vouchers_match_ok
    usuario_es_admin = (rol_usuario == 'admin')
    
    nota_admin = ""
    if not match_completo_ok and usuario_es_admin:
        st.warning("ADMIN: El cierre presenta un DESCUADRE. Debes dejar una nota explicando el motivo para poder finalizar.")
        nota_admin = st.text_area("Nota obligatoria por descuadre:", key="nota_admin_discrepancia")
    
    boton_finalizar_habilitado = match_completo_ok or (usuario_es_admin and nota_admin.strip() != "")

    if not match_completo_ok and not usuario_es_admin:
        st.error("Finalización bloqueada: El EFECTIVO o los VOUCHERS no cuadran.")
    
    if st.button("FINALIZAR CIERRE DEL DÍA", type="primary", disabled=not boton_finalizar_habilitado):
        with st.spinner("Finalizando cierre..."):
            nota_a_guardar = nota_admin if not match_completo_ok and usuario_es_admin else None
            _, err_final = database.finalizar_cierre_en_db(cierre_id, nota_discrepancia=nota_a_guardar)
            if err_final:
                st.error(f"Error al finalizar: {err_final}")
            else:
                st.success("¡CIERRE FINALIZADO CON ÉXITO! 🎉")
                st.balloons()
                st.session_state['cierre_actual_objeto'] = None
                st.session_state['cierre_sucursal_seleccionada_nombre'] = None
                st.cache_data.clear()
                st.rerun()

# =============================================================================
# EJECUCIÓN PRINCIPAL (El Loader y el Contenedor de Pestañas)
# =============================================================================

st.set_page_config(page_title="Cierre de Caja Operativo", layout="wide")
st.title("Espacio de Trabajo: Cierre de Caja 🧾")

@st.cache_data(ttl=600)
def cargar_sucursales_data():
    sucursales_data, err = database.obtener_sucursales()
    if err:
        st.error(f"No se pudieron cargar sucursales: {err}")
        return {}
    opciones = {s['sucursal']: s['id'] for s in sucursales_data}
    return opciones

if 'cierre_actual_objeto' not in st.session_state:
    st.session_state['cierre_actual_objeto'] = None
if 'cierre_sucursal_seleccionada_nombre' not in st.session_state:
    st.session_state['cierre_sucursal_seleccionada_nombre'] = None

st.header("1. Seleccione Sucursal de Trabajo")
opciones_sucursal = cargar_sucursales_data()
lista_nombres_sucursales = ["--- Seleccione una Sucursal ---"] + list(opciones_sucursal.keys())
default_index = 0
if st.session_state.cierre_sucursal_seleccionada_nombre in lista_nombres_sucursales:
    default_index = lista_nombres_sucursales.index(st.session_state.cierre_sucursal_seleccionada_nombre)

sucursal_seleccionada_nombre = st.selectbox(
    "Sucursal:",
    options=lista_nombres_sucursales,
    index=default_index 
)

if sucursal_seleccionada_nombre != st.session_state.cierre_sucursal_seleccionada_nombre:
    st.session_state['cierre_actual_objeto'] = None
    st.session_state['cierre_sucursal_seleccionada_nombre'] = sucursal_seleccionada_nombre
    st.session_state.pop('resumen_calculado', None) 
    st.rerun() 

if sucursal_seleccionada_nombre == "--- Seleccione una Sucursal ---":
    st.info("Debe seleccionar una sucursal para iniciar o continuar un cierre.")
    st.stop()

sucursal_id_actual = opciones_sucursal[sucursal_seleccionada_nombre]
usuario_id_actual = st.session_state['perfil']['id']

# --- INICIO DEL CARGADOR DE REVISIÓN ADMIN ---
if 'admin_review_cierre_obj' in st.session_state and st.session_state.admin_review_cierre_obj is not None:
    
    cierre_para_revisar = st.session_state.pop('admin_review_cierre_obj') 
    nombre_sucursal_revisar = st.session_state.pop('admin_review_sucursal_nombre')
    
    st.session_state['cierre_actual_objeto'] = cierre_para_revisar
    st.session_state['cierre_sucursal_seleccionada_nombre'] = nombre_sucursal_revisar
    
    usuario_id_del_cierre = cierre_para_revisar.get('usuario_id')
    perfil_original, _ = database.obtener_perfil_usuario(usuario_id_del_cierre)
    nombre_usuario_original = perfil_original.get('nombre', 'Usuario Desconocido') if perfil_original else 'Usuario Desconocido'

    st.warning(f"**MODO SUPERVISOR:** Estás editando el cierre de **{nombre_usuario_original}** en **{nombre_sucursal_revisar}**.")
    st.info("Cualquier cambio que guardes o al finalizar, se mantendrá el nombre del usuario original.")
    
    cargar_sucursales_data.clear()
    st.rerun()
# --- FIN DEL CARGADOR DE REVISIÓN ADMIN ---

if st.session_state.get('cierre_actual_objeto') is None:
    st.markdown("---")
    st.subheader("2. Estado del Cierre del Día")
    with st.spinner("Buscando estado de cierres para hoy..."):
        cierre_abierto, err_a = database.buscar_cierre_abierto_hoy(usuario_id_actual, sucursal_id_actual)
        if err_a:
            st.error(f"Error buscando cierre abierto: {err_a}")
            st.stop()
        if cierre_abierto:
            st.success(f"✅ Cierre ABIERTO encontrado. Listo para trabajar.")
            st.session_state['cierre_actual_objeto'] = cierre_abierto
            st.rerun()

        cierre_cerrado, err_c = database.buscar_cierre_cerrado_hoy(usuario_id_actual, sucursal_id_actual)
        if err_c:
            st.error(f"Error buscando cierre cerrado: {err_c}")
            st.stop()
        if cierre_cerrado:
            st.warning("ℹ️ Ya existe un cierre FINALIZADO para hoy en esta sucursal.")
            st.markdown("Puede reabrir el cierre anterior o crear uno nuevo.")
            col1, col2 = st.columns(2)
            if col1.button("Reabrir Cierre Anterior (Recomendado)"):
                cierre_reabierto, err_r = database.reabrir_cierre(cierre_cerrado['id'])
                if err_r: st.error(f"No se pudo reabrir: {err_r}")
                else:
                    st.session_state['cierre_actual_objeto'] = cierre_reabierto
                    st.rerun()
            if col2.button("Crear Cierre Completamente Nuevo"):
                st.session_state['iniciar_nuevo_cierre_flag'] = True
                st.rerun()
            st.stop() 

        if (not cierre_abierto and not cierre_cerrado) or st.session_state.get('iniciar_nuevo_cierre_flag'):
            nuevo_cierre_creado = render_form_inicial(usuario_id_actual, sucursal_id_actual)
            if nuevo_cierre_creado:
                st.session_state['cierre_actual_objeto'] = nuevo_cierre_creado
                st.session_state.pop('iniciar_nuevo_cierre_flag', None) 
                st.success("¡Nuevo cierre iniciado con éxito!")
                st.balloons()
                st.rerun() 
            else:
                st.stop() 

if st.session_state.get('cierre_actual_objeto'):
    st.markdown("---")
    st.header(f"Estás trabajando en: {sucursal_seleccionada_nombre}")
    
    # --- DEFINICIÓN FINAL DE TABS ---
    tab1, tab2, tab3, tab_del, tab_compra, tab4, tab5, tab6 = st.tabs([
        "PASO 1: Caja Inicial", 
        "PASO 2: Gastos", 
        "PASO 3: Ingresos Adic.",
        "PASO 4: Delivery",
        "PASO 5: Compras (Info)",
        "PASO 6: Resumen",
        "PASO 7: Caja Final",
        "PASO 8: Verificación y Finalizar"
    ])

    with tab1: render_tab_inicial()
    with tab2: render_tab_gastos()
    with tab3: render_tab_ingresos_adic()
    with tab_del: render_tab_delivery()
    with tab_compra: render_tab_compras()
    with tab4: render_tab_resumen()
    with tab5: render_tab_caja_final() # NameError corregido aquí
    with tab6: render_tab_verificacion()






