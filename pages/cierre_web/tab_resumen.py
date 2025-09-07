# cierre_web/tab_resumen.py

import streamlit as st
import database
from decimal import Decimal

def render_tab_resumen():
    """
    Renderiza la pestaña de Resumen. Esta pestaña recalcula el total teórico de efectivo
    basado en los datos ingresados en las pestañas anteriores.
    """
    
    cierre_actual = st.session_state.get('cierre_actual_objeto')
    if not cierre_actual:
        st.error("Error: No hay ningún cierre cargado en la sesión.")
        st.stop()

    cierre_id = cierre_actual['id']

    # Un botón para forzar la recarga de datos desde la DB
    if st.button("Recalcular Resumen del Día"):
        # (Streamlit automáticamente recarga al presionar un botón, 
        # lo que fuerza a las siguientes funciones (sin caché) a volver a ejecutarse)
        st.success("Resumen recalculado.")

    st.subheader("Cálculo del Saldo Teórico de Efectivo")

    # --- 1. Obtener todos los datos (Volvemos a llamar a la DB para datos frescos) ---
    
    # Saldo Inicial (Desde la sesión, ya que pudo ser editado en Tab 1)
    saldo_inicial = Decimal(str(cierre_actual.get('saldo_inicial_efectivo', 0)))

    # Pagos de Ventas (Solo Efectivo)
    pagos_venta, err_p = database.obtener_pagos_del_cierre(cierre_id)
    total_pagos_venta_efectivo = Decimal('0.00')
    pagos_venta_efectivo_lista = []
    if not err_p:
        for pago in pagos_venta:
            if pago['metodo_pago']['nombre'].lower() == 'efectivo':
                monto = Decimal(str(pago['monto']))
                total_pagos_venta_efectivo += monto
                pagos_venta_efectivo_lista.append(pago) # Guardamos para mostrar detalle

    # Ingresos Adicionales (Solo Efectivo) (Datos de Tab 3)
    ingresos_adicionales, err_i = database.obtener_ingresos_adicionales_del_cierre(cierre_id)
    total_ingresos_adicionales_efectivo = Decimal('0.00')
    ingresos_adic_efectivo_lista = []
    if not err_i:
        for ingreso in ingresos_adicionales:
            if ingreso['metodo_pago'].lower() == 'efectivo':
                monto = Decimal(str(ingreso['monto']))
                total_ingresos_adicionales_efectivo += monto
                ingresos_adic_efectivo_lista.append(ingreso)

    # Gastos (Datos de Tab 2)
    gastos, err_g = database.obtener_gastos_del_cierre(cierre_id)
    total_gastos = Decimal('0.00')
    if not err_g:
        for gasto in gastos:
            total_gastos += Decimal(str(gasto['monto']))

    # --- 2. Calcular el Total Teórico ---
    total_calculado_efectivo = (saldo_inicial + total_pagos_venta_efectivo + total_ingresos_adicionales_efectivo) - total_gastos
    
    # --- IMPORTANTE: Guardamos este cálculo en la sesión ---
    # Esto es para que el PASO 5 (Caja Final) pueda leerlo y compararlo.
    st.session_state.cierre_actual_objeto['total_calculado_teorico'] = float(total_calculado_efectivo)


    # --- 3. Mostrar la UI (Resumen) ---
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("1. Saldo Inicial (Efectivo)", f"${saldo_inicial:,.2f}")
    col2.metric("2. Ventas (Efectivo)", f"${total_pagos_venta_efectivo:,.2f}")
    col3.metric("3. Ingresos Adic. (Efectivo)", f"${total_ingresos_adicionales_efectivo:,.2f}")
    col4.metric("4. Gastos (Efectivo)", f"$-{total_gastos:,.2f}", delta_color="inverse")
    
    st.divider()
    st.header(f"Total Teórico en Caja: ${total_calculado_efectivo:,.2f}")
    st.caption("Esta es la cantidad de efectivo que debería haber físicamente en caja antes del conteo final.")

    # --- Detalles (en Expanders) ---
    st.subheader("Detalles del Cálculo")

    with st.expander("Ver detalle de Ventas en Efectivo"):
        if not pagos_venta_efectivo_lista:
            st.write("Sin ventas en efectivo.")
        else:
            # (No podemos mostrar mucho detalle aquí, ya que solo tenemos totales agrupados)
            st.write(f"Total de {len(pagos_venta_efectivo_lista)} pagos en efectivo sumando: ${total_pagos_venta_efectivo:,.2f}")

    with st.expander("Ver detalle de Ingresos Adicionales en Efectivo"):
        if not ingresos_adic_efectivo_lista:
            st.write("Sin ingresos adicionales en efectivo.")
        else:
            for ing in ingresos_adic_efectivo_lista:
                socio_nombre = ing.get('socios', {}).get('nombre', 'N/A')
                st.write(f"- Socio: {socio_nombre} | Monto: ${Decimal(str(ing['monto'])):,.2f}")
    
    with st.expander("Ver detalle de Gastos"):
        if not gastos:
            st.write("Sin gastos registrados.")
        else:
            for gasto in gastos:
                cat_nombre = gasto.get('gastos_categorias', {}).get('nombre', 'N/A')
                st.write(f"- Categoría: {cat_nombre} | Monto: ${Decimal(str(gasto['monto'])):,.2f} | Notas: {gasto.get('notas','')}")
