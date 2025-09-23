# pages/5_Cierre_de_Caja.py
# VERSIÓN CONSOLIDADA Y FINAL: Incluye Gastos (Batch Delete), Tab Delivery (Nuevo) y Tab Compras (Nuevo)

import streamlit as st
import database
import pandas as pd
from decimal import Decimal
import tempfile
import os
import json 

# --- GUARDIÁN DE SEGURIDAD (ACTUALIZADO: Bloquea al rol 'cde') ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop()

# Nueva Regla: Verificar si el rol es 'cde' y bloquearlo
rol_usuario = st.session_state.get("perfil", {}).get("rol")
if rol_usuario == 'cde':
    st.error("Acceso denegado. 🚫 Este módulo no está disponible para el rol CDE.")
    st.info("Por favor, utilice el módulo '6_Cierre_CDE'.")
    st.stop()
# ------------------------------------

# =============================================================================
# DEFINICIÓN DE CONSTANTES Y MÓDULOS (Todo lo que estaba en cierre_web/)
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

# --- Módulo: form_caja_inicial ---
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

# --- Módulo: tab_caja_inicial ---
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

# --- Módulo: tab_gastos ---
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
            st.session_state.pop('resumen_calculado', None) 
            st.rerun()

    st.divider()
    st.subheader("Gastos Registrados en este Cierre")
    df_gastos, total_gastos = cargar_gastos_registrados(cierre_id)
    
    if df_gastos.empty:
        st.info("Aún no se han registrado gastos en este cierre.")
    else:
        df_gastos["Eliminar"] = False 
        df_original = df_gastos.copy()
        
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
            width='stretch', 
            hide_index=True,
            key="editor_gastos"
        )

        # --- LÓGICA DE ELIMINACIÓN POR LOTES (BATCH DELETE) ---
        if st.button("Eliminar Gastos Seleccionados", type="primary", key="btn_eliminar_gastos"):
            
            filas_para_eliminar = edited_df_gastos[edited_df_gastos["Eliminar"] == True]
            
            if filas_para_eliminar.empty:
                st.info("No se seleccionó ningún gasto para eliminar (marca el ganchito 'Eliminar' en la fila).")
            else:
                total_a_eliminar = len(filas_para_eliminar)
                st.warning(f"Se eliminarán {total_a_eliminar} registros de gastos. Esta acción es irreversible.")
                
                errores = []
                with st.spinner(f"Eliminando {total_a_eliminar} gastos..."):
                    for index, fila in filas_para_eliminar.iterrows():
                        gasto_id = fila["ID"]
                        _, err_del = database.eliminar_gasto_caja(gasto_id)
                        if err_del:
                            errores.append(f"Gasto ID {gasto_id}: {err_del}")
                
                if errores:
                    st.error("Ocurrieron errores durante la eliminación:")
                    st.json(errores)
                else:
                    st.success(f"¡{total_a_eliminar} gastos eliminados con éxito!")
                    # Limpiar todos los cachés relevantes
                    cargar_gastos_registrados.clear()
                    st.session_state.pop('resumen_calculado', None) 
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

    # --- ESTA ES LA LÍNEA QUE DEBES AÑADIR O VERIFICAR ---
    # Filtramos la lista para incluir solo métodos activos y de tipo 'externo'
    metodos_pago_externos = [
        mp for mp in metodos_pago
        if mp.get('tipo') == 'externo' and mp.get('is_activo')
    ]
    # ----------------------------------------------------

    ingresos_lookup = cargar_ingresos_existentes(cierre_id)
    st.subheader("Registrar Ingresos Adicionales por Socio")
    st.markdown("Registre los montos recibidos por cada socio y método de pago. Use los 'expanders' (▼) para ver cada socio.")

    with st.form(key="form_ingresos_adicionales"):
        widget_keys = []
        for socio in socios:
            with st.expander(f"Socio: {socio['nombre']}"):
                # --- Y ASEGÚRATE DE USAR LA NUEVA LISTA AQUÍ ---
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
            st.session_state.pop('resumen_calculado', None) 
            st.rerun()
        else:
            st.info("No se detectaron cambios para guardar.")


# --- INICIO BLOQUE DELIVERY (NUEVO MÓDULO) ---
@st.cache_data(ttl=15) 
def cargar_deliveries_registrados(cierre_id):
    """ Carga el log de la tabla 'cierre_delivery' para el reporte de ganancias """
    delivery_data, err = database.obtener_deliveries_del_cierre(cierre_id)
    if err:
        st.error(f"Error cargando registros de delivery: {err}")
        return pd.DataFrame(), 0.0, 0.0

    if not delivery_data:
        # Columnas para el reporte de ganancias
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
            "Gasto_ID": item.get('gasto_asociado_id') # ID del gasto vinculado
        })
    
    df = pd.DataFrame(df_data)
    return df, total_cobrado_delivery, total_costo_delivery

@st.cache_data(ttl=600)
def cargar_dependencias_delivery():
    """ Carga los Socios y el ID de la Categoría "Repartidores" """
    # 1. Cargar Socios para el dropdown de Origen
    socios_data, err_s = database.obtener_socios() # Usamos la función original de socios
    if err_s:
        st.error(f"Error cargando socios: {err_s}")
    
    opciones_origen = ["PSC (Venta Local)"] + [s['nombre'] for s in socios_data] if socios_data else ["PSC (Venta Local)"]

    # 2. Cargar el ID de la categoría "Repartidores"
    repartidor_cat_id, err_cat = database.get_categoria_id_por_nombre("Repartidores")
    if err_cat or not repartidor_cat_id:
        st.error(f"ERROR CRÍTICO: {err_cat}")
        st.warning("Asegúrese de crear una categoría de gasto llamada 'Repartidores' en el módulo 'Gestionar Categorías'.")
        st.stop()
        
    return opciones_origen, repartidor_cat_id

def render_tab_delivery():
    # Cargar datos de la sesión y dependencias
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    cierre_id = cierre_actual['id']
    usuario_id = st.session_state['perfil']['id']
    sucursal_id = cierre_actual['sucursal_id']
    sucursal_nombre = st.session_state.get('cierre_sucursal_seleccionada_nombre', 'N/A')

    opciones_origen, repartidor_cat_id = cargar_dependencias_delivery()
    
    if not repartidor_cat_id:
        st.error("Detenido: No se encontró la categoría de gasto 'Repartidores'.")
        st.stop()

    st.subheader("Registrar Nuevo Delivery")
    st.info("Cada registro aquí genera un reporte de ganancia. Si el 'Costo Repartidor' es mayor a $0, se creará automáticamente un GASTO en efectivo en el 'Paso 2: Gastos' bajo la categoría 'Repartidores'.")

    with st.form(key="form_nuevo_delivery", clear_on_submit=True):
        col1, col2 = st.columns(2)
        monto_cobrado = col1.number_input("Monto Cobrado al Cliente (Informativo)", min_value=0.0, step=0.01, format="%.2f")
        costo_repartidor = col2.number_input("Costo del Repartidor (Gasto de Efectivo)", min_value=0.0, step=0.01, format="%.2f")
        
        origen_sel = st.selectbox("Origen del Pedido:", options=opciones_origen)
        notas_delivery = st.text_input("Notas (Opcional, ej: ID Pedido, Cliente)")
        
        submit_delivery = st.form_submit_button("Añadir Registro de Delivery", type="primary")

    if submit_delivery:
        with st.spinner("Registrando delivery y gasto asociado..."):
            gasto_generado_id = None
            
            # ACCIÓN 1: Si hay costo, registrar el Gasto primero.
            if costo_repartidor > 0:
                nota_gasto = f"Delivery (Origen: {origen_sel}) - {notas_delivery}"
                gasto_data, err_gasto = database.registrar_gasto(
                    cierre_id=cierre_id, 
                    categoria_id=repartidor_cat_id, 
                    monto=costo_repartidor, 
                    notas=nota_gasto,
                    usuario_id=usuario_id, 
                    sucursal_id=sucursal_id, 
                    sucursal_nombre=sucursal_nombre
                )
                if err_gasto:
                    st.error(f"Error al crear el Gasto asociado: {err_gasto}")
                    st.stop()
                gasto_generado_id = gasto_data[0]['id'] # Guardamos el ID del gasto creado
            
            # ACCIÓN 2: Registrar el log de Delivery (para el reporte de ganancias)
            _, err_delivery = database.registrar_delivery_completo(
                cierre_id, usuario_id, sucursal_id,
                monto_cobrado, costo_repartidor, origen_sel, notas_delivery,
                gasto_generado_id # Pasamos el ID del gasto (o None si el costo fue 0)
            )
                
        if err_delivery:
            st.error(f"Error al registrar el reporte de delivery: {err_delivery}")
        else:
            st.success("Delivery añadido con éxito.")
            cargar_deliveries_registrados.clear() 
            cargar_gastos_registrados.clear() # Limpiar caché de gastos también
            st.session_state.pop('resumen_calculado', None) # Invalidar caché del resumen
            st.rerun()

    # --- Mostrar la tabla de reporte de ganancias ---
    st.divider()
    st.subheader("Reporte de Ganancias: Deliveries del Día")
    df_deliveries, total_cobrado, total_costo = cargar_deliveries_registrados(cierre_id)
    
    if df_deliveries.empty:
        st.info("Aún no se han registrado deliveries en este cierre.")
    else:
        df_deliveries["Eliminar"] = False 
        df_original = df_deliveries.copy()
        
        column_config_del = {
            "ID": None, 
            "Gasto_ID": None,
            "Origen": st.column_config.TextColumn("Origen", disabled=True),
            "Cobrado": st.column_config.NumberColumn("Cobrado", format="$ %.2f", disabled=True),
            "Costo": st.column_config.NumberColumn("Costo (Gasto)", format="$ %.2f", disabled=True),
            "Ganancia": st.column_config.NumberColumn("Ganancia Neta", format="$ %.2f", disabled=True),
            "Notas": st.column_config.TextColumn("Notas", disabled=True),
            "Eliminar": st.column_config.CheckboxColumn("Eliminar", default=False, help="Elimina este registro Y el gasto en efectivo asociado de la pestaña 'Gastos'.")
        }

        edited_df_del = st.data_editor(
            df_deliveries, column_config=column_config_del,
            width='stretch', hide_index=True, key="editor_deliveries"
        )

        # Lógica de eliminación por lotes (con el botón que aprobaste)
        if st.button("Eliminar Registros Seleccionados", type="primary", key="btn_eliminar_delivery"):
            
            filas_para_eliminar = edited_df_del[edited_df_del["Eliminar"] == True]
            
            if filas_para_eliminar.empty:
                st.info("No se seleccionó ningún registro para eliminar (marca el ganchito 'Eliminar' en la fila).")
            else:
                total_a_eliminar = len(filas_para_eliminar)
                st.warning(f"Se eliminarán {total_a_eliminar} registros (y sus gastos asociados). Esta acción es irreversible.")
                
                errores = []
                with st.spinner(f"Eliminando {total_a_eliminar} registros..."):
                    for index, fila in filas_para_eliminar.iterrows():
                        del_id = fila["ID"]
                        gasto_id = fila["Gasto_ID"]
                        
                        _, err_del = database.eliminar_delivery_completo(del_id, gasto_id)
                        if err_del:
                            errores.append(f"Fila ID {del_id}: {err_del}")
                
                if errores:
                    st.error("Ocurrieron errores durante la eliminación:")
                    st.json(errores)
                else:
                    st.success(f"¡{total_a_eliminar} registros eliminados con éxito!")
                    cargar_deliveries_registrados.clear()
                    cargar_gastos_registrados.clear()
                    st.session_state.pop('resumen_calculado', None) 
                    st.rerun()

    # --- Resumen de Ganancia (Reporte) ---
    st.metric("Total Cobrado (Informativo)", f"${total_cobrado:,.2f}")
    st.metric("Total Pagado a Repartidores (Gasto)", f"${total_costo:,.2f}")
    ganancia_neta = total_cobrado - total_costo
    st.metric(
        "GANANCIA NETA DE DELIVERY", 
        f"${ganancia_neta:,.2f}",
        delta=f"{ganancia_neta:,.2f}",
        delta_color="normal" if ganancia_neta >= 0 else "inverse"
    )
# --- FIN BLOQUE DELIVERY ---


# --- INICIO BLOQUE COMPRAS (NUEVO MÓDULO INFORMATIVO) ---
@st.cache_data(ttl=15) 
def cargar_compras_registradas(cierre_id):
    """ Carga el log de la tabla 'cierre_compras' para el reporte de ganancias/ahorros """
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
            "Calculado": calculado,
            "Costo Real": costo,
            "Ahorro/Ganancia": ganancia,
            "Notas": item.get('notas', ''),
            "ID": item['id']
        })
    
    df = pd.DataFrame(df_data)
    return df, total_calculado, total_costo_real

def render_tab_compras():
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    cierre_id = cierre_actual['id']
    usuario_id = st.session_state['perfil']['id']
    sucursal_id = cierre_actual['sucursal_id']

    st.subheader("Registrar Compra (Informativo)")
    st.info("Este módulo es solo para registro y reportes. **No afecta el saldo de caja** (esos gastos deben registrarse en 'Paso 2: Gastos').")

    with st.form(key="form_nueva_compra", clear_on_submit=True):
        col1, col2 = st.columns(2)
        valor_calculado = col1.number_input("Valor Calculado/Estimado ($)", min_value=0.0, step=0.01, format="%.2f")
        costo_real = col2.number_input("Costo Real Pagado ($)", min_value=0.01, step=0.01, format="%.2f")
        notas_compra = st.text_input("Notas (Opcional, ej: Artículo, Proveedor)")
        
        submit_compra = st.form_submit_button("Añadir Registro de Compra", type="primary")

    if submit_compra:
        with st.spinner("Registrando compra..."):
            _, error_db = database.registrar_compra(
                cierre_id, usuario_id, sucursal_id, 
                valor_calculado, costo_real, notas_compra
            )
        if error_db:
            st.error(f"Error al registrar compra: {error_db}")
        else:
            st.success("Registro de compra añadido.")
            cargar_compras_registradas.clear() # Limpiar caché de compras
            st.rerun()

    # --- Mostrar la tabla de reporte ---
    st.divider()
    st.subheader("Reporte de Compras Registradas")
    df_compras, total_calc, total_costo = cargar_compras_registradas(cierre_id)
    
    if df_compras.empty:
        st.info("Aún no se han registrado compras en este cierre.")
    else:
        df_compras["Eliminar"] = False 
        
        column_config_compra = {
            "ID": None, 
            "Calculado": st.column_config.NumberColumn("Valor Calculado", format="$ %.2f", disabled=True),
            "Costo Real": st.column_config.NumberColumn("Costo Real", format="$ %.2f", disabled=True),
            "Ahorro/Ganancia": st.column_config.NumberColumn("Ahorro (Ganancia)", format="$ %.2f", disabled=True),
            "Notas": st.column_config.TextColumn("Notas", disabled=True),
            "Eliminar": st.column_config.CheckboxColumn("Eliminar", default=False)
        }

        edited_df_compra = st.data_editor(
            df_compras, column_config=column_config_compra,
            width='stretch', hide_index=True, key="editor_compras"
        )

        # Lógica de eliminación (con el botón principal que aprobaste)
        if st.button("Eliminar Compras Seleccionadas", type="primary", key="btn_eliminar_compras"):
            filas_para_eliminar = edited_df_compra[edited_df_compra["Eliminar"] == True]
            
            if filas_para_eliminar.empty:
                st.info("No se seleccionó ningún registro para eliminar.")
            else:
                total_a_eliminar = len(filas_para_eliminar)
                errores = []
                with st.spinner(f"Eliminando {total_a_eliminar} registros..."):
                    for index, fila in filas_para_eliminar.iterrows():
                        compra_id = fila["ID"]
                        _, err_del = database.eliminar_compra_registro(compra_id) # Usamos el delete simple
                        if err_del:
                            errores.append(f"Fila ID {compra_id}: {err_del}")
                
                if errores:
                    st.error("Ocurrieron errores durante la eliminación:")
                    st.json(errores)
                else:
                    st.success(f"¡{total_a_eliminar} registros eliminados con éxito!")
                    cargar_compras_registradas.clear()
                    st.rerun()

    # --- Resumen de Ganancia (Reporte) ---
    st.metric("Total Calculado (Estimado)", f"${total_calc:,.2f}")
    st.metric("Total Costo Real", f"${total_costo:,.2f}")
    ahorro_neto = total_calc - total_costo
    st.metric(
        "AHORRO NETO EN COMPRAS (GANANCIA)", 
        f"${ahorro_neto:,.2f}",
        delta=f"{ahorro_neto:,.2f}",
        delta_color="normal" if ahorro_neto >= 0 else "inverse"
    )
# --- FIN BLOQUE COMPRAS ---


# --- Módulo: tab_resumen ---
@st.cache_data(ttl=600)
def cargar_info_metodos_pago():
    """Carga todos los métodos de pago y devuelve un set con los nombres de los internos."""
    metodos, err = database.obtener_metodos_pago() # Esta es la función que ya corregimos
    if err:
        st.error(f"Error cargando info de métodos de pago: {err}")
        return set()
    
    internos = {m['nombre'] for m in metodos if m.get('tipo') == 'interno'}
    return internos

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
                reglas_socio = ingreso.get('socios') or {}
                if (metodo and metodo.lower() == 'efectivo' and 
                    reglas_socio.get('afecta_conteo_efectivo') == True):
                    monto = Decimal(str(ingreso.get('monto') or 0.0))
                    total_ingresos_adicionales_efectivo += monto
                    ingresos_adic_efectivo_lista.append(ingreso)

        # LOS GASTOS AHORA INCLUYEN AUTOMÁTICAMENTE LOS COSTOS DE DELIVERY (PLAN SIMPLIFICADO)
        gastos, err_g = database.obtener_gastos_del_cierre(cierre_id)
        total_gastos = Decimal('0.00')
        if not err_g and gastos:
            for gasto in gastos:
                total_gastos += Decimal(str(gasto.get('monto') or 0.0))

        # El cálculo vuelve a ser simple:
        total_calculado_efectivo = (saldo_inicial + total_pagos_venta_efectivo + total_ingresos_adicionales_efectivo) - total_gastos
        
        st.session_state.cierre_actual_objeto['total_calculado_teorico'] = float(total_calculado_efectivo)
        st.session_state.resumen_calculado = {
            "saldo_inicial": saldo_inicial, "total_pagos_venta_efectivo": total_pagos_venta_efectivo,
            "total_ingresos_adicionales_efectivo": total_ingresos_adicionales_efectivo,
            "total_gastos": total_gastos, "total_calculado_efectivo": total_calculado_efectivo,
            "pagos_lista": pagos_venta_efectivo_lista, "ingresos_lista": ingresos_adic_efectivo_lista,
            "gastos_lista": gastos, "cache_id": cierre_id 
        }

def render_tab_resumen():
    """
    Dashboard del Día con lógica para construir y guardar un resumen en JSON.
    """
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
    cierre_id = cierre_actual['id']

    st.subheader("Dashboard de Movimientos del Día")
    
    # Lógica de Refresco
    if st.button("🔄 Refrescar Dashboard", type="primary"):
        if 'dashboard_data' in st.session_state:
            del st.session_state['dashboard_data']
        st.session_state['guardar_resumen_flag'] = True # Activa la bandera para guardar
        st.rerun()

    # Carga de datos
    if 'dashboard_data' not in st.session_state:
        with st.spinner("Calculando totales del día..."):
            data, err = database.get_dashboard_resumen_data(cierre_id)
            if err:
                st.error(err)
                st.stop()
            st.session_state['dashboard_data'] = data
            st.session_state['guardar_resumen_flag'] = True # Activa la bandera al cargar por primera vez

    data = st.session_state['dashboard_data']
    totales_rayo = data.get('rayo', {})
    totales_socios = data.get('socios', {})
    
    st.divider()

    # --- Sección 1: Ingresos de Rayo (POS) ---
    st.markdown("### Ingresos de Rayo (POS)")
    metodos_internos = cargar_info_metodos_pago()
    total_general_rayo = sum(
        total for metodo, total in totales_rayo.items() 
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

    # --- Sección 2: Ingresos por Socios ---
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
    
    # --- BLOQUE PARA CONSTRUIR Y GUARDAR EL JSON ---
    if st.session_state.get('guardar_resumen_flag'):
        # 1. Construir el objeto JSON
        resumen_json = {
            "total_rayo_externo": float(total_general_rayo),
            "desglose_rayo": [
                {
                    "metodo": metodo,
                    "total": float(total),
                    "tipo": "interno" if metodo in metodos_internos else "externo"
                } for metodo, total in totales_rayo.items()
            ],
            "totales_por_socio": [
                {
                    "socio": socio,
                    "total": float(sum(Decimal(str(v)) for v in metodos.values())),
                    "desglose": [
                        {"metodo": m, "total": float(t)} for m, t in metodos.items()
                    ]
                } for socio, metodos in totales_socios.items()
            ]
        }
        
        # 2. Guardar en la base de datos
        _, err_save = database.guardar_resumen_del_dia(cierre_id, resumen_json)
        if err_save:
            st.error(f"No se pudo guardar el resumen: {err_save}")
        
        # 3. Desactivar la bandera para no volver a guardar hasta la próxima recarga
        del st.session_state['guardar_resumen_flag']

                    
# --- Módulo: tab_caja_final ---
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
    st.info(f"Total Teórico (calculado en Paso 5): ${saldo_teorico:,.2f}")
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
                    label=f"Input_Final_{den['nombre']}", label_visibility="collapsed", 
                    min_value=0, step=1, value=cantidad_guardada, key=f"den_final_{den['nombre']}"
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
                    label=f"Input_Final_{den['nombre']}", label_visibility="collapsed", 
                    min_value=0, step=1, value=cantidad_guardada, key=f"den_final_{den['nombre']}"
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

# --- Módulo: tab_verificacion ---
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
    set_maestros_verificables = set() # Nombres 'lower' de métodos que requieren match
    
    if metodos_maestros_raw:
        for mp in metodos_maestros_raw:
            if mp['is_activo']:
                nombre_lower = mp['nombre'].lower()
                metodos_maestros[nombre_lower] = mp
                nombres_maestros.add(nombre_lower)
                if nombre_lower != 'efectivo':
                    set_maestros_verificables.add(nombre_lower)

    # 1. Calcular totales de Ventas (POS)
    totales_sistema_consolidados = {}
    nombres_ventas_registrados = set()
    if pagos_ventas_raw:
        for pago in pagos_ventas_raw:
            if pago.get('metodo_pago') and pago.get('metodo_pago').get('nombre'):
                nombre_lower = pago['metodo_pago']['nombre'].lower()
                monto = Decimal(str(pago.get('monto', 0)))
                nombres_ventas_registrados.add(nombre_lower)
                
                if nombre_lower in set_maestros_verificables:
                    if nombre_lower not in totales_sistema_consolidados:
                        totales_sistema_consolidados[nombre_lower] = Decimal('0.00')
                    totales_sistema_consolidados[nombre_lower] += monto

    # 2. Calcular totales de Socios y AÑADIRLOS a los totales consolidados
    ingresos_informativos = [] # Lista para los ingresos que NO se suman al match
    if ingresos_adic_raw:
        for ing in ingresos_adic_raw:
            metodo_lower = (ing.get('metodo_pago') or "").lower()
            reglas_socio = ing.get('socios') or {}
            
            # LÓGICA DE CONSOLIDACIÓN:
            if (metodo_lower in set_maestros_verificables and 
                reglas_socio.get('requiere_verificacion_voucher') == True):
                
                # SÍ, este ingreso debe sumarse al match consolidado
                monto = Decimal(str(ing.get('monto', 0)))
                if metodo_lower not in totales_sistema_consolidados:
                    totales_sistema_consolidados[metodo_lower] = Decimal('0.00')
                totales_sistema_consolidados[metodo_lower] += monto
            else:
                # NO, este es un ingreso informativo (efectivo, o socio sin verificación)
                ingresos_informativos.append(ing)
            
    pagos_huerfanos = (nombres_ventas_registrados - nombres_maestros) - {'efectivo'}

    return {
        "metodos_maestros": metodos_maestros, 
        "set_maestros_verificables": set_maestros_verificables,
        "totales_consolidados": totales_sistema_consolidados, # <- EL NUEVO DICCIONARIO
        "ingresos_informativos": ingresos_informativos, # <- Los ingresos que quedaron fuera
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
    saved_verification_lookup = {}
    if datos_guardados:
        for item in datos_guardados.get('verificacion_con_match', []):
            lookup_key = item.get('lookup_key') # Usamos la lookup_key guardada
            if lookup_key:
                saved_verification_lookup[lookup_key] = item
    
    st.subheader("Estado de Conciliación General")
    # ... (El métric de Efectivo sigue igual)
    saldo_teorico = Decimal(str(cierre_actual.get('total_calculado_teorico', 0.0)))
    conteo_final_dict = cierre_actual.get('saldo_final_detalle') or {}
    saldo_fisico = Decimal(str(conteo_final_dict.get('total', 0.0)))
    diferencia_cash = saldo_fisico - saldo_teorico
    cash_match_ok = abs(diferencia_cash) < Decimal('0.01')
    delta_color = "normal" if cash_match_ok else "inverse"
    st.metric(
        label="1. ESTADO DE EFECTIVO (Diferencia de Caja Final)",
        value=f"${diferencia_cash:,.2f}",
        delta=f"{'CUADRADO' if cash_match_ok else 'DESCUADRE'}",
        delta_color=delta_color
    )
    st.divider()

    st.subheader("Sección 1: Pagos Consolidados que Requieren Match")
    st.info("Estos totales incluyen Ventas (POS) Y Cobros de Socios (Ingresos Adic.) que requieren verificación.")
    
    vouchers_match_ok = True 
    json_verificacion_con_match = [] 
    widget_data = {} 
    json_registros_informativos = [] 

    with st.form(key="form_verificacion_pagos"):
        if not datos_verif['metodos_maestros']:
             st.warning("No hay métodos de pago (reglas) cargados en la base de datos.")
        
        # 1. Iteramos sobre las REGLAS (métodos maestros), excluyendo efectivo
        for nombre_lower in datos_verif['set_maestros_verificables']:
            regla_metodo = datos_verif['metodos_maestros'][nombre_lower]
            nombre_display = regla_metodo['nombre']

            # --- LÓGICA ACTUALIZADA ---
            # Ahora solo leemos del nuevo diccionario de TOTALES CONSOLIDADOS
            total_consolidado = datos_verif['totales_consolidados'].get(nombre_lower, Decimal('0.00'))
            lookup_key = f"metodo_{nombre_lower}" # Key única para este método
            
            data_guardada = saved_verification_lookup.get(lookup_key, {})
            valor_reportado_guardado = float(data_guardada.get('total_reportado', 0.0))
            url_foto_guardada = data_guardada.get('url_foto', None)
            
            st.markdown(f"**Verificando (Total Consolidado): {nombre_display}**")
            cols_v, cols_v2, cols_v3 = st.columns(3)
            cols_v.metric("Total Sistema (Ventas + Socios)", f"${total_consolidado:,.2f}")
            valor_reportado = cols_v2.number_input(
                f"Total Reportado (Voucher {nombre_display})", min_value=0.0, step=0.01, format="%.2f",
                value=valor_reportado_guardado, key=f"verif_num_{lookup_key}"
            )
            diff_v = Decimal(str(valor_reportado)) - total_consolidado
            voucher_v_ok = abs(diff_v) < Decimal('0.01')
            if not voucher_v_ok: vouchers_match_ok = False
            
            cols_v3.metric("Diferencia", f"${diff_v:,.2f}", 
                           delta=f"{'OK' if voucher_v_ok else 'FALLO'}", 
                           delta_color="normal" if voucher_v_ok else "inverse")
            
            file_uploader_v = None
            if regla_metodo.get('requiere_foto_voucher', False):
                if url_foto_guardada:
                    st.markdown(f"✅ Foto Guardada: **[Ver Foto]({url_foto_guardada})**", unsafe_allow_html=True)
                else:
                    file_uploader_v = st.file_uploader(f"Subir foto Voucher ({nombre_display})", type=["jpg", "jpeg", "png"], key=f"verif_file_{lookup_key}")
            else:
                 st.caption(f"({nombre_display} no requiere foto obligatoria)")
            
            widget_data[lookup_key] = { "file_widget": file_uploader_v, "url_guardada": url_foto_guardada, "nombre_display": nombre_display }
            
            json_verificacion_con_match.append({
                "metodo": nombre_display, "fuente": "Consolidado (Ventas + Socios)",
                "requiere_foto": regla_metodo.get('requiere_foto_voucher', False),
                "total_sistema": float(total_consolidado), "total_reportado": float(valor_reportado),
                "match_ok": voucher_v_ok, "url_foto": None, "lookup_key": lookup_key
            })
            st.divider()

        # --- YA NO NECESITAMOS EL SEGUNDO BUCLE PARA INGRESOS ADICIONALES ---
        # (Porque ya están sumados arriba)

        submitted_verif = st.form_submit_button("Guardar Verificación de Pagos", type="primary")

    st.subheader("Sección 2: Registros Informativos")
    st.caption("Pagos Huérfanos (ventas sin regla) e Ingresos de Socios que no afectan el match (ej. Efectivo, o Socios sin 'requiere_verificacion')")
    
    with st.expander("Ver Registros Informativos"):
        
        st.markdown("**Pagos Huérfanos (Ventas)**")
        if not datos_verif['huerfanos']: st.caption("No hay pagos huérfanos.")
        for nombre_huerfano in datos_verif['huerfanos']:
            total_h = datos_verif['totales_ventas'].get(nombre_huerfano, Decimal('0.00')) # Esto sigue leyendo de ventas directas
            if total_h > 0:
                st.metric(label=f"{nombre_huerfano.title()} (Venta Huérfana)", value=f"${total_h:,.2f}")
                json_registros_informativos.append({
                    "metodo": nombre_huerfano.title(), "fuente": "Ventas (Huérfano)", "total_sistema": float(total_h)
                })

        st.markdown("**Ingresos Adicionales (Informativos)**")
        # Esto ahora solo muestra los ingresos que filtramos ANTES (ej. en efectivo)
        ingresos_informativos_lista = datos_verif.get('ingresos_informativos', [])
        if not ingresos_informativos_lista:
             st.caption("No hay ingresos adicionales informativos.")
        for ing in ingresos_informativos_lista:
            nombre_metodo = ing.get('metodo_pago', 'N/A')
            socio_nombre = ing.get('socios', {}).get('nombre', 'N/A')
            total_ing = Decimal(str(ing.get('monto', 0)))
            st.metric(label=f"{nombre_metodo} (Socio: {socio_nombre})", value=f"${total_ing:,.2f}")
            json_registros_informativos.append({
                "metodo": nombre_metodo, "fuente": f"Ingreso Adicional ({socio_nombre})", "total_sistema": float(total_ing)
            })

    # --- Lógica de Guardado (Submit) ---
    if submitted_verif:
        with st.spinner("Guardando verificación y subiendo fotos (si las hay)..."):
            hubo_error_subida = False
            for lookup_key, data in widget_data.items():
                
                archivo_subido = data["file_widget"]
                if archivo_subido is not None:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=archivo_subido.name) as tmp_file:
                        tmp_file.write(archivo_subido.getvalue())
                        ruta_temporal = tmp_file.name
                    st.write(f"Subiendo foto para {data['nombre_display']}...")
                    url_publica, err_subida = database.subir_archivo_storage(cierre_id, data['nombre_display'], ruta_temporal)
                    os.remove(ruta_temporal) 
                    if err_subida:
                        st.error(f"FALLO AL SUBIR FOTO para {data['nombre_display']}: {err_subida}")
                        hubo_error_subida = True
                    else:
                        st.success(f"Foto para {data['nombre_display']} subida con éxito.")
                        for item in json_verificacion_con_match:
                            if item.get('lookup_key') == lookup_key: 
                                item['url_foto'] = url_publica
                                break
            
            # Asignar URLs de fotos guardadas previamente si no se subió una nueva
            for item in json_verificacion_con_match:
                if item['url_foto'] is None: 
                    lookup_key = item.get('lookup_key')
                    if widget_data.get(lookup_key):
                        url_guardada_previa = widget_data[lookup_key].get('url_guardada')
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
    # --- Lógica de Finalización (Sin cambios) ---
    st.header("Finalización del Cierre")
    match_completo_ok = cash_match_ok and vouchers_match_ok
    usuario_es_admin = (rol_usuario == 'admin')
    boton_finalizar_habilitado = False
    
    if match_completo_ok: 
        boton_finalizar_habilitado = True
    elif usuario_es_admin:
        boton_finalizar_habilitado = True
        st.warning("ADMIN: El cierre presenta un DESCUADRE, pero tienes permiso para forzar la finalización.")
    else:
        boton_finalizar_habilitado = False
        razon_deshabilitado = "Finalización bloqueada: El EFECTIVO (Paso 7) o los VOUCHERS (Paso 8) no cuadran."
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
                    cargar_deliveries_registrados.clear()
                    cargar_compras_registradas.clear()
                except NameError: pass 
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

# --- INICIO DEL NUEVO CARGADOR DE REVISIÓN ADMIN ---

if 'admin_review_cierre_obj' in st.session_state and st.session_state.admin_review_cierre_obj is not None:
    
    # Si un admin saltó desde el reporte, cargamos ese cierre en la sesión
    cierre_para_revisar = st.session_state.pop('admin_review_cierre_obj') # Usamos .pop() para que se cargue solo una vez
    nombre_sucursal_revisar = st.session_state.pop('admin_review_sucursal_nombre')
    
    # Forzamos la sesión a cargar este cierre
    st.session_state['cierre_actual_objeto'] = cierre_para_revisar
    # Forzamos el selectbox a coincidir con la sucursal del cierre que estamos revisando
    st.session_state['cierre_sucursal_seleccionada_nombre'] = nombre_sucursal_revisar
    
    usuario_del_cierre = cierre_para_revisar.get('perfiles', {}).get('nombre', 'N/A') if cierre_para_revisar.get('perfiles') else 'Usuario Desconocido'
    st.warning(f"ADMIN: Estás en modo REVISIÓN/EDICIÓN para el cierre abierto de: **{usuario_del_cierre}** en **{nombre_sucursal_revisar}**.")
    
    # Limpiamos el caché del dropdown y re-ejecutamos la página
    cargar_sucursales_data.clear()
    st.rerun()

# --- FIN DEL NUEVO CARGADOR ---

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
    with tab5: render_tab_caja_final()
    with tab6: render_tab_verificacion()
