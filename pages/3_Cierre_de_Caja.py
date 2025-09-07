# pages/3_Cierre_de_Caja.py

import streamlit as st

import database
# --- Importamos TODOS los módulos de nuestras pestañas ---
from cierre_web.form_caja_inicial import render_form_inicial
from cierre_web.tab_caja_inicial import render_tab_inicial
from cierre_web.tab_gastos import render_tab_gastos
from cierre_web.tab_ingresos_adic import render_tab_ingresos_adic
from cierre_web.tab_resumen import render_tab_resumen
from cierre_web.tab_caja_final import render_tab_caja_final
from cierre_web.tab_verificacion import render_tab_verificacion 

# --- GUARDIÁN DE SEGURIDAD (Permite a TODOS los logueados) ---
if not st.session_state.get("autenticado"):
    st.error("Acceso denegado. 🚫 Por favor, inicie sesión desde la página principal.")
    st.stop()
# ------------------------------------

st.set_page_config(page_title="Cierre de Caja Operativo", layout="wide")
st.title("Espacio de Trabajo: Cierre de Caja 🧾")

# --- Funciones de Carga de Datos (Cacheadas) ---
@st.cache_data(ttl=600)
def cargar_sucursales_data():
    """Carga la lista de sucursales para el selector."""
    sucursales_data, err = database.obtener_sucursales()
    if err:
        st.error(f"No se pudieron cargar sucursales: {err}")
        return {}
    
    opciones = {s['sucursal']: s['id'] for s in sucursales_data}
    return opciones

# --- Lógica de Estado Principal ---
if 'cierre_actual_objeto' not in st.session_state:
    st.session_state['cierre_actual_objeto'] = None
if 'cierre_sucursal_seleccionada_nombre' not in st.session_state:
    st.session_state['cierre_sucursal_seleccionada_nombre'] = None


# --- UI: SELECCIÓN DE SUCURSAL ---
st.header("1. Seleccione Sucursal de Trabajo")

opciones_sucursal = cargar_sucursales_data()
lista_nombres_sucursales = ["--- Seleccione una Sucursal ---"] + list(opciones_sucursal.keys())

default_index = 0
if st.session_state.cierre_sucursal_seleccionada_nombre in lista_nombres_sucursales:
    default_index = lista_nombres_sucursales.index(st.session_state.cierre_sucursal_seleccionada_nombre)

sucursal_seleccionada_nombre = st.selectbox(
    "Sucursal:",
    options=lista_nombres_sucursales,
    index=default_index 
)

if sucursal_seleccionada_nombre != st.session_state.cierre_sucursal_seleccionada_nombre:
    st.session_state['cierre_actual_objeto'] = None
    st.session_state['cierre_sucursal_seleccionada_nombre'] = sucursal_seleccionada_nombre
    st.session_state.pop('resumen_calculado', None) 
    st.rerun() 


# ---------------------------------
if sucursal_seleccionada_nombre == "--- Seleccione una Sucursal ---":
    st.info("Debe seleccionar una sucursal para iniciar o continuar un cierre.")
    st.stop()

# --- LÓGICA DE CARGA DE CIERRE (El "Loader") ---

sucursal_id_actual = opciones_sucursal[sucursal_seleccionada_nombre]
usuario_id_actual = st.session_state['perfil']['id']


# Verificamos el estado (solo si aún no hemos cargado un cierre en la sesión)
if st.session_state.get('cierre_actual_objeto') is None:
    
    st.markdown("---")
    st.subheader("2. Estado del Cierre del Día")

    with st.spinner("Buscando estado de cierres para hoy..."):
        # 1. ¿Existe uno ABIERTO? (Prioridad 1)
        cierre_abierto, err_a = database.buscar_cierre_abierto_hoy(usuario_id_actual, sucursal_id_actual)
        if err_a:
            st.error(f"Error buscando cierre abierto: {err_a}")
            st.stop()

        if cierre_abierto:
            st.success(f"✅ Cierre ABIERTO encontrado. Listo para trabajar.")
            st.session_state['cierre_actual_objeto'] = cierre_abierto
            st.rerun()

        # 2. Si no hay ABIERTO, ¿Existe uno CERRADO? (Prioridad 2)
        cierre_cerrado, err_c = database.buscar_cierre_cerrado_hoy(usuario_id_actual, sucursal_id_actual)
        if err_c:
            st.error(f"Error buscando cierre cerrado: {err_c}")
            st.stop()

        if cierre_cerrado:
            st.warning("ℹ️ Ya existe un cierre FINALIZADO para hoy en esta sucursal.")
            st.markdown("Puede reabrir el cierre anterior para hacer modificaciones (recomendado) o crear un cierre completamente nuevo (esto funciona gracias a nuestro índice filtrado).")
            
            col1, col2 = st.columns(2)
            
            if col1.button("Reabrir Cierre Anterior (Recomendado)"):
                cierre_reabierto, err_r = database.reabrir_cierre(cierre_cerrado['id'])
                if err_r:
                    st.error(f"No se pudo reabrir: {err_r}")
                else:
                    st.session_state['cierre_actual_objeto'] = cierre_reabierto
                    st.rerun()

            if col2.button("Crear Cierre Completamente Nuevo"):
                st.session_state['iniciar_nuevo_cierre_flag'] = True
                st.rerun()

            st.stop() 

        # 3. Si no hay ABIERTO ni CERRADO (o si el usuario presionó "Crear Nuevo")
        if (not cierre_abierto and not cierre_cerrado) or st.session_state.get('iniciar_nuevo_cierre_flag'):
            
            nuevo_cierre_creado = render_form_inicial(usuario_id_actual, sucursal_id_actual)
            
            if nuevo_cierre_creado:
                st.session_state['cierre_actual_objeto'] = nuevo_cierre_creado
                st.session_state.pop('iniciar_nuevo_cierre_flag', None) 
                st.success("¡Nuevo cierre iniciado con éxito!")
                st.balloons()
                st.rerun() 
            else:
                st.stop() 


# === EL WIZARD DE PESTAÑAS (TABS) (VERSIÓN COMPLETA) ===
if st.session_state.get('cierre_actual_objeto'):
    st.markdown("---")
    st.header(f"Estás trabajando en: {sucursal_seleccionada_nombre}")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "PASO 1: Caja Inicial", 
        "PASO 2: Gastos", 
        "PASO 3: Ingresos Adic.", 
        "PASO 4: Resumen", 
        "PASO 5: Caja Final", 
        "PASO 6: Verificación y Finalizar" 
    ])

    with tab1:
        render_tab_inicial()

    with tab2:
        render_tab_gastos()

    with tab3:
        render_tab_ingresos_adic()

    with tab4:
        render_tab_resumen()
        
    with tab5:
        render_tab_caja_final()
        
    with tab6:
        render_tab_verificacion()
