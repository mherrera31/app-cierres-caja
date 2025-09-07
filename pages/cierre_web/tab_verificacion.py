# cierre_web/tab_verificacion.py

import streamlit as st
import database
from decimal import Decimal
import tempfile
import os

@st.cache_data(ttl=15) 
def cargar_datos_verificacion(cierre_id):
    """Carga todas las fuentes de datos necesarias para la verificación."""
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
    """Renderiza la pestaña final de Verificación y Finalización."""
    
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
    
    # --- CORRECCIÓN DE BUG (AttributeError) ---
    conteo_final_dict = cierre_actual.get('saldo_final_detalle') or {}
    saldo_fisico = Decimal(str(conteo_final_dict.get('total', 0.0)))
    # --- FIN DE LA CORRECCIÓN ---
    
    diferencia_cash = saldo_fisico - saldo_teorico
    cash_match_ok = abs(diferencia_cash) < Decimal('0.01')
    
    delta_color = "off"
    if not cash_match_ok:
        delta_color = "inverse"
    else:
        delta_color = "normal"

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
            if nombre_lower == 'efectivo':
                continue 

            nombre_display = regla_metodo['nombre']
            total_sistema = datos_verif['totales_ventas'].get(nombre_lower, Decimal('0.00'))
            
            data_guardada = saved_verification_lookup.get(nombre_lower, {})
            valor_reportado_guardado = float(data_guardada.get('total_reportado', 0.0))
            url_foto_guardada = data_guardada.get('url_foto', None)

            st.markdown(f"**Verificando: {nombre_display}**")
            cols = st.columns(3)
            cols[0].metric("Total del Sistema", f"${total_sistema:,.2f}")
            
            valor_reportado_input = cols[1].number_input(
                "Total Reportado (Voucher)",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                value=valor_reportado_guardado,
                key=f"verif_num_{nombre_lower}"
            )
            
            diff_voucher = Decimal(str(valor_reportado_input)) - total_sistema
            voucher_ok = abs(diff_voucher) < Decimal('0.01')
            if not voucher_ok:
                vouchers_match_ok = False 
                
            cols[2].metric("Diferencia", f"${diff_voucher:,.2f}", 
                           delta=f"{'OK' if voucher_ok else 'FALLO'}", 
                           delta_color="normal" if voucher_ok else "inverse")

            file_uploader = None
            if regla_metodo.get('requiere_foto_voucher', False):
                if url_foto_guardada:
                    st.markdown(f"✅ Foto Guardada: **[Ver Foto]({url_foto_guardada})**", unsafe_allow_html=True)
                else:
                    file_uploader = st.file_uploader(f"Subir foto de Voucher para {nombre_display}", type=["jpg", "jpeg", "png"], key=f"verif_file_{nombre_lower}")
            
            widget_data[nombre_lower] = {
                "file_widget": file_uploader,
                "url_guardada": url_foto_guardada
            }

            json_verificacion_con_match.append({
                "metodo": nombre_display,
                "fuente": "Ventas",
                "requiere_foto": regla_metodo.get('requiere_foto_voucher', False),
                "total_sistema": float(total_sistema),
                "total_reportado": float(valor_reportado_input),
                "match_ok": voucher_ok,
                "url_foto": None 
            })
            st.divider()

        submitted_verif = st.form_submit_button("Guardar Verificación de Pagos", type="primary")

    st.subheader("Sección 2: Registros Informativos (Sin Match Requerido)")
    json_registros_informativos = [] 

    with st.expander("Ver Pagos Huérfanos (Ventas sin regla) y Otros Ingresos"):
        
        st.markdown("**Pagos Huérfanos (Ventas)**")
        if not datos_verif['huerfanos']:
            st.caption("No hay pagos huérfanos.")
        for nombre_huerfano in datos_verif['huerfanos']:
            total_h = datos_verif['totales_ventas'].get(nombre_huerfano, Decimal('0.00'))
            if total_h > 0:
                st.metric(label=f"{nombre_huerfano.title()} (Venta)", value=f"${total_h:,.2f}") # Label añadido
                json_registros_informativos.append({
                    "metodo": nombre_huerfano.title(),
                    "fuente": "Ventas (Huérfano)",
                    "total_sistema": float(total_h)
                })

        st.markdown("**Ingresos Adicionales (No-Efectivo)**")
        ingresos_no_cash = False
        for nombre_lower, total_ing in datos_verif['totales_ing_adic'].items():
            if nombre_lower != 'efectivo' and total_ing > 0:
                ingresos_no_cash = True
                st.metric(label=f"{nombre_lower.title()} (Ingreso Adic.)", value=f"${total_ing:,.2f}") # Label añadido
                json_registros_informativos.append({
                    "metodo": nombre_lower.title(),
                    "fuente": "Ingreso Adicional",
                    "total_sistema": float(total_ing)
                })
        if not ingresos_no_cash:
             st.caption("No hay ingresos adicionales (no-efectivo).")

    if submitted_verif:
        with st.spinner("Guardando verificación y subiendo fotos (si las hay)..."):
            hubo_error_subida = False
            
            for nombre_lower, data in widget_data.items():
                archivo_subido = data["file_widget"]
                if archivo_subido is not None:
                    # Usamos un archivo temporal para guardar el archivo subido y obtener una ruta
                    with tempfile.NamedTemporaryFile(delete=False, suffix=archivo_subido.name) as tmp_file:
                        tmp_file.write(archivo_subido.getvalue())
                        ruta_temporal = tmp_file.name
                    
                    st.write(f"Subiendo foto para {nombre_lower}...")
                    url_publica, err_subida = database.subir_archivo_storage(
                        cierre_id,
                        nombre_lower, 
                        ruta_temporal
                    )
                    
                    os.remove(ruta_temporal) # Borramos el archivo temporal

                    if err_subida:
                        st.error(f"FALLO AL SUBIR FOTO para {nombre_lower}: {err_subida}")
                        hubo_error_subida = True
                    else:
                        st.success(f"Foto para {nombre_lower} subida con éxito.")
                        # Actualizamos el JSON que vamos a guardar
                        for item in json_verificacion_con_match:
                            if item['metodo'].lower() == nombre_lower:
                                item['url_foto'] = url_publica
                                break
            
            # Si una URL ya estaba guardada y no se subió una nueva, mantenemos la antigua
            for item in json_verificacion_con_match:
                if item['url_foto'] is None: 
                    url_guardada_previa = widget_data[item['metodo'].lower()].get('url_guardada')
                    if url_guardada_previa:
                        item['url_foto'] = url_guardada_previa 

            if not hubo_error_subida:
                final_data_json = {
                    "verificacion_con_match": json_verificacion_con_match,
                    "registros_informativos": json_registros_informativos
                }
                
                _, err_db = database.guardar_verificacion_pagos(cierre_id, final_data_json)
                
                if err_db:
                    st.error(f"Error al guardar datos de verificación en DB: {err_db}")
                else:
                    st.success("¡Verificación de pagos guardada con éxito!")
                    # Actualizamos el estado de la sesión
                    st.session_state.cierre_actual_objeto['verificacion_pagos_detalle'] = final_data_json
                    cargar_datos_verificacion.clear() # Limpiamos cache
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
                # Limpiamos el estado de sesión para forzar la recarga del loader en la próxima acción
                st.session_state['cierre_actual_objeto'] = None
                st.session_state['cierre_sucursal_seleccionada_nombre'] = None
                st.session_state.pop('resumen_calculado', None) 
                
                cargar_datos_verificacion.clear()
                try:
                    from cierre_web.tab_gastos import cargar_gastos_registrados
                    from cierre_web.tab_ingresos_adic import cargar_ingresos_existentes
                    cargar_gastos_registrados.clear()
                    cargar_ingresos_existentes.clear()
                except ImportError:
                    pass 
                
                st.rerun()
