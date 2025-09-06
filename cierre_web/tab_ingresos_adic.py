# cierre_web/tab_ingresos_adic.py

import streamlit as st
import database
from decimal import Decimal

@st.cache_data(ttl=600)
def cargar_datos_ingresos():
    """Carga los socios y métodos de pago necesarios para construir el formulario."""
    socios, err_s = database.obtener_socios()
    metodos_pago, err_mp = database.obtener_metodos_pago()
    
    if err_s or err_mp:
        return None, None, f"Error Socios: {err_s} | Error MP: {err_mp}"
    
    return socios, metodos_pago, None

@st.cache_data(ttl=15)
def cargar_ingresos_existentes(cierre_id):
    """Carga los ingresos ya registrados para pre-llenar los campos."""
    ingresos_existentes, err_ie = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
    if err_ie:
        st.error(f"Error cargando ingresos existentes: {err_ie}")
        return {}

    # Creamos un 'lookup map' (diccionario de búsqueda) para fácil acceso
    # La clave será: "socio_id::metodo_pago"
    lookup = {}
    for ingreso in ingresos_existentes:
        key = f"{ingreso['socio_id']}::{ingreso['metodo_pago']}"
        lookup[key] = float(ingreso['monto'])
    return lookup

def render_tab_ingresos_adic():
    """Renderiza el formulario de matriz para Ingresos Adicionales."""
    
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()
        
    cierre_id = cierre_actual['id']

    # --- 1. Cargar Datos ---
    socios, metodos_pago, error_carga = cargar_datos_ingresos()
    if error_carga:
        st.error(error_carga)
        st.stop()
        
    if not socios or not metodos_pago:
        st.warning("No se encontraron Socios o Métodos de Pago registrados en la base de datos.")
        st.stop()

    # Cargar los valores que ya existen en la DB para este cierre
    ingresos_lookup = cargar_ingresos_existentes(cierre_id)

    st.subheader("Registrar Ingresos Adicionales por Socio")
    st.markdown("Registre los montos recibidos por cada socio y método de pago. Use los 'expanders' (▼) para ver cada socio.")

    # --- 2. Construir el Formulario (Matriz) ---
    # Usamos un solo formulario para guardar todos los cambios a la vez
    with st.form(key="form_ingresos_adicionales"):
        
        widget_keys = [] # Lista para guardar las claves de todos los inputs que creamos

        for socio in socios:
            with st.expander(f"Socio: {socio['nombre']}"):
                
                for mp in metodos_pago:
                    socio_id = socio['id']
                    mp_nombre = mp['nombre']
                    widget_key = f"ing_{socio_id}_{mp_nombre}"
                    lookup_key = f"{socio_id}::{mp_nombre}"
                    
                    # Buscamos el valor existente para este campo
                    valor_existente = ingresos_lookup.get(lookup_key, 0.0)
                    
                    st.number_input(
                        f"Monto para {mp_nombre}:",
                        key=widget_key,
                        value=valor_existente, # Pre-llenamos el campo
                        min_value=0.0,
                        step=0.01,
                        format="%.2f"
                    )
                    # Guardamos la info necesaria para el guardado
                    widget_keys.append({
                        "widget_key": widget_key,
                        "lookup_key": lookup_key,
                        "socio_id": socio_id,
                        "mp_nombre": mp_nombre,
                        "valor_anterior": valor_existente
                    })

        submitted = st.form_submit_button("Guardar Cambios de Ingresos Adicionales", type="primary")

    # --- 3. Lógica de Guardado (POST-Formulario) ---
    if submitted:
        total_cambios = 0
        with st.spinner("Guardando ingresos..."):
            
            # Iteramos sobre todos los widgets que creamos
            for key_info in widget_keys:
                
                nuevo_valor = st.session_state[key_info['widget_key']] # Leemos el valor del input desde el estado
                valor_anterior = key_info['valor_anterior']
                
                # Comparamos si el valor cambió. Solo actualizamos la DB si hay cambios.
                if nuevo_valor != valor_anterior:
                    total_cambios += 1
                    socio_id = key_info['socio_id']
                    mp_nombre = key_info['mp_nombre']
                    
                    if valor_anterior > 0:
                        # Si ya existía un valor (incluso si el nuevo es 0), ACTUALIZAMOS
                        _, err = database.actualizar_ingreso_adicional(
                            cierre_id, socio_id, nuevo_valor, mp_nombre
                        )
                    elif nuevo_valor > 0:
                        # Si no existía (anterior=0) y el nuevo es > 0, INSERTAMOS
                        _, err = database.registrar_ingreso_adicional(
                            cierre_id, socio_id, nuevo_valor, mp_nombre, notas=""
                        )
                    else:
                        # Si anterior=0 y nuevo=0, no hacemos nada
                        err = None

                    if err:
                        st.error(f"Error guardando para {socio['nombre']}/{mp_nombre}: {err}")
                        break
        
        if total_cambios > 0:
            st.success(f"¡{total_cambios} cambios guardados con éxito!")
            # Limpiamos caché y refrescamos todo
            cargar_ingresos_existentes.clear()
            st.rerun()
        else:
            st.info("No se detectaron cambios para guardar.")