# cierre_web/tab_caja_final.py

import streamlit as st
import database
from decimal import Decimal

# Copiamos la lista de denominaciones (debe ser idéntica a la del formulario inicial)
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

def calcular_montos_finales_logica(conteo_detalle):
    """
    Esta lógica es copiada directamente de tu step_caja_final.py (Tkinter)
    para asegurar que el cálculo de "saldo siguiente" sea idéntico.
    """
    saldo_para_siguiente_dia = Decimal('0.0')
    detalle_saldo_siguiente = {}
    
    # Todas las monedas se quedan
    for den in DENOMINACIONES:
        if 'Moneda' in den['nombre']:
            cantidad_disponible = conteo_detalle.get(den['nombre'], {'cantidad': 0})['cantidad']
            if cantidad_disponible > 0:
                subtotal = Decimal(str(cantidad_disponible)) * Decimal(str(den['valor']))
                saldo_para_siguiente_dia += subtotal
                detalle_saldo_siguiente[den['nombre']] = {'cantidad': cantidad_disponible, 'subtotal': float(subtotal)}
    
    # Billetes de $1 (máximo 4)
    den_billete_1 = next((d for d in DENOMINACIONES if d['nombre'] == 'Billetes de $1'), None)
    if den_billete_1:
        cantidad_disponible_1 = conteo_detalle.get(den_billete_1['nombre'], {'cantidad': 0})['cantidad']
        cantidad_a_dejar = min(cantidad_disponible_1, 4)
        if cantidad_a_dejar > 0:
            subtotal = Decimal(str(cantidad_a_dejar)) * Decimal(str(den_billete_1['valor']))
            saldo_para_siguiente_dia += subtotal
            detalle_saldo_siguiente[den_billete_1['nombre']] = {'cantidad': cantidad_a_dejar, 'subtotal': float(subtotal)}

    # Billetes de $5 (máximo 4)
    den_billete_5 = next((d for d in DENOMINACIONES if d['nombre'] == 'Billetes de $5'), None)
    if den_billete_5:
        cantidad_disponible_5 = conteo_detalle.get(den_billete_5['nombre'], {'cantidad': 0})['cantidad']
        cantidad_a_dejar = min(cantidad_disponible_5, 4)
        if cantidad_a_dejar > 0:
            subtotal = Decimal(str(cantidad_a_dejar)) * Decimal(str(den_billete_5['valor']))
            saldo_para_siguiente_dia += subtotal
            detalle_saldo_siguiente[den_billete_5['nombre']] = {'cantidad': cantidad_a_dejar, 'subtotal': float(subtotal)}
        
    total_contado_fisico = Decimal(str(sum(d.get('subtotal', 0) for d in conteo_detalle.values())))
    total_a_depositar = total_contado_fisico - saldo_para_siguiente_dia
    
    return {
        "total_contado": float(total_contado_fisico),
        "saldo_siguiente": {"total": float(saldo_para_siguiente_dia), "detalle": detalle_saldo_siguiente},
        "total_a_depositar": float(total_a_depositar)
    }


def render_tab_caja_final():
    """
    Renderiza la pestaña de Conteo de Caja Final.
    """
    
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
        
    cierre_id = cierre_actual['id']

    # 1. Obtenemos el Saldo Teórico (calculado en PESTAÑA 4: RESUMEN)
    saldo_teorico = Decimal(str(cierre_actual.get('total_calculado_teorico', 0.0)))
    
    st.info(f"Total Teórico (calculado en Paso 4): ${saldo_teorico:,.2f}")
    st.markdown("Ingrese el conteo físico de todo el efectivo en caja para calcular la diferencia.")
    
    # Obtenemos los detalles guardados para pre-llenar el formulario (si ya se guardó antes)
    detalle_guardado = cierre_actual.get('saldo_final_detalle', {}).get('detalle', {})

    # --- 2. Formulario de Conteo Físico ---
    with st.form(key="form_conteo_final"):
        
        inputs_conteo = {}
        total_calculado_fisico = Decimal('0.00')

        st.markdown("**Billetes**")
        cols_billetes = st.columns(4)
        idx = 0
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col = cols_billetes[idx % 4]
                cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col.number_input(den['nombre'], min_value=0, step=1, value=cantidad_guardada, key=f"den_final_{den['nombre']}")
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
                idx += 1

        st.markdown("**Monedas**")
        cols_monedas = st.columns(4)
        idx = 0
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col = cols_monedas[idx % 4]
                cantidad_guardada = detalle_guardado.get(den['nombre'], {}).get('cantidad', 0)
                cantidad = col.number_input(den['nombre'], min_value=0, step=1, value=cantidad_guardada, key=f"den_final_{den['nombre']}")
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado_fisico += Decimal(str(cantidad)) * Decimal(str(den['valor']))
                idx += 1
        
        st.divider()
        st.header(f"Total Contado Físico: ${total_calculado_fisico:,.2f}")
        
        submitted_final = st.form_submit_button("Guardar Conteo Final y Calcular Depósito", type="primary")

    # --- 3. Resultados y Lógica de Guardado (POST-Formulario) ---
    st.divider()
    st.subheader("Resultados del Cierre")
    
    # Calculamos la diferencia
    diferencia = total_calculado_fisico - saldo_teorico
    
    delta_color = "off"
    if diferencia > Decimal('0.01'):
        delta_color = "inverse" # Rojo
    elif diferencia < Decimal('-0.01'):
        delta_color = "inverse" # Rojo
    else:
        delta_color = "normal" # Verde

    st.metric(
        label="DIFERENCIA DE CAJA (Físico vs. Teórico)",
        value=f"${diferencia:,.2f}",
        delta=f"{'SOBRANTE' if diferencia > 0 else 'FALTANTE' if diferencia < 0 else 'CUADRADO'}",
        delta_color=delta_color
    )

    # Si el usuario guardó el formulario, procesamos todo
    if submitted_final:
        # 1. Construir el diccionario de datos (para guardar y para calcular)
        datos_conteo_final_dict = {"total": float(total_calculado_fisico), "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                subtotal_float = float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                datos_conteo_final_dict["detalle"][nombre] = {
                    "cantidad": data['cantidad'],
                    "subtotal": subtotal_float
                }
        
        # 2. Calcular montos de depósito y saldo siguiente (Usando la lógica portada)
        calculos = calcular_montos_finales_logica(datos_conteo_final_dict['detalle'])
        
        # 3. Guardar en DB (usando la función existente)
        with st.spinner("Guardando conteo final en la base de datos..."):
            _, error_db = database.guardar_conteo_final(
                cierre_id,
                datos_conteo_final_dict,
                calculos['total_a_depositar'],
                calculos['saldo_siguiente']
            )

        if error_db:
            st.error(f"Error al guardar el conteo final: {error_db}")
        else:
            # 4. Actualizar el estado de la sesión
            st.session_state.cierre_actual_objeto['saldo_final_detalle'] = datos_conteo_final_dict
            st.session_state.cierre_actual_objeto['total_a_depositar'] = calculos['total_a_depositar']
            st.session_state.cierre_actual_objeto['saldo_siguiente_detalle'] = calculos['saldo_siguiente']
            st.session_state.cierre_actual_objeto['saldo_para_siguiente_dia'] = calculos['saldo_siguiente']['total']
            
            st.success("¡Conteo final guardado con éxito!")
            st.rerun() # Recargamos para que todo se refleje

    # 4. Mostrar Cálculos de Saldo Siguiente y Depósito
    # (Esto se muestra después de guardar, o si los datos ya existían al cargar la pestaña)
    
    saldo_sig_guardado = cierre_actual.get('saldo_siguiente_detalle', {})
    total_deposito_guardado = cierre_actual.get('total_a_depositar', 0)

    col_res1, col_res2 = st.columns(2)
    with col_res1:
        with st.container(border=True):
            st.subheader("Monto a Depositar")
            st.metric("", f"${float(total_deposito_guardado):,.2f}")

    with col_res2:
        with st.container(border=True):
            st.subheader("Saldo para Mañana (Caja Chica)")
            if not saldo_sig_guardado or not saldo_sig_guardado.get('detalle'):
                st.write("Aún no calculado (Presione Guardar).")
            else:
                for den, info in saldo_sig_guardado['detalle'].items():
                    st.text(f"- {den}: {info['cantidad']} (=${info['subtotal']:,.2f})")
            
            st.metric("Total Saldo Siguiente:", f"${float(saldo_sig_guardado.get('total', 0)):,.2f}")