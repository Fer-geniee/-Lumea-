"""
gamificacion.py -- Núcleo de gamificación (XP, niveles, racha, meta
diaria, pérdida por inactividad y avatares), solo backend.

Vive en su propio archivo, separado de app.py y database.py, para que se
pueda trabajar en paralelo con el resto del backend sin pisarse. app.py
solo hace dos cosas:
  1. registrar_gamificacion(app, db) al arrancar: crea las tablas si no
     existen y registra los endpoints de este archivo.
  2. registrar_actividad(db, usuario_id, accion) justo después de guardar
     algo que da XP (una comida, un estado de ánimo).

Todos los números (XP por acción, topes, meta, niveles, pérdida por
inactividad, avatares, ropa y accesorios) están en gamificacion_config.py.
Aquí no hay ninguno.

Tablas:
- progreso_usuario: una fila por usuario con su estado acumulado (XP
  actual, nivel máximo alcanzado, racha, avatar DiceBear elegido y avatar
  por capas: base, ropa y accesorio puestos).
- actividad_diaria: una fila por usuario y día (XP del día, meta cumplida).
- eventos_xp: una fila por cada acción registrada, con el XP que dio
  (0 si ya había llegado al tope del día), y una fila con XP negativo
  ("perdida_inactividad") cada vez que se descuenta XP por días
  inactivos. Sirve para contar cuántas veces se hizo cada acción hoy y
  para poder explicar de dónde salió el XP de cada usuario.
"""

import os
from datetime import date, timedelta
from urllib.parse import urlencode

from flask import Blueprint, has_request_context, jsonify, request, url_for

import gamificacion_config as config
from grupos_confusion import GRUPOS_CONFUSION

CARPETA_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# =====================================================================
# Lógica pura: no toca la base de datos, así que se puede probar sola
# (ver test_gamificacion.py).
# =====================================================================


def calcular_nivel(xp_total):
    """Nivel = cuántos umbrales de config.NIVELES ya alcanzó (mínimo 1)."""
    return max(1, sum(1 for umbral in config.NIVELES if xp_total >= umbral))


def nivel_alcanzado(nivel_maximo, xp_total):
    """El nivel que se muestra NUNCA baja: es el mayor entre el nivel
    máximo que ya tenía y el que le da su XP actual."""
    return max(nivel_maximo or 1, calcular_nivel(xp_total))


def limites_del_nivel(nivel):
    """(XP donde empieza `nivel`, XP donde empieza el siguiente). El
    segundo es None si ya es el último nivel."""
    inicio = config.NIVELES[nivel - 1]
    siguiente = config.NIVELES[nivel] if nivel < len(config.NIVELES) else None
    return inicio, siguiente


def rango_del_nivel(xp_total):
    """Los límites del nivel que corresponde a `xp_total`."""
    return limites_del_nivel(calcular_nivel(xp_total))


def nueva_racha(racha_actual, ultima_fecha, hoy):
    """Racha después de registrar actividad HOY.
    - Ya hubo actividad hoy: no cambia (solo cuenta una vez por día).
    - La última actividad fue ayer: sigue, +1.
    - Nunca hubo actividad, o fue antes de ayer: vuelve a empezar en 1."""
    if ultima_fecha == hoy:
        return racha_actual
    if ultima_fecha == hoy - timedelta(days=1):
        return racha_actual + 1
    return 1


def racha_vigente(racha_actual, ultima_fecha, hoy):
    """Racha que se le MUESTRA al usuario. La racha guardada solo se
    actualiza cuando hay actividad; si la última fue antes de ayer, ya se
    perdió aunque la base de datos todavía diga otro número."""
    if ultima_fecha is None or ultima_fecha < hoy - timedelta(days=1):
        return 0
    return racha_actual


def xp_a_otorgar(accion, veces_previas_hoy):
    """XP que da `accion` si ya se hizo `veces_previas_hoy` veces hoy."""
    regla = config.ACCIONES[accion]
    return regla["xp"] if veces_previas_hoy < regla["maximo_por_dia"] else 0


# ---- Puntos v2: elección nutritiva, ultraprocesados y misiones ----

CODIGOS_DE_GRUPO = {grupo["id"] for grupo in GRUPOS_CONFUSION}


def grupo_de_paquete(alimento_codigo):
    """El id del grupo de productos de paquete al que pertenece el
    alimento ("gaseosas_bebidas_azucaradas"...), o None si no es de paquete.
    Cuenta tanto las opciones del grupo como el código genérico del grupo."""
    for grupo in GRUPOS_CONFUSION:
        if grupo["id"] not in config.GRUPOS_PRODUCTO_DE_PAQUETE:
            continue
        codigos = {opcion["codigo"] for opcion in grupo["opciones"]} | {grupo["id"]}
        if alimento_codigo in codigos:
            return grupo["id"]
    return None


def es_eleccion_nutritiva(alimento_codigo, sellos):
    """True si el alimento final da el bonus de elección nutritiva: no es
    un código de grupo, no tiene sellos (lista vacía; None = no se sabe, no
    cuenta) y no es un producto de paquete."""
    if not alimento_codigo or alimento_codigo in CODIGOS_DE_GRUPO:
        return False
    if sellos is None or len(sellos) > 0:
        return False
    return grupo_de_paquete(alimento_codigo) is None


def mensaje_educativo(alimento_codigo):
    """Mensaje amable con una alternativa si el alimento es un producto de
    paquete; None si no lo es."""
    grupo = grupo_de_paquete(alimento_codigo)
    return config.MENSAJES_ULTRAPROCESADO.get(grupo) if grupo else None


def penalizacion_ultraprocesado(alimento_codigo):
    """XP que se resta por registrar un producto de paquete. Con el valor
    del config en 0 (el de siempre, ver su comentario) nunca resta nada."""
    if config.XP_PENALIZACION_ULTRAPROCESADO <= 0 or grupo_de_paquete(alimento_codigo) is None:
        return 0
    return config.XP_PENALIZACION_ULTRAPROCESADO


def misiones_nuevas(accion, alimento_codigo, comidas_hoy, ya_cumplidas):
    """Ids de las misiones que se cumplen CON esta acción (y no se habían
    cumplido hoy). comidas_hoy cuenta las comidas registradas hoy, incluida
    esta."""
    cumple = {
        "fruta": accion == "comida_registrada" and alimento_codigo in config.FRUTAS,
        "tres_comidas": accion == "comida_registrada" and comidas_hoy >= config.COMIDAS_PARA_MISION,
        "check_in_animo": accion == "estado_animo",
    }
    return [m["id"] for m in config.MISIONES_DIARIAS if cumple.get(m["id"]) and m["id"] not in ya_cumplidas]


def mision_por_id(mision_id):
    return next((m for m in config.MISIONES_DIARIAS if m["id"] == mision_id), None)


def estado_misiones(ya_cumplidas):
    """Las misiones del día con su estado, para GET /progreso."""
    return [
        {"id": m["id"], "nombre": m["nombre"], "xp": m["xp"], "cumplida": m["id"] in ya_cumplidas}
        for m in config.MISIONES_DIARIAS
    ]


# ----- Calcomanías (insignias) -----
# Cada regla recibe los "hechos" del usuario (un diccionario con lo que ya
# hizo) y el umbral de su calcomanía, y responde si la cumple. Son funciones
# puras: no tocan MySQL, así que se prueban solas (test_gamificacion.py).
# Los hechos son:
#   comidas_total     cuántas comidas tiene en historial_comida
#   misiones_hechas   ids de misiones diarias cumplidas alguna vez
#   tiene_animo       hizo al menos un check-in de ánimo
#   ayudo_ia          confirmó a mano un plato (la IA dudó)
#   racha_maxima      la racha más larga que ha tenido
#   nivel_maximo      el nivel máximo alcanzado
#   dias_ausente_max  la ausencia más larga (días completos sin actividad)
REGLAS_CALCOMANIAS = {
    "primera_foto": lambda h, umbral: h["comidas_total"] >= umbral,
    "diez_registros": lambda h, umbral: h["comidas_total"] >= umbral,
    "tres_al_dia": lambda h, umbral: "tres_comidas" in h["misiones_hechas"],
    "fruta": lambda h, umbral: "fruta" in h["misiones_hechas"],
    "como_llegas": lambda h, umbral: h["tiene_animo"],
    "ayudaste_ia": lambda h, umbral: h["ayudo_ia"],
    "racha_3": lambda h, umbral: h["racha_maxima"] >= umbral,
    "racha_7": lambda h, umbral: h["racha_maxima"] >= umbral,
    "volviste": lambda h, umbral: h["dias_ausente_max"] >= umbral,
    "nivel_5": lambda h, umbral: h["nivel_maximo"] >= umbral,
}


def calcomania_por_id(calcomania_id):
    return next((c for c in config.CALCOMANIAS if c["id"] == calcomania_id), None)


def calcomanias_cumplidas(hechos):
    """Ids de las calcomanías cuya regla cumplen estos hechos."""
    return [c["id"] for c in config.CALCOMANIAS if REGLAS_CALCOMANIAS[c["id"]](hechos, c["umbral"])]


def calcomanias_por_otorgar(hechos, ya_ganadas):
    """Las que cumplen la regla y todavía no tenían: nunca se otorga dos veces."""
    return [cid for cid in calcomanias_cumplidas(hechos) if cid not in ya_ganadas]


def dias_ausente_maximo(fechas_de_actividad):
    """La ausencia más larga entre dos días con actividad, en días completos
    sin actividad (mismo criterio que dias_inactivos). Con menos de dos días
    de actividad no hay ausencia: 0."""
    fechas = sorted(set(fechas_de_actividad))
    return max((max(0, (b - a).days - 1) for a, b in zip(fechas, fechas[1:])), default=0)


def calcomania_publica(calcomania):
    """Lo que se entrega en `calcomanias_nuevas` (sin el umbral interno)."""
    return {k: calcomania[k] for k in ("id", "nombre", "descripcion", "rol")}


def dias_inactivos(ultima_fecha, hoy):
    """Días completos sin actividad entre la última actividad y hoy. Hoy
    no cuenta (todavía puede registrar algo). Sin actividad nunca: 0."""
    if ultima_fecha is None:
        return 0
    return max(0, (hoy - ultima_fecha).days - 1)


def perdida_por_inactividad(dias, xp_total, ya_descontado):
    """Cuánto XP hay que restar AHORA por `dias` días inactivos seguidos.

    `ya_descontado` es lo que ya se descontó en este mismo período de
    inactividad (en visitas anteriores). La cuenta es: "lo que debería
    llevar perdido a hoy" menos "lo que ya perdió". Por eso preguntar dos
    veces el mismo día da 0 la segunda vez: un día nunca se descuenta dos
    veces.

    Devuelve (xp_a_restar, nuevo_ya_descontado). xp_a_restar nunca deja
    el XP por debajo de 0.
    """
    if config.XP_PERDIDO_POR_DIA_INACTIVO <= 0:
        return 0, ya_descontado
    deberia_llevar = min(config.TOPE_PERDIDA_POR_PERIODO, dias * config.XP_PERDIDO_POR_DIA_INACTIVO)
    pendiente = max(0, deberia_llevar - ya_descontado)
    return min(pendiente, xp_total), ya_descontado + pendiente


def progreso_vacio(usuario_id):
    """El estado de un usuario que todavía no tiene fila en progreso_usuario."""
    return {
        "usuario_id": usuario_id, "xp_total": 0, "nivel_maximo": 1, "racha_actual": 0,
        "racha_maxima": 0, "ultima_fecha_actividad": None, "avatar_id": None,
        "xp_perdido_periodo": 0, "xp_perdido_sin_avisar": 0,
        "avatar_base": None, "ropa_id": None, "accesorio_id": None,
    }


def aplicar_inactividad(progreso, hoy):
    """Descuenta el XP de los días inactivos que todavía no se habían
    descontado. Modifica `progreso` y devuelve el XP restado ahora.

    El XP restado se acumula en xp_perdido_sin_avisar hasta que el
    usuario abre /progreso (ahí se le avisa una sola vez). El nivel
    máximo no se toca."""
    dias = dias_inactivos(progreso["ultima_fecha_actividad"], hoy)
    restar, descontado = perdida_por_inactividad(dias, progreso["xp_total"], progreso["xp_perdido_periodo"])
    progreso["xp_total"] -= restar
    progreso["xp_perdido_periodo"] = descontado
    progreso["xp_perdido_sin_avisar"] += restar
    return restar


def sumar_actividad(progreso, xp, hoy):
    """Suma el XP de una actividad registrada HOY y actualiza nivel máximo
    y racha. Registrar algo termina el período de inactividad: el próximo
    empieza con el tope completo. Modifica `progreso` y devuelve True si
    subió de nivel."""
    nivel_antes = progreso["nivel_maximo"]
    progreso["xp_total"] += xp
    progreso["nivel_maximo"] = nivel_alcanzado(nivel_antes, progreso["xp_total"])
    progreso["racha_actual"] = nueva_racha(progreso["racha_actual"], progreso["ultima_fecha_actividad"], hoy)
    progreso["racha_maxima"] = max(progreso["racha_maxima"], progreso["racha_actual"])
    progreso["ultima_fecha_actividad"] = hoy
    progreso["xp_perdido_periodo"] = 0
    return progreso["nivel_maximo"] > nivel_antes


def desbloqueado(elemento, nivel_maximo):
    """Un avatar DiceBear o un objeto (ropa/accesorio) está desbloqueado
    si el NIVEL MÁXIMO alcanzado llega a su nivel_requerido. Como el nivel
    máximo nunca baja, nada se vuelve a bloquear al perder XP."""
    return nivel_maximo >= elemento["nivel_requerido"]


def desbloqueos_al_subir(nivel_anterior, nivel):
    """Todo lo que se abrió al pasar de `nivel_anterior` a `nivel`: avatares
    DiceBear y objetos de ropa/accesorio con
    nivel_anterior < nivel_requerido <= nivel. Lista vacía si no subió.
    Nunca incluye lo que ya estaba abierto."""
    abiertos = [
        {"tipo": "avatar", "id": a["id"], "nombre": a["nombre"], "nivel_requerido": a["nivel_requerido"]}
        for a in config.AVATARES
    ] + [
        {"tipo": o["tipo"], "id": o["id"], "nombre": o["nombre"], "nivel_requerido": o["nivel_requerido"]}
        for o in config.OBJETOS_AVATAR
    ]
    return sorted(
        (d for d in abiertos if nivel_anterior < d["nivel_requerido"] <= nivel),
        key=lambda d: (d["nivel_requerido"], d["tipo"], d["id"]),
    )


def avatar_por_id(avatar_id):
    """Busca un avatar DiceBear del catálogo; None si no existe."""
    return next((a for a in config.AVATARES if a["id"] == avatar_id), None)


def url_avatar(avatar, estado_animo=None):
    """URL de DiceBear del avatar, con la expresión del estado de ánimo
    (o la neutra si no hay)."""
    expresion = config.EXPRESION_POR_ESTADO.get(estado_animo, config.EXPRESION_NEUTRA)
    parametros = {"seed": avatar["semilla"], **config.DICEBEAR_PARAMETROS_FIJOS, **expresion}
    return f"{config.DICEBEAR_URL}?{urlencode(parametros)}"


def base_por_id(base_id):
    """Busca una base del avatar por capas; None si no existe."""
    return next((b for b in config.BASES_AVATAR if b["id"] == base_id), None)


def objeto_por_id(item_id):
    """Busca una prenda o accesorio; None si no existe."""
    return next((o for o in config.OBJETOS_AVATAR if o["id"] == item_id), None)


def columna_de_tipo(tipo):
    """Columna de progreso_usuario donde se guarda lo puesto de ese tipo
    ("ropa" -> ropa_id). Solo acepta tipos del config: el nombre de la
    columna nunca sale directo de lo que manda el usuario."""
    if tipo not in config.TIPOS_OBJETO:
        return None
    return f"{tipo}_id"


def imagen_lista(archivo):
    """True si la diseñadora ya entregó ese archivo (existe en static/)."""
    return os.path.isfile(os.path.join(CARPETA_STATIC, config.CARPETA_IMAGENES_AVATAR, archivo))


def url_imagen(archivo):
    """URL completa de una capa del avatar. Aunque el archivo no exista
    todavía, la URL se arma igual (el frontend muestra un marcador)."""
    ruta = f"{config.CARPETA_IMAGENES_AVATAR}/{archivo}"
    if has_request_context():
        return url_for("static", filename=ruta, _external=True)
    return f"/static/{ruta}"


def _describir_imagen(elemento):
    return {
        "archivo": elemento["archivo"],
        "url": url_imagen(elemento["archivo"]),
        "imagen_lista": imagen_lista(elemento["archivo"]),
    }


def estado_avatar_capas(progreso):
    """Todo lo que necesita la pantalla "personalizar avatar": la base,
    lo que tiene puesto, las capas en orden para apilarlas, y cada objeto
    con si está desbloqueado y cuántos niveles le faltan."""
    nivel = progreso["nivel_maximo"]
    base = base_por_id(progreso["avatar_base"]) or base_por_id(config.BASE_POR_DEFECTO)

    # Capas de abajo hacia arriba: base, y luego un objeto por tipo en el
    # orden de config.TIPOS_OBJETO.
    capas = [{"tipo": "base", "id": base["id"], **_describir_imagen(base)}]
    puesto = {}
    for tipo in config.TIPOS_OBJETO:
        objeto = objeto_por_id(progreso[columna_de_tipo(tipo)])
        # Si lo guardado ya no existe en el catálogo, o dejó de estar
        # disponible (p. ej. se le subió el nivel en el config), no se pone.
        if objeto is None or objeto["tipo"] != tipo or not desbloqueado(objeto, nivel):
            puesto[tipo] = None
            continue
        puesto[tipo] = {"id": objeto["id"], "nombre": objeto["nombre"], **_describir_imagen(objeto)}
        capas.append({"tipo": tipo, "id": objeto["id"], **_describir_imagen(objeto)})

    archivos = [b["archivo"] for b in config.BASES_AVATAR] + [o["archivo"] for o in config.OBJETOS_AVATAR]
    respaldo = avatar_por_id(progreso["avatar_id"]) or avatar_por_id(config.AVATAR_POR_DEFECTO)
    return {
        "nivel_maximo": nivel,
        "imagenes_listas": all(imagen_lista(a) for a in archivos),
        "base": {"id": base["id"], "nombre": base["nombre"], **_describir_imagen(base)},
        "puesto": puesto,
        "capas": capas,
        "bases": [
            {"id": b["id"], "nombre": b["nombre"], **_describir_imagen(b), "seleccionada": b["id"] == base["id"]}
            for b in config.BASES_AVATAR
        ],
        "objetos": {
            tipo: [
                {
                    "id": o["id"],
                    "tipo": o["tipo"],
                    "nombre": o["nombre"],
                    **_describir_imagen(o),
                    "nivel_requerido": o["nivel_requerido"],
                    "desbloqueado": desbloqueado(o, nivel),
                    "niveles_faltantes": max(0, o["nivel_requerido"] - nivel),
                    "puesto": bool(puesto[tipo]) and puesto[tipo]["id"] == o["id"],
                }
                for o in config.OBJETOS_AVATAR if o["tipo"] == tipo
            ]
            for tipo in config.TIPOS_OBJETO
        },
        "respaldo_dicebear": {"id": respaldo["id"], "nombre": respaldo["nombre"], "url": url_avatar(respaldo)},
    }


def reglas_publicas():
    """Las reglas vigentes, para que el frontend no tenga que copiar
    números (si el config cambia, el frontend se entera solo)."""
    return {
        "acciones": config.ACCIONES,
        "meta_diaria_xp": config.META_DIARIA_XP,
        "niveles": config.NIVELES,
        "xp_perdido_por_dia_inactivo": config.XP_PERDIDO_POR_DIA_INACTIVO,
        "tope_perdida_por_periodo": config.TOPE_PERDIDA_POR_PERIODO,
        "misiones_diarias": config.MISIONES_DIARIAS,
        "xp_penalizacion_ultraprocesado": config.XP_PENALIZACION_ULTRAPROCESADO,
    }


# =====================================================================
# Base de datos
# =====================================================================


def _asegurar_columna(cursor, tabla, columna, definicion_sql):
    """Agrega una columna a una tabla que ya existía (CREATE TABLE IF NOT
    EXISTS no modifica tablas viejas). Misma idea que
    BaseDatos._asegurar_columna en database.py."""
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (tabla, columna),
    )
    if not cursor.fetchone()[0]:
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {definicion_sql}")
        print(f"Columna agregada: {tabla}.{columna}")


def _existe_columna(cursor, tabla, columna):
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (tabla, columna),
    )
    return bool(cursor.fetchone()[0])


def asegurar_tablas(conexion):
    cursor = conexion.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progreso_usuario (
                usuario_id INT PRIMARY KEY,
                xp_total INT NOT NULL DEFAULT 0,
                nivel_maximo INT NOT NULL DEFAULT 1,
                racha_actual INT NOT NULL DEFAULT 0,
                racha_maxima INT NOT NULL DEFAULT 0,
                ultima_fecha_actividad DATE NULL,
                avatar_id VARCHAR(40) NULL,
                xp_perdido_periodo INT NOT NULL DEFAULT 0,
                xp_perdido_sin_avisar INT NOT NULL DEFAULT 0,
                avatar_base VARCHAR(40) NULL,
                ropa_id VARCHAR(40) NULL,
                accesorio_id VARCHAR(40) NULL
            )
        """)
        # Tablas creadas antes del 27 sep 2026: la columna "nivel" pasa a
        # llamarse "nivel_maximo" (hasta ese día el XP nunca bajaba, así
        # que el valor guardado ya era el máximo alcanzado).
        if _existe_columna(cursor, "progreso_usuario", "nivel") and not _existe_columna(cursor, "progreso_usuario", "nivel_maximo"):
            cursor.execute("ALTER TABLE progreso_usuario CHANGE COLUMN nivel nivel_maximo INT NOT NULL DEFAULT 1")
            print("Columna renombrada: progreso_usuario.nivel -> nivel_maximo")
        _asegurar_columna(cursor, "progreso_usuario", "xp_perdido_periodo", "xp_perdido_periodo INT NOT NULL DEFAULT 0")
        _asegurar_columna(cursor, "progreso_usuario", "xp_perdido_sin_avisar", "xp_perdido_sin_avisar INT NOT NULL DEFAULT 0")
        _asegurar_columna(cursor, "progreso_usuario", "avatar_base", "avatar_base VARCHAR(40) NULL")
        _asegurar_columna(cursor, "progreso_usuario", "ropa_id", "ropa_id VARCHAR(40) NULL")
        _asegurar_columna(cursor, "progreso_usuario", "accesorio_id", "accesorio_id VARCHAR(40) NULL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actividad_diaria (
                usuario_id INT NOT NULL,
                fecha DATE NOT NULL,
                xp_ganado INT NOT NULL DEFAULT 0,
                meta_cumplida TINYINT(1) NOT NULL DEFAULT 0,
                PRIMARY KEY (usuario_id, fecha)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventos_xp (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT NOT NULL,
                fecha DATE NOT NULL,
                accion VARCHAR(40) NOT NULL,
                xp INT NOT NULL,
                creado DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_eventos_usuario_fecha (usuario_id, fecha)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calcomanias_usuario (
                usuario_id INT NOT NULL,
                calcomania_id VARCHAR(40) NOT NULL,
                fecha DATE NOT NULL,
                PRIMARY KEY (usuario_id, calcomania_id)
            )
        """)
        conexion.commit()
    finally:
        cursor.close()


COLUMNAS_PROGRESO = list(progreso_vacio(None))


def _leer_progreso(cursor, usuario_id, bloquear=False):
    sql = "SELECT * FROM progreso_usuario WHERE usuario_id = %s" + (" FOR UPDATE" if bloquear else "")
    cursor.execute(sql, (usuario_id,))
    fila = cursor.fetchone()
    progreso = {**progreso_vacio(usuario_id), **fila} if fila else progreso_vacio(usuario_id)
    # Por si alguien bajó los umbrales de NIVELES en el config: el nivel
    # máximo nunca queda por debajo del que da el XP actual.
    progreso["nivel_maximo"] = nivel_alcanzado(progreso["nivel_maximo"], progreso["xp_total"])
    return progreso


def _guardar_progreso(cursor, progreso):
    """Crea o reemplaza la fila del usuario con todo `progreso`."""
    columnas = ", ".join(COLUMNAS_PROGRESO)
    marcas = ", ".join(["%s"] * len(COLUMNAS_PROGRESO))
    actualizar = ", ".join(f"{c} = VALUES({c})" for c in COLUMNAS_PROGRESO if c != "usuario_id")
    cursor.execute(
        f"INSERT INTO progreso_usuario ({columnas}) VALUES ({marcas}) ON DUPLICATE KEY UPDATE {actualizar}",
        [progreso[c] for c in COLUMNAS_PROGRESO],
    )


def _descontar_inactividad(cursor, progreso, hoy):
    """aplicar_inactividad + deja constancia en eventos_xp (XP negativo)."""
    restado = aplicar_inactividad(progreso, hoy)
    if restado:
        cursor.execute(
            "INSERT INTO eventos_xp (usuario_id, fecha, accion, xp) VALUES (%s, %s, %s, %s)",
            (progreso["usuario_id"], hoy, "perdida_inactividad", -restado),
        )
    return restado


def _leer_xp_de_hoy(cursor, usuario_id, hoy):
    cursor.execute(
        "SELECT xp_ganado FROM actividad_diaria WHERE usuario_id = %s AND fecha = %s",
        (usuario_id, hoy),
    )
    fila = cursor.fetchone()
    return fila["xp_ganado"] if fila else 0


def _avatar_elegido(progreso):
    """El avatar DiceBear guardado, o el de por defecto si no hay, ya no
    existe en el catálogo o ya no está disponible."""
    avatar = avatar_por_id(progreso["avatar_id"])
    if avatar is None or not desbloqueado(avatar, progreso["nivel_maximo"]):
        avatar = avatar_por_id(config.AVATAR_POR_DEFECTO)
    return avatar


PREFIJO_MISION = "mision_"  # en eventos_xp, la misión "fruta" se guarda como accion "mision_fruta"


def _veces_hoy(cursor, usuario_id, hoy, accion):
    cursor.execute(
        "SELECT COUNT(*) AS veces FROM eventos_xp WHERE usuario_id = %s AND fecha = %s AND accion = %s",
        (usuario_id, hoy, accion),
    )
    return cursor.fetchone()["veces"]


def _misiones_cumplidas_hoy(cursor, usuario_id, hoy):
    cursor.execute(
        "SELECT accion FROM eventos_xp WHERE usuario_id = %s AND fecha = %s AND accion LIKE %s",
        (usuario_id, hoy, PREFIJO_MISION + "%"),
    )
    return {fila["accion"][len(PREFIJO_MISION):] for fila in cursor.fetchall()}


def _anotar(cursor, usuario_id, hoy, accion, xp):
    cursor.execute(
        "INSERT INTO eventos_xp (usuario_id, fecha, accion, xp) VALUES (%s, %s, %s, %s)",
        (usuario_id, hoy, accion, xp),
    )


def registrar_actividad(db, usuario_id, accion, estado_animo=None, alimento_codigo=None, sellos=None,
                        confirmacion_manual=False):
    """Da el XP de `accion`, actualiza nivel, racha y meta del día.

    Para una comida (`alimento_codigo` y `sellos` del alimento FINAL, el
    que quedó guardado) también da el bonus de elección nutritiva y aplica
    la penalización por ultraprocesados (que vale 0). Para cualquier acción
    revisa las misiones diarias.

    `confirmacion_manual` es True cuando la comida la confirmó la persona a
    mano (/confirmar-alimento): cuenta para la calcomanía "ayudaste_ia".

    Antes de sumar, descuenta el XP de los días inactivos pendientes (la
    pérdida es "perezosa": se calcula cuando el usuario vuelve).

    Se llama desde app.py justo DESPUÉS de guardar la comida o el estado
    de ánimo. Devuelve un resumen para el frontend ("+25 XP", "¡misión
    cumplida!", "¡subiste de nivel!"), o None si no aplica (sin usuario) o
    si algo falla. Nunca lanza una excepción: un error de gamificación no
    debe impedir que la comida o el ánimo se guarden.
    """
    if usuario_id is None or accion not in config.ACCIONES:
        return None
    if not db.conexion or not db.conexion.is_connected():
        return None

    hoy = date.today()
    cursor = db.conexion.cursor(dictionary=True)
    try:
        # 1. XP de la acción (con su tope diario)
        xp = xp_a_otorgar(accion, _veces_hoy(cursor, usuario_id, hoy, accion))
        _anotar(cursor, usuario_id, hoy, accion, xp)
        detalle = [{"motivo": accion, "xp": xp}]

        es_comida = accion == "comida_registrada"
        # 2. Bonus por elección nutritiva (solo comidas, con su propio tope)
        if es_comida and es_eleccion_nutritiva(alimento_codigo, sellos):
            bonus = xp_a_otorgar("eleccion_nutritiva", _veces_hoy(cursor, usuario_id, hoy, "eleccion_nutritiva"))
            _anotar(cursor, usuario_id, hoy, "eleccion_nutritiva", bonus)
            if bonus:
                detalle.append({"motivo": "eleccion_nutritiva", "xp": bonus})

        # 3. Misiones del día que se cumplen con esta acción
        comidas_hoy = _veces_hoy(cursor, usuario_id, hoy, "comida_registrada") if es_comida else 0
        cumplidas = misiones_nuevas(accion, alimento_codigo, comidas_hoy, _misiones_cumplidas_hoy(cursor, usuario_id, hoy))
        misiones = []
        for mision_id in cumplidas:
            mision = mision_por_id(mision_id)
            _anotar(cursor, usuario_id, hoy, PREFIJO_MISION + mision_id, mision["xp"])
            detalle.append({"motivo": PREFIJO_MISION + mision_id, "xp": mision["xp"]})
            misiones.append({"id": mision_id, "nombre": mision["nombre"], "xp": mision["xp"]})
        ganado = sum(d["xp"] for d in detalle)

        progreso = _leer_progreso(cursor, usuario_id, bloquear=True)
        _descontar_inactividad(cursor, progreso, hoy)
        nivel_anterior = progreso["nivel_maximo"]
        subio = sumar_actividad(progreso, ganado, hoy)

        # 4. Penalización por ultraprocesados: con el config en 0 no pasa nada.
        #    El XP no baja de 0 y el nivel máximo no se toca.
        if es_comida:
            castigo = min(penalizacion_ultraprocesado(alimento_codigo), progreso["xp_total"])
            if castigo:
                progreso["xp_total"] -= castigo
                _anotar(cursor, usuario_id, hoy, "penalizacion_ultraprocesado", -castigo)
                detalle.append({"motivo": "penalizacion_ultraprocesado", "xp": -castigo})
        _guardar_progreso(cursor, progreso)

        # La meta del día cuenta solo lo ganado (lo positivo).
        xp_hoy_antes = _leer_xp_de_hoy(cursor, usuario_id, hoy)
        xp_hoy = xp_hoy_antes + ganado
        cumplida = xp_hoy >= config.META_DIARIA_XP
        cursor.execute(
            """
            INSERT INTO actividad_diaria (usuario_id, fecha, xp_ganado, meta_cumplida)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE xp_ganado = VALUES(xp_ganado), meta_cumplida = VALUES(meta_cumplida)
            """,
            (usuario_id, hoy, xp_hoy, int(cumplida)),
        )

        # 5. Calcomanías. Si fallan no se pierde el XP ya calculado: solo
        #    se avisa que no hubo calcomanías nuevas.
        try:
            calcomanias_nuevas = _otorgar_calcomanias(cursor, usuario_id, hoy, confirmacion_manual)
        except Exception as e:
            print(f"Error al otorgar calcomanías (el XP sí se guardó): {e}")
            calcomanias_nuevas = []
        db.conexion.commit()

        resumen = {
            "accion": accion,
            "xp_ganado": sum(d["xp"] for d in detalle),
            "detalle_xp": detalle,
            "tope_diario_alcanzado": xp == 0,
            "misiones_cumplidas": misiones,
            "xp_total": progreso["xp_total"],
            "nivel": progreso["nivel_maximo"],
            "subio_de_nivel": subio,
            "nivel_anterior": nivel_anterior,
            "desbloqueos": desbloqueos_al_subir(nivel_anterior, progreso["nivel_maximo"]),
            "racha_actual": progreso["racha_actual"],
            "calcomanias_nuevas": calcomanias_nuevas,
            "meta_diaria": {
                "xp_hoy": xp_hoy,
                "meta": config.META_DIARIA_XP,
                "cumplida": cumplida,
                "recien_cumplida": cumplida and xp_hoy_antes < config.META_DIARIA_XP,
            },
        }
        if estado_animo is not None:
            resumen["avatar_url"] = url_avatar(_avatar_elegido(progreso), estado_animo)
        return resumen
    except Exception as e:
        db.conexion.rollback()
        print(f"Error en gamificación (no afecta el registro guardado): {e}")
        return None
    finally:
        cursor.close()


# ----- Calcomanías: base de datos -----


def _calcomanias_ganadas(cursor, usuario_id):
    """{id: fecha} de las calcomanías que el usuario ya tiene."""
    cursor.execute("SELECT calcomania_id, fecha FROM calcomanias_usuario WHERE usuario_id = %s", (usuario_id,))
    return {fila["calcomania_id"]: fila["fecha"] for fila in cursor.fetchall()}


def _hechos_del_usuario(cursor, usuario_id, confirmacion_manual=False):
    """Junta de la base los hechos que piden las reglas (ver
    REGLAS_CALCOMANIAS). Sirve igual para el usuario que acaba de actuar y
    para quien ya cumplía una regla antes de que existieran las calcomanías.

    `confirmacion_manual` es la señal en vivo de /confirmar-alimento. Para
    quien confirmó antes de que existieran, la base solo guarda certeza_ia
    = 100 (una confirmación humana se guarda con 100.0)."""
    cursor.execute("SELECT COUNT(*) AS n, COALESCE(SUM(certeza_ia >= 100), 0) AS manuales "
                   "FROM historial_comida WHERE usuario_id = %s", (usuario_id,))
    comidas = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) AS n FROM estado_animo WHERE usuario_id = %s", (usuario_id,))
    animos = cursor.fetchone()["n"]
    cursor.execute("SELECT DISTINCT accion FROM eventos_xp WHERE usuario_id = %s AND accion LIKE %s",
                   (usuario_id, PREFIJO_MISION + "%"))
    misiones = {fila["accion"][len(PREFIJO_MISION):] for fila in cursor.fetchall()}
    cursor.execute("SELECT fecha FROM actividad_diaria WHERE usuario_id = %s", (usuario_id,))
    fechas = [fila["fecha"] for fila in cursor.fetchall()]
    progreso = _leer_progreso(cursor, usuario_id)
    return {
        "comidas_total": comidas["n"],
        "misiones_hechas": misiones,
        "tiene_animo": animos > 0,
        "ayudo_ia": confirmacion_manual or int(comidas["manuales"]) > 0,
        "racha_maxima": progreso["racha_maxima"],
        "nivel_maximo": progreso["nivel_maximo"],
        "dias_ausente_max": dias_ausente_maximo(fechas),
    }


def _otorgar_calcomanias(cursor, usuario_id, hoy, confirmacion_manual=False):
    """Otorga las calcomanías que ya se cumplen y no se tenían. Devuelve
    cuáles son nuevas (ya en su forma pública). INSERT IGNORE + la llave
    primaria (usuario, calcomanía) hacen imposible otorgarla dos veces."""
    hechos = _hechos_del_usuario(cursor, usuario_id, confirmacion_manual)
    nuevas = calcomanias_por_otorgar(hechos, _calcomanias_ganadas(cursor, usuario_id))
    for calcomania_id in nuevas:
        cursor.execute("INSERT IGNORE INTO calcomanias_usuario (usuario_id, calcomania_id, fecha) VALUES (%s, %s, %s)",
                       (usuario_id, calcomania_id, hoy))
    return [calcomania_publica(calcomania_por_id(cid)) for cid in nuevas]


def resumen_calcomanias(cursor, usuario_id):
    """{"ganadas": n, "total": n} para GET /progreso."""
    return {"ganadas": len(_calcomanias_ganadas(cursor, usuario_id)), "total": len(config.CALCOMANIAS)}


def obtener_calcomanias(db, usuario_id):
    """Para GET /calcomanias. A quien ya cumplía una regla antes de que
    existiera el sistema se la otorga aquí, sin anunciarla como nueva (su
    fecha es la de hoy: no se sabe cuándo la cumplió)."""
    cursor = db.conexion.cursor(dictionary=True)
    try:
        _otorgar_calcomanias(cursor, usuario_id, date.today())
        ganadas = _calcomanias_ganadas(cursor, usuario_id)
        db.conexion.commit()
    except Exception:
        db.conexion.rollback()
        raise
    finally:
        cursor.close()
    lista = [
        {
            **{k: c[k] for k in ("id", "nombre", "descripcion", "como_se_gana", "rol")},
            "ganada": c["id"] in ganadas,
            "fecha": ganadas[c["id"]].isoformat() if c["id"] in ganadas else None,
        }
        for c in config.CALCOMANIAS
    ]
    return {"ganadas": len(ganadas), "total": len(config.CALCOMANIAS), "calcomanias": lista}


def _estado_animo_de_hoy(cursor, usuario_id, hoy):
    """Último estado de ánimo registrado HOY por el usuario, o None."""
    cursor.execute(
        "SELECT estado FROM estado_animo WHERE usuario_id = %s AND DATE(fecha) = %s ORDER BY id DESC LIMIT 1",
        (usuario_id, hoy),
    )
    fila = cursor.fetchone()
    return fila["estado"] if fila else None


def obtener_progreso(db, usuario_id):
    """Estado completo para GET /progreso. Aquí también se descuenta
    (perezosamente) el XP de los días inactivos, y se entrega UNA sola vez
    el aviso de cuánto XP se perdió desde la última visita."""
    hoy = date.today()
    cursor = db.conexion.cursor(dictionary=True)
    try:
        progreso = _leer_progreso(cursor, usuario_id, bloquear=True)
        _descontar_inactividad(cursor, progreso, hoy)
        xp_perdido = progreso["xp_perdido_sin_avisar"]
        if xp_perdido:
            progreso["xp_perdido_sin_avisar"] = 0  # ya se le avisó
            _guardar_progreso(cursor, progreso)
        xp_hoy = _leer_xp_de_hoy(cursor, usuario_id, hoy)
        estado_hoy = _estado_animo_de_hoy(cursor, usuario_id, hoy)
        misiones_hoy = _misiones_cumplidas_hoy(cursor, usuario_id, hoy)
        db.conexion.commit()
    except Exception:
        db.conexion.rollback()
        raise
    finally:
        cursor.close()

    avatar = _avatar_elegido(progreso)
    nivel = progreso["nivel_maximo"]
    inicio, siguiente = limites_del_nivel(nivel)
    ultima = progreso["ultima_fecha_actividad"]
    return {
        "xp_total": progreso["xp_total"],
        "nivel": nivel,
        "xp_inicio_nivel": inicio,
        "xp_siguiente_nivel": siguiente,
        "xp_faltante_siguiente_nivel": max(0, siguiente - progreso["xp_total"]) if siguiente is not None else None,
        "racha_actual": racha_vigente(progreso["racha_actual"], ultima, hoy),
        "racha_maxima": progreso["racha_maxima"],
        "ultima_fecha_actividad": ultima.isoformat() if ultima else None,
        "xp_perdido_desde_ultima_visita": xp_perdido,
        "mensaje_regreso": config.MENSAJE_REGRESO if xp_perdido else None,
        "meta_diaria": {
            "xp_hoy": xp_hoy,
            "meta": config.META_DIARIA_XP,
            "cumplida": xp_hoy >= config.META_DIARIA_XP,
        },
        "misiones": estado_misiones(misiones_hoy),
        "avatar": {
            "id": avatar["id"],
            "nombre": avatar["nombre"],
            "url": url_avatar(avatar),
            "estado_animo_hoy": estado_hoy,
            "url_con_animo": url_avatar(avatar, estado_hoy),
            "urls_por_estado": {estado: url_avatar(avatar, estado) for estado in config.EXPRESION_POR_ESTADO},
        },
        "reglas": reglas_publicas(),
    }


def _leer_progreso_sin_cambiar(db, usuario_id):
    """Lee el progreso para mostrarlo. Termina la transacción al final:
    app.py usa UNA sola conexión, y una lectura sin commit deja abierta una
    transacción que seguiría viendo los datos viejos (MySQL guarda una
    "foto" de la base al empezar cada transacción)."""
    cursor = db.conexion.cursor(dictionary=True)
    try:
        return _leer_progreso(cursor, usuario_id)
    finally:
        cursor.close()
        db.conexion.commit()


def listar_avatares(db, usuario_id):
    progreso = _leer_progreso_sin_cambiar(db, usuario_id)
    elegido = _avatar_elegido(progreso)
    nivel = progreso["nivel_maximo"]
    return {
        "xp_total": progreso["xp_total"],
        "nivel_maximo": nivel,
        "avatar_actual": elegido["id"],
        "avatares": [
            {
                "id": a["id"],
                "nombre": a["nombre"],
                "url": url_avatar(a),
                "nivel_requerido": a["nivel_requerido"],
                "desbloqueado": desbloqueado(a, nivel),
                "niveles_faltantes": max(0, a["nivel_requerido"] - nivel),
                "seleccionado": a["id"] == elegido["id"],
            }
            for a in config.AVATARES
        ],
    }


def _respuesta_bloqueado(que, elemento, nivel):
    return False, 403, {
        "error": f'{que} "{elemento["id"]}" todavía está bloqueado.',
        "nivel_requerido": elemento["nivel_requerido"],
        "nivel_maximo": nivel,
        "niveles_faltantes": elemento["nivel_requerido"] - nivel,
    }


def elegir_avatar(db, usuario_id, avatar_id):
    """Guarda el avatar DiceBear elegido. Devuelve (ok, codigo_http, cuerpo)."""
    avatar = avatar_por_id(avatar_id)
    if avatar is None:
        return False, 400, {"error": f'El avatar "{avatar_id}" no existe.'}

    cursor = db.conexion.cursor(dictionary=True)
    try:
        progreso = _leer_progreso(cursor, usuario_id, bloquear=True)
        if not desbloqueado(avatar, progreso["nivel_maximo"]):
            db.conexion.rollback()
            return _respuesta_bloqueado("El avatar", avatar, progreso["nivel_maximo"])
        progreso["avatar_id"] = avatar_id
        _guardar_progreso(cursor, progreso)
        db.conexion.commit()
    finally:
        cursor.close()
    return True, 200, {
        "success": True,
        "avatar": {"id": avatar["id"], "nombre": avatar["nombre"], "url": url_avatar(avatar)},
    }


def obtener_avatar_capas(db, usuario_id):
    return estado_avatar_capas(_leer_progreso_sin_cambiar(db, usuario_id))


def _cambiar_avatar_capas(db, usuario_id, cambio):
    """Lee el progreso bloqueando la fila, le aplica `cambio(progreso)` y
    guarda. `cambio` devuelve None si todo bien, o (codigo, cuerpo) de
    error. Devuelve (ok, codigo_http, cuerpo)."""
    cursor = db.conexion.cursor(dictionary=True)
    try:
        progreso = _leer_progreso(cursor, usuario_id, bloquear=True)
        error = cambio(progreso)
        if error:
            db.conexion.rollback()
            return error
        _guardar_progreso(cursor, progreso)
        db.conexion.commit()
    finally:
        cursor.close()
    return True, 200, {"success": True, **estado_avatar_capas(progreso)}


def elegir_base(db, usuario_id, base_id):
    if base_por_id(base_id) is None:
        return False, 400, {"error": f'La base "{base_id}" no existe.'}

    def cambio(progreso):
        progreso["avatar_base"] = base_id

    return _cambiar_avatar_capas(db, usuario_id, cambio)


def equipar(db, usuario_id, tipo, item_id):
    columna = columna_de_tipo(tipo)
    if columna is None:
        return False, 400, {"error": f'El tipo "{tipo}" no existe. Tipos: {", ".join(config.TIPOS_OBJETO)}.'}
    objeto = objeto_por_id(item_id)
    if objeto is None:
        return False, 400, {"error": f'El objeto "{item_id}" no existe.'}
    if objeto["tipo"] != tipo:
        return False, 400, {"error": f'El objeto "{item_id}" es de tipo "{objeto["tipo"]}", no "{tipo}".'}

    def cambio(progreso):
        if not desbloqueado(objeto, progreso["nivel_maximo"]):
            return _respuesta_bloqueado("El objeto", objeto, progreso["nivel_maximo"])
        progreso[columna] = item_id

    return _cambiar_avatar_capas(db, usuario_id, cambio)


def quitar(db, usuario_id, tipo):
    columna = columna_de_tipo(tipo)
    if columna is None:
        return False, 400, {"error": f'El tipo "{tipo}" no existe. Tipos: {", ".join(config.TIPOS_OBJETO)}.'}

    def cambio(progreso):
        progreso[columna] = None

    return _cambiar_avatar_capas(db, usuario_id, cambio)


# =====================================================================
# Endpoints
# =====================================================================

bp = Blueprint("gamificacion", __name__)
_db = None  # la instancia de BaseDatos de app.py, asignada en registrar_gamificacion()


def registrar_gamificacion(app, db):
    """Llamar una vez al arrancar app.py."""
    global _db
    _db = db
    if db.conexion and db.conexion.is_connected():
        asegurar_tablas(db.conexion)
    app.register_blueprint(bp)


def _usuario_id_desde_email(email):
    """(usuario_id, None) o (None, respuesta_de_error). Toda la
    identificación del usuario pasa por aquí: si el login cambia (p. ej.
    a sesión o token), solo hay que cambiar esta función."""
    if not email:
        return None, (jsonify({"error": 'Falta el parámetro "email".'}), 400)
    perfil = _db.obtener_perfil_por_email(email)
    if not perfil:
        return None, (jsonify({"error": "No existe un perfil con ese correo."}), 404)
    return perfil["id"], None


def _datos_con_campos(*campos):
    """(datos, None) o (None, respuesta 400) si falta alguno de `campos`."""
    datos = request.get_json(silent=True) or {}
    for campo in campos:
        if not datos.get(campo):
            return None, (jsonify({"error": f'Falta el campo "{campo}".'}), 400)
    return datos, None


@bp.route("/progreso", methods=["GET"])
def ruta_progreso():
    usuario_id, error = _usuario_id_desde_email(request.args.get("email"))
    if error:
        return error
    return jsonify({"success": True, "progreso": obtener_progreso(_db, usuario_id)}), 200


@bp.route("/calcomanias", methods=["GET"])
def ruta_calcomanias():
    usuario_id, error = _usuario_id_desde_email(request.args.get("email"))
    if error:
        return error
    return jsonify({"success": True, **obtener_calcomanias(_db, usuario_id)}), 200


@bp.route("/avatares", methods=["GET"])
def ruta_avatares():
    usuario_id, error = _usuario_id_desde_email(request.args.get("email"))
    if error:
        return error
    return jsonify({"success": True, **listar_avatares(_db, usuario_id)}), 200


@bp.route("/avatar", methods=["POST"])
def ruta_elegir_avatar():
    datos, error = _datos_con_campos("avatar_id")
    if error:
        return error
    usuario_id, error = _usuario_id_desde_email(datos.get("email"))
    if error:
        return error
    _, codigo, cuerpo = elegir_avatar(_db, usuario_id, datos["avatar_id"])
    return jsonify(cuerpo), codigo


# ----- Avatar por capas (Figma): base + ropa + accesorio -----

@bp.route("/avatar", methods=["GET"])
def ruta_avatar_capas():
    usuario_id, error = _usuario_id_desde_email(request.args.get("email"))
    if error:
        return error
    return jsonify({"success": True, **obtener_avatar_capas(_db, usuario_id)}), 200


@bp.route("/avatar/base", methods=["POST"])
def ruta_elegir_base():
    datos, error = _datos_con_campos("base_id")
    if error:
        return error
    usuario_id, error = _usuario_id_desde_email(datos.get("email"))
    if error:
        return error
    _, codigo, cuerpo = elegir_base(_db, usuario_id, datos["base_id"])
    return jsonify(cuerpo), codigo


@bp.route("/avatar/equipar", methods=["POST"])
def ruta_equipar():
    datos, error = _datos_con_campos("tipo", "item_id")
    if error:
        return error
    usuario_id, error = _usuario_id_desde_email(datos.get("email"))
    if error:
        return error
    _, codigo, cuerpo = equipar(_db, usuario_id, datos["tipo"], datos["item_id"])
    return jsonify(cuerpo), codigo


@bp.route("/avatar/quitar", methods=["POST"])
def ruta_quitar():
    datos, error = _datos_con_campos("tipo")
    if error:
        return error
    usuario_id, error = _usuario_id_desde_email(datos.get("email"))
    if error:
        return error
    _, codigo, cuerpo = quitar(_db, usuario_id, datos["tipo"])
    return jsonify(cuerpo), codigo
