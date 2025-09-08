# database.py - Módulo de Conexión a Base de Datos

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pytz
from datetime import datetime, timedelta
import json

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

# Nueva función para obtener métodos de pago y sus flags
def obtener_metodos_pago_con_flags():
    try:
        # --- CORRECCIÓN --- Se añade 'is_activo' al select
        response = supabase.table('metodos_pago').select('id, nombre, requiere_conteo, requiere_foto_voucher, is_activo').order('nombre').execute()
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

# Nueva función para guardar la verificación de pagos
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
        # Seleccionamos las nuevas columnas de reglas
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
        # Ahora hacemos un JOIN a socios para traernos sus reglas
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

# --- NUEVA FUNCIÓN AÑADIDA ---
# NUEVA FUNCIÓN PARA SUBIR ARCHIVOS A STORAGE
def subir_archivo_storage(cierre_id, metodo_pago_nombre, ruta_archivo_local):
    """
    Sube un archivo a Supabase Storage y devuelve la URL pública.
    """
    
    # --- CAMBIA ESTO: Pon el nombre real de tu "Bucket" de Supabase Storage ---
    BUCKET_NAME = "cierre-comprobantes" 
    # -------------------------------------------------------------------

    try:
        # Extraer la extensión del archivo (ej: .jpg, .png)
        extension = os.path.splitext(ruta_archivo_local)[1]
        
        # Crear un nombre de archivo único para evitar colisiones
        timestamp = int(datetime.now().timestamp())
        nombre_archivo_storage = f"{cierre_id}/{metodo_pago_nombre.replace(' ', '_')}_{timestamp}{extension}"

        # Leer el archivo local en modo binario
        with open(ruta_archivo_local, 'rb') as f:
            datos_archivo = f.read()

        # Subir el archivo al bucket de Storage
        response = supabase.storage.from_(BUCKET_NAME).upload(
            path=nombre_archivo_storage,
            file=datos_archivo
        )
        
        # Obtener la URL pública del archivo que acabamos de subir
        url_publica_response = supabase.storage.from_(BUCKET_NAME).get_public_url(nombre_archivo_storage)
        
        return url_publica_response, None

    except Exception as e:
        return None, f"Error al subir archivo a Storage: {e}"
    
def finalizar_cierre_en_db(cierre_id):
    """
    Marca el cierre especificado como 'CERRADO' en la base de datos.
    """
    try:
        datos = {"estado": "CERRADO", "fecha_hora_cierre_real": datetime.now(pytz.timezone('America/Panama')).isoformat()}
        response = supabase.table('cierres_caja').update(datos).eq('id', cierre_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al finalizar el cierre: {e}"
    
# --- FUNCIONES DE ADMINISTRACIÓN PARA CATEGORÍAS DE GASTOS ---

def admin_get_todas_categorias():
    """
    Obtiene todas las categorías de gastos, incluyendo activas e inactivas.
    Ordena por activas primero, luego alfabéticamente.
    """
    try:
        response = supabase.table('gastos_categorias').select('id, nombre, is_activo') \
            .order('is_activo', desc=True) \
            .order('nombre', desc=False) \
            .execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener todas las categorías: {e}"

def admin_crear_categoria(nombre_categoria):
    """
    Crea una nueva categoría de gasto. Por defecto, se crea como activa.
    """
    if not nombre_categoria:
        return None, "El nombre no puede estar vacío."
        
    try:
        datos = {"nombre": nombre_categoria, "is_activo": True}
        response = supabase.table('gastos_categorias').insert(datos).execute()
        return response.data, None
    except Exception as e:
        # Manejar error de duplicado (si el nombre ya existe y tienes una restricción UNIQUE)
        if "23505" in str(e): # Error de violación de restricción única
            return None, f"La categoría '{nombre_categoria}' ya existe."
        return None, f"Error al crear la categoría: {e}"

def admin_desactivar_categoria(categoria_id):
    """
    Desactiva una categoría de gasto (marcado lógico).
    No la borra para mantener la integridad de los gastos históricos.
    """
    try:
        datos = {"is_activo": False}
        response = supabase.table('gastos_categorias').update(datos).eq('id', categoria_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al desactivar la categoría: {e}"
    
# --- FUNCIONES DE ADMINISTRACIÓN PARA REPORTES DE CIERRES ---

def admin_get_lista_usuarios():
    """
    Obtiene una lista simple de todos los usuarios (perfiles) para los filtros del reporte.
    """
    try:
        # Asumimos que la tabla 'perfiles' tiene 'id' y 'nombre'
        response = supabase.table('perfiles').select('id, nombre').order('nombre').execute()
        return response.data, None
    except Exception as e:
        return [], f"Error al obtener lista de usuarios: {e}"

def admin_buscar_cierres_filtrados(fecha_inicio, fecha_fin, sucursal_id=None, usuario_id=None, solo_discrepancia=False):
    """
    Busca y filtra todos los cierres de caja segun los parámetros del admin.
    Esta función une tablas para obtener los nombres del perfil (usuario) y la sucursal.
    """
    try:
        # Empezamos la consulta seleccionando todo de cierres_caja y pidiendo las columnas relacionadas
        # de perfiles (el nombre) y sucursales (el nombre de la sucursal).
        query = supabase.table('cierres_caja').select(
            '*, perfiles(nombre), sucursales(sucursal)'
        )

        # 1. Filtro de Fecha (Ahora Opcional)
        if fecha_inicio:
            query = query.gte('fecha_operacion', fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha_operacion', fecha_fin)
            
        # 2. Filtro de Sucursal (Opcional)
        if sucursal_id:
            query = query.eq('sucursal_id', sucursal_id)

        # 3. Filtro de Usuario (Opcional)
        if usuario_id:
            query = query.eq('usuario_id', usuario_id)

        # 4. Filtro de Discrepancia (Opcional) (Req. 31)
        if solo_discrepancia:
            # Basado en la columna que definimos en iniciar_cierre_en_db
            query = query.eq('discrepancia_saldo_inicial', True)

        # Ordenar por fecha descendente y ejecutar
        response = query.order('fecha_operacion', desc=True).execute()
        return response.data, None

    except Exception as e:
        return [], f"Error al buscar cierres filtrados: {e}"

def eliminar_gasto_caja(gasto_id):
    """
    Elimina permanentemente un registro de gasto usando su ID.
    """
    try:
        response = supabase.table('gastos_caja').delete().eq('id', gasto_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al eliminar el gasto: {e}"

# database.py (AÑADIR ESTO AL FINAL)

# --- FUNCIONES DE ADMINISTRACIÓN PARA SOCIOS (CON HARD DELETE) ---

def admin_get_todos_socios():
    """ Obtiene todos los socios para el editor de admin """
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
    Esto fallará si el socio tiene registros asociados (ej: en ingresos_adicionales).
    """
    try:
        response = supabase.table('socios').delete().eq('id', socio_id).execute()
        return response.data, None
    except Exception as e:
        if "23503" in str(e): # Error de Foreign Key
             return None, "Error: No se puede eliminar. Este socio tiene registros históricos (ingresos) asociados."
        return None, f"Error al eliminar el socio: {e}"

# database.py (AÑADIR ESTAS 4 FUNCIONES NUEVAS)

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
        # 1. Eliminar el registro de reporte de delivery
        supabase.table('cierre_delivery').delete().eq('id', delivery_id).execute()
        
        # 2. Si tenía un gasto asociado (costo > 0), eliminarlo también.
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
    (No necesita sincronización ya que no toca gastos_caja).
    """
    try:
        response = supabase.table('cierre_compras').delete().eq('id', compra_id).execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al eliminar el registro de compra: {e}"

# --- FUNCIONES DE REGISTRO DE CARGA (MÓDULO SEPARADO) ---

def get_registro_carga(fecha_operacion, sucursal_id):
    """
    Busca el registro de carga único para una fecha y sucursal específicas.
    """
    try:
        response = supabase.table('registros_carga') \
            .select('*') \
            .eq('fecha_operacion', fecha_operacion) \
            .eq('sucursal_id', sucursal_id) \
            .maybe_single() \
            .execute()
        return response.data, None
    except Exception as e:
        return None, f"Error al buscar el registro de carga: {e}"

def upsert_registro_carga(fecha_operacion, sucursal_id, usuario_id, datos_carga):
    """
    Crea un nuevo registro de carga o ACTUALIZA uno existente si ya existe
    uno para esa fecha y sucursal (basado en el CONSTRAINT 'unique_fecha_sucursal').
    
    datos_carga (dict): debe contener carga_facturada, carga_retirada, carga_sin_retirar.
    """
    try:
        registro = {
            "fecha_operacion": fecha_operacion,
            "sucursal_id": sucursal_id,
            "usuario_id": usuario_id, # Siempre actualiza al último usuario que guardó
            "carga_facturada": datos_carga['carga_facturada'],
            "carga_retirada": datos_carga['carga_retirada'],
            "carga_sin_retirar": datos_carga['carga_sin_retirar']
        }
        
        # Upsert usa el constraint "unique_fecha_sucursal" que definimos en el SQL.
        response = supabase.table('registros_carga') \
            .upsert(registro, on_conflict="unique_fecha_sucursal") \
            .execute()
        
        return response.data, None
    except Exception as e:
        return None, f"Error al guardar (upsert) el registro de carga: {e}"
