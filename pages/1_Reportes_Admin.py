            # pages/1_Reportes_Admin.py
# VERSIÓN CONSOLIDADA Y CORREGIDA (Arregla IndentationError y Deprecation Warnings)

import streamlit as st
import sys
import os
import database
import pandas as pd
from datetime import datetime
from decimal import Decimal

# --- (Bloque de ImportPath y Guardián de Seguridad - sin cambios) ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)

if not st.session_state.get("autenticado"):
    st.error("Acceso denegado...")
    st.stop() 
if st.session_state.get("perfil", {}).get("rol") != 'admin':
    st.error("Acceso denegado...")
    st.stop()
# ------------------------------------

st.set_page_config(page_title="Reportes de Cierre", layout="wide")
st.title("Panel de Reportes Administrativos")

# --- (Funciones de Caché para Filtros - sin cambios) ---
@st.cache_data(ttl=600) 
def cargar_filtros_data_operativo():
    sucursales_data, _ = database.obtener_sucursales()
    usuarios_data, _ = database.admin_get_lista_usuarios()
    return sucursales_data, usuarios_data

@st.cache_data(ttl=600) 
def cargar_filtros_data_cde():
    sucursales_data, _ = database.obtener_sucursales_cde()
    usuarios_data, _ = database.admin_get_lista_usuarios()
    return sucursales_data, usuarios_data

@st.cache_data(ttl=600)
def cargar_data_filtros_avanzados():
    categorias, _ = database.admin_get_todas_categorias()
    socios, _ = database.admin_get_todos_socios()
    metodos, _ = database.obtener_metodos_pago()
    return categorias, socios, metodos

# --- PESTAÑAS PRINCIPALES ---
tab_op, tab_cde, tab_agg = st.tabs([
    "📊 Reportes de Cierres (Log)", 
    "🏦 Reportes CDE (Log)",
    "📈 Reportes Agregados (Suma)"
])

# ==========================================================
# PESTAÑA 1: REPORTE OPERATIVO (Tu reporte original)
# ==========================================================
with tab_op:
    
    # --- Funciones Auxiliares del Reporte Operativo ---
    def op_mostrar_reporte_denominaciones(titulo, data_dict):
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
            # CORREGIDO: Advertencia de Deprecación
            st.dataframe(df, width='stretch', hide_index=True)
        except Exception as e:
            st.json(detalle)
            st.error(f"Error al renderizar dataframe: {e}")
            
        st.metric(label=f"TOTAL CONTADO ({titulo})", value=f"${float(total):,.2f}")

    def op_mostrar_reporte_verificacion(data_dict):
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

    def op_mostrar_reporte_gastos(cierre_id):
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
            
            # CORREGIDO: Advertencia de Deprecación
            st.dataframe(df_data, width='stretch')
            st.metric("TOTAL GASTOS", f"${total_gastos:,.2f}")
    
    def comando_reabrir_operativo(cierre_id):
        _, error = database.reabrir_cierre(cierre_id)
        if error:
            st.error(f"No se pudo reabrir el cierre: {error}")
        else:
            st.success(f"¡Cierre {cierre_id} reabierto con éxito!")
            cargar_filtros_data_operativo.clear()
            st.rerun() 

    # --- NUEVA FUNCIÓN (AÑADIDA Y CORREGIDA INDENTACIÓN) ---
    def comando_revisar_abierto(cierre_objeto, nombre_sucursal):
        """
        Guarda el objeto del cierre seleccionado en la sesión y 
        prepara al admin para "saltar" a ese cierre en la otra página.
        """
        st.session_state['admin_review_cierre_obj'] = cierre_objeto
        st.session_state['admin_review_sucursal_nombre'] = nombre_sucursal
        st.success(f"Modo Revisión (Admin) activado para: {nombre_sucursal}. Por favor, navega a la página 'Cierre de Caja' desde la barra lateral.")
        st.warning("La página de Cierre de Caja se cargará automáticamente con esta sesión abierta.")

    # --- Filtros (Operativo) ---
    sucursales_db_op, usuarios_db_op = cargar_filtros_data_operativo()
    opciones_sucursal_op = {"TODAS": None}
    for s in sucursales_db_op: opciones_sucursal_op[s['sucursal']] = s['id'] 
    opciones_usuario_op = {"TODOS": None}
    for u in usuarios_db_op: opciones_usuario_op[u['nombre']] = u['id'] 

    st.header("Filtros de Búsqueda (Operativos)")
    col_filtros1_op, col_filtros2_op = st.columns(2)
    with col_filtros1_op:
        fecha_ini_op = st.date_input("Fecha Desde", value=None, key="op_fecha_ini")
        sel_sucursal_nombre_op = st.selectbox("Sucursal (Operativa)", options=opciones_sucursal_op.keys(), key="op_sucursal")
    with col_filtros2_op:
        fecha_fin_op = st.date_input("Fecha Hasta", value=None, key="op_fecha_fin")
        sel_usuario_nombre_op = st.selectbox("Usuario", options=opciones_usuario_op.keys(), key="op_usuario")
    
    solo_disc_op = st.checkbox("Mostrar solo cierres operativos con discrepancia inicial")
    
    sucursal_id_filtrar_op = opciones_sucursal_op[sel_sucursal_nombre_op]
    usuario_id_filtrar_op = opciones_usuario_op[sel_usuario_nombre_op]

    if st.button("Buscar Cierres Operativos", type="primary"):
        str_ini_op = fecha_ini_op.strftime("%Y-%m-%d") if fecha_ini_op else None
        str_fin_op = fecha_fin_op.strftime("%Y-%m-%d") if fecha_fin_op else (datetime.now().strftime("%Y-%m-%d") if fecha_ini_op else None)
        
        cierres_op, error_op = database.admin_buscar_cierres_filtrados(
            fecha_inicio=str_ini_op, fecha_fin=str_fin_op,
            sucursal_id=sucursal_id_filtrar_op, usuario_id=usuario_id_filtrar_op,
            solo_discrepancia=solo_disc_op
        )
        
        if error_op:
            st.error(f"Error de Base de Datos: {error_op}")
        elif not cierres_op:
            st.warning("No se encontraron cierres operativos que coincidan con esos filtros.")
        else:
            st.success(f"Se encontraron {len(cierres_op)} cierres operativos.")
            
            for cierre in cierres_op:
                user_nombre = cierre.get('perfiles', {}).get('nombre', 'N/A') if cierre.get('perfiles') else 'Usuario N/A'
                suc_nombre = cierre.get('sucursales', {}).get('sucursal', 'N/A') if cierre.get('sucursales') else 'Sucursal N/A'
                titulo_expander = f"📅 {cierre['fecha_operacion']}  |  👤 {user_nombre}  |  🏠 {suc_nombre}  |  ({cierre['estado']})"
                
                with st.expander(titulo_expander):
                    tab_resumen, tab_inicial, tab_final, tab_verif, tab_gastos = st.tabs([
                        "Resumen", "Caja Inicial", "Caja Final", "Verificación", "Gastos"
                    ])
                    
                    # --- BLOQUE LÓGICO MODIFICADO (CORREGIDO INDENTACIÓN) ---
                    with tab_resumen:
                        st.subheader("Resumen del Cierre")
                        if cierre.get('estado') == 'CERRADO':
                            st.button(
                                "Reabrir este Cierre (Admin)", key=f"reabrir_{cierre['id']}", 
                                on_click=comando_reabrir_operativo, args=(cierre['id'],),
                                type="secondary"
                            )
                        elif cierre.get('estado') == 'ABIERTO':
                            st.warning("Este cierre aún está ABIERTO.")
                            st.button(
                                "Entrar a Revisar/Editar este Cierre (Admin)", key=f"revisar_{cierre['id']}",
                                on_click=comando_revisar_abierto, 
                                args=(cierre, suc_nombre,), # Pasamos el objeto cierre COMPLETO
                                type="primary"
                            )

                        st.markdown(f"**Discrepancia Inicial Detectada:** {'Sí' if cierre['discrepancia_saldo_inicial'] else 'No'}")
                        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                        col_r1.metric("Saldo Inicial (Contado)", f"${float(cierre.get('saldo_inicial_efectivo') or 0):,.2f}")
                        col_r2.metric("Saldo Final (Contado)", f"${float(cierre.get('saldo_final_efectivo') or 0):,.2f}")
                        col_r3.metric("Total a Depositar", f"${float(cierre.get('total_a_depositar') or 0):,.2f}")
                        col_r4.metric("Saldo Día Siguiente", f"${float(cierre.get('saldo_para_siguiente_dia') or 0):,.2f}")

                    with tab_inicial:
                        op_mostrar_reporte_denominaciones("Detalle de Caja Inicial", cierre.get('saldo_inicial_detalle'))
                    with tab_final:
                        op_mostrar_reporte_denominaciones("Detalle de Caja Final", cierre.get('saldo_final_detalle'))
                    with tab_verif:
                        op_mostrar_reporte_verificacion(cierre.get('verificacion_pagos_detalle'))
                    with tab_gastos:
                        op_mostrar_reporte_gastos(cierre['id'])


# ==========================================================
# PESTAÑA 2: REPORTE CDE (NUEVO MÓDULO)
# ==========================================================
with tab_cde:
    
    # --- Funciones Auxiliares del Reporte CDE ---
    def cde_mostrar_reporte_efectivo(titulo, detalle_dict, total_sistema, total_contado):
        st.subheader(titulo)
        discrepancia = Decimal(str(total_contado)) - Decimal(str(total_sistema))
        match_ok = abs(discrepancia) < Decimal('0.01')

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sistema (Pagos)", f"${float(total_sistema):,.2f}")
        col2.metric("Total Contado (Manual)", f"${float(total_contado):,.2f}")
        col3.metric("Discrepancia", f"${float(discrepancia):,.2f}", delta="CUADRADO" if match_ok else "DESCUADRE", delta_color="normal" if match_ok else "inverse")
        
        with st.expander("Ver desglose del conteo de denominaciones"):
            if not detalle_dict or not detalle_dict.get('detalle'):
                st.info("No hay datos de conteo registrados.")
            else:
                try:
                    df = pd.DataFrame.from_dict(detalle_dict.get('detalle', {}), orient='index').reset_index()
                    df.columns = ["Denominación", "Cantidad", "Subtotal"]
                    # CORREGIDO: Advertencia de Deprecación
                    st.dataframe(df, width='stretch', hide_index=True)
                except Exception:
                    st.json(detalle_dict.get('detalle'))

    def cde_mostrar_verificacion_metodos(data_dict, totales_sistema_dia):
        st.subheader("Verificación de Otros Métodos (No Efectivo)")
        if not data_dict:
            st.info("No se guardaron verificaciones manuales para otros métodos.")
            return

        for metodo, data_guardada in data_dict.items():
            # Nueva estructura de JSON: Saltamos los huérfanos/info en este reporte detallado
            if isinstance(data_guardada, dict):
                
                st.markdown(f"**Método: {metodo}**")
                total_manual = data_guardada.get('total_manual', 0.0)
                total_sistema = data_guardada.get('total_sistema', 0.0) # Usamos el total guardado en el JSON
                match_ok = data_guardada.get('match_ok', False)
                url_foto = data_guardada.get('url_foto', None)
                discrepancia = Decimal(str(total_manual)) - Decimal(str(total_sistema))
            
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Sistema (Pagos)", f"${float(total_sistema):,.2f}")
                col2.metric("Total Reportado (Manual)", f"${float(total_manual):,.2f}")
                col3.metric("Discrepancia", f"${float(discrepancia):,.2f}", delta="OK" if match_ok else "FALLO", delta_color="normal" if match_ok else "inverse")
                
                if url_foto:
                    st.markdown(f"**[Ver Foto Adjunta]({url_foto})**", unsafe_allow_html=True)
                
                st.divider()


    # --- Filtros (CDE) ---
    sucursales_db_cde, usuarios_db_cde = cargar_filtros_data_cde()
    opciones_sucursal_cde = {"TODAS": None}
    for s in sucursales_db_cde: opciones_sucursal_cde[s['sucursal']] = s['id'] 
    opciones_usuario_cde = {"TODOS": None}
    for u in usuarios_db_cde: opciones_usuario_cde[u['nombre']] = u['id'] 

    st.header("Filtros de Búsqueda (CDE)")
    col_filtros1_cde, col_filtros2_cde = st.columns(2)
    with col_filtros1_cde:
        fecha_ini_cde = st.date_input("Fecha Desde", value=None, key="cde_fecha_ini")
        sel_sucursal_nombre_cde = st.selectbox("Sucursal (CDE)", options=opciones_sucursal_cde.keys(), key="cde_sucursal")
    with col_filtros2_cde:
        fecha_fin_cde = st.date_input("Fecha Hasta", value=None, key="cde_fecha_fin")
        sel_usuario_nombre_cde = st.selectbox("Usuario", options=opciones_usuario_cde.keys(), key="cde_usuario")
    
    sucursal_id_filtrar_cde = opciones_sucursal_cde[sel_sucursal_nombre_cde]
    usuario_id_filtrar_cde = opciones_usuario_cde[sel_usuario_nombre_cde]

    if st.button("Buscar Cierres CDE", type="primary", key="btn_buscar_cde"):
        str_ini_cde = fecha_ini_cde.strftime("%Y-%m-%d") if fecha_ini_cde else None
        str_fin_cde = fecha_fin_cde.strftime("%Y-%m-%d") if fecha_fin_cde else (datetime.now().strftime("%Y-%m-%d") if fecha_ini_cde else None)
        
        cierres_cde, error_cde = database.admin_buscar_cierres_cde_filtrados(
            fecha_inicio=str_ini_cde, fecha_fin=str_fin_cde,
            sucursal_id=sucursal_id_filtrar_cde, usuario_id=usuario_id_filtrar_cde
        )

        if error_cde:
            st.error(f"Error de Base de Datos (CDE): {error_cde}")
        elif not cierres_cde:
            st.warning("No se encontraron cierres CDE que coincidan con esos filtros.")
        else:
            st.success(f"Se encontraron {len(cierres_cde)} cierres CDE.")
            
            for cierre in cierres_cde:
                user_nombre = cierre.get('perfiles', {}).get('nombre', 'N/A') if cierre.get('perfiles') else 'Usuario N/A'
                suc_nombre = cierre.get('sucursales', {}).get('sucursal', 'N/A') if cierre.get('sucursales') else 'Sucursal N/A'
                titulo_expander = f"📅 {cierre['fecha_operacion']}  |  👤 {user_nombre}  |  🏠 {suc_nombre}  |  ({cierre['estado']})"
                
                if cierre.get('discrepancia'):
                    titulo_expander += " ⚠️ CON DISCREPANCIA"

                with st.expander(titulo_expander):
                    
                    st.subheader("Resumen de Verificación CDE")
                    st.markdown(f"**Cierre Forzado por Admin:** {'Sí' if cierre.get('discrepancia') else 'No'}")
                    
                    # (No recalculamos los totales en vivo aquí, solo mostramos los datos como se guardaron)
                    # 1. Mostrar reporte de efectivo
                    cde_mostrar_reporte_efectivo(
                        "Reporte de Efectivo",
                        cierre.get('detalle_conteo_efectivo'),
                        cierre.get('total_efectivo_sistema', 0), # Usamos el total guardado
                        cierre.get('total_efectivo_contado', 0)
                    )
                    
                    st.divider()
                    
                    # 2. Mostrar reporte de otros métodos
                    # Pasamos un dict vacío para los totales en vivo ya que solo queremos mostrar los datos guardados
                    cde_mostrar_verificacion_metodos(
                        cierre.get('verificacion_metodos'),
                        {} 
                    )
# ==========================================================
# PESTAÑA 3: REPORTES AGREGADOS (COMPLETAMENTE REDISEÑADA)
# ==========================================================
with tab_agg:
    st.header("Reportes Agregados con Filtros Avanzados")
    
    # --- Cargar datos para los dropdowns de filtros ---
    sucursales_db_agg, usuarios_db_agg = cargar_filtros_data_operativo()
    categorias_db_agg, socios_db_agg, metodos_db_agg = cargar_data_filtros_avanzados()

    # --- Selector de Tipo de Reporte ---
    tipo_reporte = st.radio(
        "Seleccione el tipo de reporte:",
        ["Gastos por Categoría", "Ingresos por Socio", "Totales por Método de Pago"], # <-- NUEVA OPCIÓN
        horizontal=True,
        key="tipo_reporte_agg"
    )

    st.subheader("Filtros")
    
    # --- Filtros Comunes ---
    col_f1, col_f2, col_f3 = st.columns(3)
    fecha_ini_agg = col_f1.date_input("Fecha Desde (Opcional)", value=None, key="agg_fecha_ini")
    fecha_fin_agg = col_f2.date_input("Fecha Hasta (Opcional)", value=None, key="agg_fecha_fin")
    
    opciones_sucursal_agg = {"TODAS": None}
    for s in sucursales_db_agg: opciones_sucursal_agg[s['sucursal']] = s['id'] 
    sel_sucursal_nombre_agg = col_f3.selectbox("Filtrar por Sucursal", options=opciones_sucursal_agg.keys(), key="agg_sucursal")
    sucursal_id_filtrar_agg = opciones_sucursal_agg[sel_sucursal_nombre_agg]

    # --- Filtros Específicos y Lógica de Reporte ---
    
    if tipo_reporte == "Gastos por Categoría":
        col_g1, col_g2 = st.columns(2)
        opciones_categoria = {"TODAS": None}
        for c in categorias_db_agg: opciones_categoria[c['nombre']] = c['id']
        sel_cat_nombre = col_g1.selectbox("Filtrar por Categoría", options=opciones_categoria.keys())
        categoria_id_filtrar = opciones_categoria[sel_cat_nombre]

        opciones_usuario = {"TODOS": None}
        for u in usuarios_db_agg: opciones_usuario[u['nombre']] = u['id']
        sel_user_nombre = col_g2.selectbox("Filtrar por Usuario", options=opciones_usuario.keys())
        usuario_id_filtrar = opciones_usuario[sel_user_nombre]

        if st.button("Generar Reporte de Gastos", type="primary"):
            str_ini = fecha_ini_agg.strftime('%Y-%m-%d') if fecha_ini_agg else None
            str_fin = fecha_fin_agg.strftime('%Y-%m-%d') if fecha_fin_agg else None
            with st.spinner("Generando reporte..."):
                data, err = database.admin_reporte_gastos_agregados(
                    fecha_inicio=str_ini, fecha_fin=str_fin, sucursal_id=sucursal_id_filtrar_agg,
                    categoria_id=categoria_id_filtrar, usuario_id=usuario_id_filtrar
                )
            st.subheader("Resultados: Gastos por Categoría")
            if err: st.error(f"Error: {err}")
            elif not data: st.warning("No se encontraron gastos para los filtros seleccionados.")
            else:
                df = pd.DataFrame(data)
                df['total_gastado'] = df['total_gastado'].astype(float)
                st.metric("Total General Gastado en el Periodo", f"${df['total_gastado'].sum():,.2f}") # <-- TOTAL MOVIDO ARRIBA
                st.dataframe(df.style.format({"total_gastado": "${:,.2f}"}), width='stretch')
                st.bar_chart(df, x='categoria_nombre', y='total_gastado')

    elif tipo_reporte == "Ingresos por Socio":
        col_i1, col_i2 = st.columns(2)
        opciones_socio = {"TODOS": None}
        for s in socios_db_agg: opciones_socio[s['nombre']] = s['id']
        sel_socio_nombre = col_i1.selectbox("Filtrar por Socio", options=opciones_socio.keys())
        socio_id_filtrar = opciones_socio[sel_socio_nombre]

        opciones_metodo = {"TODOS": None}
        for m in metodos_db_agg: opciones_metodo[m['nombre']] = m['nombre']
        sel_metodo_nombre = col_i2.selectbox("Filtrar por Método de Pago", options=opciones_metodo.keys())
        metodo_filtrar = opciones_metodo[sel_metodo_nombre]

        if st.button("Generar Reporte de Ingresos", type="primary"):
            str_ini = fecha_ini_agg.strftime('%Y-%m-%d') if fecha_ini_agg else None
            str_fin = fecha_fin_agg.strftime('%Y-%m-%d') if fecha_fin_agg else None
            with st.spinner("Generando reporte..."):
                data, err = database.admin_reporte_ingresos_socios(
                    fecha_inicio=str_ini, fecha_fin=str_fin, sucursal_id=sucursal_id_filtrar_agg,
                    socio_id=socio_id_filtrar, metodo_pago=metodo_filtrar
                )
            st.subheader("Resultados: Ingresos por Socio y Método")
            if err: st.error(f"Error: {err}")
            elif not data: st.warning("No se encontraron ingresos para los filtros seleccionados.")
            else:
                df = pd.DataFrame(data)
                df['total_ingresado'] = df['total_ingresado'].astype(float)
                st.metric("Total General Ingresado por Socios en el Periodo", f"${df['total_ingresado'].sum():,.2f}") # <-- TOTAL MOVIDO ARRIBA
                try:
                    df_pivot = df.pivot_table(index='socio_nombre', columns='metodo_pago', values='total_ingresado', aggfunc='sum', fill_value=0, margins=True, margins_name="TOTAL POR MÉTODO")
                    df_pivot['TOTAL POR SOCIO'] = df_pivot.sum(axis=1)
                    st.dataframe(df_pivot.style.format("${:,.2f}"), width='stretch')
                except Exception:
                    st.dataframe(df.style.format({"total_ingresado": "${:,.2f}"}), width='stretch')

    elif tipo_reporte == "Totales por Método de Pago":
        if st.button("Generar Reporte por Método de Pago", type="primary"):
            str_ini = fecha_ini_agg.strftime('%Y-%m-%d') if fecha_ini_agg else None
            str_fin = fecha_fin_agg.strftime('%Y-%m-%d') if fecha_fin_agg else None
            with st.spinner("Generando reporte..."):
                data, err = database.admin_reporte_metodo_pago(
                    fecha_inicio=str_ini, fecha_fin=str_fin, sucursal_id=sucursal_id_filtrar_agg
                )
            st.subheader("Resultados: Movimientos por Método de Pago")
            if err: st.error(f"Error: {err}")
            elif not data: st.warning("No se encontraron movimientos para los filtros seleccionados.")
            else:
                df = pd.DataFrame(data)
                df = df.astype({'total_ingresos': float, 'total_egresos': float, 'neto': float})
                
                # Calcular y mostrar totales generales arriba
                total_ingresos_general = df['total_ingresos'].sum()
                total_egresos_general = df['total_egresos'].sum()
                neto_general = total_ingresos_general - total_egresos_general
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Total Ingresos", f"${total_ingresos_general:,.2f}")
                col_m2.metric("Total Egresos", f"${total_egresos_general:,.2f}")
                col_m3.metric("Neto General del Periodo", f"${neto_general:,.2f}")

                st.dataframe(df.style.format({
                    "total_ingresos": "${:,.2f}", 
                    "total_egresos": "${:,.2f}", 
                    "neto": "${:,.2f}"
                }), width='stretch')
