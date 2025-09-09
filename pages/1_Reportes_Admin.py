            # pages/1_Reportes_Admin.py
# VERSIÓN CONSOLIDADA Y CORREGIDA (Arregla IndentationError y Deprecation Warnings)

import streamlit as st
import sys, os, database, pandas as pd
from datetime import datetime

# --- (Bloque de ImportPath y Guardián de Seguridad - sin cambios) ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
if not st.session_state.get("autenticado") or st.session_state.get("perfil", {}).get("rol") != 'admin':
    st.error("Acceso denegado.")
    st.stop()
# ------------------------------------

st.set_page_config(page_title="Reportes de Cierre", layout="wide")
st.title("Panel de Reportes Administrativos")

# --- (Funciones de Caché para Filtros - sin cambios) ---
@st.cache_data(ttl=600) 
def cargar_filtros_data_basicos():
    sucursales, _ = database.obtener_sucursales()
    usuarios, _ = database.admin_get_lista_usuarios()
    metodos, _ = database.obtener_metodos_pago()
    socios, _ = database.admin_get_todos_socios() # Necesitamos los socios para el filtro
    return sucursales, usuarios, metodos, socios

# --- PESTAÑAS PRINCIPALES ---
tab_op, tab_cde, tab_analisis = st.tabs([
    "📊 Cierres Operativos (Log)", 
    "🏦 Cierres CDE (Log)",
    "📈 Análisis de Ingresos"
])

# ==========================================================
# PESTAÑA 1: REPORTE OPERATIVO (LOG DE CIERRES)
# ==========================================================
with tab_op:
    
    # --- Funciones Auxiliares del Reporte Operativo ---
    def op_mostrar_reporte_denominaciones(titulo, data_dict):
        st.subheader(titulo)
        if not data_dict or not data_dict.get('detalle'):
            st.info("No hay datos de conteo para este paso.")
            return
        detalle = data_dict.get('detalle', {})
        total = data_dict.get('total', 0)
        try:
            df = pd.DataFrame.from_dict(detalle, orient='index').reset_index()
            df.columns = ["Denominación", "Cantidad", "Subtotal"]
            st.dataframe(df, width='stretch', hide_index=True)
        except Exception as e:
            st.json(detalle)
            st.error(f"Error al renderizar: {e}")
        st.metric(label=f"TOTAL CONTADO ({titulo})", value=f"${float(total):,.2f}")

    def op_mostrar_reporte_verificacion(data_dict):
        # ... (código sin cambios)
        st.subheader("Reporte de Verificación de Pagos")
        if not data_dict or (not data_dict.get('verificacion_con_match') and not data_dict.get('registros_informativos')):
            st.info("No hay datos de verificación guardados para este cierre.")
            return
        st.markdown("**Pagos Verificados (Match)**")
        verificados = data_dict.get('verificacion_con_match', [])
        if not verificados: st.markdown("*N/A*")
        for item in verificados:
            match_texto = "OK ✔️" if item.get('match_ok') else "FALLO ❌"
            st.markdown(f"**{item.get('metodo')}** (Fuente: *{item.get('fuente')}*)")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Sistema", f"${item.get('total_sistema', 0):,.2f}")
            col2.metric("Total Reportado", f"${item.get('total_reportado', 0):,.2f}")
            col3.metric("Estado Match", f"{match_texto}")
            url_foto = item.get('url_foto')
            if url_foto: st.markdown(f"**[Ver Foto Adjunta]({url_foto})**", unsafe_allow_html=True)
            st.divider()
        st.markdown("**Pagos Informativos (Sin Match)**")
        informativos = data_dict.get('registros_informativos', [])
        if not informativos: st.markdown("*N/A*")
        for item in informativos:
            st.markdown(f"**{item.get('metodo')}** (Fuente: *{item.get('fuente')}*)")
            st.metric(label=f"{item.get('metodo')} (Informativo)", value=f"${item.get('total_sistema', 0):,.2f}")
            st.divider()

    def op_mostrar_reporte_gastos(cierre_id):
        # ... (código sin cambios)
        st.subheader("Reporte de Gastos")
        gastos_lista, err_g = database.obtener_gastos_del_cierre(cierre_id)
        if err_g: st.error(f"Error: {err_g}")
        elif not gastos_lista: st.info("No se registraron gastos.")
        else:
            total_gastos = 0
            df_data = []
            for gasto in gastos_lista:
                nombre_cat = gasto.get('gastos_categorias', {}).get('nombre', 'N/A') if gasto.get('gastos_categorias') else 'N/A'
                monto = gasto.get('monto', 0)
                total_gastos += monto
                df_data.append({"Categoría": nombre_cat, "Monto": monto, "Notas": gasto.get('notas')})
            st.dataframe(df_data, width='stretch')
            st.metric("TOTAL GASTOS", f"${total_gastos:,.2f}")
    
    def comando_reabrir_operativo(cierre_id):
        _, error = database.reabrir_cierre(cierre_id)
        if error: st.error(f"No se pudo reabrir: {error}")
        else:
            st.success(f"¡Cierre {cierre_id} reabierto!")
            cargar_filtros_data_basicos.clear()
            st.rerun() 

    def comando_revisar_abierto(cierre_objeto, nombre_sucursal):
        st.session_state['admin_review_cierre_obj'] = cierre_objeto
        st.session_state['admin_review_sucursal_nombre'] = nombre_sucursal
        st.success(f"Modo Revisión activado para: {nombre_sucursal}. Navega a 'Cierre de Caja'.")
    
    # --- Filtros (Operativo) ---
    st.header("Log de Cierres de Caja Operativos")
    sucursales_db_op, usuarios_db_op, _, _ = cargar_filtros_data_basicos() # <-- LLAMADA CORREGIDA
    opciones_sucursal_op = {"TODAS": None, **{s['sucursal']: s['id'] for s in sucursales_db_op}}
    opciones_usuario_op = {"TODOS": None, **{u['nombre']: u['id'] for u in usuarios_db_op}}

    col_filtros1_op, col_filtros2_op = st.columns(2)
    with col_filtros1_op:
        fecha_ini_op = st.date_input("Fecha Desde", value=None, key="op_fecha_ini")
        sel_sucursal_nombre_op = st.selectbox("Sucursal (Operativa)", options=opciones_sucursal_op.keys(), key="op_sucursal")
    with col_filtros2_op:
        fecha_fin_op = st.date_input("Fecha Hasta", value=None, key="op_fecha_fin")
        sel_usuario_nombre_op = st.selectbox("Usuario", options=opciones_usuario_op.keys(), key="op_usuario")
    
    solo_disc_op = st.checkbox("Mostrar solo cierres con discrepancia inicial")
    
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
# PESTAÑA 3: ANÁLISIS DE INGRESOS (CON FILTRO DE SOCIO)
# ==========================================================
with tab_analisis:
    st.header("Análisis de Ingresos por Cierre Verificado")
    st.info("Este reporte extrae los totales de ingresos del resumen guardado en cada cierre.")

    sucursales_db, usuarios_db, metodos_db, socios_db = cargar_filtros_data_basicos()

    st.subheader("Filtros (Todos opcionales)")
    
    col_f1, col_f2 = st.columns(2)
    fecha_ini_agg = col_f1.date_input("Fecha Desde", value=None, key="analisis_fi")
    fecha_fin_agg = col_f2.date_input("Fecha Hasta", value=None, key="analisis_ff")

    col_f3, col_f4 = st.columns(2)
    op_suc = {"TODAS": None, **{s['sucursal']: s['id'] for s in sucursales_db}}
    sel_suc_id = op_suc[col_f3.selectbox("Sucursal", options=op_suc.keys(), key="analisis_s")]
    
    op_user = {"TODOS": None, **{u['nombre']: u['id'] for u in usuarios_db}}
    sel_user_id = op_user[col_f4.selectbox("Usuario", options=op_user.keys(), key="analisis_u")]

    # --- NUEVO FILTRO DE SOCIO ---
    col_f5, col_f6 = st.columns(2)
    
    # Creamos la lista de Socios + "Ventas (POS)"
    opciones_socio_psc = {"TODOS": None, "Ventas (POS)": "ventas_pos"}
    for s in socios_db:
        opciones_socio_psc[s['nombre']] = s['id']
    
    sel_socio_llave = col_f5.selectbox("Filtrar por Socio o Ventas (POS)", options=opciones_socio_psc.keys(), key="analisis_socio")
    socio_id_filtrar = opciones_socio_psc[sel_socio_llave]

    op_metodo = {"TODOS": None, **{m['nombre']: m['nombre'] for m in metodos_db}}
    sel_metodo = op_metodo[col_f6.selectbox("Método de Pago", options=op_metodo.keys(), key="analisis_m")]

    if st.button("Generar Reporte de Ingresos", type="primary"):
        str_ini = fecha_ini_agg.strftime('%Y-%m-%d') if fecha_ini_agg else None
        str_fin = fecha_fin_agg.strftime('%Y-%m-%d') if fecha_fin_agg else None
        
        # Lógica especial para el filtro de Socio/PSC
        socio_id_param = None
        if socio_id_filtrar and socio_id_filtrar != "ventas_pos":
            socio_id_param = socio_id_filtrar
        
        with st.spinner("Generando reporte..."):
            data, err = database.admin_reporte_ingresos_json(
                fecha_inicio=str_ini, fecha_fin=str_fin,
                sucursal_id=sel_suc_id,
                usuario_id=sel_user_id,
                metodo_pago=sel_metodo,
                socio_id=socio_id_param
            )
        
        st.subheader("Resultados: Ingresos Verificados")
        if err: st.error(f"Error: {err}")
        elif not data: st.warning("No se encontraron ingresos para los filtros seleccionados.")
        else:
            df = pd.DataFrame(data).astype({'total_sistema': float})
            
            # Si el usuario filtró por "Ventas (POS)", filtramos el dataframe
            if socio_id_filtrar == "ventas_pos":
                df = df[df['fuente'].str.contains("Ventas", na=False)]

            st.metric("Total General Ingresado (Según filtros)", f"${df['total_sistema'].sum():,.2f}")
            st.dataframe(df.style.format({"total_sistema": "${:,.2f}"}), width='stretch')
            
            st.subheader("Totales por Método de Pago")
            df_grouped = df.groupby('metodo_pago')['total_sistema'].sum().sort_values(ascending=False)
            st.bar_chart(df_grouped)
