# pages/4_Gestionar_Socios.py

import streamlit as st
import sys
import os
import database
import pandas as pd
import time

# --- BLOQUE DE CORRECCIÓN DE IMPORTPATH ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)
# --- FIN DEL BLOQUE ---


# --- GUARDIÁN DE SEGURIDAD (ADMIN) ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop() 

if st.session_state.get("perfil", {}).get("rol") != 'admin':
    st.error("Acceso denegado. Esta sección es solo para administradores. 🔒")
    st.stop()
# ------------------------------------


# --- Lógica de la Página ---
st.set_page_config(page_title="Gestión de Socios", layout="wide")
st.title("Administrar Socios de Negocio 🤝")

def recargar_socios():
    cargar_data_socios.clear()

@st.cache_data(ttl=10) 
def cargar_data_socios():
    """ Carga todos los socios para el editor """
    socios, error = database.admin_get_todos_socios()
    if error:
        st.error(f"Error cargando socios: {error}")
        return pd.DataFrame() 

    if not socios:
         return pd.DataFrame(columns=["Nombre", "Afecta Efectivo", "Req. Voucher", "ID"])

    df = pd.DataFrame(socios)
    df_renamed = df.rename(columns={
        "nombre": "Nombre",
        "afecta_conteo_efectivo": "Afecta Efectivo",
        "requiere_verificacion_voucher": "Req. Voucher",
        "id": "ID"
    })
    
    df_final = df_renamed[["Nombre", "Afecta Efectivo", "Req. Voucher", "ID"]]
    df_final["Eliminar"] = False # Añadimos columna de control para borrado
    return df_final


# --- 1. AÑADIR NUEVO SOCIO ---
st.subheader("Añadir Nuevo Socio")
with st.form(key="form_nuevo_socio", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    nuevo_nombre = col1.text_input("Nombre del nuevo socio:")
    afecta_efectivo = col2.checkbox("¿Afecta Conteo de Efectivo?", value=True, help="Si se marca, los ingresos en 'Efectivo' de este socio se sumarán al conteo de caja.")
    req_voucher = col3.checkbox("¿Requiere Verificación (Voucher)?", value=False, help="Si se marca, los ingresos (no efectivo) de este socio requerirán un match/foto en el Paso 6.")
    
    submit_nuevo = st.form_submit_button("Crear Socio")

if submit_nuevo:
    if not nuevo_nombre:
        st.warning("El nombre no puede estar vacío.")
    else:
        _, error = database.admin_crear_socio(nuevo_nombre, afecta_efectivo, req_voucher)
        if error:
            st.error(f"Error al crear: {error}")
        else:
            st.success(f"¡Socio '{nuevo_nombre}' creado con éxito!")
            recargar_socios()
            st.rerun()

st.divider()

# --- 2. EDITAR O ELIMINAR SOCIOS EXISTENTES ---
st.subheader("Socios Existentes (Editar / Eliminar)")

df_socios = cargar_data_socios()

if df_socios.empty:
    st.info("No hay socios registrados.")
else:
    df_original = df_socios.copy()

    column_config = {
        "Nombre": st.column_config.TextColumn("Nombre Socio", width="large", required=True), 
        "ID": None, # Ocultamos la columna ID
        "Afecta Efectivo": st.column_config.CheckboxColumn("Afecta Efectivo", help="¿Ingresos en efectivo de este socio afectan la caja?"),
        "Req. Voucher": st.column_config.CheckboxColumn("Req. Voucher", help="¿Ingresos (no efectivo) requieren match en el cierre?"),
        "Eliminar": st.column_config.CheckboxColumn(
            "Eliminar",
            help="Marcar para BORRAR PERMANENTEMENTE este socio. La acción es irreversible y fallará si tiene datos históricos.",
        )
    }

    edited_df = st.data_editor(
        df_socios,
        column_config=column_config,
        width='stretch', 
        hide_index=True,
        key="editor_socios"
    )

    # --- LÓGICA DE DETECCIÓN DE CAMBIOS ---
    
    # 1. DETECTAR ELIMINACIÓN (Usando el patrón del check de 'Eliminar')
    try:
        fila_para_eliminar = (edited_df["Eliminar"] == True) & (df_original["Eliminar"] == False)
        if fila_para_eliminar.any():
            fila_data = edited_df.loc[fila_para_eliminar].iloc[0]
            socio_id_del = fila_data["ID"]
            socio_nombre_del = fila_data["Nombre"]
            
            st.error(f"¿Seguro que deseas ELIMINAR PERMANENTEMENTE al socio '{socio_nombre_del}'?")
            st.caption("Esta acción no se puede deshacer y fallará si el socio tiene ingresos registrados en cierres pasados.")
            
            if st.button("CONFIRMAR ELIMINACIÓN PERMANENTE", type="primary"):
                with st.spinner("Eliminando..."):
                    _, err_del = database.admin_eliminar_socio(socio_id_del)
                    if err_del:
                        st.error(f"Error al eliminar: {err_del}")
                        time.sleep(3)
                    else:
                        st.success(f"Socio '{socio_nombre_del}' eliminado.")
                        recargar_socios()
                st.rerun()

    except Exception as e:
        st.error(f"Error procesando borrado: {e}")

    # 2. DETECTAR ACTUALIZACIÓN (Si no hay un borrado pendiente)
    if not (edited_df["Eliminar"] == True).any():
        try:
            # Comparamos ignorando la columna "Eliminar" que es solo de control
            cols_comparar = ["Nombre", "Afecta Efectivo", "Req. Voucher"]
            if not edited_df[cols_comparar].equals(df_original[cols_comparar]):
                
                # Encontrar diferencias
                diff = df_original[cols_comparar].compare(edited_df[cols_comparar])
                fila_idx = diff.index[0]
                
                # Obtener los datos COMPLETOS de la fila cambiada
                fila_cambiada_data = edited_df.iloc[fila_idx]
                socio_id_upd = df_original.iloc[fila_idx]["ID"]
                
                st.write(f"Actualizando socio: {fila_cambiada_data['Nombre']}...")

                data_para_db = {
                    "nombre": fila_cambiada_data["Nombre"],
                    "afecta_conteo_efectivo": fila_cambiada_data["Afecta Efectivo"],
                    "requiere_verificacion_voucher": fila_cambiada_data["Req. Voucher"]
                }

                _, error_update = database.admin_actualizar_socio_reglas(socio_id_upd, data_para_db)
                
                if error_update:
                    st.error(f"Error al actualizar: {error_update}")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.success(f"Socio '{data_para_db['nombre']}' actualizado.")
                    recargar_socios() # Limpiar el caché
                    st.rerun() 

        except Exception as e:
            # Esto puede ocurrir brevemente mientras el editor se actualiza
            # st.error(f"Error procesando actualización: {e}")
            pass
