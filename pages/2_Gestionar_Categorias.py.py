# pages/2_Gestionar_Categorias.py

import streamlit as st
import database
import pandas as pd

# --- GUARDIÁN DE SEGURIDAD ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop() 

if st.session_state.get("perfil", {}).get("rol") != 'admin':
    st.error("Acceso denegado. Esta sección es solo para administradores. 🔒")
    st.stop()
# ------------------------------------


# --- Lógica de la Página ---

st.set_page_config(page_title="Categorías de Gastos", layout="centered")
st.title("Administrar Categorías de Gastos 🗂️")

def recargar_categorias():
    """Función para limpiar el caché y forzar la recarga de datos."""
    cargar_data_categorias.clear()

@st.cache_data(ttl=10) # Reducimos el TTL para ver cambios rápidos
def cargar_data_categorias():
    """Llama a la función de DB que ya teníamos."""
    categorias, error = database.admin_get_todas_categorias()
    if error:
        st.error(f"Error cargando categorías: {error}")
        return pd.DataFrame() 

    if not categorias:
         return pd.DataFrame(columns=["Nombre", "is_activo", "ID"])

    # Convertimos los datos a un DataFrame. ESTA VEZ traemos el booleano real.
    df_data = []
    for cat in categorias:
        df_data.append({
            "Nombre": cat['nombre'],
            "is_activo": cat['is_activo'], # Traemos el estado booleano real
            "ID": cat['id']
        })
    return pd.DataFrame(df_data)

# --- UI: Añadir Nueva Categoría ---

st.subheader("Añadir Nueva Categoría")
with st.form(key="form_nueva_cat", clear_on_submit=True):
    nuevo_nombre = st.text_input("Nombre de la nueva categoría:")
    submit_nuevo = st.form_submit_button("Crear Categoría")

if submit_nuevo:
    if not nuevo_nombre:
        st.warning("El nombre no puede estar vacío.")
    else:
        _, error = database.admin_crear_categoria(nuevo_nombre)
        if error:
            st.error(f"Error al crear: {error}")
        else:
            st.success(f"¡Categoría '{nuevo_nombre}' creada con éxito!")
            recargar_categorias()


# --- UI: Lista de Categorías Existentes ---

st.divider()
st.subheader("Categorías Existentes")

df_categorias = cargar_data_categorias()

if df_categorias.empty:
    st.info("No hay categorías registradas o no se pudieron cargar.")
else:
    # Copia del dataframe original para comparar cambios
    df_original = df_categorias.copy()

    # --- Configuración de Columnas (CORREGIDA) ---
    column_config = {
        "Nombre": st.column_config.TextColumn("Nombre Categoría", width="large", disabled=True), # Deshabilitamos edición del nombre aquí
        "ID": None, # <--- REQUISITO 1: Ocultamos la columna ID
        
        # --- REQUISITO 2: Usamos el Checkbox como un interruptor (toggle) ---
        "is_activo": st.column_config.CheckboxColumn(
            "Activa",
            help="Marca para Activar, desmarca para Desactivar.",
            default=False
        )
    }

    # Renderizar el editor de datos
    edited_df = st.data_editor(
        df_categorias,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        key="editor_categorias"
    )

    # --- Lógica de Detección de Cambios (Toggle) ---
    # Comparamos el dataframe original con el editado para ver qué cambió
    try:
        # Encuentra las filas donde el estado de "is_activo" cambió
        cambios = edited_df[df_original["is_activo"] != edited_df["is_activo"]]

        if not cambios.empty:
            # Procesamos el primer cambio detectado
            fila_cambiada = cambios.iloc[0]
            cat_id = fila_cambiada["ID"]
            cat_nombre = fila_cambiada["Nombre"]
            nuevo_estado = fila_cambiada["is_activo"] # El nuevo estado (True o False)

            if nuevo_estado == True:
                # El usuario marcó la casilla (False -> True)
                st.write(f"Activando '{cat_nombre}'...")
                _, error = database.admin_activar_categoria(cat_id)
            else:
                # El usuario desmarcó la casilla (True -> False)
                st.write(f"Desactivando '{cat_nombre}'...")
                _, error = database.admin_desactivar_categoria(cat_id)

            if error:
                 st.error(f"Error al actualizar: {error}")
            else:
                 st.success(f"Estado de '{cat_nombre}' actualizado.")
                 recargar_categorias() # Limpiamos caché
                 st.rerun() # Forzamos recarga de la página para reflejar el cambio
                 
    except Exception as e:
        st.error(f"Ocurrió un error procesando el cambio: {e}")