# database.py - Módulo de Conexión a Base de Datos (VERSIÓN CONSOLIDADA Y CORREGIDA)

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pytz
from datetime import datetime, timedelta
import json
from decimal import Decimal # Importar Decimal para los cálculos

load_dotenv()
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def iniciar_sesion(email, password):
    try:
        sesion = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return sesion, None
    except Exception as e:
        return None, str(e)

def cerrar_sesion():
    supabase.auth.sign_out()

def obtener_perfil_usuario(user_id):
    try:
        response = supabase.table('perfiles').select('id, nombre, rol').eq('id', user_id).single().execute()
        return response.data, None if response.data else "No se encontró un perfil para este usuario."
    except Exception as e:
        return None, f"Error al buscar perfil: {str(e)}"

def obtener_sucursales():
    try:
        response = supabase.table('sucursales').select('id, sucursal').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener sucursales: {e}"

def buscar_cierre_abierto_hoy(usuario_id, sucursal_id):
    try:
        tz_panama = pytz.timezone('America/Panama')
        fecha_actual = datetime.now(tz_panama).strftime('%Y-%m-%d')
        response = supabase.table('cierres_caja').select('*').eq('usuario_id', usuario_id).eq('sucursal_id', sucursal_id).eq('fecha_operacion', fecha_actual).eq('estado', 'ABIERTO').maybe_single().execute()
        
        if response is None or response.data is None:
            return None, None

        return response.data, None
    except Exception as e:
        return None, f"Error al buscar cierre: {e}"

def buscar_cierre_cerrado_hoy(usuario_id, sucursal_id):
    try:
        tz_panama = pytz.timezone('America/Panama')
        fecha_actual = datetime.now(tz_panama).strftime('%Y-%m-%d')
        response = supabase.table('cierres_caja').select('*').eq('usuario_id', usuario_id).eq('sucursal_id', sucursal_id).eq('fecha_operacion', fecha_actual).eq('estado', 'CERRADO').maybe_single().execute()
        
        if response is None or response.data is None:
            return None, None

        return response.data, None
    except Exception as e:
        return None, f"Error al buscar cierre: {e}"

def reabrir_cierre(cierre_id):
    try:
        datos = {"estado": "ABIERTO"}
        supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        response = supabase.table('cierres_caja').select('*').eq('id', cierre_id).single().execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al reabrir el cierre: {e}"

def iniciar_cierre_en_db(usuario_id, sucursal_id, datos_saldo_inicial, marcar_discrepancia=False):
    try:
        discrepancia_detectada = marcar_discrepancia
        discrepancia_mensaje = ""
        
        response_ultimo_cierre = supabase.table('cierres_caja').select('saldo_para_siguiente_dia').eq('sucursal_id', sucursal_id).eq('estado', 'CERRADO').order('fecha_operacion', desc=True).limit(1).maybe_single().execute()
        
        saldo_anterior = 0
        if response_ultimo_cierre and response_ultimo_cierre.data:
            saldo_anterior = response_ultimo_cierre.data.get('saldo_para_siguiente_dia', 0)
            
            if saldo_anterior != datos_saldo_inicial['total']:
                discrepancia_detectada = True
                discrepancia_mensaje = f"El saldo inicial de caja (${datos_saldo_inicial['total']:.2f}) no coincide con el saldo para el día siguiente del último cierre (${saldo_anterior:.2f})."
        
        tz_panama = pytz.timezone('America/Panama')
        fecha_actual = datetime.now(tz_panama).strftime('%Y-%m-%d')
        datos = {
            "usuario_id": usuario_id, "sucursal_id": sucursal_id,
            "fecha_operacion": fecha_actual, "estado": "ABIERTO",
            "saldo_inicial_efectivo": datos_saldo_inicial['total'],
            "saldo_inicial_detalle": datos_saldo_inicial,
            "discrepancia_saldo_inicial": discrepancia_detectada
        }
        
        insert_response = supabase.table('cierres_caja').insert(datos).execute()
        
        if not insert_response or not insert_response.data or len(insert_response.data) == 0:
            return None, "La inserción del nuevo cierre falló o no devolvió datos."
        
        nuevo_cierre_creado = supabase.table('cierres_caja').select('*').eq('id', insert_response.data[0]['id']).single().execute()

        return nuevo_cierre_creado.data, discrepancia_mensaje
    except Exception as e:
        if "23505" in str(e): 
            cierre_existente, _ = buscar_cierre_abierto_hoy(usuario_id, sucursal_id)
            if cierre_existente:
                return cierre_existente, None
            else:
                return None, f"Error de concurrencia: El cierre ya existe, pero no se pudo recuperar."
        return None, f"Error inesperado al iniciar cierre: {e}"
        
def actualizar_saldo_inicial(cierre_id, datos_saldo_inicial):
    try:
        datos = {
            "saldo_inicial_efectivo": datos_saldo_inicial['total'],
            "saldo_inicial_detalle": datos_saldo_inicial
        }
        response = supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al actualizar saldo inicial: {e}"
        
def obtener_categorias_gastos():
    try:
        response = supabase.table('gastos_categorias').select('id, nombre').eq('is_activo', True).order('nombre').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener categorías: {e}"

def registrar_gasto(cierre_id, categoria_id, monto, notas, usuario_id, sucursal_id, sucursal_nombre):
    try:
        datos = {
            "cierre_id": cierre_id, "categoria_id": categoria_id, "monto": monto,
            "notas": notas, "usuario_id": usuario_id, "sucursal_id": sucursal_id, "sucursal": sucursal_nombre
        }
        # ESTA ES LA SINTAXIS CORRECTA (SIN .select())
        response = supabase.table('gastos_caja').insert(datos).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al registrar el gasto: {e}"

def obtener_gastos_del_cierre(cierre_id):
    try:
        response = supabase.table('gastos_caja').select('*, gastos_categorias(nombre)').eq('cierre_id', cierre_id).order('created_at').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener los gastos: {e}"

def obtener_pagos_del_cierre(cierre_id):
    try:
        response_cierre = supabase.table('cierres_caja').select('sucursal_id, fecha_operacion').eq('id', cierre_id).single().execute()
        cierre_info = response_cierre.data

        if not cierre_info:
            return [], "No se encontró información del cierre de caja."

        sucursal_id = cierre_info['sucursal_id']
        fecha_operacion_str = cierre_info['fecha_operacion']
        
        response_sucursal = supabase.table('sucursales').select('sucursal').eq('id', sucursal_id).single().execute()
        nombre_sucursal = response_sucursal.data['sucursal']

        fecha_inicio_dia = datetime.strptime(fecha_operacion_str, '%Y-%m-%d')
        fecha_fin_dia = fecha_inicio_dia + timedelta(days=1)
        
        response_pagos = supabase.table('pagos').select('monto, metodo_pago').eq('sucursal', nombre_sucursal).gte('created_at', fecha_inicio_dia.isoformat()).lt('created_at', fecha_fin_dia.isoformat()).execute()
        pagos = response_pagos.data

        pagos_con_nombres = []
        for pago in pagos:
            monto_float = float(pago['monto'])
            nombre_metodo = pago['metodo_pago']
            pagos_con_nombres.append({'monto': monto_float, 'metodo_pago': {'nombre': nombre_metodo}})

        return pagos_con_nombres, None
    except Exception as e:
        return [], f"Error al obtener los pagos: {e}"

def obtener_metodos_pago_con_flags():
    try:
        response = supabase.table('metodos_pago').select('id, nombre, requiere_conteo, requiere_foto_voucher, is_activo, is_cde').order('nombre').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener los métodos de pago con flags: {e}"

def guardar_conteo_final(cierre_id, datos_conteo_final, total_a_depositar, saldo_siguiente_detalle):
    try:
        datos = {
            "saldo_final_efectivo": datos_conteo_final['total'],
            "saldo_final_detalle": datos_conteo_final,
            "total_a_depositar": total_a_depositar,
            "saldo_para_siguiente_dia": saldo_siguiente_detalle['total'],
            "saldo_siguiente_detalle": saldo_siguiente_detalle,
            "estado": "ABIERTO" 
        }
        response = supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al guardar el conteo final: {e}"

def guardar_verificacion_pagos(cierre_id, datos_verificacion):
    try:
        datos = {"verificacion_pagos_detalle": datos_verificacion}
        response = supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al guardar la verificación de pagos: {e}"


def obtener_metodos_pago():
    try:
        response = supabase.table('metodos_pago').select('id, nombre').order('nombre').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener métodos de pago: {e}"

def obtener_socios():
    try:
        # (Sin filtro 'is_activo' según solicitud del usuario)
        response = supabase.table('socios').select('id, nombre, afecta_conteo_efectivo, requiere_verificacion_voucher').order('nombre').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener socios: {e}"
        
def registrar_ingreso_adicional(cierre_id, socio_id, monto, metodo_pago, notas):
    try:
        datos = {
            "cierre_id": cierre_id, "socio_id": socio_id, "monto": monto,
            "metodo_pago": metodo_pago, "notas": notas
        }
        response = supabase.table('ingresos_adicionales').insert(datos).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al registrar el ingreso adicional: {e}"

def actualizar_ingreso_adicional(cierre_id, socio_id, monto, metodo_pago):
    try:
        datos = {"monto": monto}
        response = supabase.table('ingresos_adicionales').update(datos).eq('cierre_id', cierre_id).eq('socio_id', socio_id).eq('metodo_pago', metodo_pago).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al actualizar el ingreso adicional: {e}"

def obtener_ingresos_adicionales_del_cierre(cierre_id):
    try:
        response = supabase.table('ingresos_adicionales').select('*, socios(nombre, afecta_conteo_efectivo, requiere_verificacion_voucher)').eq('cierre_id', cierre_id).order('created_at').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener los ingresos adicionales: {e}"
        
def guardar_saldo_siguiente(cierre_id, saldo_siguiente_detalle):
    try:
        datos = {
            "saldo_para_siguiente_dia": saldo_siguiente_detalle['total'],
            "saldo_siguiente_detalle": saldo_siguiente_detalle['detalle']
        }
        response = supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al guardar el saldo para el día siguiente: {e}"

def subir_archivo_storage(cierre_id, metodo_pago_nombre, ruta_archivo_local):
    BUCKET_NAME = "cierre-comprobantes" 
    try:
        extension = os.path.splitext(ruta_archivo_local)[1]
        timestamp = int(datetime.now().timestamp())
        nombre_archivo_storage = f"{cierre_id}/{metodo_pago_nombre.replace(' ', '_')}_{timestamp}{extension}"

        with open(ruta_archivo_local, 'rb') as f:
            datos_archivo = f.read()

        response = supabase.storage.from_(BUCKET_NAME).upload(
            path=nombre_archivo_storage,
            file=datos_archivo
        )
        url_publica_response = supabase.storage.from_(BUCKET_NAME).get_public_url(nombre_archivo_storage)
        return url_publica_response, None

    except Exception as e:
        return None, f"Error al subir archivo a Storage: {e}"
    
def finalizar_cierre_en_db(cierre_id):
    try:
        datos = {"estado": "CERRADO", "fecha_hora_cierre_real": datetime.now(pytz.timezone('America/Panama')).isoformat()}
        response = supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al finalizar el cierre: {e}"
    
# --- FUNCIONES DE ADMINISTRACIÓN PARA CATEGORÍAS DE GASTOS ---

def admin_get_todas_categorias():
    try:
        response = supabase.table('gastos_categorias').select('id, nombre, is_activo') \
            .order('is_activo', desc=True) \
            .order('nombre', desc=False) \
            .execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener todas las categorías: {e}"

def admin_crear_categoria(nombre_categoria):
    if not nombre_categoria:
        return None, "El nombre no puede estar vacío."
    try:
        datos = {"nombre": nombre_categoria, "is_activo": True}
        response = supabase.table('gastos_categorias').insert(datos).execute()
        return response.data, None
    except Exception as e:
        if "23505" in str(e): 
            return None, f"La categoría '{nombre_categoria}' ya existe."
        return None, f"Error al crear la categoría: {e}"

def admin_desactivar_categoria(categoria_id):
    try:
        datos = {"is_activo": False}
        response = supabase.table('gastos_categorias').update(datos).eq('id', categoria_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al desactivar la categoría: {e}"

def admin_activar_categoria(categoria_id):
    try:
        datos = {"is_activo": True}
        response = supabase.table('gastos_categorias').update(datos).eq('id', categoria_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al activar la categoría: {e}"

# --- FUNCIONES DE ADMINISTRACIÓN PARA REPORTES DE CIERRES ---

def admin_get_lista_usuarios():
    try:
        response = supabase.table('perfiles').select('id, nombre').order('nombre').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener lista de usuarios: {e}"

def admin_buscar_cierres_filtrados(fecha_inicio, fecha_fin, sucursal_id=None, usuario_id=None, solo_discrepancia=False):
    try:
        query = supabase.table('cierres_caja').select(
            '*, perfiles(nombre), sucursales(sucursal)'
        )
        if fecha_inicio:
            query = query.gte('fecha_operacion', fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha_operacion', fecha_fin)
        if sucursal_id:
            query = query.eq('sucursal_id', sucursal_id)
        if usuario_id:
            query = query.eq('usuario_id', usuario_id)
        if solo_discrepancia:
            query = query.eq('discrepancia_saldo_inicial', True)

        response = query.order('fecha_operacion', desc=True).execute()
        return response.data, None

    except Exception as e:
        return [], f"Error al buscar cierres filtrados: {e}"

def eliminar_gasto_caja(gasto_id):
    try:
        response = supabase.table('gastos_caja').delete().eq('id', gasto_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al eliminar el gasto: {e}"


# --- INICIO BLOQUE: NUEVAS FUNCIONES DE MÓDULOS ---

# --- FUNCIONES DE ADMINISTRACIÓN PARA SOCIOS (CON HARD DELETE) ---

def admin_get_todos_socios():
    """ Obtiene todos los socios para el editor de admin (sin is_activo) """
    try:
        response = supabase.table('socios') \
            .select('id, nombre, afecta_conteo_efectivo, requiere_verificacion_voucher') \
            .order('nombre', desc=False) \
            .execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener todos los socios: {e}"

def admin_crear_socio(nombre, afecta_efectivo, requiere_voucher):
    """ Crea un nuevo socio (Sin campo is_activo) """
    if not nombre:
        return None, "El nombre no puede estar vacío."
    try:
        datos = {
            "nombre": nombre, 
            "afecta_conteo_efectivo": afecta_efectivo,
            "requiere_verificacion_voucher": requiere_voucher
        }
        response = supabase.table('socios').insert(datos).execute()
        return response.data, None
    except Exception as e:
        if "23505" in str(e): # Error de violación de restricción única
            return None, f"El socio '{nombre}' ya existe."
        return None, f"Error al crear el socio: {e}"

def admin_actualizar_socio_reglas(socio_id, data_dict):
    """
    Actualiza el nombre y las reglas de un socio.
    data_dict debe contener: nombre, afecta_conteo_efectivo, requiere_verificacion_voucher
    """
    try:
        response = supabase.table('socios').update(data_dict).eq('id', socio_id).execute()
        return response.data, None
    except Exception as e:
        if "23505" in str(e):
             return None, "Error: Ese nombre de socio ya existe."
        return None, f"Error al actualizar el socio: {e}"

def admin_eliminar_socio(socio_id):
    """
    ELIMINA PERMANENTEMENTE un socio de la base de datos (HARD DELETE).
    """
    try:
        response = supabase.table('socios').delete().eq('id', socio_id).execute()
        return response.data, None
    except Exception as e:
        if "23503" in str(e): # Error de Foreign Key
             return None, "Error: No se puede eliminar. Este socio tiene registros históricos (ingresos) asociados."
        return None, f"Error al eliminar el socio: {e}"


# --- FUNCIONES DE GESTIÓN DE DELIVERY (CON DOBLE ESCRITURA) ---

def get_categoria_id_por_nombre(nombre_categoria):
    """
    Busca el ID de una categoría de gasto específica por su nombre exacto.
    """
    try:
        response = supabase.table('gastos_categorias') \
            .select('id') \
            .eq('nombre', nombre_categoria) \
            .eq('is_activo', True) \
            .limit(1) \
            .maybe_single() \
            .execute()
        
        if response.data:
            return response.data['id'], None
        else:
            return None, f"No se encontró la categoría activa '{nombre_categoria}'. Por favor, créala en el módulo 'Gestionar Categorías'."
    except Exception as e:
        return None, f"Error buscando categoría: {e}"

def registrar_delivery_completo(cierre_id, usuario_id, sucursal_id, monto_cobrado, costo_repartidor, origen_nombre, notas, gasto_asociado_id):
    """
    Registra la entrada completa en la tabla 'cierre_delivery' para el reporte de ganancias.
    """
    try:
        datos = {
            "cierre_id": cierre_id,
            "usuario_id": usuario_id,
            "sucursal_id": sucursal_id,
            "monto_cobrado": monto_cobrado,
            "costo_repartidor": costo_repartidor,
            "origen_nombre": origen_nombre,
            "notas": notas,
            "gasto_asociado_id": gasto_asociado_id  # Será NULL si el costo fue 0
        }
        response = supabase.table('cierre_delivery').insert(datos).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al registrar en cierre_delivery: {e}"

def obtener_deliveries_del_cierre(cierre_id):
    """
    Obtiene todos los registros de 'cierre_delivery' para un cierre_id (para el reporte de ganancias).
    """
    try:
        response = supabase.table('cierre_delivery') \
            .select('*') \
            .eq('cierre_id', cierre_id) \
            .order('created_at') \
            .execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener los registros de delivery: {e}"

def eliminar_delivery_completo(delivery_id, gasto_asociado_id):
    """
    Elimina el registro de la tabla 'cierre_delivery' Y TAMBIÉN elimina 
    el gasto correspondiente de 'gastos_caja' (si existe) para mantener la sincronía.
    """
    try:
        supabase.table('cierre_delivery').delete().eq('id', delivery_id).execute()
        if gasto_asociado_id:
            supabase.table('gastos_caja').delete().eq('id', gasto_asociado_id).execute()
        return True, None
    except Exception as e:
        return None, f"Error al eliminar el registro completo de delivery: {e}"


# --- FUNCIONES DE REGISTRO DE COMPRAS (INFORMATIVO) ---

def registrar_compra(cierre_id, usuario_id, sucursal_id, valor_calculado, costo_real, notas):
    """
    Registra una entrada de compra puramente informativa. 
    NO AFECTA A GASTOS_CAJA.
    """
    try:
        datos = {
            "cierre_id": cierre_id,
            "usuario_id": usuario_id,
            "sucursal_id": sucursal_id,
            "valor_calculado": valor_calculado,
            "costo_real": costo_real,
            "notas": notas
        }
        response = supabase.table('cierre_compras').insert(datos).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al registrar la compra: {e}"

def obtener_compras_del_cierre(cierre_id):
    """
    Obtiene todos los registros de 'cierre_compras' para un cierre_id.
    """
    try:
        response = supabase.table('cierre_compras') \
            .select('*') \
            .eq('cierre_id', cierre_id) \
            .order('created_at') \
            .execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener los registros de compras: {e}"

def eliminar_compra_registro(compra_id):
    """
    Elimina permanentemente un registro de compra. 
    """
    try:
        response = supabase.table('cierre_compras').delete().eq('id', compra_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al eliminar el registro de compra: {e}"


# --- FUNCIONES DE REGISTRO DE CARGA (MÓDULO SEPARADO) ---

def get_registro_carga(fecha_operacion, sucursal_id):
    """
    Busca el registro de carga único.
    (Versión actualizada del Paso 77 - Maneja respuesta vacía sin .maybe_single())
    """
    try:
        response = supabase.table('cierre_registros_carga') \
            .select('*') \
            .eq('fecha_operacion', fecha_operacion) \
            .eq('sucursal_id', sucursal_id) \
            .limit(1) \
            .execute() 

        if response is None:
            return None, "Error de API: La respuesta de la base de datos fue Nula (None)."

        if response.data:
            return response.data[0], None  # Devuelve el dict del registro
        else:
            return None, None # (Correcto: No hay registro, no hay error)

    except Exception as e:
        return None, f"Error al buscar el registro de carga: {e}"

def upsert_registro_carga(fecha_operacion, sucursal_id, usuario_id, datos_carga):
    """
    Crea o Actualiza un registro de carga.
    (Versión actualizada del Paso 53 - usa nombres de columna en on_conflict)
    """
    try:
        registro = {
            "fecha_operacion": fecha_operacion,
            "sucursal_id": sucursal_id,
            "usuario_id": usuario_id, 
            "carga_facturada": datos_carga['carga_facturada'],
            "carga_retirada": datos_carga['carga_retirada'],
            "carga_sin_retirar": datos_carga['carga_sin_retirar']
        }
        
        response = supabase.table('cierre_registros_carga') \
            .upsert(registro, on_conflict="fecha_operacion, sucursal_id") \
            .execute()
        
        if response is None:
             return None, "Error de API al guardar: La respuesta de la base de datos fue Nula (None)."

        return response.data, None
    except Exception as e:
        return None, f"Error al guardar (upsert) el registro de carga: {e}"


# --- BLOQUE COMPLETO DE FUNCIONES CIERRE CDE (CONSOLIDADO Y CORREGIDO) ---

def obtener_sucursales_cde():
    """
    Obtiene solo las sucursales que están marcadas como CDE (terminan en 'CDE').
    (Parcheado con verificación 'is None')
    """
    try:
        response = supabase.table('sucursales').select('id, sucursal').like('sucursal', '%CDE').execute()
        if response is None:
            return [], "Error API: Respuesta Nula al buscar sucursales CDE"
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener sucursales CDE: {e}"

def obtener_metodos_pago_cde():
    """
    Obtiene solo los métodos de pago marcados con is_cde = true.
    (Parcheado con verificación 'is None')
    """
    try:
        response = supabase.table('metodos_pago') \
            .select('id, nombre') \
            .eq('is_cde', True) \
            .neq('nombre', 'Efectivo') \
            .order('nombre') \
            .execute()
        if response is None:
            return [], "Error API: Respuesta Nula al buscar métodos CDE"
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener métodos de pago CDE: {e}"

def calcular_totales_pagos_dia_sucursal(fecha_str, sucursal_nombre):
    """
    Calcula la suma de todos los pagos (de la tabla 'pagos') agrupados por método.
    (Parcheado con verificación 'is None')
    """
    try:
        tz_panama = pytz.timezone('America/Panama')
        fecha_inicio_dia = tz_panama.localize(datetime.strptime(fecha_str, '%Y-%m-%d'))
        fecha_fin_dia = fecha_inicio_dia + timedelta(days=1)
        
        response_pagos = supabase.table('pagos') \
            .select('monto, metodo_pago') \
            .eq('sucursal', sucursal_nombre) \
            .gte('created_at', fecha_inicio_dia.isoformat()) \
            .lt('created_at', fecha_fin_dia.isoformat()) \
            .execute()
        
        if response_pagos is None:
            return None, 0.0, "Error API: Respuesta Nula al calcular totales de pagos"
            
        pagos = response_pagos.data
        if not pagos:
            return {}, 0.0, None 

        totales_por_metodo = {}
        total_efectivo = 0.0
        
        for pago in pagos:
            metodo = pago['metodo_pago']
            monto = Decimal(str(pago.get('monto', 0)))
            
            if metodo.lower() == 'efectivo':
                total_efectivo += monto
            else:
                if metodo not in totales_por_metodo:
                    totales_por_metodo[metodo] = Decimal('0.00')
                totales_por_metodo[metodo] += monto

        totales_por_metodo_float = {k: float(v) for k, v in totales_por_metodo.items()}
        return totales_por_metodo_float, float(total_efectivo), None

    except Exception as e:
        return None, 0.0, f"Error al calcular totales de pagos: {e}"

def buscar_cierre_cde_existente_hoy(fecha_str, sucursal_id):
    """
    (Versión CORREGIDA del Paso 77 - Flujo Botón "Abrir")
    Maneja respuesta vacía sin .maybe_single().
    """
    try:
        response = supabase.table('cierres_cde') \
            .select('*') \
            .eq('fecha_operacion', fecha_str) \
            .eq('sucursal_id', sucursal_id) \
            .limit(1) \
            .execute() 

        if response is None:
            return None, "Error de API: La respuesta de la base de datos fue Nula (None)."

        if response.data:
            return response.data[0], None  # Devuelve el dict del registro existente
        else:
            return None, None # (Correcto: No hay registro, no hay error)

    except Exception as e:
        return None, f"Error al buscar cierre CDE existente: {e}"


def crear_nuevo_cierre_cde(fecha_str, sucursal_id, usuario_id):
    """
    (Versión CORREGIDA - Flujo Botón "Abrir")
    Esta función SÓLO CREA un nuevo cierre CDE.
    """
    try:
        suc_data_resp = supabase.table('sucursales').select('sucursal').eq('id', sucursal_id).single().execute()
        if not suc_data_resp or not suc_data_resp.data:
             return None, "No se encontró el nombre de la sucursal."
            
        sucursal_nombre = suc_data_resp.data['sucursal']
        
        totales_metodos_dict, total_efectivo, err_calc = calcular_totales_pagos_dia_sucursal(fecha_str, sucursal_nombre)
        if err_calc:
            return None, f"Error al calcular totales de pagos: {err_calc}"

        datos_nuevo = {
            "fecha_operacion": fecha_str,
            "sucursal_id": sucursal_id,
            "usuario_id": usuario_id,
            "estado": "ABIERTO",
            "total_efectivo_sistema": total_efectivo
        }
        
        # --- ESTA ES LA LÍNEA CORREGIDA ---
        # El .insert() se ejecuta directamente y devuelve los datos insertados.
        response_nuevo = supabase.table('cierres_cde').insert(datos_nuevo).execute()
        # --- FIN DE LA CORRECCIÓN ---
        
        if response_nuevo is None:
            return None, "Error API: Respuesta Nula al CREAR cierre CDE"
        
        # Insert devuelve una LISTA de registros, queremos el primero (y único).
        return response_nuevo.data[0], None

    except Exception as e:
        return None, f"Error al crear nuevo cierre CDE: {e}"

def obtener_metodos_pago_NO_cde(totales_sistema_dict):
    """
    (Función NUEVA del Paso 73 - Reporte Informativo)
    Obtiene los métodos de pago que NO son CDE pero SÍ recibieron pagos hoy.
    """
    try:
        response = supabase.table('metodos_pago') \
            .select('nombre') \
            .eq('is_cde', False) \
            .eq('is_activo', True) \
            .neq('nombre', 'Efectivo') \
            .execute()

        if response is None:
            return [], "Error API: Respuesta Nula buscando métodos NO-CDE"

        metodos_activos_no_cde = {m['nombre'] for m in response.data}
        metodos_con_pagos = []
        
        for metodo_sistema, total in totales_sistema_dict.items():
            if metodo_sistema in metodos_activos_no_cde:
                metodos_con_pagos.append({"nombre": metodo_sistema, "total": total})
                
        return metodos_con_pagos, None
        
    except Exception as e:
        return [], f"Error al obtener métodos NO-CDE: {e}"

def guardar_conteo_cde(cierre_cde_id, total_contado, detalle_conteo, verificacion_metodos_json):
    """
    (Función parcheada del Paso 70)
    Actualiza el Cierre CDE con los conteos manuales del usuario.
    """
    try:
        datos = {
            "total_efectivo_contado": total_contado,
            "detalle_conteo_efectivo": detalle_conteo,
            "verificacion_metodos": verificacion_metodos_json
        }
        response = supabase.table('cierres_cde').update(datos).eq('id', cierre_cde_id).execute()
        if response is None:
            return None, "Error API: Respuesta Nula al guardar conteo CDE"
        return response.data, None
    except Exception as e:
        return None, f"Error al guardar conteo CDE: {e}"

def finalizar_cierre_cde(cierre_cde_id, con_discrepancia=False):
    """
    (Función parcheada del Paso 70)
    Marca el Cierre CDE como CERRADO.
    """
    try:
        datos = {
            "estado": "CERRADO",
            "discrepancia": con_discrepancia
        }
        response = supabase.table('cierres_cde').update(datos).eq('id', cierre_cde_id).execute()
        if response is None:
            return None, "Error API: Respuesta Nula al finalizar cierre CDE"
        return response.data, None
    except Exception as e:
        return None, f"Error al finalizar cierre CDE: {e}"

# --- FIN BLOQUE COMPLETO CIERRE CDE ---

# database.py (AÑADIR ESTA FUNCIÓN AL FINAL DEL ARCHIVO)

def admin_buscar_cierres_cde_filtrados(fecha_inicio, fecha_fin, sucursal_id=None, usuario_id=None):
    """
    Busca y filtra todos los cierres de CDE (solo el módulo de verificación).
    (Esta es la función que faltaba y que el reporte '1_Reportes_Admin.py' necesita).
    """
    try:
        query = supabase.table('cierres_cde').select(
            '*, perfiles(nombre), sucursales(sucursal)'
        )

        if fecha_inicio:
            query = query.gte('fecha_operacion', fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha_operacion', fecha_fin)
            
        if sucursal_id:
            query = query.eq('sucursal_id', sucursal_id)

        if usuario_id:
            query = query.eq('usuario_id', usuario_id)

        response = query.order('fecha_operacion', desc=True).execute()
        
        # Parche de seguridad (por si acaso)
        if response is None:
            return None, "Error API: Respuesta Nula al buscar cierres CDE filtrados"

        return response.data, None

    except Exception as e:
        return [], f"Error al buscar cierres CDE filtrados: {e}"

# --- FUNCIONES DE REPORTES AGREGADOS ---

def admin_reporte_gastos_agregados(fecha_inicio=None, fecha_fin=None, sucursal_id=None, categoria_id=None, usuario_id=None):
    """
    Llama a la función SQL avanzada 'reporte_gastos_agregados'.
    Todos los filtros son opcionales.
    """
    try:
        params = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'p_sucursal_id': sucursal_id,
            'p_categoria_id': categoria_id,
            'p_usuario_id': usuario_id
        }
        # Filtramos los parámetros que son None para no enviarlos
        params = {k: v for k, v in params.items() if v is not None}
            
        response = supabase.rpc('reporte_gastos_agregados', params).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al ejecutar reporte de gastos: {e}"

def admin_reporte_ingresos_socios(fecha_inicio=None, fecha_fin=None, sucursal_id=None, socio_id=None, metodo_pago=None):
    """
    Llama a la función SQL avanzada 'reporte_ingresos_socios'.
    Todos los filtros son opcionales.
    """
    try:
        params = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'p_sucursal_id': sucursal_id,
            'p_socio_id': socio_id,
            'p_metodo_pago': metodo_pago
        }
        # Filtramos los parámetros que son None para no enviarlos
        params = {k: v for k, v in params.items() if v is not None}

        response = supabase.rpc('reporte_ingresos_socios', params).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al ejecutar reporte de ingresos por socio: {e}"

def admin_reporte_metodo_pago(fecha_inicio=None, fecha_fin=None, sucursal_id=None):
    """
    Llama a la función SQL 'reporte_movimientos_por_metodo' para obtener un
    resumen de ingresos y egresos por cada método de pago.
    """
    try:
        params = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'p_sucursal_id': sucursal_id
        }
        params = {k: v for k, v in params.items() if v is not None}
            
        response = supabase.rpc('reporte_movimientos_por_metodo', params).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al ejecutar reporte por método de pago: {e}"
