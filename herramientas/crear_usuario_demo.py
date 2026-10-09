"""
crear_usuario_demo.py -- cuenta de DEMOSTRACIÓN para grabar el video.

Arma demo@lumea.co con 7 días de actividad inventada (comidas, check-ins de
ánimo y misiones), terminando AYER: así hoy queda libre para registrar algo
en vivo durante la grabación y la racha sigue vigente. Para que la racha
no se pierda, córrelo el mismo día de la grabación o el día anterior.

    python3 herramientas/crear_usuario_demo.py                # crea (si no existe)
    python3 herramientas/crear_usuario_demo.py --borrar       # borra y la vuelve a crear
    python3 herramientas/crear_usuario_demo.py --solo-borrar  # solo la borra

Es una cuenta de demostración: en el video se dice así. NO hay fotos ni
datos de personas reales: el perfil es genérico y las comidas son un plan
fijo de alimentos de la tabla (más abajo, PLAN_DE_LA_SEMANA).

La contraseña se genera al azar en cada corrida y SOLO sale en pantalla:
no se guarda en ningún archivo ni en el repositorio (en MySQL queda su hash
de bcrypt, como en cualquier cuenta).

Los datos NO se escriben a mano en las tablas de gamificación: se pasan por
las mismas funciones de la app (registrar_actividad), con la fecha de cada
día simulada. Así el XP, la racha, el nivel, las misiones y las calcomanías
son exactamente los que daría la app de verdad.

Solo toca las filas de EMAIL_DEMO: no borra ni cambia nada de nadie más.
Necesita MySQL encendido (no necesita el servidor Flask).
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import secrets
from datetime import date, timedelta

import bcrypt

import gamificacion as g
import gamificacion_config as config
from database import conectar_mysql
from sellos import obtener_sellos

EMAIL_DEMO = "demo@lumea.co"
# Datos genéricos: no corresponden a ninguna persona real.
PERFIL_DEMO = {
    "nombre": "Cuenta de demostración", "edad": 15, "genero": "otro",
    "objetivo": "comer_balanceado",
}

# Los 7 días terminan ayer. Cada día: las comidas (código del alimento y la
# certeza con que la IA la reconoció, siempre menor que 100: no hay
# confirmaciones manuales) y el check-in de ánimo (None = ese día no hizo
# check-in). Hay un día malo a propósito: el XP no depende del ánimo.
# Con este plan: 9 comidas (la décima sería la calcomanía "diez_registros"),
# una racha de 7 días, y las misiones de fruta, 3 comidas y check-in.
# "dias_atras" cuenta desde hoy: 7 = hace una semana, 1 = ayer.
PLAN_DE_LA_SEMANA = [
    {"dias_atras": 7, "comidas": [("arepa", 91.4)], "animo": None},
    {"dias_atras": 6, "comidas": [("banano", 97.8), ("bandeja_paisa", 88.6)], "animo": "bien"},
    {"dias_atras": 5, "comidas": [("huevo", 84.2)], "animo": "mal"},
    {"dias_atras": 4, "comidas": [("pandebono", 79.5)], "animo": None},
    {"dias_atras": 3, "comidas": [("arepa", 95.0), ("natilla", 82.4), ("pandebono", 77.1)], "animo": "bien"},
    {"dias_atras": 2, "comidas": [], "animo": "muy_bien"},
    {"dias_atras": 1, "comidas": [("bandeja_paisa", 86.9)], "animo": "bien"},
]

TABLAS_DEL_USUARIO = (
    "eventos_xp", "actividad_diaria", "progreso_usuario", "calcomanias_usuario",
    "historial_comida", "estado_animo",
)
# Resultado esperado de la demo (la herramienta avisa si no se cumple).
NIVELES_ESPERADOS = (3, 4)
CALCOMANIAS_ESPERADAS = (4, 6)


class _Db:
    """Lo mínimo que gamificacion.py necesita de BaseDatos: .conexion. No se
    crea BaseDatos() para no correr sus migraciones de esquema."""
    def __init__(self, conexion):
        self.conexion = conexion


class _DiaSimulado:
    """Reemplaza a `date` dentro de gamificacion.py (que solo la usa para
    date.today()): devuelve el día que se está simulando, no el de hoy."""
    dia = None

    @classmethod
    def today(cls):
        return date(cls.dia.year, cls.dia.month, cls.dia.day)  # un date normal


def _generar_contrasena():
    # Sin letras que se confunden (0/O, 1/l/I) para poder leerla en el video.
    alfabeto = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(12))


def _buscar_id(cursor):
    cursor.execute("SELECT id FROM perfil WHERE email = %s", (EMAIL_DEMO,))
    fila = cursor.fetchone()
    return fila[0] if fila else None


def borrar_demo(conexion):
    """Borra de MySQL todo lo de EMAIL_DEMO. Devuelve True si existía."""
    cursor = conexion.cursor()
    usuario_id = _buscar_id(cursor)
    if usuario_id is not None:
        for tabla in TABLAS_DEL_USUARIO:
            cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
        cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
    conexion.commit()
    cursor.close()
    return usuario_id is not None


def _crear_perfil(conexion, contrasena):
    hash_bcrypt = bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO perfil (nombre, email, edad, genero, objetivo, password_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (PERFIL_DEMO["nombre"], EMAIL_DEMO, PERFIL_DEMO["edad"], PERFIL_DEMO["genero"],
         PERFIL_DEMO["objetivo"], hash_bcrypt),
    )
    conexion.commit()
    usuario_id = cursor.lastrowid
    cursor.close()
    return usuario_id


def _guardar_comida(conexion, usuario_id, dia, codigo, certeza):
    """Lo mismo que BaseDatos.registrar_comida, pero con la fecha del día simulado."""
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(
        "SELECT nombre_pantalla, calorias, es_saludable FROM tabla_alimentos WHERE alimento_codigo = %s",
        (codigo,),
    )
    info = cursor.fetchone()
    if info is None:
        cursor.close()
        raise SystemExit(f"El alimento '{codigo}' del plan no está en tabla_alimentos.")
    cursor.execute(
        "INSERT INTO historial_comida (usuario_id, fecha, alimento_codigo, alimento_detectado, certeza_ia, "
        "calorias_aprox, balanceado) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (usuario_id, dia, codigo, info["nombre_pantalla"], certeza, info["calorias"], info["es_saludable"]),
    )
    conexion.commit()
    cursor.close()


def _guardar_animo(conexion, usuario_id, dia, estado):
    cursor = conexion.cursor()
    cursor.execute("INSERT INTO estado_animo (usuario_id, fecha, estado) VALUES (%s, %s, %s)", (usuario_id, dia, estado))
    conexion.commit()
    cursor.close()


def _simular_semana(conexion, usuario_id):
    """Recorre los 7 días en orden, pasando cada acción por registrar_actividad."""
    db = _Db(conexion)
    fecha_real = g.date
    g.date = _DiaSimulado  # dentro de gamificacion.py, "hoy" es el día simulado
    try:
        for dia_plan in PLAN_DE_LA_SEMANA:
            _DiaSimulado.dia = date.today() - timedelta(days=dia_plan["dias_atras"])
            for codigo, certeza in dia_plan["comidas"]:
                _guardar_comida(conexion, usuario_id, _DiaSimulado.dia, codigo, certeza)
                resumen = g.registrar_actividad(
                    db, usuario_id, "comida_registrada", alimento_codigo=codigo, sellos=obtener_sellos(db, codigo),
                )
                if resumen is None:
                    raise SystemExit("registrar_actividad no pudo guardar (¿MySQL apagado o tablas sin crear?).")
            if dia_plan["animo"]:
                _guardar_animo(conexion, usuario_id, _DiaSimulado.dia, dia_plan["animo"])
                g.registrar_actividad(db, usuario_id, "estado_animo", estado_animo=dia_plan["animo"])
    finally:
        g.date = fecha_real  # que no quede el día simulado si algo falla
    return db


def _poner_avatar(db, usuario_id, nivel):
    """Viste el avatar con lo que ya está desbloqueado (se ve mejor en el video)."""
    ropa = "camiseta_lumea" if nivel >= 3 else "buzo_verde"
    for tipo, item in (("ropa", ropa), ("accesorio", "gafas")):
        ok, codigo, _ = g.equipar(db, usuario_id, tipo, item)
        if not ok:
            print(f"  (no se pudo poner {item}: código {codigo})")


def crear_demo(conexion):
    contrasena = _generar_contrasena()
    usuario_id = _crear_perfil(conexion, contrasena)
    db = _simular_semana(conexion, usuario_id)

    progreso = g.obtener_progreso(db, usuario_id)  # hoy: sin pérdida (la última actividad fue ayer)
    _poner_avatar(db, usuario_id, progreso["nivel"])
    calcomanias = g.obtener_calcomanias(db, usuario_id)
    ganadas = [c["nombre"] for c in calcomanias["calcomanias"] if c["ganada"]]

    print("\nCuenta de demostración lista")
    print(f"  correo:     {EMAIL_DEMO}")
    print(f"  contraseña: {contrasena}   (solo sale aquí; no se guarda en ningún archivo)")
    print(f"  nivel {progreso['nivel']} · {progreso['xp_total']} XP · racha {progreso['racha_actual']} días "
          f"· {calcomanias['ganadas']} de {calcomanias['total']} calcomanías")
    print(f"  calcomanías: {', '.join(ganadas)}")
    print("  Hoy está libre: registra algo en vivo en la grabación (suma a la racha y a las misiones de hoy).")
    print("  En el video: \"esta es una cuenta de demostración\".")

    problemas = []
    if progreso["nivel"] not in NIVELES_ESPERADOS:
        problemas.append(f"el nivel es {progreso['nivel']} y se esperaba {NIVELES_ESPERADOS[0]} o {NIVELES_ESPERADOS[1]}")
    if not CALCOMANIAS_ESPERADAS[0] <= calcomanias["ganadas"] <= CALCOMANIAS_ESPERADAS[1]:
        problemas.append(f"hay {calcomanias['ganadas']} calcomanías y se esperaban de {CALCOMANIAS_ESPERADAS[0]} a {CALCOMANIAS_ESPERADAS[1]}")
    if progreso["racha_actual"] < len(PLAN_DE_LA_SEMANA):
        problemas.append(f"la racha es {progreso['racha_actual']} y se esperaban {len(PLAN_DE_LA_SEMANA)} días")
    if problemas:
        print("\nOJO: el resultado no es el esperado (¿cambió gamificacion_config.py?): " + "; ".join(problemas))
        print("Ajusta PLAN_DE_LA_SEMANA y vuelve a correr con --borrar.")
        return 1
    return 0


def main():
    args = set(_sys.argv[1:])
    desconocidos = args - {"--borrar", "--solo-borrar"}
    if desconocidos:
        raise SystemExit(f"Opción desconocida: {', '.join(sorted(desconocidos))}. Usa --borrar o --solo-borrar.")

    conexion = conectar_mysql()
    if conexion is None:
        raise SystemExit("MySQL no está disponible: enciéndelo (Ajustes del Sistema → MySQL → Start) y vuelve a correr.")
    conexion.cursor().execute("USE lumea_db")
    g.asegurar_tablas(conexion)  # solo crea las tablas de gamificación si faltan

    cursor = conexion.cursor()
    existe = _buscar_id(cursor) is not None
    cursor.close()

    if "--solo-borrar" in args or "--borrar" in args:
        print(f"Cuenta {EMAIL_DEMO} borrada." if borrar_demo(conexion) else f"La cuenta {EMAIL_DEMO} no existía.")
        if "--solo-borrar" in args:
            return 0
    elif existe:
        print(f"La cuenta {EMAIL_DEMO} ya existe. Usa --borrar para borrarla y crearla de nuevo (con otra contraseña).")
        return 1

    try:
        return crear_demo(conexion)
    except BaseException:
        # Si algo falla a medias, no dejar una cuenta incompleta.
        conexion.rollback()
        borrar_demo(conexion)
        raise
    finally:
        conexion.close()


if __name__ == "__main__":
    _sys.exit(main())
