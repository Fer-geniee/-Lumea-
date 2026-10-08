"""
Prueba todos los endpoints contra el backend corriendo (python3 app.py).

    python3 test_api.py              # prueba y al final borra sus datos de prueba
    python3 test_api.py --conservar  # prueba y deja los datos para mirarlos

Cada corrida usa un correo nuevo (__test_api_<hora>__@lumea.test): así
empieza siempre sin XP ni historial y las expectativas de gamificación son
exactas. La limpieza final borra SOLO filas de correos con ese patrón.
"""
import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import sys
import time

import requests

import gamificacion_config as config
from grupos_confusion import GRUPOS_CONFUSION

# Cualquier foto de comida sirve. Por defecto, Backend/prueba.jpeg, que ya
# viene en el repo.
RUTA_IMAGEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prueba.jpeg")

BASE_URL = os.environ.get("LUMEA_URL", "http://127.0.0.1:5002")  # LUMEA_URL: probar contra otro puerto
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
    # Desde el login con Bcrypt, crear una cuenta exige contraseña (mínimo 6).
    datos = {
        "nombre": "Prueba test_api", "email": EMAIL_PRUEBA, "edad": 15, "genero": "otro",
        "peso": 55.0, "altura": 160, "objetivo": "comer_balanceado",
    }
    verificar("POST /perfil sin contraseña (cuenta nueva) -> 400", post("/perfil", datos), esperado=400)
    verificar("POST /perfil con contraseña corta -> 400", post("/perfil", {**datos, "contraseña": "123"}), esperado=400)
    verificar("POST /perfil", post("/perfil", {**datos, "contraseña": "prueba-123"}))
    verificar("POST /perfil otra vez con contraseña -> 409", post("/perfil", {**datos, "contraseña": "otra-123"}), esperado=409)
    verificar("POST /perfil sin contraseña (editar) -> 200", post("/perfil", {**datos, "edad": 16}))
    cuerpo = verificar("GET /perfil", get("/perfil", email=EMAIL_PRUEBA))
    comprobar("GET /perfil no trae password_hash", "password_hash" not in (cuerpo.get("perfil") or {}))


def xp_por_motivo(gami):
    return {d["motivo"]: d["xp"] for d in gami.get("detalle_xp", [])}


def probar_estado_animo():
    xp_animo = config.ACCIONES["estado_animo"]["xp"]
    xp_mision = next(m["xp"] for m in config.MISIONES_DIARIAS if m["id"] == "check_in_animo")
    cuerpo = verificar("POST /estado-animo (muy_mal)", post("/estado-animo", {"email": EMAIL_PRUEBA, "estado": "muy_mal"}))
    gami = cuerpo.get("gamificacion") or {}
    # Regla de contenido: el XP NO depende del ánimo reportado.
    comprobar("estado 'muy_mal' da el XP normal (no se castiga el ánimo)", xp_por_motivo(gami).get("estado_animo") == xp_animo,
              f"detalle_xp={gami.get('detalle_xp')}")
    comprobar("el primer check-in cumple la misión del día", [m["id"] for m in gami.get("misiones_cumplidas", [])] == ["check_in_animo"]
              and gami.get("xp_ganado") == xp_animo + xp_mision, f"xp_ganado={gami.get('xp_ganado')}")
    xp_total = gami.get("xp_ganado", 0)
    comprobar("avatar_url es un compañero gaze con los ojos de 'muy_mal'",
              (gami.get("avatar_url") or "").startswith(config.DICEBEAR_URL + "?")
              and "eyesVariant=" + config.EXPRESION_POR_ESTADO["muy_mal"]["eyesVariant"] in (gami.get("avatar_url") or ""),
              f"avatar_url={gami.get('avatar_url')}")

    cuerpo = verificar("POST /estado-animo otra vez (muy_bien)", post("/estado-animo", {"email": EMAIL_PRUEBA, "estado": "muy_bien"}))
    gami = cuerpo.get("gamificacion") or {}
    esperado = xp_animo if config.ACCIONES["estado_animo"]["maximo_por_dia"] > 1 else 0
    comprobar("el tope diario se respeta en estado de ánimo (y la misión no se repite)", gami.get("xp_ganado") == esperado,
              f"xp_ganado={gami.get('xp_ganado')}, esperado={esperado}")
    verificar("GET /estado-animo", get("/estado-animo", email=EMAIL_PRUEBA), mostrar=False)
    cuerpo = verificar("GET /estado-animo?dias=7", get("/estado-animo", email=EMAIL_PRUEBA, dias=7), mostrar=False)
    registros = cuerpo.get("historial", [])
    comprobar("los últimos 7 días traen fecha y estado de lo registrado hoy",
              len(registros) >= 2 and all(r.get("fecha") and r.get("estado") for r in registros), f"{len(registros)} registros")
    verificar("GET /estado-animo?dias=0 -> 400", get("/estado-animo", email=EMAIL_PRUEBA, dias=0), esperado=400)
    return xp_total + gami.get("xp_ganado", 0)


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
    if cuerpo.get("success"):
        comprobar("/predecir trae sellos_advertencia como lista", isinstance(cuerpo.get("sellos_advertencia"), list),
                  f"sellos_advertencia={cuerpo.get('sellos_advertencia')!r}")
    return (cuerpo.get("gamificacion") or {}).get("xp_ganado", 0)


def probar_confirmar_alimento():
    cuerpo = verificar("POST /confirmar-alimento", post("/confirmar-alimento", {"alimento_codigo": "banano", "email": EMAIL_PRUEBA}))
    gami = cuerpo.get("gamificacion") or {}
    motivos = xp_por_motivo(gami)
    comprobar("confirmar una comida da el XP de comida", motivos.get("comida_registrada") == config.ACCIONES["comida_registrada"]["xp"],
              f"detalle_xp={gami.get('detalle_xp')}")
    comprobar("banano da el bonus por registro y la misión fruta",
              motivos.get("bonus_registro") == config.ACCIONES["bonus_registro"]["xp"] and "mision_fruta" in motivos,
              f"detalle_xp={gami.get('detalle_xp')}")
    comprobar("banano trae un consejo sin 'para_completar' (es una fruta)",
              isinstance(cuerpo.get("consejo"), dict) and cuerpo["consejo"]["para_completar"] is None
              and cuerpo["consejo"]["grupo"] == "frutas_verduras", f"consejo={cuerpo.get('consejo')}")
    comprobar("banano no activa sellos de advertencia (lista vacía)", cuerpo.get("sellos_advertencia") == [],
              f"sellos_advertencia={cuerpo.get('sellos_advertencia')!r}")
    comprobar("banano no trae mensaje educativo", cuerpo.get("mensaje_educativo") is None)
    comprobar("la gamificación trae nivel_anterior y desbloqueos (lista)",
              isinstance(gami.get("nivel_anterior"), int) and isinstance(gami.get("desbloqueos"), list),
              f"nivel_anterior={gami.get('nivel_anterior')!r}, desbloqueos={gami.get('desbloqueos')!r}")
    nuevas = {c["id"] for c in gami.get("calcomanias_nuevas", [])}
    comprobar("confirmar a mano da las calcomanías 'ayudaste_ia' y 'fruta' (misión fruta)",
              {"ayudaste_ia", "fruta"} <= nuevas, f"calcomanias_nuevas={sorted(nuevas)}")
    comprobar("cada calcomanía nueva trae id, nombre, descripcion y rol",
              all(set(c) == {"id", "nombre", "descripcion", "rol"} for c in gami.get("calcomanias_nuevas", [])))
    xp = gami.get("xp_ganado", 0)

    gaseosa = next(gr for gr in GRUPOS_CONFUSION if gr["id"] == "gaseosas_bebidas_azucaradas")["opciones"][0]["codigo"]
    cuerpo = verificar(f"POST /confirmar-alimento ({gaseosa})", post("/confirmar-alimento", {"alimento_codigo": gaseosa, "email": EMAIL_PRUEBA}), mostrar=False)
    gami = cuerpo.get("gamificacion") or {}
    comprobar("un producto de paquete trae mensaje educativo", bool(cuerpo.get("mensaje_educativo")), f"{cuerpo.get('mensaje_educativo')!r}")
    comprobar("un producto de paquete da el mismo bonus por registro que una fruta y no resta XP",
              xp_por_motivo(gami).get("bonus_registro") == config.ACCIONES["bonus_registro"]["xp"]
              and all(d["xp"] >= 0 for d in gami.get("detalle_xp", [])))
    comprobar("el consejo de un producto de paquete trae una entrada por cada sello",
              [s["sello"] for s in (cuerpo.get("consejo") or {}).get("sellos", [])] == cuerpo.get("sellos_advertencia"),
              f"sellos={cuerpo.get('sellos_advertencia')}, consejo={cuerpo.get('consejo')}")
    xp += gami.get("xp_ganado", 0)
    # Los códigos de agrupación visual nunca deben aceptarse (ver grupos_confusion.py)
    verificar("POST /confirmar-alimento con 'sopas' (debe rechazar)",
              post("/confirmar-alimento", {"alimento_codigo": "sopas", "email": EMAIL_PRUEBA}), esperado=400)
    return xp


def probar_historial():
    cuerpo = verificar("GET /historial", get("/historial", email=EMAIL_PRUEBA), mostrar=False)
    registros = cuerpo.get("historial", [])
    comprobar("cada registro de /historial trae sellos_advertencia", bool(registros) and all("sellos_advertencia" in r for r in registros))
    banano = next((r for r in registros if r.get("alimento_codigo") == "banano"), {})
    comprobar("el banano del historial no tiene sellos", banano.get("sellos_advertencia") == [], f"{banano.get('sellos_advertencia')!r}")
    comprobar("cada registro de /historial trae es_fruta (booleano)", all(isinstance(r.get("es_fruta"), bool) for r in registros))
    comprobar("el banano es fruta y la gaseosa no", banano.get("es_fruta") is True
              and all(r["es_fruta"] is False for r in registros if r.get("alimento_codigo") not in config.FRUTAS))


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
    misiones = {m["id"]: m["cumplida"] for m in p.get("misiones", [])}
    comprobar("GET /progreso trae las misiones del día con su estado",
              misiones.get("fruta") is True and misiones.get("check_in_animo") is True and set(misiones) == {m["id"] for m in config.MISIONES_DIARIAS},
              f"misiones={misiones}")
    # Usuario que registró hoy: no hay días inactivos, así que no pierde nada.
    comprobar("sin inactividad no hay XP perdido ni mensaje", p.get("xp_perdido_desde_ultima_visita") == 0
              and p.get("mensaje_regreso") is None, f"perdido={p.get('xp_perdido_desde_ultima_visita')}")
    resumen = p.get("calcomanias") or {}
    comprobar("GET /progreso trae el resumen de calcomanías", resumen.get("total") == len(config.CALCOMANIAS)
              and resumen.get("ganadas", 0) >= 2, f"calcomanias={resumen}")
    cuerpo = verificar("GET /calcomanias", get("/calcomanias", email=EMAIL_PRUEBA), mostrar=False)
    lista = cuerpo.get("calcomanias", [])
    comprobar("GET /calcomanias lista todo el catálogo con sus campos",
              len(lista) == len(config.CALCOMANIAS) == cuerpo.get("total")
              and all({"id", "nombre", "descripcion", "como_se_gana", "rol", "ganada", "fecha"} <= set(c) for c in lista))
    comprobar("las ganadas de /calcomanias coinciden con /progreso",
              cuerpo.get("ganadas") == sum(c["ganada"] for c in lista) == resumen.get("ganadas"),
              f"{cuerpo.get('ganadas')} vs {resumen.get('ganadas')}")
    verificar("GET /calcomanias sin email -> 400", get("/calcomanias"), esperado=400)
    verificar("GET /calcomanias sin perfil -> 404", get("/calcomanias", email="nadie@lumea.test"), esperado=404)
    nivel = p.get("nivel", 1)

    cuerpo = verificar("GET /avatares", get("/avatares", email=EMAIL_PRUEBA), mostrar=False)
    desbloqueados = {a["id"] for a in cuerpo.get("avatares", []) if a["desbloqueado"]}
    esperados = {a["id"] for a in config.AVATARES if a["nivel_requerido"] <= nivel}
    comprobar("avatares desbloqueados según el nivel máximo", desbloqueados == esperados, f"{sorted(desbloqueados)}")

    bloqueado = max(config.AVATARES, key=lambda a: a["nivel_requerido"])["id"]
    verificar(f"POST /avatar bloqueado ({bloqueado}) -> 403", post("/avatar", {"email": EMAIL_PRUEBA, "avatar_id": bloqueado}), esperado=403)
    verificar("POST /avatar que no existe -> 400", post("/avatar", {"email": EMAIL_PRUEBA, "avatar_id": "no_existe"}), esperado=400)
    verificar("POST /avatar sin perfil -> 404", post("/avatar", {"email": "nadie@lumea.test", "avatar_id": "luna"}), esperado=404)
    verificar("POST /avatar desbloqueado (luna)", post("/avatar", {"email": EMAIL_PRUEBA, "avatar_id": "luna"}))
    cuerpo = verificar("GET /avatares después de elegir", get("/avatares", email=EMAIL_PRUEBA), mostrar=False)
    comprobar("avatar_actual quedó en luna", cuerpo.get("avatar_actual") == "luna")
    verificar("GET /progreso sin email -> 400", get("/progreso"), esperado=400)
    return nivel


def probar_avatar_capas(nivel):
    """Avatar por capas (Figma): base + ropa + accesorio. Funciona aunque
    las imágenes todavía no existan (responde con los nombres de archivo)."""
    cuerpo = verificar("GET /avatar", get("/avatar", email=EMAIL_PRUEBA), mostrar=False)
    comprobar("GET /avatar: base por defecto", (cuerpo.get("base") or {}).get("id") == config.BASE_POR_DEFECTO)
    comprobar("GET /avatar: trae los nombres de archivo", (cuerpo.get("base") or {}).get("archivo") == "base_1.png")
    comprobar("GET /avatar: nada puesto al empezar", cuerpo.get("puesto") == {t: None for t in config.TIPOS_OBJETO})
    objetos = [o for lista in (cuerpo.get("objetos") or {}).values() for o in lista]
    comprobar("GET /avatar: desbloqueado según el nivel máximo",
              all(o["desbloqueado"] == (o["nivel_requerido"] <= nivel) for o in objetos) and len(objetos) == len(config.OBJETOS_AVATAR))

    verificar("POST /avatar/base (base_2)", post("/avatar/base", {"email": EMAIL_PRUEBA, "base_id": "base_2"}), mostrar=False)
    verificar("POST /avatar/base que no existe -> 400", post("/avatar/base", {"email": EMAIL_PRUEBA, "base_id": "base_9"}), esperado=400)

    libre = next(o for o in config.OBJETOS_AVATAR if o["nivel_requerido"] <= nivel)
    cuerpo = verificar(f"POST /avatar/equipar ({libre['id']})",
                       post("/avatar/equipar", {"email": EMAIL_PRUEBA, "tipo": libre["tipo"], "item_id": libre["id"]}), mostrar=False)
    comprobar("las capas quedan base + lo puesto", [c["tipo"] for c in cuerpo.get("capas", [])] == ["base", libre["tipo"]])

    caro = max(config.OBJETOS_AVATAR, key=lambda o: o["nivel_requerido"])
    cuerpo = verificar(f"POST /avatar/equipar bloqueado ({caro['id']}) -> 403",
                       post("/avatar/equipar", {"email": EMAIL_PRUEBA, "tipo": caro["tipo"], "item_id": caro["id"]}), esperado=403)
    comprobar("el 403 dice cuántos niveles faltan", cuerpo.get("niveles_faltantes") == caro["nivel_requerido"] - nivel)
    otro_tipo = next(t for t in config.TIPOS_OBJETO if t != libre["tipo"])
    verificar("POST /avatar/equipar con el tipo equivocado -> 400",
              post("/avatar/equipar", {"email": EMAIL_PRUEBA, "tipo": otro_tipo, "item_id": libre["id"]}), esperado=400)
    verificar("POST /avatar/equipar sin item_id -> 400", post("/avatar/equipar", {"email": EMAIL_PRUEBA, "tipo": "ropa"}), esperado=400)
    verificar("POST /avatar/equipar sin perfil -> 404",
              post("/avatar/equipar", {"email": "nadie@lumea.test", "tipo": libre["tipo"], "item_id": libre["id"]}), esperado=404)

    cuerpo = verificar(f"POST /avatar/quitar ({libre['tipo']})", post("/avatar/quitar", {"email": EMAIL_PRUEBA, "tipo": libre["tipo"]}), mostrar=False)
    comprobar("después de quitar solo queda la base", [c["tipo"] for c in cuerpo.get("capas", [])] == ["base"])
    verificar("POST /avatar/quitar tipo que no existe -> 400", post("/avatar/quitar", {"email": EMAIL_PRUEBA, "tipo": "zapatos"}), esperado=400)
    verificar("GET /avatar sin email -> 400", get("/avatar"), esperado=400)


def limpiar_datos_de_prueba():
    """Borra de MySQL todo lo que dejaron las corridas de este script."""
    from database import BaseDatos
    db = BaseDatos()
    cursor = db.conexion.cursor()
    cursor.execute("SELECT id FROM perfil WHERE email LIKE %s", (PATRON_EMAIL_PRUEBA,))
    ids = [fila[0] for fila in cursor.fetchall()]
    for usuario_id in ids:
        for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "calcomanias_usuario", "historial_comida", "estado_animo"):
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
    nivel = probar_gamificacion(xp)
    probar_avatar_capas(nivel)

    fallas = [nombre for nombre, ok in resultados if not ok]
    print(f"\n{len(resultados) - len(fallas)}/{len(resultados)} pruebas OK.")
    if fallas:
        print("Fallaron:", ", ".join(fallas))

    if "--conservar" in sys.argv:
        print(f"Datos de prueba conservados (correo {EMAIL_PRUEBA}).")
    else:
        limpiar_datos_de_prueba()
    sys.exit(1 if fallas else 0)
