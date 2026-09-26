"""
gamificacion.py -- Núcleo de gamificación (XP, niveles, racha, meta
diaria y avatares), solo backend.

Vive en su propio archivo, separado de app.py y database.py, para que se
pueda trabajar en paralelo con el resto del backend sin pisarse. app.py
solo hace dos cosas:
  1. registrar_gamificacion(app, db) al arrancar: crea las tablas si no
     existen y registra los endpoints de este archivo.
  2. registrar_actividad(db, usuario_id, accion) justo después de guardar
     algo que da XP (una comida, un estado de ánimo).

Todos los números (XP por acción, topes, meta, niveles, avatares) están
en gamificacion_config.py. Aquí no hay ninguno.

Tablas:
- progreso_usuario: una fila por usuario con su estado acumulado.
- actividad_diaria: una fila por usuario y día (XP del día, meta cumplida).
- eventos_xp: una fila por cada acción registrada, con el XP que dio
  (0 si ya había llegado al tope del día). Sirve para contar cuántas
  veces se hizo cada acción hoy y para poder explicar de dónde salió el
  XP de cada usuario.
"""

from datetime import date, timedelta
from urllib.parse import urlencode

from flask import Blueprint, jsonify, request

import gamificacion_config as config

# =====================================================================
# Lógica pura: no toca la base de datos, así que se puede probar sola
# (ver test_gamificacion.py).
# =====================================================================


def calcular_nivel(xp_total):
    """Nivel = cuántos umbrales de config.NIVELES ya alcanzó (mínimo 1)."""
    return max(1, sum(1 for umbral in config.NIVELES if xp_total >= umbral))


def rango_del_nivel(xp_total):
    """(XP donde empieza el nivel actual, XP donde empieza el siguiente).
    El segundo es None si ya está en el último nivel."""
    nivel = calcular_nivel(xp_total)
    inicio = config.NIVELES[nivel - 1]
    siguiente = config.NIVELES[nivel] if nivel < len(config.NIVELES) else None
    return inicio, siguiente


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


def avatar_por_id(avatar_id):
    """Busca un avatar del catálogo; None si no existe."""
    return next((a for a in config.AVATARES if a["id"] == avatar_id), None)


def url_avatar(avatar, estado_animo=None):
    """URL de DiceBear del avatar, con la expresión del estado de ánimo
    (o la neutra si no hay)."""
    expresion = config.EXPRESION_POR_ESTADO.get(estado_animo, config.EXPRESION_NEUTRA)
    parametros = {"seed": avatar["semilla"], **config.DICEBEAR_PARAMETROS_FIJOS, **expresion}
    return f"{config.DICEBEAR_URL}?{urlencode(parametros)}"


def reglas_publicas():
    """Las reglas vigentes, para que el frontend no tenga que copiar
    números (si el config cambia, el frontend se entera solo)."""
    return {
        "acciones": config.ACCIONES,
        "meta_diaria_xp": config.META_DIARIA_XP,
        "niveles": config.NIVELES,
    }


# =====================================================================
# Base de datos
# =====================================================================


def asegurar_tablas(conexion):
    cursor = conexion.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progreso_usuario (
                usuario_id INT PRIMARY KEY,
                xp_total INT NOT NULL DEFAULT 0,
                nivel INT NOT NULL DEFAULT 1,
                racha_actual INT NOT NULL DEFAULT 0,
                racha_maxima INT NOT NULL DEFAULT 0,
                ultima_fecha_actividad DATE NULL,
                avatar_id VARCHAR(40) NULL
            )
        """)
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
        conexion.commit()
    finally:
        cursor.close()


def _leer_progreso(cursor, usuario_id, bloquear=False):
    sql = "SELECT * FROM progreso_usuario WHERE usuario_id = %s" + (" FOR UPDATE" if bloquear else "")
    cursor.execute(sql, (usuario_id,))
    return cursor.fetchone() or {
        "usuario_id": usuario_id, "xp_total": 0, "nivel": 1, "racha_actual": 0,
        "racha_maxima": 0, "ultima_fecha_actividad": None, "avatar_id": None,
    }


def _leer_xp_de_hoy(cursor, usuario_id, hoy):
    cursor.execute(
        "SELECT xp_ganado FROM actividad_diaria WHERE usuario_id = %s AND fecha = %s",
        (usuario_id, hoy),
    )
    fila = cursor.fetchone()
    return fila["xp_ganado"] if fila else 0


def _avatar_elegido(progreso):
    """El avatar guardado, o el de por defecto si no hay o ya no existe
    en el catálogo (p. ej. si se quitó del config)."""
    return avatar_por_id(progreso["avatar_id"]) or avatar_por_id(config.AVATAR_POR_DEFECTO)


def registrar_actividad(db, usuario_id, accion, estado_animo=None):
    """Da el XP de `accion`, actualiza nivel, racha y meta del día.

    Se llama desde app.py justo DESPUÉS de guardar la comida o el estado
    de ánimo. Devuelve un resumen para el frontend ("+10 XP", "¡subiste
    de nivel!", "¡meta cumplida!"), o None si no aplica (sin usuario) o
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
        cursor.execute(
            "SELECT COUNT(*) AS veces FROM eventos_xp WHERE usuario_id = %s AND fecha = %s AND accion = %s",
            (usuario_id, hoy, accion),
        )
        xp = xp_a_otorgar(accion, cursor.fetchone()["veces"])
        cursor.execute(
            "INSERT INTO eventos_xp (usuario_id, fecha, accion, xp) VALUES (%s, %s, %s, %s)",
            (usuario_id, hoy, accion, xp),
        )

        progreso = _leer_progreso(cursor, usuario_id, bloquear=True)
        nivel_antes = calcular_nivel(progreso["xp_total"])
        xp_total = progreso["xp_total"] + xp
        nivel = calcular_nivel(xp_total)
        racha = nueva_racha(progreso["racha_actual"], progreso["ultima_fecha_actividad"], hoy)
        racha_maxima = max(progreso["racha_maxima"], racha)
        cursor.execute(
            """
            INSERT INTO progreso_usuario
                (usuario_id, xp_total, nivel, racha_actual, racha_maxima, ultima_fecha_actividad, avatar_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                xp_total = VALUES(xp_total), nivel = VALUES(nivel),
                racha_actual = VALUES(racha_actual), racha_maxima = VALUES(racha_maxima),
                ultima_fecha_actividad = VALUES(ultima_fecha_actividad)
            """,
            (usuario_id, xp_total, nivel, racha, racha_maxima, hoy, progreso["avatar_id"]),
        )

        xp_hoy_antes = _leer_xp_de_hoy(cursor, usuario_id, hoy)
        xp_hoy = xp_hoy_antes + xp
        cumplida = xp_hoy >= config.META_DIARIA_XP
        cursor.execute(
            """
            INSERT INTO actividad_diaria (usuario_id, fecha, xp_ganado, meta_cumplida)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE xp_ganado = VALUES(xp_ganado), meta_cumplida = VALUES(meta_cumplida)
            """,
            (usuario_id, hoy, xp_hoy, int(cumplida)),
        )
        db.conexion.commit()

        resumen = {
            "accion": accion,
            "xp_ganado": xp,
            "tope_diario_alcanzado": xp == 0,
            "xp_total": xp_total,
            "nivel": nivel,
            "subio_de_nivel": nivel > nivel_antes,
            "racha_actual": racha,
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


def _estado_animo_de_hoy(cursor, usuario_id, hoy):
    """Último estado de ánimo registrado HOY por el usuario, o None."""
    cursor.execute(
        "SELECT estado FROM estado_animo WHERE usuario_id = %s AND DATE(fecha) = %s ORDER BY id DESC LIMIT 1",
        (usuario_id, hoy),
    )
    fila = cursor.fetchone()
    return fila["estado"] if fila else None


def obtener_progreso(db, usuario_id):
    hoy = date.today()
    cursor = db.conexion.cursor(dictionary=True)
    try:
        progreso = _leer_progreso(cursor, usuario_id)
        xp_hoy = _leer_xp_de_hoy(cursor, usuario_id, hoy)
        estado_hoy = _estado_animo_de_hoy(cursor, usuario_id, hoy)
    finally:
        cursor.close()

    avatar = _avatar_elegido(progreso)
    inicio, siguiente = rango_del_nivel(progreso["xp_total"])
    ultima = progreso["ultima_fecha_actividad"]
    return {
        "xp_total": progreso["xp_total"],
        "nivel": calcular_nivel(progreso["xp_total"]),
        "xp_inicio_nivel": inicio,
        "xp_siguiente_nivel": siguiente,
        "racha_actual": racha_vigente(progreso["racha_actual"], ultima, hoy),
        "racha_maxima": progreso["racha_maxima"],
        "ultima_fecha_actividad": ultima.isoformat() if ultima else None,
        "meta_diaria": {
            "xp_hoy": xp_hoy,
            "meta": config.META_DIARIA_XP,
            "cumplida": xp_hoy >= config.META_DIARIA_XP,
        },
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


def listar_avatares(db, usuario_id):
    cursor = db.conexion.cursor(dictionary=True)
    try:
        progreso = _leer_progreso(cursor, usuario_id)
    finally:
        cursor.close()
    elegido = _avatar_elegido(progreso)
    return {
        "xp_total": progreso["xp_total"],
        "avatar_actual": elegido["id"],
        "avatares": [
            {
                "id": a["id"],
                "nombre": a["nombre"],
                "url": url_avatar(a),
                "xp_requerido": a["xp_requerido"],
                "desbloqueado": progreso["xp_total"] >= a["xp_requerido"],
                "seleccionado": a["id"] == elegido["id"],
            }
            for a in config.AVATARES
        ],
    }


def elegir_avatar(db, usuario_id, avatar_id):
    """Guarda el avatar elegido. Devuelve (ok, codigo_http, cuerpo)."""
    avatar = avatar_por_id(avatar_id)
    if avatar is None:
        return False, 400, {"error": f'El avatar "{avatar_id}" no existe.'}

    cursor = db.conexion.cursor(dictionary=True)
    try:
        progreso = _leer_progreso(cursor, usuario_id)
        if progreso["xp_total"] < avatar["xp_requerido"]:
            faltan = avatar["xp_requerido"] - progreso["xp_total"]
            return False, 403, {
                "error": f'El avatar "{avatar_id}" todavía está bloqueado.',
                "xp_requerido": avatar["xp_requerido"],
                "xp_faltante": faltan,
            }
        cursor.execute(
            """
            INSERT INTO progreso_usuario (usuario_id, avatar_id) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE avatar_id = VALUES(avatar_id)
            """,
            (usuario_id, avatar_id),
        )
        db.conexion.commit()
    finally:
        cursor.close()
    return True, 200, {
        "success": True,
        "avatar": {"id": avatar["id"], "nombre": avatar["nombre"], "url": url_avatar(avatar)},
    }


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


@bp.route("/progreso", methods=["GET"])
def ruta_progreso():
    usuario_id, error = _usuario_id_desde_email(request.args.get("email"))
    if error:
        return error
    return jsonify({"success": True, "progreso": obtener_progreso(_db, usuario_id)}), 200


@bp.route("/avatares", methods=["GET"])
def ruta_avatares():
    usuario_id, error = _usuario_id_desde_email(request.args.get("email"))
    if error:
        return error
    return jsonify({"success": True, **listar_avatares(_db, usuario_id)}), 200


@bp.route("/avatar", methods=["POST"])
def ruta_elegir_avatar():
    datos = request.get_json(silent=True) or {}
    if not datos.get("avatar_id"):
        return jsonify({"error": 'Falta el campo "avatar_id".'}), 400
    usuario_id, error = _usuario_id_desde_email(datos.get("email"))
    if error:
        return error
    _, codigo, cuerpo = elegir_avatar(_db, usuario_id, datos["avatar_id"])
    return jsonify(cuerpo), codigo
