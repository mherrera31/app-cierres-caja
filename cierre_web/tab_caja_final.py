# cierre_web/tab_caja_final.py

import streamlit as st
import database
from decimal import Decimal

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
    
    # --- CORRECCIÓN DE BUG (AttributeError) ---
    datos_saldo_final_guardado = cierre_actual.get('saldo_final_detalle') or {}
    detalle_guardado = datos_saldo_final_guardado.get('detalle', {})
    # --- FIN DE LA CORRECCIÓN ---

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
    if diferencia > Decimal('0.01'):
        delta_color = "inverse" 
    elif diferencia < Decimal('-0.01'):
        delta_color = "inverse" 
    else:
        delta_color = "normal" 

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
                    "cantidad": data['cantidad'],
                    "subtotal": subtotal_float
                }
                detalle_para_calculo[nombre] = {"cantidad": data['cantidad'], "subtotal": subtotal_float}
        
        calculos = calcular_montos_finales_logica(detalle_para_calculo)
        
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
            # --- CORRECCIÓN DE BUG (Label Vacío) ---
            st.metric(label="Monto Total a Depositar:", value=f"${float(total_deposito_guardado or 0):,.2f}", label_visibility="collapsed") 

    with col_res2:
        with st.container(border=True):
            st.subheader("Saldo para Mañana (Caja Chica)")
            detalle_saldo_sig = saldo_sig_guardado.get('detalle', {})
            if not detalle_saldo_sig:
                st.write("Aún no calculado (Presione Guardar).")
            else:
                for den, info in detalle_saldo_sig.items():
                    st.text(f"- {den}: {info['cantidad']} (=${info['subtotal']:,.2f})")
            
            st.metric("Total Saldo Siguiente:", f"${float(saldo_sig_guardado.get('total', 0)):,.2f}")
