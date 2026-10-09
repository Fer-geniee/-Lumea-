"""
test_flujo_completo.py -- El recorrido de un estudiante de verdad, de punta a
punta, contra el servidor real (python3 app.py) y los modelos actuales.

    python3 test_flujo_completo.py                 # corre y al final borra sus datos
    python3 test_flujo_completo.py --conservar     # deja los datos para mirarlos
    python3 test_flujo_completo.py --log servidor.log   # además revisa que el log
                                                        # no tenga hashes ni contraseñas

El recorrido: registro con contraseña -> login -> predecir con una foto ->
confirmar una opción de un grupo -> check-in de ánimo -> progreso (XP,
misiones, racha) -> historial con sellos -> avatar. Y los errores que un
estudiante puede provocar: contraseña incorrecta, correo que no existe, foto
vacía, código de alimento que no existe.

Cada corrida usa un correo nuevo (__flujo_<hora>__@lumea.test), así que
empieza sin XP ni historial. La limpieza borra SOLO filas de correos con
ese patrón.
"""
import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import sys
import time

import requests

import gamificacion_config as config

BASE_URL = os.environ.get("LUMEA_URL", "http://127.0.0.1:5002")  # LUMEA_URL: probar contra otro puerto
HEADERS = {"User-Agent": "curl/8.7.1"}  # igual que test_api.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOTO_COMIDA = os.path.join(BASE_DIR, "prueba.jpeg")
# Una foto que dispara el grupo de las sopas. dataset/ no está en git: si no
# existe, el paso 4 confirma directamente una opción del grupo.
FOTO_SOPA = os.path.join(BASE_DIR, "dataset", "sopas", "02934.jpg")
PATRON_EMAIL = "__flujo_%__@lumea.test"
EMAIL = PATRON_EMAIL.replace("%", str(int(time.time())))
CONTRASENA = "flujo-lumea-2026"

resultados = []


def paso(texto):
    print(f"\n== {texto}")


def comprobar(nombre, condicion, detalle=""):
    resultados.append((nombre, bool(condicion)))
    print(f"  [{'OK' if condicion else 'FALLA'}] {nombre}" + (f" ({detalle})" if detalle else ""))
    return bool(condicion)


def post(ruta, datos=None, **kwargs):
    return requests.post(f"{BASE_URL}{ruta}", json=datos, headers=HEADERS, **kwargs)


def get(ruta, **params):
    return requests.get(f"{BASE_URL}{ruta}", headers=HEADERS, params=params)


def cuerpo(respuesta):
    try:
        return respuesta.json()
    except ValueError:
        return {}


# Lo que la gamificación anunció durante el recorrido (lo llena xp_de, que se
# llama con cada respuesta que trae "gamificacion").
calcomanias_anunciadas = []
desbloqueos_anunciados = []


def xp_de(respuesta_json):
    gami = respuesta_json.get("gamificacion") or {}
    calcomanias_anunciadas.extend(c["id"] for c in gami.get("calcomanias_nuevas", []))
    desbloqueos_anunciados.extend((d["tipo"], d["id"]) for d in gami.get("desbloqueos", []))
    return gami.get("xp_ganado", 0)


def main():
    try:
        requests.get(f"{BASE_URL}/alimentos", headers=HEADERS, timeout=5)
    except requests.ConnectionError:
        sys.exit(f"El backend no está encendido en {BASE_URL}: corre python3 app.py")

    xp_esperado = 0
    comidas_guardadas = 0

    paso("1. Ana crea su cuenta")
    datos = {"nombre": "Ana Flujo", "email": EMAIL, "edad": 15, "genero": "femenino",
             "objetivo": "comer_balanceado"}
    comprobar("sin contraseña -> 400", post("/perfil", datos).status_code == 400)
    comprobar("contraseña de 5 caracteres -> 400", post("/perfil", {**datos, "contraseña": "12345"}).status_code == 400)
    r = post("/perfil", {**datos, "contraseña": CONTRASENA})
    comprobar("con contraseña -> 200", r.status_code == 200, r.text[:120])
    r = post("/perfil", {**datos, "contraseña": "otra-clave-123"})
    comprobar("registrarse otra vez con el mismo correo -> 409", r.status_code == 409)
    r = get("/perfil", email=EMAIL)
    comprobar("GET /perfil no trae el hash", r.status_code == 200 and "password_hash" not in r.text and "$2b$" not in r.text)

    paso("2. Ana inicia sesión")
    r = post("/login", {"email": EMAIL, "contraseña": CONTRASENA})
    c = cuerpo(r)
    comprobar("contraseña correcta -> 200 con su perfil", r.status_code == 200 and (c.get("perfil") or {}).get("email") == EMAIL)
    comprobar("la respuesta del login no trae el hash ni la contraseña", "$2b$" not in r.text and CONTRASENA not in r.text)
    mal = post("/login", {"email": EMAIL, "contraseña": "no-es-esta"})
    comprobar("contraseña incorrecta -> 401", mal.status_code == 401)
    nadie = post("/login", {"email": "nadie." + EMAIL, "contraseña": CONTRASENA})
    comprobar("correo que no existe -> 401 con el MISMO mensaje", nadie.status_code == 401 and cuerpo(nadie) == cuerpo(mal))

    paso("3. Ana le toma una foto a su comida")
    with open(FOTO_COMIDA, "rb") as f:
        r = requests.post(f"{BASE_URL}/predecir", headers=HEADERS, files={"file": f}, data={"email": EMAIL})
    c = cuerpo(r)
    comprobar("/predecir responde 200", r.status_code == 200, f"{c.get('alimento')} {c.get('certeza')}%")
    if c.get("success"):
        comidas_guardadas += 1
        xp_esperado += xp_de(c)
        comprobar("trae sellos_advertencia y mensaje_educativo", "sellos_advertencia" in c and "mensaje_educativo" in c)
    else:
        comprobar("si no la guardó, pide confirmar", c.get("seleccion_manual") is True)
    r = requests.post(f"{BASE_URL}/predecir", headers=HEADERS, files={"file": ("vacia.jpg", b"", "image/jpeg")}, data={"email": EMAIL})
    comprobar("foto vacía -> 400 con un mensaje claro", r.status_code == 400 and "error" in cuerpo(r), cuerpo(r).get("error", ""))
    r = requests.post(f"{BASE_URL}/predecir", headers=HEADERS, files={"file": ("texto.jpg", b"esto no es una foto", "image/jpeg")})
    comprobar("archivo que no es imagen -> 400", r.status_code == 400)

    paso("4. Una sopa: la app pide confirmar y Ana elige una opción del grupo")
    if os.path.exists(FOTO_SOPA):
        with open(FOTO_SOPA, "rb") as f:
            r = requests.post(f"{BASE_URL}/predecir", headers=HEADERS, files={"file": f}, data={"email": EMAIL})
        c = cuerpo(r)
    else:
        print("  (no está dataset/sopas/02934.jpg: se confirma directamente una opción del grupo)")
        r, c = None, {}
    opciones = c.get("opciones_detalle") or []
    if c.get("seleccion_manual") and opciones:
        comprobar("pide confirmar con opciones_detalle", True, ", ".join(o["nombre"] for o in opciones))
        elegida = opciones[0]["codigo"]
    else:
        # Con otro modelo la foto podría reconocerse sola; igual se prueba la
        # confirmación con una opción real de un grupo.
        if r is not None:
            comprobar("el modelo reconoció la foto sin pedir confirmación (se confirma igual una opción de grupo)", r.status_code == 200)
        if c.get("success"):
            comidas_guardadas += 1
            xp_esperado += xp_de(c)
        elegida = "ajiaco"
    r = post("/confirmar-alimento", {"alimento_codigo": elegida, "email": EMAIL})
    c = cuerpo(r)
    comprobar(f"confirmar '{elegida}' -> 200 y guardado", r.status_code == 200 and c.get("guardado_baseDatos") is True)
    comidas_guardadas += 1
    xp_esperado += xp_de(c)
    comprobar("el alimento final no es un código de grupo", c.get("alimento_codigo") not in {"sopas", "dulces"})
    comprobar("código que no existe -> 400", post("/confirmar-alimento", {"alimento_codigo": "no_existe", "email": EMAIL}).status_code == 400)
    comprobar("código de grupo ('sopas') -> 400", post("/confirmar-alimento", {"alimento_codigo": "sopas", "email": EMAIL}).status_code == 400)

    paso("5. Ana registra una fruta (misión del día)")
    r = post("/confirmar-alimento", {"alimento_codigo": "mango", "email": EMAIL})
    c = cuerpo(r)
    gami = c.get("gamificacion") or {}
    comidas_guardadas += 1
    xp_esperado += xp_de(c)
    comprobar("la fruta cumple la misión 'fruta'", "fruta" in [m["id"] for m in gami.get("misiones_cumplidas", [])])
    comprobar("la fruta da el bonus por registro", any(d["motivo"] == "bonus_registro" for d in gami.get("detalle_xp", [])))
    comprobar("la respuesta trae el consejo de la fruta (sin 'para_completar')",
              isinstance(c.get("consejo"), dict) and c["consejo"]["para_completar"] is None)

    paso("6. Check-in de ánimo")
    r = post("/estado-animo", {"email": EMAIL, "estado": "mal"})
    c = cuerpo(r)
    gami = c.get("gamificacion") or {}
    xp_esperado += xp_de(c)
    comprobar("check-in -> 200 con la cara del avatar", r.status_code == 200 and bool(gami.get("avatar_url")))
    comprobar("un ánimo 'mal' da el mismo XP que cualquier otro",
              {d["motivo"]: d["xp"] for d in gami.get("detalle_xp", [])}.get("estado_animo") == config.ACCIONES["estado_animo"]["xp"])

    paso("7. Ana mira su progreso")
    r = get("/progreso", email=EMAIL)
    p = cuerpo(r).get("progreso", {})
    comprobar("xp_total = suma de todo lo ganado", p.get("xp_total") == xp_esperado, f"{p.get('xp_total')} vs {xp_esperado}")
    comprobar("racha de 1 día", p.get("racha_actual") == 1)
    misiones = {m["id"]: m["cumplida"] for m in p.get("misiones", [])}
    comprobar("misiones del día con su estado", misiones.get("fruta") and misiones.get("check_in_animo")
              and misiones.get("tres_comidas") == (comidas_guardadas >= config.COMIDAS_PARA_MISION), f"{misiones}")
    comprobar("sin inactividad, sin XP perdido", p.get("xp_perdido_desde_ultima_visita") == 0)

    paso("7b. Sus calcomanías")
    comprobar("las primeras calcomanías se anunciaron en el momento",
              {"primera_foto", "ayudaste_ia", "fruta", "como_llegas"} <= set(calcomanias_anunciadas), f"{calcomanias_anunciadas}")
    comprobar("ninguna calcomanía se anunció dos veces", len(calcomanias_anunciadas) == len(set(calcomanias_anunciadas)))
    resumen = p.get("calcomanias") or {}
    r = get("/calcomanias", email=EMAIL)
    c = cuerpo(r)
    ganadas = {x["id"] for x in c.get("calcomanias", []) if x["ganada"]}
    comprobar("GET /calcomanias -> 200 con las 10 del catálogo", r.status_code == 200 and len(c.get("calcomanias", [])) == len(config.CALCOMANIAS))
    comprobar("las ganadas son exactamente las que se anunciaron", ganadas == set(calcomanias_anunciadas), f"{sorted(ganadas)}")
    comprobar("/progreso y /calcomanias cuentan lo mismo", resumen.get("ganadas") == c.get("ganadas") == len(ganadas))
    nivel_final = p.get("nivel", 1)
    esperados = {(o["tipo"], o["id"]) for o in config.OBJETOS_AVATAR if 1 < o["nivel_requerido"] <= nivel_final}
    esperados |= {("avatar", a["id"]) for a in config.AVATARES if 1 < a["nivel_requerido"] <= nivel_final}
    comprobar(f"los desbloqueos anunciados son todo lo que abre el nivel {nivel_final}, sin repetir",
              sorted(desbloqueos_anunciados) == sorted(esperados), f"{sorted(desbloqueos_anunciados)}")

    paso("8. Ana revisa su historial")
    r = get("/historial", email=EMAIL)
    c = cuerpo(r)
    registros = c.get("historial", [])
    comprobar("el historial tiene todas sus comidas", c.get("cantidad_registros") == comidas_guardadas,
              f"{c.get('cantidad_registros')} vs {comidas_guardadas}")
    comprobar("cada registro trae sus sellos", bool(registros) and all("sellos_advertencia" in x for x in registros))
    comprobar("cada registro trae es_fruta y solo el mango lo es",
              all(isinstance(x.get("es_fruta"), bool) for x in registros)
              and {x["alimento_codigo"] for x in registros if x["es_fruta"]} == {"mango"})

    paso("9. Ana personaliza su avatar")
    r = get("/avatar", email=EMAIL)
    comprobar("GET /avatar -> 200", r.status_code == 200)
    libre = next(o for o in config.OBJETOS_AVATAR if o["nivel_requerido"] == 1)
    r = post("/avatar/equipar", {"email": EMAIL, "tipo": libre["tipo"], "item_id": libre["id"]})
    comprobar(f"ponerse {libre['nombre']} -> 200", r.status_code == 200)
    caro = max(config.OBJETOS_AVATAR, key=lambda o: o["nivel_requerido"])
    r = post("/avatar/equipar", {"email": EMAIL, "tipo": caro["tipo"], "item_id": caro["id"]})
    comprobar(f"{caro['nombre']} (nivel {caro['nivel_requerido']}) bloqueado -> 403", r.status_code == 403)

    if "--log" in sys.argv:
        ruta_log = sys.argv[sys.argv.index("--log") + 1]
        paso("10. El log del servidor no tiene hashes ni contraseñas")
        with open(ruta_log, encoding="utf-8", errors="replace") as f:
            texto = f.read()
        comprobar("sin hashes de bcrypt en el log", "$2b$" not in texto and "$2a$" not in texto)
        comprobar("sin la contraseña en el log", CONTRASENA not in texto)

    fallas = [nombre for nombre, ok in resultados if not ok]
    print(f"\n{len(resultados) - len(fallas)}/{len(resultados)} comprobaciones OK.")
    if fallas:
        print("Fallaron:", ", ".join(fallas))
    if "--conservar" in sys.argv:
        print(f"Datos conservados (correo {EMAIL}).")
    else:
        limpiar()
    sys.exit(1 if fallas else 0)


def limpiar():
    """Borra de MySQL solo lo de los correos de prueba de este script."""
    from database import conectar_mysql  # solo la conexión: NO se crea BaseDatos()
    conexion = conectar_mysql()
    if conexion is None:
        print("(No se limpiaron los datos de prueba: MySQL no está disponible.)")
        return
    cursor = conexion.cursor()
    cursor.execute("USE lumea_db")
    cursor.execute("SELECT id FROM perfil WHERE email LIKE %s", (PATRON_EMAIL,))
    ids = [fila[0] for fila in cursor.fetchall()]
    for usuario_id in ids:
        for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "calcomanias_usuario", "historial_comida", "estado_animo"):
            cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
        cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
    conexion.commit()
    conexion.close()
    print(f"Datos de prueba borrados ({len(ids)} perfil(es)).")


if __name__ == "__main__":
    main()
