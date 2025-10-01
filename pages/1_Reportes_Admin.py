# pages/1_Reportes_Admin.py
# VERSIÓN CONSOLIDADA Y CORREGIDA (Arregla IndentationError y Deprecation Warnings)

import streamlit as st
import sys
import os
import database
import pandas as pd
from datetime import datetime
from decimal import Decimal
import json

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

# --- BLOQUE DE CORRECCIÓN DE IMPORTPATH ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
# --- FIN DEL BLOQUE ---

# --- GUARDIÁN DE SEGURIDAD (ADMIN) ---
if not st.session_state.get("autenticado") or st.session_state.get("perfil", {}).get("rol") != 'admin':
    st.error("Acceso denegado. Esta sección es solo para administradores. 🔒")
    st.stop()
# ------------------------------------

st.set_page_config(page_title="Reportes de Cierre", layout="wide")
st.title("Panel de Reportes Administrativos")

# --- FUNCIONES DE CACHÉ PARA CARGAR DATOS DE FILTROS ---
@st.cache_data(ttl=600) 
def cargar_filtros_data_basicos():
    sucursales, _ = database.obtener_sucursales()
    usuarios, _ = database.admin_get_lista_usuarios()
    metodos, _ = database.obtener_metodos_pago()
    socios, _ = database.admin_get_todos_socios()
    categorias, _ = database.admin_get_todas_categorias()
    return sucursales, usuarios, metodos, socios, categorias

@st.cache_data(ttl=600) 
def cargar_filtros_data_cde():
    sucursales, _ = database.obtener_sucursales_cde()
    usuarios, _ = database.admin_get_lista_usuarios()
    return sucursales, usuarios

# --- PESTAÑAS PRINCIPALES ---
tab_op, tab_cde, tab_analisis, tab_gastos, tab_delivery = st.tabs([
    "📊 Cierres Operativos (Log)", 
    "🏦 Cierres CDE (Log)",
    "📈 Análisis de Ingresos",
    "💸 Reporte de Gastos",
    "🛵 Reporte de Delivery"
])

# ==========================================================
# PESTAÑA 1: REPORTE OPERATIVO (LOG DE CIERRES)
# ==========================================================
with tab_op:
    st.header("Log de Cierres de Caja Operativos")

    # --- NUEVAS FUNCIONES AUXILIARES DE REPORTE ---
            
    def op_mostrar_reporte_denominaciones(titulo, data_dict):
        st.subheader(titulo)
        if not data_dict or not data_dict.get('detalle'):
            st.info("No hay datos de conteo para este paso.")
            return
        df_data = [{"Denominación": k, "Cantidad": v.get('cantidad'), "Subtotal": v.get('subtotal')} for k, v in data_dict.get('detalle', {}).items()]
        df = pd.DataFrame(df_data)
        st.dataframe(df, hide_index=True, width='stretch') # CORREGIDO
        st.metric(label=f"TOTAL CONTADO ({titulo})", value=f"${float(data_dict.get('total', 0)):,.2f}")

    def op_mostrar_reporte_ingresos_adic(cierre_id):
        st.subheader("Reporte de Ingresos Adicionales")
        ingresos_lista, err = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
        if err:
            st.error(f"Error: {err}")
        elif not ingresos_lista:
            st.info("No se registraron ingresos adicionales.")
        else:
            df_data = [{
                "Socio": i.get('socios', {}).get('nombre', 'N/A'),
                "Método": i.get('metodo_pago', 'N/A'),
                "Monto": float(i.get('monto', 0)),
                "Notas": i.get('notas', '')
            } for i in ingresos_lista]
            df = pd.DataFrame(df_data)
            st.metric("TOTAL INGRESOS ADICIONALES", f"${df['Monto'].sum():,.2f}")
            st.dataframe(df.style.format({"Monto": "${:,.2f}"}), hide_index=True, width='stretch') # CORREGIDO

    def op_mostrar_reporte_delivery(cierre_id):
        st.subheader("Reporte de Deliveries")
        deliveries_lista, err = database.obtener_deliveries_del_cierre(cierre_id)
        if err:
            st.error(f"Error: {err}")
        elif not deliveries_lista:
            st.info("No se registraron deliveries.")
        else:
            df_data = []
            for d in deliveries_lista:
                cobrado = float(d.get('monto_cobrado', 0))
                costo = float(d.get('costo_repartidor', 0))
                df_data.append({
                    "Origen": d.get('origen_nombre', 'N/A'),
                    "Monto Cobrado": cobrado,
                    "Costo Repartidor": costo,
                    "Ganancia Neta": cobrado - costo,
                    "Notas": d.get('notas', '')
                })
            df = pd.DataFrame(df_data)

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Cobrado", f"${df['Monto Cobrado'].sum():,.2f}")
            col2.metric("Total Costo Repartidores", f"${df['Costo Repartidor'].sum():,.2f}")
            col3.metric("Ganancia Neta Total", f"${df['Ganancia Neta'].sum():,.2f}")

            st.dataframe(df.style.format({
                "Monto Cobrado": "${:,.2f}",
                "Costo Repartidor": "${:,.2f}",
                "Ganancia Neta": "${:,.2f}"
             }), hide_index=True, width='stretch') # CORREGIDO     

    def op_mostrar_tab_resumen(cierre_dict):
       st.subheader("Resumen del Cierre")
    
       nota_discrepancia = cierre_dict.get('nota_discrepancia')
       if nota_discrepancia:
           st.warning(f"⚠️ **Nota de Admin por Descuadre:** {nota_discrepancia}")

       if cierre_dict.get('discrepancia_saldo_inicial'):
           st.info("ℹ️ Este cierre inició con una discrepancia en el saldo inicial.")

       resumen_guardado = cierre_dict.get('resumen_del_dia')
       if not resumen_guardado:
           st.info("Mostrando datos de un cierre con formato antiguo.")
           a_depositar = float(cierre_dict.get('total_a_depositar') or 0)
           saldo_siguiente = float(cierre_dict.get('saldo_para_siguiente_dia') or 0)
           col1, col2 = st.columns(2)
           col1.metric("A Depositar", f"${a_depositar:,.2f}")
           col2.metric("Saldo para Siguiente Día", f"${saldo_siguiente:,.2f}")
           return

       depositado = float(cierre_dict.get('total_a_depositar') or 0)
       saldo_siguiente = float(cierre_dict.get('saldo_para_siguiente_dia') or 0)
       total_rayo = float(resumen_guardado.get('total_rayo_externo', 0))
    
       gastos_lista, _ = database.obtener_gastos_del_cierre(cierre_dict['id'])
       total_gastos = sum(float(g.get('monto', 0)) for g in gastos_lista) if gastos_lista else 0
    
       total_del_dia = total_rayo - total_gastos

       st.divider()
       col1, col2, col3, col4, col5 = st.columns(5)
       col1.metric("Depositado", f"${depositado:,.2f}")
       col2.metric("Saldo Día Siguiente", f"${saldo_siguiente:,.2f}")
       col3.metric("Total Rayo (Externo)", f"${total_rayo:,.2f}")
       col4.metric("Total Gastos", f"${total_gastos:,.2f}")
       col5.metric("Total del Día", f"${total_del_dia:,.2f}")
       st.divider()

       st.markdown("#### Ingresos de Rayo (POS)")
       total_rayo_externo = float(resumen_guardado.get('total_rayo_externo', 0))
       st.metric("Total General de Rayo (Externo)", f"${total_rayo_externo:,.2f}")

       desglose_rayo = resumen_guardado.get('desglose_rayo', [])
       if not desglose_rayo:
           st.caption("No se registraron ingresos de Rayo (POS).")
       else:
           with st.expander("Ver desglose de Rayo (POS) por método de pago"):
               for item in sorted(desglose_rayo, key=lambda x: x['metodo']):
                   label = f"{item['metodo']} (Interno)" if item.get('tipo') == 'interno' else item['metodo']
                   st.metric(label=label, value=f"${float(item.get('total', 0)):,.2f}")

       st.divider()
    
       st.markdown("#### Ingresos por Socios")
       totales_por_socio = resumen_guardado.get('totales_por_socio', [])
       if not totales_por_socio:
           st.info("No se encontraron ingresos de Socios para este cierre.")
       else:
           num_socios = len(totales_por_socio)
           cols = st.columns(num_socios if num_socios > 0 else 1)
        
           for i, socio_data in enumerate(sorted(totales_por_socio, key=lambda x: x['socio'])):
               with cols[i]:
                   total_socio = float(socio_data.get('total', 0))
                   st.metric(label=f"Total {socio_data.get('socio')}", value=f"${total_socio:,.2f}")
                
                   with st.expander("Ver desglose"):
                       for desglose in socio_data.get('desglose', []):
                           st.write(f"{desglose.get('metodo')}: **${float(desglose.get('total', 0)):,.2f}**")

    def op_mostrar_reporte_verificacion(data_dict):
        st.subheader("Reporte de Verificación de Pagos")
        if not data_dict:
            st.info("No hay datos de verificación guardados.")
            return

        # --- INICIO DE LA MODIFICACIÓN ---
        # 1. Mostramos la nueva sección de Verificación de Efectivo
        st.markdown("**Verificación de Efectivo**")
        verif_efectivo = data_dict.get('verificacion_efectivo')

        if not verif_efectivo:
            st.info("No hay datos guardados sobre la verificación de efectivo para este cierre (probablemente es un cierre antiguo).")
        else:
            match_ok = verif_efectivo.get('match_ok', False)
            delta_color = "normal" if match_ok else "inverse"
            delta_text = "CUADRADO" if match_ok else "DESCUADRE"
        
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Teórico (Sistema)", f"${verif_efectivo.get('total_teorico', 0):,.2f}")
            col2.metric("Total Físico (Contado)", f"${verif_efectivo.get('total_fisico', 0):,.2f}")
            col3.metric(
                "Diferencia",
                f"${verif_efectivo.get('diferencia', 0):,.2f}",
                delta=delta_text,
                delta_color=delta_color
            )
        st.divider()

        # 2. El resto de la función se mantiene, con un título actualizado
        st.markdown("**Verificación Consolidada (Otros Métodos)**")
        # --- FIN DE LA MODIFICACIÓN ---

    verificados = data_dict.get('verificacion_consolidada', [])
    if not verificados: 
        st.markdown("*No se realizaron verificaciones para otros métodos.*")
    
    for item in verificados:
        match_texto = "OK ✔️" if item.get('match_ok') else "FALLO ❌"
        st.markdown(f"**{item.get('metodo')}**")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sistema", f"${item.get('total_sistema', 0):,.2f}")
        col2.metric("Total Reportado", f"${item.get('total_reportado', 0):,.2f}")
        col3.metric("Estado", match_texto)
        if item.get('url_foto'): 
            st.markdown(f"**[Ver Foto Adjunta]({item.get('url_foto')})**")
        st.divider()

    st.markdown("**Reporte Informativo Completo (JSON)**")
    reporte_info = data_dict.get('reporte_informativo_completo', {})
    if not reporte_info: 
        st.markdown("*No hay datos informativos.*")
    else:
        with st.expander("Ver desglose informativo detallado"):
            st.json(reporte_info)

    def op_mostrar_reporte_compras(cierre_id):
       """Muestra la tabla de compras informativas registradas en el cierre."""
       st.subheader("Reporte de Compras (Informativo)")
       compras_lista, err = database.obtener_compras_del_cierre(cierre_id)
       if err:
        st.error(f"Error cargando compras: {err}")
       elif not compras_lista:
        st.info("No se registraron compras en este cierre.")
       else:
          df_data = []
          for c in compras_lista:
              calculado = float(c.get('valor_calculado', 0))
              costo = float(c.get('costo_real', 0))
              df_data.append({
                  "Valor Calculado": calculado,
                  "Costo Real": costo,
                  "Ahorro/Ganancia": calculado - costo,
                  "Notas": c.get('notas', '')
              })
          df = pd.DataFrame(df_data)

          col1, col2, col3 = st.columns(3)
          col1.metric("Total Valor Calculado", f"${df['Valor Calculado'].sum():,.2f}")
          col2.metric("Total Costo Real", f"${df['Costo Real'].sum():,.2f}")
          col3.metric("Ahorro Neto Total", f"${df['Ahorro/Ganancia'].sum():,.2f}")

          st.dataframe(df.style.format({
              "Valor Calculado": "${:,.2f}",
              "Costo Real": "${:,.2f}",
              "Ahorro/Ganancia": "${:,.2f}"
           }), hide_index=True, width='stretch')

    def op_mostrar_reporte_gastos(cierre_id):
        st.subheader("Reporte de Gastos")
        gastos_lista, err_g = database.obtener_gastos_del_cierre(cierre_id)
        if err_g: st.error(f"Error: {err_g}")
        elif not gastos_lista: st.info("No se registraron gastos.")
        else:
            df_data = [{"Categoría": g.get('gastos_categorias', {}).get('nombre', 'N/A'), "Monto": g.get('monto', 0), "Notas": g.get('notas', '')} for g in gastos_lista]
            df = pd.DataFrame(df_data)
            st.dataframe(df, hide_index=True, width='stretch') # CORREGIDO
            st.metric("TOTAL GASTOS", f"${df['Monto'].sum():,.2f}")
                    
    # --- Filtros (Operativo) ---
    sucursales_db_op, usuarios_db_op, _, _, _ = cargar_filtros_data_basicos()
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
    
    # 1. Inicializar la memoria para los resultados si no existe
    if 'cierres_operativos_resultados' not in st.session_state:
        st.session_state.cierres_operativos_resultados = None

    # 2. El botón de búsqueda ahora SOLO guarda los resultados en la memoria
    if st.button("Buscar Cierres Operativos", type="primary"):
        str_ini_op = fecha_ini_op.strftime("%Y-%m-%d") if fecha_ini_op else None
        str_fin_op = fecha_fin_op.strftime("%Y-%m-%d") if fecha_fin_op else None
        sucursal_id_filtrar_op = opciones_sucursal_op[sel_sucursal_nombre_op]
        usuario_id_filtrar_op = opciones_usuario_op[sel_usuario_nombre_op]
        
        with st.spinner("Buscando..."):
            cierres_op, error_op = database.admin_buscar_cierres_filtrados(
                fecha_inicio=str_ini_op, fecha_fin=str_fin_op,
                sucursal_id=sucursal_id_filtrar_op, usuario_id=usuario_id_filtrar_op,
                solo_discrepancia=solo_disc_op
            )
        
        if error_op:
            st.error(f"Error de DB: {error_op}")
            st.session_state.cierres_operativos_resultados = [] # Guardar lista vacía en caso de error
        else:
            st.session_state.cierres_operativos_resultados = cierres_op # Guardar resultados en memoria

    # 3. La visualización de resultados ahora ocurre FUERA del if del botón
    # Se ejecuta siempre, leyendo desde la memoria.
    if st.session_state.cierres_operativos_resultados is not None:
        if not st.session_state.cierres_operativos_resultados:
            st.warning("No se encontraron cierres operativos con esos filtros.")
        else:
            # Ahora este bucle se dibujará incluso después de presionar "Supervisar"
            for cierre in st.session_state.cierres_operativos_resultados:
                user_nombre = cierre.get('perfiles', {}).get('nombre', 'N/A')
                suc_nombre = cierre.get('sucursales', {}).get('sucursal', 'N/A')
                titulo_expander = f"📅 {cierre['fecha_operacion']} | 👤 {user_nombre} | 🏠 {suc_nombre} | ({cierre['estado']})"
                
                with st.expander(titulo_expander):
                    st.markdown("**Acciones de Administrador:**")
                    if st.button("📝 Supervisar / Editar este Cierre", key=f"edit_{cierre['id']}"):
                        cierre_a_cargar = cierre
                        if cierre['estado'] == 'CERRADO':
                            with st.spinner("Reabriendo cierre..."):
                                cierre_reabierto, err_r = database.reabrir_cierre(cierre['id'])
                                if err_r:
                                    st.error(f"No se pudo reabrir: {err_r}")
                                    st.stop()
                                cierre_a_cargar = cierre_reabierto
                        
                        st.session_state['admin_review_cierre_obj'] = cierre_a_cargar
                        st.session_state['admin_review_sucursal_nombre'] = suc_nombre
                        
                        # Esta línea ahora sí se ejecutará correctamente
                        st.switch_page("pages/5_Cierre_de_Caja.py")

                    st.divider()

                    # Las pestañas de visualización del reporte se mantienen igual
                    # 1. Añadimos la nueva pestaña "Compras"
                    t_res, t_ini, t_fin, t_verif, t_gastos, t_ing_adic, t_del, t_comp = st.tabs([
                        "Resumen", "Caja Inicial", "Caja Final", "Verificación", "Gastos",
                        "Ingresos Adic.", "Delivery", "Compras"
                    ])

                    with t_res: op_mostrar_tab_resumen(cierre)
                    with t_ini: op_mostrar_reporte_denominaciones("Detalle Caja Inicial", cierre.get('saldo_inicial_detalle'))
                    
                    # 2. Modificamos la pestaña "Caja Final" para añadir la nueva información
                    with t_fin: 
                        op_mostrar_reporte_denominaciones("Detalle Conteo Físico Final", cierre.get('saldo_final_detalle'))
                        st.divider()
                        st.subheader("Resultados Calculados")

                        col1, col2 = st.columns(2)
                        with col1:
                            # --- INICIO DE LA CORRECCIÓN ---
                            # Usamos "or 0" para manejar de forma segura el caso en que el valor sea None
                            monto_a_depositar = cierre.get('total_a_depositar') or 0
                            st.metric("Monto a Depositar", f"${float(monto_a_depositar):,.2f}")
                            # --- FIN DE LA CORRECCIÓN ---
                        
                        with col2:
                            saldo_siguiente_dict = cierre.get('saldo_siguiente_detalle', {})
                            if saldo_siguiente_dict and saldo_siguiente_dict.get('detalle'):
                                with st.expander("Ver desglose del Saldo para Día Siguiente"):
                                    # Ordenar el detalle para una mejor visualización
                                    # Usamos .get('detalle', {}).items() para seguridad
                                    items_ordenados = sorted(
                                        saldo_siguiente_dict.get('detalle', {}).items(), 
                                        key=lambda item: DENOMINACIONES[[d['nombre'] for d in DENOMINACIONES].index(item[0])]['valor']
                                    )
                                    for den, info in items_ordenados:
                                        st.text(f"- {den}: {info['cantidad']} (${info.get('subtotal', 0):,.2f})")
                            
                            # Aplicamos la misma corrección robusta aquí
                            total_saldo_siguiente = (saldo_siguiente_dict or {}).get('total') or 0
                            st.metric("Total Saldo Día Siguiente", f"${float(total_saldo_siguiente):,.2f}")

                    with t_verif: op_mostrar_reporte_verificacion(cierre.get('verificacion_pagos_detalle'))
                    with t_gastos: op_mostrar_reporte_gastos(cierre['id'])
                    with t_ing_adic: op_mostrar_reporte_ingresos_adic(cierre['id'])
                    with t_del: op_mostrar_reporte_delivery(cierre['id'])
                    
                    # 3. Llamamos a la nueva función en la nueva pestaña
                    with t_comp: op_mostrar_reporte_compras(cierre['id'])

# ==========================================================
# PESTAÑA 2: REPORTE CDE (NUEVO MÓDULO)
# ==========================================================
with tab_cde:
    st.header("Log de Cierres de Verificación CDE")
            
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
# PESTAÑA 3: ANÁLISIS DE INGRESOS
# ==========================================================
with tab_analisis:
    st.header("Análisis de Ingresos Detallado")
    @st.cache_data(ttl=300)
    def cargar_y_procesar_datos_ingresos(lista_sucursal_ids=None, fecha_inicio=None, fecha_fin=None, usuario_id=None):
        cierres, err = database.admin_buscar_resumenes_para_analisis(lista_sucursal_ids=lista_sucursal_ids, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, usuario_id=usuario_id)
        if err: st.error(f"No se pudieron cargar los datos de ingresos: {err}"); return pd.DataFrame()
        if not cierres: return pd.DataFrame()
        flat_data = []
        for cierre in cierres:
            resumen = cierre.get('resumen_del_dia', {})
            info_base = {"Fecha": cierre['fecha_operacion'], "Sucursal": cierre.get('sucursales', {}).get('sucursal', 'N/A'), "Usuario": cierre.get('perfiles', {}).get('nombre', 'N/A')}
            for item in resumen.get('desglose_rayo', []): flat_data.append({**info_base, "Fuente": "Rayo (POS)", "Metodo": item['metodo'], "Tipo": item['tipo'], "Total": item['total']})
            for socio in resumen.get('totales_por_socio', []):
                for desglose in socio.get('desglose', []): flat_data.append({**info_base, "Fuente": socio['socio'], "Metodo": desglose['metodo'], "Tipo": "externo", "Total": desglose['total']})
        df = pd.DataFrame(flat_data)
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date
            df['Total'] = pd.to_numeric(df['Total'])
        return df

    sucursales_db, usuarios_db, metodos_db, socios_db, _ = cargar_filtros_data_basicos()
    op_suc = {s['sucursal']: s['id'] for s in sucursales_db}
    op_user = {"TODOS": None, **{u['nombre']: u['id'] for u in usuarios_db}}
    
    st.subheader("Filtros")
    col1, col2 = st.columns(2)
    with col1:
        fecha_ini = st.date_input("Fecha Desde", value=None, key="analisis_fi_final")
        sel_sucursales_nombres = st.multiselect("Sucursal(es)", options=list(op_suc.keys()), key="analisis_s_final")
    with col2:
        fecha_fin = st.date_input("Fecha Hasta", value=None, key="analisis_ff_final")
        sel_usuario_nombre = st.selectbox("Usuario", options=op_user.keys(), key="analisis_u_final")
    col3, col4 = st.columns(2)
    with col3:
        sel_fuente = st.selectbox("Fuente de Ingreso", options=["TODAS"] + ["Rayo (POS)"] + [s['nombre'] for s in socios_db], key="analisis_fuente_final")
    with col4:
        sel_metodo = st.selectbox("Método de Pago", options=["TODOS"] + [m['nombre'] for m in metodos_db], key="analisis_metodo_final")

    if st.button("Generar Reporte de Ingresos", type="primary"):
        str_ini = fecha_ini.strftime('%Y-%m-%d') if fecha_ini else None
        str_fin = fecha_fin.strftime('%Y-%m-%d') if fecha_fin else None
        sucursal_ids_filtrar = [op_suc[nombre] for nombre in sel_sucursales_nombres] if sel_sucursales_nombres else None
        usuario_id_filtrar = op_user[sel_usuario_nombre]
        df_ingresos = cargar_y_procesar_datos_ingresos(lista_sucursal_ids=sucursal_ids_filtrar, fecha_inicio=str_ini, fecha_fin=str_fin, usuario_id=usuario_id_filtrar)
        if df_ingresos.empty:
            st.warning("No se encontraron ingresos con los filtros primarios seleccionados.")
        else:
            df_filtrado = df_ingresos.copy()
            if sel_fuente != "TODAS": df_filtrado = df_filtrado[df_filtrado['Fuente'] == sel_fuente]
            if sel_metodo != "TODOS": df_filtrado = df_filtrado[df_filtrado['Metodo'] == sel_metodo]
            st.divider()
            st.subheader("Resultados del Análisis")
            if df_filtrado.empty:
                st.warning("La combinación de filtros no arrojó resultados.")
            else:
                ingreso_total = df_filtrado['Total'].sum()
                total_interno = df_filtrado[df_filtrado['Tipo'] == 'interno']['Total'].sum()
                total_real = ingreso_total - total_interno
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Ingreso Total (Bruto)", f"${ingreso_total:,.2f}")
                col_m2.metric("Total Interno (Informativo)", f"${total_interno:,.2f}")
                col_m3.metric("Total Real (Externo)", f"${total_real:,.2f}")
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.markdown("**Totales por Fuente de Ingreso**")
                    st.dataframe(df_filtrado.groupby('Fuente')['Total'].sum().sort_values(ascending=False).map('${:,.2f}'.format))
                with col_t2:
                    st.markdown("**Totales por Método de Pago**")
                    st.dataframe(df_filtrado.groupby('Metodo')['Total'].sum().sort_values(ascending=False).map('${:,.2f}'.format))
                st.subheader("Ingresos por Día")
                ingresos_por_dia = df_filtrado.groupby('Fecha')['Total'].sum()
                st.bar_chart(ingresos_por_dia)
                with st.expander("Ver detalle completo de ingresos"):
                    st.dataframe(df_filtrado.style.format({"Total": "${:,.2f}"}), hide_index=True, use_container_width=True)

# ==========================================================
# PESTAÑA 4: REPORTE DE GASTOS
# ==========================================================
with tab_gastos:
    st.header("Reporteador de Gastos")
    sucursales_db_g, usuarios_db_g, _, _, categorias_db_g = cargar_filtros_data_basicos()
    op_suc_g = {s['sucursal']: s['id'] for s in sucursales_db_g}
    op_user_g = {"TODOS": None, **{u['nombre']: u['id'] for u in usuarios_db_g}}
    op_cat_g = {"TODAS": None, **{c['nombre']: c['id'] for c in categorias_db_g}}
    st.subheader("Filtros")
    colg1, colg2 = st.columns(2)
    with colg1:
        fecha_ini_g = st.date_input("Fecha Desde", value=None, key="gastos_fi")
        sel_sucursales_g = st.multiselect("Sucursal(es)", options=list(op_suc_g.keys()), key="gastos_s")
    with colg2:
        fecha_fin_g = st.date_input("Fecha Hasta", value=None, key="gastos_ff")
        sel_usuario_g = st.selectbox("Usuario", options=op_user_g.keys(), key="gastos_u")
    sel_categoria_g = st.selectbox("Categoría de Gasto", options=op_cat_g.keys(), key="gastos_c")
    if st.button("Buscar Gastos", type="primary"):
        str_ini_g = fecha_ini_g.strftime("%Y-%m-%d") if fecha_ini_g else None
        str_fin_g = fecha_fin_g.strftime("%Y-%m-%d") if fecha_fin_g else None
        sucursal_ids_g = [op_suc_g[nombre] for nombre in sel_sucursales_g] if sel_sucursales_g else None
        usuario_id_g = op_user_g[sel_usuario_g]
        categoria_id_g = op_cat_g[sel_categoria_g]
        with st.spinner("Buscando gastos..."):
            gastos, err = database.admin_buscar_gastos_filtrados(
                lista_sucursal_ids=sucursal_ids_g, fecha_inicio=str_ini_g, fecha_fin=str_fin_g,
                usuario_id=usuario_id_g, categoria_id=categoria_id_g
            )
        if err: st.error(f"Error al buscar gastos: {err}")
        elif not gastos: st.warning("No se encontraron gastos con los filtros seleccionados.")
        else:
            st.subheader("Resultados de la Búsqueda")
            df_data = []
            for g in gastos:
                df_data.append({
                    "Fecha": pd.to_datetime(g['created_at']).strftime('%Y-%m-%d %H:%M'),
                    "Usuario": g.get('perfiles', {}).get('nombre', 'N/A') if g.get('perfiles') else 'N/A',
                    "Sucursal": g.get('sucursal', 'N/A'),
                    "Categoría": g.get('gastos_categorias', {}).get('nombre', 'N/A') if g.get('gastos_categorias') else 'N/A',
                    "Monto": float(g.get('monto', 0)),
                    "Notas": g.get('notas', '')
                })
            df = pd.DataFrame(df_data)
            st.metric("Total Gastado (según filtros)", f"${df['Monto'].sum():,.2f}")
            st.dataframe(df.style.format({"Monto": "${:,.2f}"}), use_container_width=True)
            st.subheader("Total de Gastos por Categoría")
            df_grouped = df.groupby("Categoría")["Monto"].sum().sort_values(ascending=False)
            st.bar_chart(df_grouped)

# ==========================================================
# PESTAÑA 5: REPORTE DE DELIVERY
# ==========================================================
with tab_delivery:
    st.header("Reporteador de Deliveries")
    sucursales_db_d, usuarios_db_d, _, socios_db_d, _ = cargar_filtros_data_basicos()
    op_suc_d = {s['sucursal']: s['id'] for s in sucursales_db_d}
    op_user_d = {"TODOS": None, **{u['nombre']: u['id'] for u in usuarios_db_d}}
    op_origen_d = {"TODOS": None, "PSC (Venta Local)": "PSC (Venta Local)", **{s['nombre']: s['nombre'] for s in socios_db_d}}
    
    st.subheader("Filtros")
    cold1, cold2 = st.columns(2)
    with cold1:
        fecha_ini_d = st.date_input("Fecha Desde", value=None, key="delivery_fi")
        sel_sucursales_d = st.multiselect("Sucursal(es)", options=list(op_suc_d.keys()), key="delivery_s")
    with cold2:
        fecha_fin_d = st.date_input("Fecha Hasta", value=None, key="delivery_ff")
        sel_usuario_d = st.selectbox("Usuario", options=op_user_d.keys(), key="delivery_u")
    sel_origen_d = st.selectbox("Origen del Pedido", options=op_origen_d.keys(), key="delivery_o")
    if st.button("Buscar Deliveries", type="primary"):
        str_ini_d = fecha_ini_d.strftime("%Y-%m-%d") if fecha_ini_d else None
        str_fin_d = fecha_fin_d.strftime("%Y-%m-%d") if fecha_fin_d else None
        sucursal_ids_d = [op_suc_d[nombre] for nombre in sel_sucursales_d] if sel_sucursales_d else None
        usuario_id_d = op_user_d[sel_usuario_d]
        origen_nombre_d = op_origen_d[sel_origen_d]
        with st.spinner("Buscando deliveries..."):
            deliveries, err = database.admin_buscar_deliveries_filtrados(
                lista_sucursal_ids=sucursal_ids_d, fecha_inicio=str_ini_d, fecha_fin=str_fin_d,
                usuario_id=usuario_id_d, origen_nombre=origen_nombre_d
            )
        if err: st.error(f"Error al buscar deliveries: {err}")
        elif not deliveries: st.warning("No se encontraron deliveries con los filtros seleccionados.")
        else:
            st.subheader("Resultados de la Búsqueda")
            df_data = []
            for d in deliveries:
                cobrado = float(d.get('monto_cobrado', 0))
                costo = float(d.get('costo_repartidor', 0))
                df_data.append({
                    "Fecha": pd.to_datetime(d['created_at']).strftime('%Y-%m-%d %H:%M'),
                    "Usuario": d.get('perfiles', {}).get('nombre', 'N/A') if d.get('perfiles') else 'N/A',
                    "Sucursal": d.get('sucursales', {}).get('sucursal', 'N/A') if d.get('sucursales') else 'N/A',
                    "Origen": d.get('origen_nombre', 'N/A'),
                    "Monto Cobrado": cobrado,
                    "Costo Repartidor": costo,
                    "Ganancia Neta": cobrado - costo,
                    "Notas": d.get('notas', '')
                })
            df = pd.DataFrame(df_data)
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("Total Cobrado", f"${df['Monto Cobrado'].sum():,.2f}")
            col_t2.metric("Total Costo Repartidores", f"${df['Costo Repartidor'].sum():,.2f}")
            col_t3.metric("Ganancia Neta Total", f"${df['Ganancia Neta'].sum():,.2f}")
            st.dataframe(df.style.format({"Monto Cobrado": "${:,.2f}", "Costo Repartidor": "${:,.2f}", "Ganancia Neta": "${:,.2f}"}), use_container_width=True)
            st.subheader("Ganancia Neta por Origen")
            df_grouped = df.groupby("Origen")["Ganancia Neta"].sum().sort_values(ascending=False)
            st.bar_chart(df_grouped)
