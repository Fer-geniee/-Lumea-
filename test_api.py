"""
Prueba todos los endpoints contra el backend corriendo (python3 app.py).

    python3 test_api.py              # prueba y al final borra sus datos de prueba
    python3 test_api.py --conservar  # prueba y deja los datos para mirarlos

Cada corrida usa un correo nuevo (__test_api_<hora>__@lumea.test): así
empieza siempre sin XP ni historial y las expectativas de gamificación son
exactas. La limpieza final borra SOLO filas de correos con ese patrón.
"""

import os
import sys
import time

import requests

import gamificacion_config as config

# Cualquier foto de comida sirve. Por defecto, Backend/prueba.jpeg, que ya
# viene en el repo.
RUTA_IMAGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba.jpeg")

BASE_URL = "http://127.0.0.1:5002"
PATRON_EMAIL_PRUEBA = "__test_api_%__@lumea.test"
EMAIL_PRUEBA = PATRON_EMAIL_PRUEBA.replace("%", str(int(time.time())))

# User-Agent explícito: si un firewall/software de seguridad está
# bloqueando específicamente el User-Agent por defecto de la librería
# requests ("python-requests/x.x"), identificarnos como curl lo evita.
HEADERS = {"User-Agent": "curl/8.7.1"}

resultados = []


def verificar(nombre, respuesta, esperado=200, mostrar=True):
    ok = respuesta.status_code == esperado
    resultados.append((nombre, ok))
    print(f"[{'OK' if ok else 'FALLA'}] {nombre} -> HTTP {respuesta.status_code}")
    try:
        cuerpo = respuesta.json()
    except ValueError:
        print("    (respuesta no es JSON)", respuesta.text[:200])
        return {}
    if mostrar or not ok:
        print("   ", cuerpo)
    return cuerpo


def comprobar(nombre, condicion, detalle=""):
    """Para verificar un VALOR de la respuesta, no solo el código HTTP."""
    resultados.append((nombre, bool(condicion)))
    print(f"[{'OK' if condicion else 'FALLA'}] {nombre}" + (f" ({detalle})" if detalle else ""))


def get(ruta, **params):
    return requests.get(f"{BASE_URL}{ruta}", headers=HEADERS, params=params)


def post(ruta, json=None, **kwargs):
    return requests.post(f"{BASE_URL}{ruta}", headers=HEADERS, json=json, **kwargs)


def probar_perfil():
    verificar("POST /perfil", post("/perfil", {
        "nombre": "Prueba test_api", "email": EMAIL_PRUEBA, "edad": 15, "genero": "otro",
        "peso": 55.0, "altura": 160, "objetivo": "comer_balanceado",
    }))
    verificar("GET /perfil", get("/perfil", email=EMAIL_PRUEBA))


def probar_estado_animo():
    xp_animo = config.ACCIONES["estado_animo"]["xp"]
    cuerpo = verificar("POST /estado-animo (muy_mal)", post("/estado-animo", {"email": EMAIL_PRUEBA, "estado": "muy_mal"}))
    gami = cuerpo.get("gamificacion") or {}
    # Regla de contenido: el XP NO depende del ánimo reportado.
    comprobar("estado 'muy_mal' da el XP normal (no se castiga el ánimo)", gami.get("xp_ganado") == xp_animo,
              f"xp_ganado={gami.get('xp_ganado')}")
    comprobar("avatar_url trae la expresión de 'muy_mal'",
              "mouth=" + config.EXPRESION_POR_ESTADO["muy_mal"]["mouth"] in (gami.get("avatar_url") or ""))

    cuerpo = verificar("POST /estado-animo otra vez (muy_bien)", post("/estado-animo", {"email": EMAIL_PRUEBA, "estado": "muy_bien"}))
    gami = cuerpo.get("gamificacion") or {}
    esperado = xp_animo if config.ACCIONES["estado_animo"]["maximo_por_dia"] > 1 else 0
    comprobar("el tope diario se respeta en estado de ánimo", gami.get("xp_ganado") == esperado,
              f"xp_ganado={gami.get('xp_ganado')}, esperado={esperado}")
    verificar("GET /estado-animo", get("/estado-animo", email=EMAIL_PRUEBA), mostrar=False)
    return xp_animo


def probar_prediccion():
    with open(RUTA_IMAGEN, "rb") as f:
        cuerpo = verificar("POST /predecir", requests.post(
            f"{BASE_URL}/predecir", headers=HEADERS, files={"file": f}, data={"email": EMAIL_PRUEBA},
        ))
    if cuerpo.get("seleccion_manual") and cuerpo.get("opciones_sugeridas"):
        # Grupo de confusión: no guarda nada, pide confirmar entre opciones.
        codigos = [o["codigo"] for o in cuerpo.get("opciones_detalle", [])]
        comprobar("opciones_detalle coincide con opciones_sugeridas", codigos == cuerpo["opciones_sugeridas"])
        return 0
    return (cuerpo.get("gamificacion") or {}).get("xp_ganado", 0)


def probar_confirmar_alimento():
    cuerpo = verificar("POST /confirmar-alimento", post("/confirmar-alimento", {"alimento_codigo": "banano", "email": EMAIL_PRUEBA}))
    xp = (cuerpo.get("gamificacion") or {}).get("xp_ganado")
    comprobar("confirmar una comida da el XP de comida", xp == config.ACCIONES["comida_registrada"]["xp"], f"xp_ganado={xp}")
    # Los códigos de agrupación visual nunca deben aceptarse (ver grupos_confusion.py)
    verificar("POST /confirmar-alimento con 'sopas' (debe rechazar)",
              post("/confirmar-alimento", {"alimento_codigo": "sopas", "email": EMAIL_PRUEBA}), esperado=400)
    return xp or 0


def probar_historial():
    verificar("GET /historial", get("/historial", email=EMAIL_PRUEBA), mostrar=False)


def probar_alimentos():
    cuerpo = verificar("GET /alimentos", get("/alimentos"), mostrar=False)
    comprobar("GET /alimentos trae la lista", cuerpo.get("cantidad", 0) > 0, f"cantidad={cuerpo.get('cantidad')}")


def probar_gamificacion(xp_esperado):
    cuerpo = verificar("GET /progreso", get("/progreso", email=EMAIL_PRUEBA), mostrar=False)
    p = cuerpo.get("progreso", {})
    comprobar("xp_total = suma del XP ganado en esta corrida", p.get("xp_total") == xp_esperado,
              f"xp_total={p.get('xp_total')}, esperado={xp_esperado}")
    comprobar("racha de 1 día", p.get("racha_actual") == 1, f"racha={p.get('racha_actual')}")
    comprobar("meta diaria cumplida", (p.get("meta_diaria") or {}).get("cumplida") is (xp_esperado >= config.META_DIARIA_XP))
    comprobar("el avatar muestra el último ánimo de hoy", (p.get("avatar") or {}).get("estado_animo_hoy") == "muy_bien")
    comprobar("GET /progreso expone las reglas del config", (p.get("reglas") or {}).get("meta_diaria_xp") == config.META_DIARIA_XP)

    cuerpo = verificar("GET /avatares", get("/avatares", email=EMAIL_PRUEBA), mostrar=False)
    desbloqueados = {a["id"] for a in cuerpo.get("avatares", []) if a["desbloqueado"]}
    esperados = {a["id"] for a in config.AVATARES if a["xp_requerido"] <= xp_esperado}
    comprobar("avatares desbloqueados según el XP", desbloqueados == esperados, f"{sorted(desbloqueados)}")

    bloqueado = max(config.AVATARES, key=lambda a: a["xp_requerido"])["id"]
    verificar(f"POST /avatar bloqueado ({bloqueado}) -> 403", post("/avatar", {"email": EMAIL_PRUEBA, "avatar_id": bloqueado}), esperado=403)
    verificar("POST /avatar que no existe -> 400", post("/avatar", {"email": EMAIL_PRUEBA, "avatar_id": "no_existe"}), esperado=400)
    verificar("POST /avatar sin perfil -> 404", post("/avatar", {"email": "nadie@lumea.test", "avatar_id": "luna"}), esperado=404)
    verificar("POST /avatar desbloqueado (luna)", post("/avatar", {"email": EMAIL_PRUEBA, "avatar_id": "luna"}))
    cuerpo = verificar("GET /avatares después de elegir", get("/avatares", email=EMAIL_PRUEBA), mostrar=False)
    comprobar("avatar_actual quedó en luna", cuerpo.get("avatar_actual") == "luna")
    verificar("GET /progreso sin email -> 400", get("/progreso"), esperado=400)


def limpiar_datos_de_prueba():
    """Borra de MySQL todo lo que dejaron las corridas de este script."""
    from database import BaseDatos
    db = BaseDatos()
    cursor = db.conexion.cursor()
    cursor.execute("SELECT id FROM perfil WHERE email LIKE %s", (PATRON_EMAIL_PRUEBA,))
    ids = [fila[0] for fila in cursor.fetchall()]
    for usuario_id in ids:
        for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "historial_comida", "estado_animo"):
            cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
        cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
    db.conexion.commit()
    cursor.close()
    print(f"Datos de prueba borrados ({len(ids)} perfil(es) de prueba).")


if __name__ == "__main__":
    probar_perfil()
    xp = probar_estado_animo()
    xp += probar_prediccion()
    xp += probar_confirmar_alimento()
    probar_historial()
    probar_alimentos()
    probar_gamificacion(xp)

    fallas = [nombre for nombre, ok in resultados if not ok]
    print(f"\n{len(resultados) - len(fallas)}/{len(resultados)} pruebas OK.")
    if fallas:
        print("Fallaron:", ", ".join(fallas))

    if "--conservar" in sys.argv:
        print(f"Datos de prueba conservados (correo {EMAIL_PRUEBA}).")
    else:
        limpiar_datos_de_prueba()
    sys.exit(1 if fallas else 0)
