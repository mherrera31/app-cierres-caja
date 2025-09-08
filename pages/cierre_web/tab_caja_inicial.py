# cierre_web/tab_caja_inicial.py

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

def render_tab_inicial():
    """
    Renderiza el contenido de la pestaña "Caja Inicial", permitiendo la EDICIÓN
    del conteo inicial que ya está cargado en la sesión.
    """

    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()

    cierre_id = cierre_actual['id']

    # --- CORRECCIÓN DE BUG (AttributeError) ---
    datos_saldo_inicial_guardado = cierre_actual.get('saldo_inicial_detalle') or {}
    detalle_guardado = datos_saldo_inicial_guardado.get('detalle', {})
    # --- FIN DE LA CORRECCIÓN ---
    
    st.info("Puedes editar las cantidades de tu conteo inicial y guardar los cambios.")

    with st.form(key="form_EDITAR_conteo_inicial"):
        
        inputs_conteo = {}
        total_calculado = Decimal('0.00')

        # --- ORDEN CORREGIDO Y FORMATO DE LISTA ---
        
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

        # --- FIN DE CAMBIOS DE FORMATO ---
        
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
