"""
dato_del_dia.py -- el dato curioso del día (GET /dato-del-dia).

Es el MISMO dato para todas las personas durante un día de Bogotá: no recibe
parámetros ni datos personales. Sale de las filas de tabla_alimentos que
tienen dato_curioso.

Cómo se elige (sin azar y sin guardar nada en la base):
  1. Se ordenan los alimentos por el hash SHA-256 de su código: un orden fijo
     que parece barajado, y que no cambia mientras los datos no cambien.
  2. El día elige el elemento `fecha.toordinal() % n` de esa lista. Días
     seguidos recorren la lista completa, sin repetir, antes de volver a empezar.
"""
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

ZONA_BOGOTA = ZoneInfo("America/Bogota")


def fecha_de_hoy():
    """El día de hoy en Bogotá (no el del servidor)."""
    return datetime.now(ZONA_BOGOTA).date()


def _huella(fila):
    return hashlib.sha256(fila["alimento_codigo"].encode("utf-8")).hexdigest()


def elegir_dato(filas, fecha):
    """La fila elegida para `fecha`, o None si no hay ningún dato curioso.
    `filas`: dicts con alimento_codigo, nombre_pantalla y dato_curioso; las
    que tienen el dato vacío no cuentan."""
    con_dato = sorted(
        (f for f in filas if f.get("dato_curioso") and f["dato_curioso"].strip()),
        key=_huella,
    )
    if not con_dato:
        return None
    return con_dato[fecha.toordinal() % len(con_dato)]


def respuesta_del_dia(filas, fecha):
    """El cuerpo JSON de GET /dato-del-dia, o None si no hay datos."""
    fila = elegir_dato(filas, fecha)
    if fila is None:
        return None
    return {
        "fecha": fecha.isoformat(),
        "alimento_codigo": fila["alimento_codigo"],
        "nombre": fila["nombre_pantalla"],
        "dato_curioso": fila["dato_curioso"].strip(),
    }
