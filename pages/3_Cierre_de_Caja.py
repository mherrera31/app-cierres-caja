# pages/3_Cierre_de_Caja.py
# VERSIÓN CONSOLIDADA (TODO EN UNO)

import streamlit as st
import database
import pandas as pd
from decimal import Decimal
import tempfile
import os
import json # Necesario para el reporte de admin (aunque este m_dulo no lo usa, lo dejamos por si acaso)

# --- GUARDIÁN DE SEGURIDAD (Permite a TODOS los logueados) ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop()
# ------------------------------------

# =============================================================================
# DEFINICIÓN DE CONSTANTES Y MÓDULOS (Todo lo que estaba en cierre_web/)
# =============================================================================

# Constante copiada de (shared_widgets.py / tab_*.py)
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

# --- Módulo: form_caja_inicial (del Paso 137) ---
def render_form_inicial(usuario_id, sucursal_id):
    st.info("No se encontró ningún cierre para hoy. Se debe crear uno nuevo.")
    st.subheader("Paso A: Conteo de Caja Inicial")
    st.markdown("Ingrese las cantidades de dinero (conteo físico) con las que inicia la caja hoy.")

    with st.form(key="form_conteo_inicial"):
        inputs_conteo = {}
        total_calculado = Decimal('0.00')
        
        st.markdown("**Monedas**")
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1]) 
                col_lab.write(den['nombre']) 
                cantidad = col_inp.number_input(
                    label=f"Input_{den['nombre']}", 
                    label_visibility="collapsed", 
                    min_value=0, 
                    step=1, 
                    key=f"den_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado += Decimal(str(cantidad)) * Decimal(str(den['valor']))

        st.markdown("**Billetes**")
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad = col_inp.number_input(
                    label=f"Input_{den['nombre']}", 
                    label_visibility="collapsed", 
                    min_value=0, 
                    step=1, 
                    key=f"den_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.divider()
        st.header(f"Total Contado Inicial: ${total_calculado:,.2f}")
        submitted = st.form_submit_button("Guardar y Empezar Cierre", type="primary")

    if submitted:
        datos_conteo_final = {"total": float(total_calculado), "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                datos_conteo_final["detalle"][nombre] = {
                    "cantidad": data['cantidad'],
                    "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                }
        
        if st.session_state.get('ignorar_discrepancia_flag') == True:
            marcar_discrepancia = True
            st.session_state.pop('ignorar_discrepancia_flag', None) 
        else:
            marcar_discrepancia = False

        with st.spinner("Creando nuevo cierre en la base de datos..."):
            nuevo_cierre, error_db = database.iniciar_cierre_en_db(
                usuario_id, 
                sucursal_id, 
                datos_conteo_final,
                marcar_discrepancia=marcar_discrepancia
            )
        
        if nuevo_cierre and error_db:
            st.warning(f"ADVERTENCIA: {error_db}")
            st.markdown("¿Desea continuar de todas formas? (Esto marcará el cierre con una discrepancia).")
            col_warn1, col_warn2 = st.columns(2)
            if col_warn1.button("Sí, continuar e ignorar advertencia"):
                st.session_state['ignorar_discrepancia_flag'] = True
                st.rerun() 
            if col_warn2.button("No, cancelar (Corregiré el conteo)"):
                pass
            return None
        elif error_db:
            st.error(f"Error Crítico al crear cierre: {error_db}")
            return None
        elif nuevo_cierre:
            return nuevo_cierre 

    return None

# --- Módulo: tab_caja_inicial (del Paso 167) ---
def render_tab_inicial():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']

    datos_saldo_inicial_guardado = cierre_actual.get('saldo_inicial_detalle') or {}
    detalle_guardado = datos_saldo_inicial_guardado.get('detalle', {})
    
    st.info("Puedes editar las cantidades de tu conteo inicial y guardar los cambios.")

    with st.form(key="form_EDITAR_conteo_inicial"):
        inputs_conteo = {}
        total_calculado = Decimal('0.00')

        st.markdown("**Monedas**")
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(
                    label=f"Input_Edit_{den['nombre']}", 
                    label_visibility="collapsed", 
                    min_value=0, 
                    step=1, 
                    value=cantidad_guardada,
                    key=f"den_edit_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado += Decimal(str(cantidad)) * Decimal(str(den['valor']))

        st.markdown("**Billetes**")
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(
                    label=f"Input_Edit_{den['nombre']}", 
                    label_visibility="collapsed", 
                    min_value=0, 
                    step=1, 
                    value=cantidad_guardada,
                    key=f"den_edit_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.divider()
        st.header(f"Total Contado Inicial: ${total_calculado:,.2f}")
        submitted = st.form_submit_button("Guardar Cambios en Caja Inicial", type="primary")

    if submitted:
        datos_conteo_actualizados = {"total": float(total_calculado), "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                datos_conteo_actualizados["detalle"][nombre] = {
                    "cantidad": data['cantidad'],
                    "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                }
        with st.spinner("Actualizando saldo inicial..."):
            _, error_db = database.actualizar_saldo_inicial(cierre_id, datos_conteo_actualizados)
        if error_db:
            st.error(f"No se pudo actualizar el saldo: {error_db}")
        else:
            st.session_state.cierre_actual_objeto["saldo_inicial_detalle"] = datos_conteo_actualizados
            st.session_state.cierre_actual_objeto["saldo_inicial_efectivo"] = datos_conteo_actualizados['total']
            st.success("¡Saldo inicial actualizado con éxito!")
            st.rerun()

# --- Módulo: tab_gastos (del Paso 150) ---
@st.cache_data(ttl=600)
def cargar_categorias_gastos_activas():
    categorias_data, err = database.obtener_categorias_gastos()
    if err:
        st.error(f"Error cargando categorías: {err}")
        return {}, {}
    opciones_cat = {c['nombre']: c['id'] for c in categorias_data}
    return opciones_cat

@st.cache_data(ttl=15) 
def cargar_gastos_registrados(cierre_id):
    gastos_data, err = database.obtener_gastos_del_cierre(cierre_id)
    if err:
        st.error(f"Error cargando gastos registrados: {err}")
        return pd.DataFrame(), 0.0
    if not gastos_data:
        return pd.DataFrame(columns=["Categoría", "Monto", "Notas"]), 0.0
    df_data = []
    total_gastos = 0.0
    for gasto in gastos_data:
        nombre_cat = gasto.get('gastos_categorias', {}).get('nombre', 'N/A') if gasto.get('gastos_categorias') else 'N/A'
        monto = float(gasto.get('monto', 0))
        total_gastos += monto
        df_data.append({"Categoría": nombre_cat, "Monto": monto, "Notas": gasto.get('notas', '')})
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

    with st.form(key="form_nuevo_gasto", clear_on_submit=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            categoria_nombre_sel = st.selectbox("Categoría:", options=categorias_dict.keys())
        with col2:
            monto_gasto = st.number_input("Monto ($):", min_value=0.01, step=0.01, format="%.2f")
        notas_gasto = st.text_input("Notas (Opcional):")
        submit_gasto = st.form_submit_button("Añadir Gasto", type="primary")

    if submit_gasto:
        categoria_id_sel = categorias_dict[categoria_nombre_sel]
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
            st.session_state.pop('resumen_calculado', None) # Borra el caché del Resumen (Paso 4)
            st.rerun()

    st.divider()
    st.subheader("Gastos Registrados en este Cierre")
    df_gastos, total_gastos = cargar_gastos_registrados(cierre_id)
    if df_gastos.empty:
        st.info("Aún no se han registrado gastos en este cierre.")
    else:
        st.dataframe(
            df_gastos, use_container_width=True, hide_index=True,
            column_config={"Monto": st.column_config.NumberColumn(format="$ %.2f")}
        )
        st.metric(label="Total Gastado (Efectivo)", value=f"${total_gastos:,.2f}")


# --- Módulo: tab_ingresos_adic (del Paso 150) ---
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

    ingresos_lookup = cargar_ingresos_existentes(cierre_id)
    st.subheader("Registrar Ingresos Adicionales por Socio")
    st.markdown("Registre los montos recibidos por cada socio y método de pago. Use los 'expanders' (▼) para ver cada socio.")

    with st.form(key="form_ingresos_adicionales"):
        widget_keys = [] 
        for socio in socios:
            with st.expander(f"Socio: {socio['nombre']}"):
                for mp in metodos_pago:
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
            st.session_state.pop('resumen_calculado', None) # Borra el caché del Resumen (Paso 4)
            st.rerun()
        else:
            st.info("No se detectaron cambios para guardar.")


# --- Módulo: tab_resumen (del Paso 165) ---
def _ejecutar_calculo_resumen(cierre_id, cierre_actual_obj):
    with st.spinner("Calculando resumen con datos actualizados..."):
        saldo_inicial = Decimal(str(cierre_actual_obj.get('saldo_inicial_efectivo') or 0.0))

        pagos_venta, err_p = database.obtener_pagos_del_cierre(cierre_id)
        total_pagos_venta_efectivo = Decimal('0.00')
        pagos_venta_efectivo_lista = []
        if not err_p and pagos_venta:
            for pago in pagos_venta:
                metodo = pago.get('metodo_pago')
                if metodo and metodo.get('nombre') and metodo.get('nombre').lower() == 'efectivo':
                    monto = Decimal(str(pago.get('monto') or 0.0))
                    total_pagos_venta_efectivo += monto
                    pagos_venta_efectivo_lista.append(pago) 

        ingresos_adicionales, err_i = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
        total_ingresos_adicionales_efectivo = Decimal('0.00')
        ingresos_adic_efectivo_lista = []
        if not err_i and ingresos_adicionales:
            for ingreso in ingresos_adicionales:
                metodo = ingreso.get('metodo_pago')
                if metodo and metodo.lower() == 'efectivo':
                    monto = Decimal(str(ingreso.get('monto') or 0.0))
                    total_ingresos_adicionales_efectivo += monto
                    ingresos_adic_efectivo_lista.append(ingreso)

        gastos, err_g = database.obtener_gastos_del_cierre(cierre_id)
        total_gastos = Decimal('0.00')
        if not err_g and gastos:
            for gasto in gastos:
                total_gastos += Decimal(str(gasto.get('monto') or 0.0))

        total_calculado_efectivo = (saldo_inicial + total_pagos_venta_efectivo + total_ingresos_adicionales_efectivo) - total_gastos
        
        st.session_state.cierre_actual_objeto['total_calculado_teorico'] = float(total_calculado_efectivo)
        
        st.session_state.resumen_calculado = {
            "saldo_inicial": saldo_inicial,
            "total_pagos_venta_efectivo": total_pagos_venta_efectivo,
            "total_ingresos_adicionales_efectivo": total_ingresos_adicionales_efectivo,
            "total_gastos": total_gastos,
            "total_calculado_efectivo": total_calculado_efectivo,
            "pagos_lista": pagos_venta_efectivo_lista,
            "ingresos_lista": ingresos_adic_efectivo_lista,
            "gastos_lista": gastos,
            "cache_id": cierre_id 
        }

def render_tab_resumen():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']

    st.subheader("Cálculo del Saldo Teórico de Efectivo")
    st.info("Este es el resumen de todo el efectivo. Presiona 'Recalcular' si has añadido nuevos gastos o ingresos en las otras pestañas.")

    if st.button("Recalcular Resumen (Refrescar Manual)", type="primary"):
        _ejecutar_calculo_resumen(cierre_id, cierre_actual)
        st.success("Resumen refrescado.")

    resumen_cache = st.session_state.get('resumen_calculado')
    if not resumen_cache or resumen_cache.get('cache_id') != cierre_id:
        _ejecutar_calculo_resumen(cierre_id, cierre_actual)

    st.divider()
    resumen_guardado = st.session_state.get('resumen_calculado')

    if not resumen_guardado:
        st.warning("Calculando datos del resumen... (Presiona el botón de Recalcular si esto no desaparece).")
    else:
        val_total_teorico = resumen_guardado.get('total_calculado_efectivo') or 0.0
        val_saldo_ini = resumen_guardado.get('saldo_inicial') or 0.0
        val_ventas_efec = resumen_guardado.get('total_pagos_venta_efectivo') or 0.0
        val_ing_adic_efec = resumen_guardado.get('total_ingresos_adicionales_efectivo') or 0.0
        val_total_gastos = resumen_guardado.get('total_gastos') or 0.0
        
        st.header(f"Total Teórico en Caja: ${val_total_teorico:,.2f}")
        st.caption("Esta es la cantidad de efectivo que debería haber físicamente en caja antes del conteo final.")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("1. Saldo Inicial (Efectivo)", f"${val_saldo_ini:,.2f}")
        col2.metric("2. Ventas (Efectivo)", f"${val_ventas_efec:,.2f}")
        col3.metric("3. Ingresos Adic. (Efectivo)", f"${val_ing_adic_efec:,.2f}")
        col4.metric("4. Gastos (Efectivo)", f"$-{val_total_gastos:,.2f}", delta_color="inverse")

        st.divider()
        st.subheader("Detalles del Cálculo")
        
        lista_pagos = resumen_guardado.get('pagos_lista', [])
        lista_ingresos = resumen_guardado.get('ingresos_lista', [])
        lista_gastos = resumen_guardado.get('gastos_lista', [])

        with st.expander("Ver detalle de Ventas en Efectivo"):
            if not lista_pagos: st.write("Sin ventas en efectivo.")
            else: st.write(f"Total de {len(lista_pagos)} pagos en efectivo sumando: ${val_ventas_efec:,.2f}")

        with st.expander("Ver detalle de Ingresos Adicionales en Efectivo"):
            if not lista_ingresos: st.write("Sin ingresos adicionales en efectivo.")
            else:
                for ing in lista_ingresos:
                    socio_nombre = ing.get('socios', {}).get('nombre', 'N/A')
                    st.write(f"- Socio: {socio_nombre} | Monto: ${Decimal(str(ing.get('monto') or 0)):,.2f}")
    
        with st.expander("Ver detalle de Gastos"):
            if not lista_gastos: st.write("Sin gastos registrados.")
            else:
                for gasto in lista_gastos:
                    cat_nombre = gasto.get('gastos_categorias', {}).get('nombre', 'N/A')
                    st.write(f"- Categoría: {cat_nombre} | Monto: ${Decimal(str(gasto.get('monto') or 0)):,.2f} | Notas: {gasto.get('notas','')}")

# --- Módulo: tab_caja_final (del Paso 167) ---
def calcular_montos_finales_logica(conteo_detalle):
    saldo_para_siguiente_dia = Decimal('0.0')
    detalle_saldo_siguiente = {}
    
    for den in DENOMINACIONES:
        if 'Moneda' in den['nombre']:
            detalle_conteo = conteo_detalle or {}
            cantidad_disponible = detalle_conteo.get(den['nombre'], {'cantidad': 0})['cantidad']
            if cantidad_disponible > 0:
                subtotal = Decimal(str(cantidad_disponible)) * Decimal(str(den['valor']))
                saldo_para_siguiente_dia += subtotal
                detalle_saldo_siguiente[den['nombre']] = {'cantidad': cantidad_disponible, 'subtotal': float(subtotal)}
    
    den_billete_1 = next((d for d in DENOMINACIONES if d['nombre'] == 'Billetes de $1'), None)
    if den_billete_1:
        detalle_conteo = conteo_detalle or {}
        cantidad_disponible_1 = detalle_conteo.get(den_billete_1['nombre'], {'cantidad': 0})['cantidad']
        cantidad_a_dejar = min(cantidad_disponible_1, 4)
        if cantidad_a_dejar > 0:
            subtotal = Decimal(str(cantidad_a_dejar)) * Decimal(str(den_billete_1['valor']))
            saldo_para_siguiente_dia += subtotal
            detalle_saldo_siguiente[den_billete_1['nombre']] = {'cantidad': cantidad_a_dejar, 'subtotal': float(subtotal)}

    den_billete_5 = next((d for d in DENOMINACIONES if d['nombre'] == 'Billetes de $5'), None)
    if den_billete_5:
        detalle_conteo = conteo_detalle or {}
        cantidad_disponible_5 = detalle_conteo.get(den_billete_5['nombre'], {'cantidad': 0})['cantidad']
        cantidad_a_dejar = min(cantidad_disponible_5, 4)
        if cantidad_a_dejar > 0:
            subtotal = Decimal(str(cantidad_a_dejar)) * Decimal(str(den_billete_5['valor']))
            saldo_para_siguiente_dia += subtotal
            detalle_saldo_siguiente[den_billete_5['nombre']] = {'cantidad': cantidad_a_dejar, 'subtotal': float(subtotal)}
        
    total_contado_fisico = Decimal(str(sum(d.get('subtotal', 0) for d in (conteo_detalle or {}).values())))
    total_a_depositar = total_contado_fisico - saldo_para_siguiente_dia
    
    return {
        "total_contado": float(total_contado_fisico),
        "saldo_siguiente": {"total": float(saldo_para_siguiente_dia), "detalle": detalle_saldo_siguiente},
        "total_a_depositar": float(total_a_depositar)
    }

def render_tab_caja_final():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']
    saldo_teorico = Decimal(str(cierre_actual.get('total_calculado_teorico', 0.0)))
    
    st.info(f"Total Teórico (calculado en Paso 4): ${saldo_teorico:,.2f}")
    st.markdown("Ingrese el conteo físico de todo el efectivo en caja para calcular la diferencia.")
    
    datos_saldo_final_guardado = cierre_actual.get('saldo_final_detalle') or {}
    detalle_guardado = datos_saldo_final_guardado.get('detalle', {})

    with st.form(key="form_conteo_final"):
        inputs_conteo = {}
        total_calculado_fisico = Decimal('0.00')

        st.markdown("**Monedas**")
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(
                    label=f"Input_Final_{den['nombre']}", 
                    label_visibility="collapsed", 
                    min_value=0, 
                    step=1, 
                    value=cantidad_guardada, 
                    key=f"den_final_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))

        st.markdown("**Billetes**")
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col_lab, col_inp = st.columns([2, 1])
                col_lab.write(den['nombre'])
                cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col_inp.number_input(
                    label=f"Input_Final_{den['nombre']}", 
                    label_visibility="collapsed", 
                    min_value=0, 
                    step=1, 
                    value=cantidad_guardada, 
                    key=f"den_final_{den['nombre']}"
                )
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
        
        st.divider()
        st.header(f"Total Contado Físico: ${total_calculado_fisico:,.2f}")
        submitted_final = st.form_submit_button("Guardar Conteo Final y Calcular Depósito", type="primary")

    st.divider()
    st.subheader("Resultados del Cierre")
    
    diferencia = total_calculado_fisico - saldo_teorico
    delta_color = "off"
    if diferencia > Decimal('0.01'): delta_color = "inverse" 
    elif diferencia < Decimal('-0.01'): delta_color = "inverse" 
    else: delta_color = "normal" 

    st.metric(
        label="DIFERENCIA DE CAJA (Físico vs. Teórico)",
        value=f"${diferencia:,.2f}",
        delta=f"{'SOBRANTE' if diferencia > 0 else 'FALTANTE' if diferencia < 0 else 'CUADRADO'}",
        delta_color=delta_color
    )

    if submitted_final:
        datos_conteo_final_dict = {"total": float(total_calculado_fisico), "detalle": {}}
        detalle_para_calculo = {} 
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                subtotal_float = float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                datos_conteo_final_dict["detalle"][nombre] = {
                    "cantidad": data['cantidad'], "subtotal": subtotal_float
                }
                detalle_para_calculo[nombre] = {"cantidad": data['cantidad'], "subtotal": subtotal_float}
        
        calculos = calcular_montos_finales_logica(detalle_para_calculo)
        
        with st.spinner("Guardando conteo final en la base de datos..."):
            _, error_db = database.guardar_conteo_final(
                cierre_id, datos_conteo_final_dict,
                calculos['total_a_depositar'], calculos['saldo_siguiente']
            )

        if error_db:
            st.error(f"Error al guardar el conteo final: {error_db}")
        else:
            st.session_state.cierre_actual_objeto['saldo_final_detalle'] = datos_conteo_final_dict
            st.session_state.cierre_actual_objeto['total_a_depositar'] = calculos['total_a_depositar']
            st.session_state.cierre_actual_objeto['saldo_siguiente_detalle'] = calculos['saldo_siguiente']
            st.session_state.cierre_actual_objeto['saldo_para_siguiente_dia'] = calculos['saldo_siguiente']['total']
            st.success("¡Conteo final guardado con éxito!")
            st.rerun() 

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
            if not detalle_saldo_sig: st.write("Aún no calculado (Presione Guardar).")
            else:
                for den, info in detalle_saldo_sig.items():
                    st.text(f"- {den}: {info['cantidad']} (=${info['subtotal']:,.2f})")
            st.metric("Total Saldo Siguiente:", f"${float(saldo_sig_guardado.get('total', 0)):,.2f}")

# --- Módulo: tab_verificacion (del Paso 167) ---
@st.cache_data(ttl=15) 
def cargar_datos_verificacion(cierre_id):
    pagos_ventas_raw, err_p = database.obtener_pagos_del_cierre(cierre_id)
    metodos_maestros_raw, err_m = database.obtener_metodos_pago_con_flags()
    ingresos_adic_raw, err_i = database.obtener_ingresos_adicionales_del_cierre(cierre_id)

    if err_m:
         st.error(f"Error Crítico al cargar Métodos de Pago: {err_m}")
         st.stop()
    if err_p or err_i:
        st.warning(f"Error Pagos: {err_p} | Error Ingresos: {err_i}")
        
    metodos_maestros = {}
    nombres_maestros = set()
    if metodos_maestros_raw:
        for mp in metodos_maestros_raw:
            if mp['is_activo']:
                nombre_lower = mp['nombre'].lower()
                metodos_maestros[nombre_lower] = mp
                nombres_maestros.add(nombre_lower)

    totales_sistema_ventas = {}
    nombres_ventas_registrados = set()
    if pagos_ventas_raw:
        for pago in pagos_ventas_raw:
            if pago.get('metodo_pago') and pago.get('metodo_pago').get('nombre'):
                nombre = pago['metodo_pago']['nombre']
                nombre_lower = nombre.lower()
                monto = Decimal(str(pago.get('monto', 0)))
                nombres_ventas_registrados.add(nombre_lower)
                if nombre_lower not in totales_sistema_ventas:
                    totales_sistema_ventas[nombre_lower] = Decimal('0.00')
                totales_sistema_ventas[nombre_lower] += monto
            
    totales_sistema_ing_adic = {}
    if ingresos_adic_raw:
        for ing in ingresos_adic_raw:
            nombre = ing.get('metodo_pago')
            if nombre: 
                nombre_lower = nombre.lower()
                monto = Decimal(str(ing.get('monto', 0)))
                if nombre_lower not in totales_sistema_ing_adic:
                    totales_sistema_ing_adic[nombre_lower] = Decimal('0.00')
                totales_sistema_ing_adic[nombre_lower] += monto

    pagos_huerfanos = (nombres_ventas_registrados - nombres_maestros) - {'efectivo'}

    return {
        "metodos_maestros": metodos_maestros,
        "totales_ventas": totales_sistema_ventas,
        "totales_ing_adic": totales_sistema_ing_adic,
        "huerfanos": pagos_huerfanos
    }, None

def render_tab_verificacion():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']
    rol_usuario = st.session_state['perfil']['rol']

    datos_verif, error = cargar_datos_verificacion(cierre_id)
    if error:
        st.error(error)
        st.stop()

    datos_guardados = cierre_actual.get('verificacion_pagos_detalle') or {}
    saved_verification_lookup = {item['metodo'].lower(): item for item in datos_guardados.get('verificacion_con_match', [])}

    st.subheader("Estado de Conciliación General")
    saldo_teorico = Decimal(str(cierre_actual.get('total_calculado_teorico', 0.0)))
    conteo_final_dict = cierre_actual.get('saldo_final_detalle') or {}
    saldo_fisico = Decimal(str(conteo_final_dict.get('total', 0.0)))
    
    diferencia_cash = saldo_fisico - saldo_teorico
    cash_match_ok = abs(diferencia_cash) < Decimal('0.01')
    
    delta_color = "off"
    if not cash_match_ok: delta_color = "inverse"
    else: delta_color = "normal"

    st.metric(
        label="1. ESTADO DE EFECTIVO (Diferencia de Caja Final)",
        value=f"${diferencia_cash:,.2f}",
        delta=f"{'CUADRADO' if cash_match_ok else 'DESCUADRE'}",
        delta_color=delta_color
    )

    st.divider()
    st.subheader("Sección 1: Pagos de Ventas (Requiere Match de Voucher)")
    
    vouchers_match_ok = True 
    json_verificacion_con_match = [] 
    widget_data = {} 

    with st.form(key="form_verificacion_pagos"):
        if not datos_verif['metodos_maestros']:
             st.warning("No hay métodos de pago (reglas) cargados en la base de datos.")
        
        for nombre_lower, regla_metodo in datos_verif['metodos_maestros'].items():
            if nombre_lower == 'efectivo': continue 

            nombre_display = regla_metodo['nombre']
            total_sistema = datos_verif['totales_ventas'].get(nombre_lower, Decimal('0.00'))
            
            data_guardada = saved_verification_lookup.get(nombre_lower, {})
            valor_reportado_guardado = float(data_guardada.get('total_reportado', 0.0))
            url_foto_guardada = data_guardada.get('url_foto', None)

            st.markdown(f"**Verificando: {nombre_display}**")
            cols = st.columns(3)
            cols[0].metric("Total del Sistema", f"${total_sistema:,.2f}")
            
            valor_reportado_input = cols[1].number_input(
                "Total Reportado (Voucher)", min_value=0.0, step=0.01, format="%.2f",
                value=valor_reportado_guardado, key=f"verif_num_{nombre_lower}"
            )
            
            diff_voucher = Decimal(str(valor_reportado_input)) - total_sistema
            voucher_ok = abs(diff_voucher) < Decimal('0.01')
            if not voucher_ok: vouchers_match_ok = False 
                
            cols[2].metric("Diferencia", f"${diff_voucher:,.2f}", 
                           delta=f"{'OK' if voucher_ok else 'FALLO'}", 
                           delta_color="normal" if voucher_ok else "inverse")

            file_uploader = None
            if regla_metodo.get('requiere_foto_voucher', False):
                if url_foto_guardada:
                    st.markdown(f"✅ Foto Guardada: **[Ver Foto]({url_foto_guardada})**", unsafe_allow_html=True)
                else:
                    file_uploader = st.file_uploader(f"Subir foto de Voucher para {nombre_display}", type=["jpg", "jpeg", "png"], key=f"verif_file_{nombre_lower}")
            
            widget_data[nombre_lower] = { "file_widget": file_uploader, "url_guardada": url_foto_guardada }

            json_verificacion_con_match.append({
                "metodo": nombre_display, "fuente": "Ventas",
                "requiere_foto": regla_metodo.get('requiere_foto_voucher', False),
                "total_sistema": float(total_sistema), "total_reportado": float(valor_reportado_input),
                "match_ok": voucher_ok, "url_foto": None 
            })
            st.divider()

        submitted_verif = st.form_submit_button("Guardar Verificación de Pagos", type="primary")

    st.subheader("Sección 2: Registros Informativos (Sin Match Requerido)")
    json_registros_informativos = [] 

    with st.expander("Ver Pagos Huérfanos (Ventas sin regla) y Otros Ingresos"):
        st.markdown("**Pagos Huérfanos (Ventas)**")
        if not datos_verif['huerfanos']: st.caption("No hay pagos huérfanos.")
        for nombre_huerfano in datos_verif['huerfanos']:
            total_h = datos_verif['totales_ventas'].get(nombre_huerfano, Decimal('0.00'))
            if total_h > 0:
                st.metric(label=f"{nombre_huerfano.title()} (Venta)", value=f"${total_h:,.2f}")
                json_registros_informativos.append({
                    "metodo": nombre_huerfano.title(), "fuente": "Ventas (Huérfano)", "total_sistema": float(total_h)
                })

        st.markdown("**Ingresos Adicionales (No-Efectivo)**")
        ingresos_no_cash = False
        for nombre_lower, total_ing in datos_verif['totales_ing_adic'].items():
            if nombre_lower != 'efectivo' and total_ing > 0:
                ingresos_no_cash = True
                st.metric(label=f"{nombre_lower.title()} (Ingreso Adic.)", value=f"${total_ing:,.2f}")
                json_registros_informativos.append({
                    "metodo": nombre_lower.title(), "fuente": "Ingreso Adicional", "total_sistema": float(total_ing)
                })
        if not ingresos_no_cash: st.caption("No hay ingresos adicionales (no-efectivo).")

    if submitted_verif:
        with st.spinner("Guardando verificación y subiendo fotos (si las hay)..."):
            hubo_error_subida = False
            for nombre_lower, data in widget_data.items():
                archivo_subido = data["file_widget"]
                if archivo_subido is not None:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=archivo_subido.name) as tmp_file:
                        tmp_file.write(archivo_subido.getvalue())
                        ruta_temporal = tmp_file.name
                    
                    st.write(f"Subiendo foto para {nombre_lower}...")
                    url_publica, err_subida = database.subir_archivo_storage(cierre_id, nombre_lower, ruta_temporal)
                    os.remove(ruta_temporal) 

                    if err_subida:
                        st.error(f"FALLO AL SUBIR FOTO para {nombre_lower}: {err_subida}")
                        hubo_error_subida = True
                    else:
                        st.success(f"Foto para {nombre_lower} subida con éxito.")
                        for item in json_verificacion_con_match:
                            if item['metodo'].lower() == nombre_lower: item['url_foto'] = url_publica
            
            for item in json_verificacion_con_match:
                if item['url_foto'] is None: 
                    url_guardada_previa = widget_data[item['metodo'].lower()].get('url_guardada')
                    if url_guardada_previa: item['url_foto'] = url_guardada_previa 

            if not hubo_error_subida:
                final_data_json = {
                    "verificacion_con_match": json_verificacion_con_match,
                    "registros_informativos": json_registros_informativos
                }
                _, err_db = database.guardar_verificacion_pagos(cierre_id, final_data_json)
                
                if err_db: st.error(f"Error al guardar datos de verificación en DB: {err_db}")
                else:
                    st.success("¡Verificación de pagos guardada con éxito!")
                    st.session_state.cierre_actual_objeto['verificacion_pagos_detalle'] = final_data_json
                    cargar_datos_verificacion.clear() 
                    st.rerun()

    st.divider()
    st.header("Finalización del Cierre")
    
    match_completo_ok = cash_match_ok and vouchers_match_ok
    usuario_es_admin = (rol_usuario == 'admin')
    boton_finalizar_habilitado = False
    razon_deshabilitado = ""

    if match_completo_ok:
        boton_finalizar_habilitado = True
    elif usuario_es_admin:
        boton_finalizar_habilitado = True
        st.warning("ADMIN: El cierre presenta un DESCUADRE (en efectivo o vouchers), pero tienes permiso para forzar la finalización.")
    else:
        boton_finalizar_habilitado = False
        if not cash_match_ok:
            razon_deshabilitado = "Finalización bloqueada: El conteo de EFECTIVO (Paso 5) no cuadra con el RESUMEN (Paso 4)."
        elif not vouchers_match_ok:
            razon_deshabilitado = "Finalización bloqueada: Los montos reportados de VOUCHERS (Paso 6) no cuadran con el Sistema."
        st.error(razon_deshabilitado)

    if st.button("FINALIZAR CIERRE DEL DÍA", type="primary", disabled=not boton_finalizar_habilitado):
        with st.spinner("Finalizando cierre..."):
            _, err_final = database.finalizar_cierre_en_db(cierre_id)
            if err_final:
                st.error(f"Error al finalizar: {err_final}")
            else:
                st.success("¡CIERRE FINALIZADO CON ÉXITO! 🎉")
                st.balloons()
                st.session_state['cierre_actual_objeto'] = None
                st.session_state['cierre_sucursal_seleccionada_nombre'] = None
                st.session_state.pop('resumen_calculado', None) 
                
                cargar_datos_verificacion.clear()
                try:
                    cargar_gastos_registrados.clear()
                    cargar_ingresos_existentes.clear()
                except NameError:
                    pass # Los módulos no están en scope, pero está bien.
                st.rerun()


# =============================================================================
# EJECUCIÓN PRINCIPAL (El Loader y el Contenedor de Pestañas)
# =============================================================================

st.set_page_config(page_title="Cierre de Caja Operativo", layout="wide")
st.title("Espacio de Trabajo: Cierre de Caja 🧾")

# --- Funciones de Carga de Datos (Cacheadas) ---
@st.cache_data(ttl=600)
def cargar_sucursales_data():
    sucursales_data, err = database.obtener_sucursales()
    if err:
        st.error(f"No se pudieron cargar sucursales: {err}")
        return {}
    opciones = {s['sucursal']: s['id'] for s in sucursales_data}
    return opciones

# --- Lógica de Estado Principal ---
if 'cierre_actual_objeto' not in st.session_state:
    st.session_state['cierre_actual_objeto'] = None
if 'cierre_sucursal_seleccionada_nombre' not in st.session_state:
    st.session_state['cierre_sucursal_seleccionada_nombre'] = None

# --- UI: SELECCIÓN DE SUCURSAL ---
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

# --- LÓGICA DE CARGA DE CIERRE (El "Loader") ---
sucursal_id_actual = opciones_sucursal[sucursal_seleccionada_nombre]
usuario_id_actual = st.session_state['perfil']['id']

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

# === EL WIZARD DE PESTAÑAS (TABS) (VERSIÓN COMPLETA) ===
if st.session_state.get('cierre_actual_objeto'):
    st.markdown("---")
    st.header(f"Estás trabajando en: {sucursal_seleccionada_nombre}")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "PASO 1: Caja Inicial", 
        "PASO 2: Gastos", 
        "PASO 3: Ingresos Adic.", 
        "PASO 4: Resumen", 
        "PASO 5: Caja Final", 
        "PASO 6: Verificación y Finalizar" 
    ])

    with tab1: render_tab_inicial()
    with tab2: render_tab_gastos()
    with tab3: render_tab_ingresos_adic()
    with tab4: render_tab_resumen()
    with tab5: render_tab_caja_final()
    with tab6: render_tab_verificacion()
