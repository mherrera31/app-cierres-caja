# App_Web.py (Esta es nuestra nueva página principal de Login)

import streamlit as st
import database

# Inicializar el estado de la sesión (si no existe)
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["perfil"] = None
    st.session_state["sesion_auth"] = None

def intentar_login(email, password):
    """Llama a las funciones de DB para autenticar y obtener perfil."""
    # 1. Usamos la función de DB existente para iniciar sesión en Supabase Auth
    sesion, error_auth = database.iniciar_sesion(email, password)
    if error_auth:
        st.error(f"Error de Autenticación: {error_auth}")
        return

    # 2. Si Auth tiene éxito, usamos la función de DB para obtener el perfil (rol)
    perfil, error_perfil = database.obtener_perfil_usuario(sesion.user.id)
    if error_perfil:
        st.error(f"Error de Perfil: {error_perfil}")
        return

    # 3. Éxito: Guardamos todo en el st.session_state
    st.session_state["autenticado"] = True
    st.session_state["sesion_auth"] = sesion
    st.session_state["perfil"] = perfil
    st.rerun() # Volver a ejecutar el script para mostrar la vista de "logueado"

def hacer_logout():
    """Borra el estado de la sesión y refresca."""
    st.session_state["autenticado"] = False
    st.session_state["perfil"] = None
    st.session_state["sesion_auth"] = None
    # (Nota: database.cerrar_sesion() solo limpia el token del cliente local, 
    # en Streamlit, limpiar el session_state es lo más importante)
    st.rerun()


# --- Lógica de la Interfaz (UI) ---

# CASO 1: El usuario YA está logueado
if st.session_state["autenticado"]:
    perfil = st.session_state["perfil"]
    st.set_page_config(page_title="App Cierres", layout="centered")
    st.title(f"¡Bienvenido, {perfil.get('nombre', 'Usuario')}! 👋")
    st.subheader(f"Rol: {perfil.get('rol', 'N/A').title()}")
    st.markdown("---")
    st.markdown(
        """
        Has iniciado sesión correctamente.
        
        Usa la **barra lateral de navegación (sidebar) a la izquierda** (haz clic en > si está oculta) 
        para acceder a los módulos disponibles para tu rol.
        """
    )
    
    st.button("Cerrar Sesión (Logout)", on_click=hacer_logout, type="primary")

# CASO 2: El usuario NO está logueado
else:
    st.set_page_config(page_title="Login Cierres", layout="centered")
    st.title("Sistema de Cierre de Caja 🔒")
    st.markdown("Por favor, inicie sesión para continuar.")

    with st.form(key="login_form"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        
        submit_button = st.form_submit_button(label="Entrar")

    if submit_button:
        if not email or not password:
            st.warning("El email y la contraseña no pueden estar vacíos.")
        else:
            intentar_login(email, password)