# cierre_web/tab_gastos.py

import streamlit as st
import database
import pandas as pd

# Usamos cache para las categorías, no queremos llamarlas cada vez que se añade un gasto
@st.cache_data(ttl=600)
def cargar_categorias_gastos_activas():
    """
    Carga solo las categorías ACTIVAS para el formulario.
    Usa la función existente de database.py.
    """
    categorias_data, err = database.obtener_categorias_gastos()
    if err:
        st.error(f"Error cargando categorías: {err}")
        return {}, {}
    
    # Creamos un dict {Nombre: ID} para el selectbox y un set para validación
    opciones_cat = {c['nombre']: c['id'] for c in categorias_data}
    return opciones_cat

@st.cache_data(ttl=15) # Cache corto para la lista de gastos (refresca rápido)
def cargar_gastos_registrados(cierre_id):
    """Carga los gastos ya registrados para este cierre."""
    gastos_data, err = database.obtener_gastos_del_cierre(cierre_id)
    if err:
        st.error(f"Error cargando gastos registrados: {err}")
        return pd.DataFrame(), 0.0

    if not gastos_data:
        return pd.DataFrame(columns=["Categoría", "Monto", "Notas"]), 0.0

    df_data = []
    total_gastos = 0.0
    for gasto in gastos_data:
        nombre_cat = gasto.get('gastos_categorias', {}).get('nombre', 'N/A') if gasto.get('gastos_categorias') else 'N/A'
        monto = float(gasto.get('monto', 0))
        total_gastos += monto
        df_data.append({
            "Categoría": nombre_cat,
            "Monto": monto,
            "Notas": gasto.get('notas', '')
        })
    
    df = pd.DataFrame(df_data)
    return df, total_gastos

def render_tab_gastos():
    """
    Renderiza el contenido de la pestaña "Registrar Gastos".
    """
    
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()

    cierre_id = cierre_actual['id']
    usuario_id = st.session_state['perfil']['id']
    sucursal_id = cierre_actual['sucursal_id']
    sucursal_nombre = st.session_state['cierre_sucursal_seleccionada_nombre']

    # --- 1. Formulario para AÑADIR Gasto ---
    st.subheader("Registrar Nuevo Gasto en Efectivo")
    
    categorias_dict = cargar_categorias_gastos_activas()
    if not categorias_dict:
        st.error("No se encontraron categorías de gastos activas. Por favor, añada categorías en el Panel de Administración.")
        st.stop()

    with st.form(key="form_nuevo_gasto", clear_on_submit=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            categoria_nombre_sel = st.selectbox("Categoría:", options=categorias_dict.keys())
        with col2:
            monto_gasto = st.number_input("Monto ($):", min_value=0.01, step=0.01, format="%.2f")
        
        notas_gasto = st.text_input("Notas (Opcional):")
        
        submit_gasto = st.form_submit_button("Añadir Gasto", type="primary")

    # --- Lógica de Guardado (POST-Formulario) ---
    if submit_gasto:
        categoria_id_sel = categorias_dict[categoria_nombre_sel]
        
        with st.spinner("Registrando gasto..."):
            _, error_db = database.registrar_gasto(
                cierre_id=cierre_id,
                categoria_id=categoria_id_sel,
                monto=monto_gasto,
                notas=notas_gasto,
                usuario_id=usuario_id,
                sucursal_id=sucursal_id,
                sucursal_nombre=sucursal_nombre
            )
            
        if error_db:
            st.error(f"Error al registrar gasto: {error_db}")
        else:
            st.success(f"Gasto de ${monto_gasto:,.2f} en '{categoria_nombre_sel}' añadido.")
            # Limpiamos el caché de la lista de gastos para que se recargue
            cargar_gastos_registrados.clear()
            # (Streamlit refresca automáticamente el resto de la página)

    # --- 2. Lista de Gastos Registrados ---
    st.divider()
    st.subheader("Gastos Registrados en este Cierre")
    
    df_gastos, total_gastos = cargar_gastos_registrados(cierre_id)
    
    if df_gastos.empty:
        st.info("Aún no se han registrado gastos en este cierre.")
    else:
        # Mostramos la tabla de gastos
        st.dataframe(
            df_gastos,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Monto": st.column_config.NumberColumn(format="$ %.2f")
            }
        )
        st.metric(label="Total Gastado (Efectivo)", value=f"${total_gastos:,.2f}")