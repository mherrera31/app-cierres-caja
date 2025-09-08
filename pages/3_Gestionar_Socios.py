# pages/4_Gestionar_Socios.py
# VERSIÓN 2: Con formularios explícitos de Actualizar/Eliminar y corrección de error JSON Bool.

import streamlit as st
import sys
import os
import database
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


st.set_page_config(page_title="Gestión de Socios", layout="centered")
st.title("Administrar Socios de Negocio 🤝")

def recargar_socios():
    cargar_lista_socios.clear()

@st.cache_data(ttl=10) 
def cargar_lista_socios():
    """ Carga todos los socios (como lista de dicts) para los formularios """
    socios, error = database.admin_get_todos_socios()
    if error:
        st.error(f"Error cargando socios: {error}")
        return []
    return socios

# --- 1. SECCIÓN DE CREAR SOCIO ---
with st.expander("Añadir Nuevo Socio", expanded=False):
    with st.form(key="form_nuevo_socio", clear_on_submit=True):
        st.subheader("Datos del Nuevo Socio")
        nuevo_nombre = st.text_input("Nombre del nuevo socio:")
        afecta_efectivo = st.checkbox("¿Afecta Conteo de Efectivo?", value=True, help="Si se marca, los ingresos en 'Efectivo' de este socio se sumarán al conteo de caja.")
        req_voucher = st.checkbox("¿Requiere Verificación (Voucher)?", value=False, help="Si se marca, los ingresos (no efectivo) de este socio requerirán un match/foto en el Paso 6.")
        
        submit_nuevo = st.form_submit_button("Crear Socio")

    if submit_nuevo:
        if not nuevo_nombre:
            st.warning("El nombre no puede estar vacío.")
        else:
            with st.spinner("Creando..."):
                _, error = database.admin_crear_socio(nuevo_nombre, afecta_efectivo, req_voucher)
            if error:
                st.error(f"Error al crear: {error}")
            else:
                st.success(f"¡Socio '{nuevo_nombre}' creado con éxito!")
                recargar_socios()
                time.sleep(1) # Esperar para que el usuario vea el mensaje
                st.rerun()

st.divider()

# --- 2. SECCIÓN DE EDITAR / ELIMINAR SOCIO ---
st.header("Editar o Eliminar Socios Existentes")

socios_lista = cargar_lista_socios()

if not socios_lista:
    st.info("No hay socios registrados para editar.")
    st.stop()

# Crear un mapa de Nombres a IDs para el SelectBox
mapa_socios_nombres = {s['nombre']: s['id'] for s in socios_lista}
opciones_select = ["--- Seleccione un socio ---"] + list(mapa_socios_nombres.keys())

socio_nombre_sel = st.selectbox("Socio a gestionar:", options=opciones_select)

# Si el usuario selecciona un socio válido (no la opción por defecto)
if socio_nombre_sel != "--- Seleccione un socio ---":
    
    # 1. Encontrar el objeto completo del socio seleccionado
    socio_id_sel = mapa_socios_nombres[socio_nombre_sel]
    # Usamos next() para encontrar el dict completo del socio en la lista cargada
    socio_data = next((s for s in socios_lista if s['id'] == socio_id_sel), None)

    if not socio_data:
        st.error("Error: No se encontraron los datos del socio seleccionado. Refrescando...")
        recargar_socios()
        st.rerun()
        
    st.markdown("---")
    
    # 2. FORMULARIO DE ACTUALIZACIÓN (pre-llenado con datos actuales)
    with st.form(key="form_editar_socio"):
        st.subheader(f"Editando: {socio_data['nombre']}")
        
        # Inputs pre-llenados con los valores actuales
        edit_nombre = st.text_input("Nombre:", value=socio_data['nombre'])
        edit_afecta = st.checkbox(
            "¿Afecta Conteo de Efectivo?", 
            value=bool(socio_data['afecta_conteo_efectivo']), # Cast a bool nativo de Python (Corrige el error)
            help="¿Ingresos en efectivo de este socio afectan la caja?"
        )
        edit_voucher = st.checkbox(
            "¿Requiere Verificación (Voucher)?", 
            value=bool(socio_data['requiere_verificacion_voucher']), # Cast a bool nativo de Python (Corrige el error)
            help="¿Ingresos (no efectivo) requieren match en el cierre?"
        )

        submit_update = st.form_submit_button("Guardar Cambios")

    if submit_update:
        if not edit_nombre:
            st.warning("El nombre no puede estar vacío.")
        else:
            # Construir el diccionario solo con los datos actualizados
            data_para_db = {
                "nombre": edit_nombre,
                "afecta_conteo_efectivo": edit_afecta, # Esto ya es un bool nativo de Python (del widget st.checkbox)
                "requiere_verificacion_voucher": edit_voucher # Esto también
            }
            
            with st.spinner("Actualizando..."):
                _, err_upd = database.admin_actualizar_socio_reglas(socio_id_sel, data_para_db)
                
            if err_upd:
                st.error(f"Error al actualizar: {err_upd}")
            else:
                st.success(f"¡Socio '{edit_nombre}' actualizado!")
                recargar_socios()
                time.sleep(1)
                st.rerun()

    # 3. ZONA DE PELIGRO - ELIMINACIÓN
    st.markdown("---")
    with st.expander("🚨 Zona de Peligro: Eliminar Socio"):
        st.warning(f"ADVERTENCIA: Está a punto de ELIMINAR PERMANENTEMENTE al socio '{socio_data['nombre']}'. Esta acción no se puede deshacer.")
        st.caption("La eliminación fallará si este socio tiene ingresos registrados en cierres pasados (para proteger la integridad de los reportes).")
        
        if st.button("Confirmar Eliminación Permanente", type="primary"):
            with st.spinner(f"Eliminando a {socio_data['nombre']}..."):
                _, err_del = database.admin_eliminar_socio(socio_id_sel)
            
            if err_del:
                st.error(f"Error al eliminar: {err_del}")
            else:
                st.success(f"Socio '{socio_data['nombre']}' eliminado permanentemente.")
                recargar_socios()
                time.sleep(2)
                st.rerun()
