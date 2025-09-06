# cierre_web/tab_verificacion.py

import streamlit as st
import database
from decimal import Decimal
import tempfile
import os

# --- Funciones de Carga de Datos (Cacheadas) ---

@st.cache_data(ttl=15) # Cache corto. Se debe limpiar si los ingresos/pagos cambian.
def cargar_datos_verificacion(cierre_id):
    """Carga todas las fuentes de datos necesarias para la verificación."""
    pagos_ventas_raw, err_p = database.obtener_pagos_del_cierre(cierre_id)
    metodos_maestros_raw, err_m = database.obtener_metodos_pago_con_flags()
    ingresos_adic_raw, err_i = database.obtener_ingresos_adicionales_del_cierre(cierre_id)

    if err_p or err_m or err_i:
        return None, f"Error Pagos: {err_p} | Error Métodos: {err_m} | Error Ingresos: {err_i}"

    # Procesar Reglas (Métodos Maestros)
    metodos_maestros = {}
    nombres_maestros = set()
    for mp in metodos_maestros_raw:
        if mp['is_activo']:
            nombre_lower = mp['nombre'].lower()
            metodos_maestros[nombre_lower] = mp
            nombres_maestros.add(nombre_lower)

    # Procesar Pagos de Ventas (Totales Sistema)
    totales_sistema_ventas = {}
    nombres_ventas_registrados = set()
    for pago in pagos_ventas_raw:
        nombre = pago['metodo_pago']['nombre']
        nombre_lower = nombre.lower()
        monto = Decimal(str(pago['monto']))
        nombres_ventas_registrados.add(nombre_lower)
        if nombre_lower not in totales_sistema_ventas:
            totales_sistema_ventas[nombre_lower] = Decimal('0.00')
        totales_sistema_ventas[nombre_lower] += monto
            
    # Procesar Ingresos Adicionales
    totales_sistema_ing_adic = {}
    for ing in ingresos_adic_raw:
        nombre = ing['metodo_pago']
        nombre_lower = nombre.lower()
        monto = Decimal(str(ing['monto']))
        if nombre_lower not in totales_sistema_ing_adic:
            totales_sistema_ing_adic[nombre_lower] = Decimal('0.00')
        totales_sistema_ing_adic[nombre_lower] += monto

    # Identificar Huérfanos (Pagos de Venta que no están en la lista maestra)
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

    # Cargar todos los datos necesarios
    datos_verif, error = cargar_datos_verificacion(cierre_id)
    if error:
        st.error(error)
        st.stop()

    datos_guardados = cierre_actual.get('verificacion_pagos_detalle') or {}
    saved_verification_lookup = {item['metodo'].lower(): item for item in datos_guardados.get('verificacion_con_match', [])}

    # --- 1. Estado del Efectivo (Leído del Paso 4 y 5) ---
    st.subheader("Estado de Conciliación General")
    
    saldo_teorico = Decimal(str(cierre_actual.get('total_calculado_teorico', 0.0)))
    conteo_final_dict = cierre_actual.get('saldo_final_detalle', {})
    saldo_fisico = Decimal(str(conteo_final_dict.get('total', 0.0)))
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

    # --- 2. Formulario de Verificación (No-Efectivo) ---
    st.divider()
    st.subheader("Sección 1: Pagos de Ventas (Requiere Match de Voucher)")
    
    vouchers_match_ok = True # Asumimos que todo está bien hasta que encontremos un error
    json_verificacion_con_match = [] # Aquí construimos el JSON para guardar
    widget_data = {} # Para guardar los widgets de subida de archivos

    with st.form(key="form_verificacion_pagos"):
        
        for nombre_lower, regla_metodo in datos_verif['metodos_maestros'].items():
            if nombre_lower == 'efectivo':
                continue # Omitimos efectivo

            nombre_display = regla_metodo['nombre']
            total_sistema = datos_verif['totales_ventas'].get(nombre_lower, Decimal('0.00'))
            
            # Buscamos datos guardados previamente
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
            
            # Diferencia
            diff_voucher = Decimal(str(valor_reportado_input)) - total_sistema
            voucher_ok = abs(diff_voucher) < Decimal('0.01')
            if not voucher_ok:
                vouchers_match_ok = False # Si CUALQUIERA falla, el match general falla
                
            cols[2].metric("Diferencia", f"${diff_voucher:,.2f}", 
                           delta=f"{'OK' if voucher_ok else 'FALLO'}", 
                           delta_color="normal" if voucher_ok else "inverse")

            # Lógica de Foto
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

            # Construir el objeto JSON para este método
            json_verificacion_con_match.append({
                "metodo": nombre_display,
                "fuente": "Ventas",
                "requiere_foto": regla_metodo.get('requiere_foto_voucher', False),
                "total_sistema": float(total_sistema),
                "total_reportado": float(valor_reportado_input),
                "match_ok": voucher_ok,
                "url_foto": None # Se llenará en la lógica de guardado si se sube un archivo nuevo
            })
            st.divider()

        submitted_verif = st.form_submit_button("Guardar Verificación de Pagos", type="primary")

    
    # --- 3. Sección Informativa (Huérfanos e Ingresos Adic.) ---
    st.subheader("Sección 2: Registros Informativos (Sin Match Requerido)")
    json_registros_informativos = [] # Construimos la otra parte del JSON

    with st.expander("Ver Pagos Huérfanos (Ventas sin regla) y Otros Ingresos"):
        
        st.markdown("**Pagos Huérfanos (Ventas)**")
        if not datos_verif['huerfanos']:
            st.caption("No hay pagos huérfanos.")
        for nombre_huerfano in datos_verif['huerfanos']:
            total_h = datos_verif['totales_ventas'].get(nombre_huerfano, Decimal('0.00'))
            if total_h > 0:
                st.metric(f"{nombre_huerfano.title()} (Venta)", f"${total_h:,.2f}")
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
                st.metric(f"{nombre_lower.title()} (Ingreso Adic.)", f"${total_ing:,.2f}")
                json_registros_informativos.append({
                    "metodo": nombre_lower.title(),
                    "fuente": "Ingreso Adicional",
                    "total_sistema": float(total_ing)
                })
        if not ingresos_no_cash:
             st.caption("No hay ingresos adicionales (no-efectivo).")


    # --- 4. Lógica de Guardado (POST-Formulario de Verificación) ---
    if submitted_verif:
        with st.spinner("Guardando verificación y subiendo fotos (si las hay)..."):
            hubo_error_subida = False
            
            # Iterar sobre los widgets de archivo y subir fotos
            for nombre_lower, data in widget_data.items():
                archivo_subido = data["file_widget"]
                if archivo_subido is not None:
                    # Guardar el archivo temporalmente para obtener una ruta
                    with tempfile.NamedTemporaryFile(delete=False, suffix=archivo_subido.name) as tmp_file:
                        tmp_file.write(archivo_subido.getvalue())
                        ruta_temporal = tmp_file.name
                    
                    st.write(f"Subiendo foto para {nombre_lower}...")
                    url_publica, err_subida = database.subir_archivo_storage(
                        cierre_id,
                        nombre_lower, # Nombre del método como parte del path
                        ruta_temporal
                    )
                    
                    os.remove(ruta_temporal) # Borrar archivo temporal

                    if err_subida:
                        st.error(f"FALLO AL SUBIR FOTO para {nombre_lower}: {err_subida}")
                        hubo_error_subida = True
                    else:
                        st.success(f"Foto para {nombre_lower} subida con éxito.")
                        # Buscamos en nuestro JSON y actualizamos la URL
                        for item in json_verificacion_con_match:
                            if item['metodo'].lower() == nombre_lower:
                                item['url_foto'] = url_publica
                                break
            
            # Si una URL ya estaba guardada y no se subió una nueva, mantenemos la antigua
            for item in json_verificacion_con_match:
                if item['url_foto'] is None: # Si no se subió una nueva foto
                    url_guardada_previa = widget_data[item['metodo'].lower()].get('url_guardada')
                    if url_guardada_previa:
                        item['url_foto'] = url_guardada_previa # Mantener la que ya estaba

            if not hubo_error_subida:
                # Construir el JSON final
                final_data_json = {
                    "verificacion_con_match": json_verificacion_con_match,
                    "registros_informativos": json_registros_informativos
                }
                
                # Guardar en DB
                _, err_db = database.guardar_verificacion_pagos(cierre_id, final_data_json)
                
                if err_db:
                    st.error(f"Error al guardar datos de verificación en DB: {err_db}")
                else:
                    st.success("¡Verificación de pagos guardada con éxito!")
                    # Actualizar el estado de sesión y recargar
                    st.session_state.cierre_actual_objeto['verificacion_pagos_detalle'] = final_data_json
                    cargar_datos_verificacion.clear() # Limpiar cache
                    st.rerun()

    # --- 5. Lógica del Botón FINALIZAR CIERRE ---
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


    # Mostrar el botón (habilitado o deshabilitado)
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
                # (El usuario tendrá que refrescar o volver a seleccionar sucursal para empezar de nuevo)