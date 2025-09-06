# cierre_web/form_caja_inicial.py

import streamlit as st
import database
from decimal import Decimal

# La lista de denominaciones que definimos en la app de escritorio
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

def render_form_inicial(usuario_id, sucursal_id):
    """
    Renderiza el formulario de conteo inicial y maneja la lógica de creación del cierre en la DB.
    Devuelve el objeto del nuevo cierre si se crea exitosamente, o None si aún está esperando input.
    """
    
    st.info("No se encontró ningún cierre para hoy. Se debe crear uno nuevo.")
    st.subheader("Paso A: Conteo de Caja Inicial")
    st.markdown("Ingrese las cantidades de dinero (conteo físico) con las que inicia la caja hoy.")

    # Usamos st.form para que la página no se recargue con cada número que ponemos
    with st.form(key="form_conteo_inicial"):
        
        inputs_conteo = {}
        total_calculado = Decimal('0.00')

        st.markdown("**Billetes**")
        cols_billetes = st.columns(4)
        idx = 0
        for den in DENOMINACIONES:
            if "Billete" in den['nombre']:
                col = cols_billetes[idx % 4]
                # Usamos number_input para solo aceptar números enteros
                cantidad = col.number_input(den['nombre'], min_value=0, step=1, key=f"den_{den['nombre']}")
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado += Decimal(str(cantidad)) * Decimal(str(den['valor']))
                idx += 1

        st.markdown("**Monedas**")
        cols_monedas = st.columns(4)
        idx = 0
        for den in DENOMINACIONES:
            if "Moneda" in den['nombre']:
                col = cols_monedas[idx % 4]
                cantidad = col.number_input(den['nombre'], min_value=0, step=1, key=f"den_{den['nombre']}")
                inputs_conteo[den['nombre']] = {"cantidad": cantidad, "valor": den['valor']}
                total_calculado += Decimal(str(cantidad)) * Decimal(str(den['valor']))
                idx += 1
        
        st.divider()
        st.header(f"Total Contado Inicial: ${total_calculado:,.2f}")
        
        submitted = st.form_submit_button("Guardar y Empezar Cierre", type="primary")

    # --- Lógica de Guardado (Fuera del 'with st.form') ---
    if submitted:
        # 1. Construir el diccionario de datos como lo espera la DB
        # (Replicando la lógica de get_data() de nuestro DenominationFrame de Tkinter)
        datos_conteo_final = {"total": float(total_calculado), "detalle": {}}
        for nombre, data in inputs_conteo.items():
            if data['cantidad'] > 0:
                datos_conteo_final["detalle"][nombre] = {
                    "cantidad": data['cantidad'],
                    "subtotal": float(Decimal(str(data['cantidad'])) * Decimal(str(data['valor'])))
                }
        
        # 2. Manejar la discrepancia (si la hay)
        # Verificamos si ya hemos confirmado la discrepancia (guardado en session_state)
        if st.session_state.get('ignorar_discrepancia_flag') == True:
            marcar_discrepancia = True
            st.session_state.pop('ignorar_discrepancia_flag', None) # Limpiar flag
        else:
            marcar_discrepancia = False

        with st.spinner("Creando nuevo cierre en la base de datos..."):
            nuevo_cierre, error_db = database.iniciar_cierre_en_db(
                usuario_id, 
                sucursal_id, 
                datos_conteo_final,
                marcar_discrepancia=marcar_discrepancia
            )
        
        # 3. Manejar la respuesta de la DB
        if nuevo_cierre and error_db:
            # Este es el caso especial: El cierre se creó, PERO hay una discrepancia con el día anterior.
            # Mostramos la advertencia y los botones de confirmación.
            st.warning(f"ADVERTENCIA: {error_db}")
            st.markdown("¿Desea continuar de todas formas? (Esto marcará el cierre con una discrepancia).")
            
            col_warn1, col_warn2 = st.columns(2)
            if col_warn1.button("Sí, continuar e ignorar advertencia"):
                st.session_state['ignorar_discrepancia_flag'] = True
                st.rerun() # Volvemos a ejecutar el script, el 'submitted' se volverá a evaluar

            if col_warn2.button("No, cancelar (Corregiré el conteo)"):
                # Simplemente no hacemos nada, el formulario sigue visible
                pass
            return None # Aún no devolvemos un cierre, esperamos decisión

        elif error_db:
            # Hubo un error fatal (como el error 23505 que ya solucionamos, u otro)
            st.error(f"Error Crítico al crear cierre: {error_db}")
            return None
            
        elif nuevo_cierre:
            # ¡Éxito! El cierre se creó Y no hubo discrepancia.
            return nuevo_cierre # Devolvemos el objeto del cierre

    return None # Aún no se ha enviado el formulario