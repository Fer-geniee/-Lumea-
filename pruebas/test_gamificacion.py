"""
Pruebas de la gamificación. Correr con:

    python3 test_gamificacion.py

La mayoría NO necesita servidor ni MySQL: racha entre días, niveles,
topes diarios, pérdida de XP por inactividad (simulando días), que el
nivel no baje, que nada se vuelva a bloquear, el avatar por capas y que
el config sea coherente.

TestConMySQL sí usa la base de datos (con un usuario de prueba que no
existe en perfil, y que borra al terminar) para comprobar lo mismo con
las consultas SQL de verdad. Si MySQL no está encendido, esas pruebas se
saltan solas.

Las pruebas de los endpoints (con servidor) están en test_api.py.
"""
import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import unittest
from datetime import date, timedelta
from unittest import mock

import inspect
import json
import os
from urllib.parse import parse_qs, urlparse

import gamificacion as g
import gamificacion_config as config
from database import BaseDatos, conectar_mysql
from grupos_confusion import GRUPOS_CONFUSION

# Valores válidos de DiceBear gaze 10.x, verificados el 7 oct 2026 en
# @dicebear/styles 10.6.0. Si alguien pone en el config una forma o unos ojos
# que no existen, DiceBear responde 400 y el compañero no se ve: estas
# pruebas lo detectan antes.
FORMAS_GAZE = {"circle", "square", "triangle", "pentagon", "hexagon", "octagon", "diamond",
               "pill", "column", "egg", "arch"}
OJOS_GAZE = {"dots", "big", "small", "shine", "beans", "bars", "wide", "tall", "happy", "grin", "squint"}
PARAMETROS_URL_GAZE = {"seed", "shapeVariant", "bodyColor", "eyesVariant"}

HOY = date(2026, 9, 26)
AYER = HOY - timedelta(days=1)
# Hoy NO se pierde XP por inactividad (config en 0), pero el mecanismo sigue en
# el código y se enciende subiendo esos dos valores. Estas pruebas lo ejercitan
# con valores de prueba (5 por día, tope de 20) puestos solo mientras corre
# cada prueba; las pruebas de "con la configuración real" leen el config.
XP_DIA = 5
TOPE = 20


def con_perdida_encendida(objetivo):
    """Decorador (de una prueba o de toda una clase): corre con la pérdida por
    inactividad encendida (XP_DIA y TOPE)."""
    objetivo = mock.patch.object(config, "XP_PERDIDO_POR_DIA_INACTIVO", XP_DIA)(objetivo)
    return mock.patch.object(config, "TOPE_PERDIDA_POR_PERIODO", TOPE)(objetivo)


def perdida_real(dias_inactivos):
    """Lo que pierde quien pasó `dias_inactivos` días sin actividad con el config de verdad."""
    return min(config.TOPE_PERDIDA_POR_PERIODO, dias_inactivos * config.XP_PERDIDO_POR_DIA_INACTIVO)


def progreso_con(xp_total, ultima_fecha, nivel_maximo=None, **otros):
    """Un progreso de usuario de mentira, como el que sale de la base."""
    p = g.progreso_vacio(1)
    p.update(xp_total=xp_total, ultima_fecha_actividad=ultima_fecha,
             nivel_maximo=nivel_maximo or g.calcular_nivel(xp_total), **otros)
    return p


class TestRacha(unittest.TestCase):
    def test_primera_actividad_empieza_en_1(self):
        self.assertEqual(g.nueva_racha(0, None, HOY), 1)

    def test_segunda_actividad_del_mismo_dia_no_suma(self):
        self.assertEqual(g.nueva_racha(3, HOY, HOY), 3)

    def test_actividad_ayer_extiende(self):
        self.assertEqual(g.nueva_racha(3, AYER, HOY), 4)

    def test_hueco_de_un_dia_reinicia(self):
        self.assertEqual(g.nueva_racha(3, HOY - timedelta(days=2), HOY), 1)

    def test_racha_mostrada_se_pierde_si_la_ultima_fue_antes_de_ayer(self):
        self.assertEqual(g.racha_vigente(5, HOY - timedelta(days=2), HOY), 0)

    def test_racha_mostrada_sigue_si_la_ultima_fue_ayer(self):
        # Todavía puede registrar hoy y mantenerla.
        self.assertEqual(g.racha_vigente(5, AYER, HOY), 5)

    def test_racha_mostrada_sin_actividad(self):
        self.assertEqual(g.racha_vigente(0, None, HOY), 0)


class TestNiveles(unittest.TestCase):
    def test_sin_xp_es_nivel_1(self):
        self.assertEqual(g.calcular_nivel(0), 1)

    def test_justo_en_el_umbral_sube(self):
        self.assertEqual(g.calcular_nivel(config.NIVELES[1]), 2)
        self.assertEqual(g.calcular_nivel(config.NIVELES[1] - 1), 1)

    def test_ultimo_nivel_no_tiene_siguiente(self):
        xp_maximo = config.NIVELES[-1] + 10_000
        self.assertEqual(g.calcular_nivel(xp_maximo), len(config.NIVELES))
        self.assertEqual(g.rango_del_nivel(xp_maximo), (config.NIVELES[-1], None))

    def test_rango_intermedio(self):
        self.assertEqual(g.rango_del_nivel(config.NIVELES[2]), (config.NIVELES[2], config.NIVELES[3]))


class TestTopesDiarios(unittest.TestCase):
    def test_da_xp_hasta_el_maximo_y_luego_cero(self):
        for accion, regla in config.ACCIONES.items():
            with self.subTest(accion=accion):
                for veces in range(regla["maximo_por_dia"]):
                    self.assertEqual(g.xp_a_otorgar(accion, veces), regla["xp"])
                self.assertEqual(g.xp_a_otorgar(accion, regla["maximo_por_dia"]), 0)


class TestConfigCoherente(unittest.TestCase):
    def test_niveles_empiezan_en_0_y_crecen(self):
        self.assertEqual(config.NIVELES[0], 0)
        self.assertEqual(config.NIVELES, sorted(set(config.NIVELES)))

    def test_meta_diaria_alcanzable_en_un_dia(self):
        maximo_diario = sum(r["xp"] * r["maximo_por_dia"] for r in config.ACCIONES.values())
        self.assertLessEqual(config.META_DIARIA_XP, maximo_diario)

    def test_avatares_ids_unicos_y_default_gratis(self):
        ids = [a["id"] for a in config.AVATARES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(g.avatar_por_id(config.AVATAR_POR_DEFECTO)["nivel_requerido"], 1)

    def test_niveles_requeridos_existen(self):
        for elemento in config.AVATARES + config.OBJETOS_AVATAR:
            with self.subTest(id=elemento["id"]):
                self.assertTrue(1 <= elemento["nivel_requerido"] <= len(config.NIVELES))

    def test_perdida_no_negativa(self):
        self.assertGreaterEqual(config.XP_PERDIDO_POR_DIA_INACTIVO, 0)
        self.assertGreaterEqual(config.TOPE_PERDIDA_POR_PERIODO, 0)

    def test_mensaje_de_regreso_amable(self):
        # Nunca un regaño, y nada de comida, peso ni cuerpo.
        mensaje = config.MENSAJE_REGRESO.lower()
        self.assertTrue(mensaje.strip())
        for palabra in ("perdiste", "castigo", "culpa", "debes", "peso", "calor", "saludable"):
            self.assertNotIn(palabra, mensaje)

    def test_catalogo_de_capas_coherente(self):
        self.assertEqual(len(config.BASES_AVATAR), 2)
        self.assertIsNotNone(g.base_por_id(config.BASE_POR_DEFECTO))
        ids = [o["id"] for o in config.OBJETOS_AVATAR] + [b["id"] for b in config.BASES_AVATAR]
        self.assertEqual(len(ids), len(set(ids)))
        for objeto in config.OBJETOS_AVATAR:
            with self.subTest(id=objeto["id"]):
                self.assertIn(objeto["tipo"], config.TIPOS_OBJETO)
                # Desde el 9 oct los objetos cambian a la persona voxel-art:
                # llevan `parametros` de DiceBear, ya no un archivo PNG.
                self.assertNotIn("archivo", objeto)
                self.assertTrue(objeto["parametros"])
        # Las bases PNG están EN DESUSO pero se conservan.
        for base in config.BASES_AVATAR:
            self.assertEqual(base["archivo"], f'{base["id"]}.png')

    def test_una_prenda_o_accesorio_por_cada_etapa(self):
        niveles = sorted(o["nivel_requerido"] for o in config.OBJETOS_AVATAR)
        self.assertEqual(niveles, list(range(1, len(config.NIVELES) + 1)))

    def test_la_ropa_por_defecto_existe_y_esta_abierta_desde_el_nivel_1(self):
        objeto = g.objeto_por_id(config.OBJETOS_POR_DEFECTO["ropa"])
        self.assertEqual((objeto["tipo"], objeto["nivel_requerido"]), ("ropa", 1))

    def test_los_parametros_de_las_prendas_son_de_dicebear_y_no_llevan_gorras(self):
        for objeto in config.OBJETOS_AVATAR:
            with self.subTest(id=objeto["id"]):
                clave = {"ropa": "outfitVariant", "accesorio": "glassesVariant"}[objeto["tipo"]]
                self.assertEqual(list(objeto["parametros"]), [clave])
                self.assertNotIn(objeto["parametros"][clave], ("cap", "beanie"))

    def test_rasgos_coherentes(self):
        self.assertEqual(set(config.RASGOS_POR_DEFECTO), set(config.RASGOS))
        for clave, valor in config.RASGOS_POR_DEFECTO.items():
            with self.subTest(rasgo=clave):
                self.assertTrue(g.rasgo_valido(clave, valor))
        self.assertEqual({k for k, r in config.RASGOS.items() if "ninguno" in r}, {"cheeksVariant", "beardVariant"})
        self.assertEqual(len(config.RASGOS["skinColor"]["opciones"]), 8)
        self.assertEqual(len(config.RASGOS["hairColor"]["opciones"]), 12)
        self.assertEqual(len(config.RASGOS["eyesVariant"]["opciones"]), 8)
        self.assertEqual(len(config.RASGOS["mouthVariant"]["opciones"]), 10)
        self.assertEqual(len(config.RASGOS["shirtColor"]["opciones"]), 10)
        self.assertEqual(list(config.RASGOS["skinColor"]["opciones"].values()), [f"Tono {n}" for n in range(1, 9)])
        # Las gorras y los gorros reemplazan el peinado en voxel-art: no son peinados.
        for no_peinado in ("cap", "beanie", "animalEars", "bunnyEars"):
            self.assertNotIn(no_peinado, config.RASGOS["topVariant"]["opciones"])

    def test_hay_algo_para_estrenar_desde_el_nivel_1(self):
        self.assertTrue(any(o["nivel_requerido"] == 1 for o in config.OBJETOS_AVATAR))

    def test_hay_expresion_para_cada_estado_de_animo_valido(self):
        self.assertEqual(set(config.EXPRESION_POR_ESTADO), BaseDatos.ESTADOS_VALIDOS)

    def test_expresiones_existen_en_dicebear(self):
        for estado, expresion in [("neutra", config.EXPRESION_NEUTRA), *config.EXPRESION_POR_ESTADO.items()]:
            with self.subTest(estado=estado):
                self.assertEqual(set(expresion), {"eyesVariant"})
                self.assertIn(expresion["eyesVariant"], OJOS_GAZE)

    def test_cada_companero_tiene_forma_y_color_validos(self):
        for avatar in config.AVATARES:
            with self.subTest(avatar=avatar["id"]):
                self.assertIn(avatar["forma"], FORMAS_GAZE)
                # Color hexadecimal de 6 dígitos, SIN "#" (así lo pide DiceBear).
                self.assertRegex(avatar["color"], r"^[0-9A-Fa-f]{6}$")

    def test_la_url_base_es_gaze_10(self):
        self.assertEqual(config.DICEBEAR_URL, "https://api.dicebear.com/10.x/gaze/svg")


class TestUrlAvatar(unittest.TestCase):
    @staticmethod
    def parametros(url):
        return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

    def test_usa_la_semilla_la_forma_el_color_y_los_ojos_del_animo(self):
        avatar = g.avatar_por_id("sol")
        url = g.url_avatar(avatar, "muy_bien")
        self.assertTrue(url.startswith(config.DICEBEAR_URL + "?"))
        self.assertEqual(self.parametros(url), {
            "seed": "lumea-sol", "shapeVariant": avatar["forma"], "bodyColor": avatar["color"],
            "eyesVariant": config.EXPRESION_POR_ESTADO["muy_bien"]["eyesVariant"],
        })

    def test_sin_estado_usa_ojos_neutros(self):
        url = g.url_avatar(g.avatar_por_id("sol"))
        self.assertEqual(self.parametros(url)["eyesVariant"], config.EXPRESION_NEUTRA["eyesVariant"])

    def test_todas_las_urls_son_gaze_validas_y_quietas(self):
        for avatar in config.AVATARES:
            for estado in [None, *config.EXPRESION_POR_ESTADO]:
                with self.subTest(avatar=avatar["id"], estado=estado):
                    url = g.url_avatar(avatar, estado)
                    self.assertTrue(url.startswith("https://api.dicebear.com/10.x/gaze/svg?"))
                    parametros = self.parametros(url)
                    # Solo estos cuatro parámetros: sin animationVariant (las URL son quietas).
                    self.assertEqual(set(parametros), PARAMETROS_URL_GAZE)
                    self.assertIn(parametros["shapeVariant"], FORMAS_GAZE)
                    self.assertIn(parametros["eyesVariant"], OJOS_GAZE)
                    self.assertRegex(parametros["bodyColor"], r"^[0-9A-Fa-f]{6}$")

    def test_los_cinco_animos_dan_las_mismas_semillas(self):
        # Cambia la cara (los ojos), nunca la semilla: el compañero es el mismo.
        for avatar in config.AVATARES:
            with self.subTest(avatar=avatar["id"]):
                semillas = {self.parametros(g.url_avatar(avatar, estado))["seed"] for estado in config.EXPRESION_POR_ESTADO}
                self.assertEqual(semillas, {avatar["semilla"]})

    def test_ningun_avatar_depende_de_datos_del_usuario(self):
        # La semilla sale del catálogo (fija); nunca parece un correo ni cambia con la persona.
        for avatar in config.AVATARES:
            self.assertRegex(avatar["semilla"], r"^lumea-[a-z]+$")
        # url_avatar solo recibe el compañero y el ánimo: ninguna otra cosa va a DiceBear.
        self.assertEqual(
            list(inspect.signature(g.url_avatar).parameters), ["avatar", "estado_animo"])


def opcion_de_grupo(grupo_id, indice=0):
    grupo = next(gr for gr in GRUPOS_CONFUSION if gr["id"] == grupo_id)
    return grupo["opciones"][indice]["codigo"]


class TestPuntosV2(unittest.TestCase):
    """Mensajes de productos de paquete y misiones (lógica pura)."""

    def test_mensaje_educativo_solo_para_productos_de_paquete(self):
        self.assertIsNone(g.mensaje_educativo("banano"))
        self.assertIsNone(g.mensaje_educativo("ajiaco"))
        for grupo_id in config.GRUPOS_PRODUCTO_DE_PAQUETE:
            with self.subTest(grupo=grupo_id):
                self.assertEqual(g.mensaje_educativo(opcion_de_grupo(grupo_id)), config.MENSAJES_ULTRAPROCESADO[grupo_id])
                self.assertEqual(g.mensaje_educativo(grupo_id), config.MENSAJES_ULTRAPROCESADO[grupo_id])

    def test_mensajes_educativos_amables_y_con_alternativa(self):
        for grupo_id, mensaje in config.MENSAJES_ULTRAPROCESADO.items():
            with self.subTest(grupo=grupo_id):
                texto = mensaje.lower()
                self.assertIn("otro día", texto)  # propone una alternativa para otro momento
                for palabra in ("saludable", "malo", "evita", "no deberías", "culpa", "peso", "engorda"):
                    self.assertNotIn(palabra, texto)

    def test_penalizacion_en_0_no_resta_nada(self):
        self.assertEqual(config.XP_PENALIZACION_ULTRAPROCESADO, 0)
        self.assertEqual(g.penalizacion_ultraprocesado(opcion_de_grupo("gaseosas_bebidas_azucaradas")), 0)

    def test_penalizacion_si_se_activara(self):
        with mock.patch.object(config, "XP_PENALIZACION_ULTRAPROCESADO", 3):
            self.assertEqual(g.penalizacion_ultraprocesado(opcion_de_grupo("dulces")), 3)
            self.assertEqual(g.penalizacion_ultraprocesado("banano"), 0)

    def test_mision_fruta(self):
        self.assertEqual(g.misiones_nuevas("comida_registrada", "mango", 1, set()), ["fruta"])
        self.assertEqual(g.misiones_nuevas("comida_registrada", "arepa", 1, set()), [])

    def test_mision_tres_comidas(self):
        self.assertEqual(g.misiones_nuevas("comida_registrada", "arepa", 2, set()), [])
        self.assertEqual(g.misiones_nuevas("comida_registrada", "arepa", config.COMIDAS_PARA_MISION, set()), ["tres_comidas"])

    def test_mision_check_in_animo(self):
        self.assertEqual(g.misiones_nuevas("estado_animo", None, 0, set()), ["check_in_animo"])

    def test_cada_mision_una_vez_al_dia(self):
        ya = {"fruta", "tres_comidas", "check_in_animo"}
        self.assertEqual(g.misiones_nuevas("comida_registrada", "uva", 5, ya), [])
        self.assertEqual(g.misiones_nuevas("estado_animo", None, 0, ya), [])

    def test_estado_de_las_misiones(self):
        estado = g.estado_misiones({"fruta"})
        self.assertEqual([m["id"] for m in estado], [m["id"] for m in config.MISIONES_DIARIAS])
        self.assertEqual({m["id"]: m["cumplida"] for m in estado},
                         {m["id"]: m["id"] == "fruta" for m in config.MISIONES_DIARIAS})

    def test_config_de_puntos_v2_coherente(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "clases.json"), encoding="utf-8") as f:
            clases = json.load(f)
        clases = set(clases.values()) if isinstance(clases, dict) else set(clases)
        for fruta in config.FRUTAS:
            self.assertIn(fruta, clases)
        ids_grupos = {gr["id"] for gr in GRUPOS_CONFUSION}
        for grupo_id in config.GRUPOS_PRODUCTO_DE_PAQUETE:
            self.assertIn(grupo_id, ids_grupos)
            self.assertIn(grupo_id, config.MENSAJES_ULTRAPROCESADO)
        self.assertEqual({m["id"] for m in config.MISIONES_DIARIAS}, {"fruta", "tres_comidas", "check_in_animo"})


@con_perdida_encendida
class TestPerdidaPorInactividad(unittest.TestCase):
    def test_hoy_y_ayer_no_son_dias_inactivos(self):
        self.assertEqual(g.dias_inactivos(HOY, HOY), 0)
        # Actividad ayer: hoy todavía puede registrar, no hay día perdido.
        self.assertEqual(g.dias_inactivos(AYER, HOY), 0)
        self.assertEqual(g.dias_inactivos(None, HOY), 0)

    def test_pierde_por_cada_dia_inactivo(self):
        # Última actividad hace 3 días -> 2 días completos sin nada.
        p = progreso_con(100, HOY - timedelta(days=3))
        self.assertEqual(g.aplicar_inactividad(p, HOY), 2 * XP_DIA)
        self.assertEqual(p["xp_total"], 100 - 2 * XP_DIA)
        self.assertEqual(p["xp_perdido_sin_avisar"], 2 * XP_DIA)

    def test_no_pasa_del_tope_por_periodo(self):
        p = progreso_con(500, HOY - timedelta(days=60))
        self.assertEqual(g.aplicar_inactividad(p, HOY), TOPE)
        self.assertEqual(p["xp_total"], 500 - TOPE)

    def test_el_xp_nunca_baja_de_cero(self):
        p = progreso_con(3, HOY - timedelta(days=10))
        g.aplicar_inactividad(p, HOY)
        self.assertEqual(p["xp_total"], 0)

    def test_no_se_descuenta_dos_veces_el_mismo_dia(self):
        p = progreso_con(100, HOY - timedelta(days=3))
        primera = g.aplicar_inactividad(p, HOY)
        segunda = g.aplicar_inactividad(p, HOY)
        self.assertEqual(primera, 2 * XP_DIA)
        self.assertEqual(segunda, 0)
        self.assertEqual(p["xp_total"], 100 - 2 * XP_DIA)

    def test_al_dia_siguiente_solo_se_descuenta_el_dia_nuevo(self):
        p = progreso_con(100, HOY - timedelta(days=3))
        g.aplicar_inactividad(p, HOY)
        manana = HOY + timedelta(days=1)
        self.assertEqual(g.aplicar_inactividad(p, manana), XP_DIA)
        self.assertEqual(p["xp_total"], 100 - 3 * XP_DIA)

    def test_visitas_diarias_nunca_superan_el_tope(self):
        p = progreso_con(500, AYER)
        total = sum(g.aplicar_inactividad(p, HOY + timedelta(days=d)) for d in range(30))
        self.assertEqual(total, TOPE)

    def test_registrar_algo_empieza_un_periodo_nuevo(self):
        p = progreso_con(500, HOY - timedelta(days=30))
        g.aplicar_inactividad(p, HOY)          # pierde el tope completo
        g.sumar_actividad(p, 10, HOY)          # vuelve
        otra_vez = HOY + timedelta(days=30)    # se va otro mes
        self.assertEqual(g.aplicar_inactividad(p, otra_vez), TOPE)

    def test_con_valor_0_se_desactiva(self):
        with mock.patch.object(config, "XP_PERDIDO_POR_DIA_INACTIVO", 0):
            p = progreso_con(100, HOY - timedelta(days=30))
            self.assertEqual(g.aplicar_inactividad(p, HOY), 0)
            self.assertEqual(p["xp_total"], 100)


@con_perdida_encendida
class TestNivelNuncaBaja(unittest.TestCase):
    def test_perder_xp_no_baja_el_nivel(self):
        # Llega justo al nivel 3 y luego se va muchos días.
        p = progreso_con(config.NIVELES[2], AYER)
        self.assertEqual(p["nivel_maximo"], 3)
        g.aplicar_inactividad(p, HOY + timedelta(days=30))
        self.assertLess(p["xp_total"], config.NIVELES[2])
        self.assertEqual(p["nivel_maximo"], 3)
        self.assertEqual(g.nivel_alcanzado(p["nivel_maximo"], p["xp_total"]), 3)

    def test_para_volver_a_subir_hay_que_pasar_el_siguiente_umbral(self):
        p = progreso_con(config.NIVELES[2] - TOPE, AYER, nivel_maximo=3)
        subio = g.sumar_actividad(p, 10, HOY)
        self.assertFalse(subio)
        self.assertEqual(p["nivel_maximo"], 3)
        p["xp_total"] = config.NIVELES[3] - 5
        self.assertTrue(g.sumar_actividad(p, 10, HOY))
        self.assertEqual(p["nivel_maximo"], 4)


class TestNadaSeVuelveABloquear(unittest.TestCase):
    def test_avatares_y_objetos_siguen_desbloqueados_al_perder_xp(self):
        nivel = 5
        p = progreso_con(config.NIVELES[nivel - 1], AYER)
        antes = {e["id"] for e in config.AVATARES + config.OBJETOS_AVATAR if g.desbloqueado(e, p["nivel_maximo"])}
        g.aplicar_inactividad(p, HOY + timedelta(days=30))
        despues = {e["id"] for e in config.AVATARES + config.OBJETOS_AVATAR if g.desbloqueado(e, p["nivel_maximo"])}
        self.assertTrue(antes)
        self.assertEqual(antes, despues)

    def test_lo_puesto_sigue_puesto_al_perder_xp(self):
        objeto = next(o for o in config.OBJETOS_AVATAR if o["nivel_requerido"] > 1)
        p = progreso_con(config.NIVELES[objeto["nivel_requerido"] - 1], AYER, **{f'{objeto["tipo"]}_id': objeto["id"]})
        g.aplicar_inactividad(p, HOY + timedelta(days=30))
        estado = g.estado_avatar_capas(p)
        self.assertEqual(estado["puesto"][objeto["tipo"]]["id"], objeto["id"])


class TestAvatarPorCapas(unittest.TestCase):
    def test_usuario_nuevo_es_la_persona_neutra_con_la_camiseta_lisa(self):
        estado = g.estado_avatar_capas(g.progreso_vacio(1))
        persona = estado["persona"]
        self.assertEqual(persona["estilo"], "voxel-art")
        self.assertEqual(persona["rasgos"], config.RASGOS_POR_DEFECTO)
        self.assertEqual(persona["puesto"]["ropa"], {"id": "camiseta_lisa", "nombre": "Camiseta lisa",
                                                      "parametros": {"outfitVariant": "plain"}})
        self.assertIsNone(persona["puesto"]["accesorio"])
        self.assertEqual(estado["puesto"], persona["puesto"])

    def test_el_contrato_de_persona_y_rasgos_disponibles(self):
        estado = g.estado_avatar_capas(g.progreso_vacio(1))
        self.assertEqual(set(estado["rasgos_disponibles"]), set(config.RASGOS))
        peinado = estado["rasgos_disponibles"]["topVariant"]
        self.assertEqual(peinado["nombre"], "Peinado")
        self.assertEqual(peinado["opciones"]["braids"], "Trenzas")
        self.assertEqual(estado["rasgos_disponibles"]["beardVariant"]["ninguno"], "Ninguna")
        self.assertNotIn("ninguno", estado["rasgos_disponibles"]["skinColor"])
        for lista in estado["objetos"].values():
            for o in lista:
                self.assertTrue({"id", "nombre", "parametros", "nivel_requerido", "desbloqueado"} <= set(o))

    def test_lo_puesto_aparece_en_persona_y_en_objetos(self):
        p = progreso_con(config.NIVELES[-1], HOY, ropa_id="overol", accesorio_id="gafas_sol")
        estado = g.estado_avatar_capas(p)
        self.assertEqual(estado["persona"]["puesto"]["ropa"]["id"], "overol")
        self.assertEqual(estado["persona"]["puesto"]["ropa"]["parametros"], {"outfitVariant": "overalls"})
        self.assertEqual(estado["persona"]["puesto"]["accesorio"]["id"], "gafas_sol")
        puestos = [o["id"] for lista in estado["objetos"].values() for o in lista if o["puesto"]]
        self.assertEqual(sorted(puestos), ["gafas_sol", "overol"])

    def test_ids_viejos_cuentan_como_nada_puesto_sin_error(self):
        # buzo_verde, gafas, ruana... eran de las capas PNG y ya no existen.
        p = progreso_con(config.NIVELES[-1], HOY, ropa_id="buzo_verde", accesorio_id="gafas")
        estado = g.estado_avatar_capas(p)
        self.assertEqual(estado["persona"]["puesto"]["ropa"]["id"], "camiseta_lisa")
        self.assertIsNone(estado["persona"]["puesto"]["accesorio"])
        # Un accesorio guardado en la columna de la ropa tampoco se pone.
        p = progreso_con(config.NIVELES[-1], HOY, ropa_id="gafas_sol")
        self.assertEqual(g.estado_avatar_capas(p)["persona"]["puesto"]["ropa"]["id"], "camiseta_lisa")

    def test_rasgos_guardados_se_mezclan_con_los_de_por_defecto(self):
        p = progreso_con(0, None, avatar_rasgos='{"topVariant": "braids", "beardVariant": "goatee"}')
        rasgos = g.estado_avatar_capas(p)["persona"]["rasgos"]
        self.assertEqual(rasgos["topVariant"], "braids")
        self.assertEqual(rasgos["beardVariant"], "goatee")
        self.assertEqual(rasgos["skinColor"], config.RASGOS_POR_DEFECTO["skinColor"])

    def test_rasgos_guardados_que_ya_no_valen_o_estan_rotos_se_ignoran(self):
        for guardado in ('{"topVariant": "cap", "nada": 1}', "esto no es json", "[1, 2]"):
            with self.subTest(guardado=guardado):
                p = progreso_con(0, None, avatar_rasgos=guardado)
                self.assertEqual(g.rasgos_de(p), config.RASGOS_POR_DEFECTO)

    def test_validar_rasgos(self):
        self.assertIsNone(g.validar_rasgos({"topVariant": "braids", "cheeksVariant": None, "beardVariant": None}))
        malos = [
            {}, None, [], "braids",
            {"colorDeLaLuna": "x"},                    # clave que no existe
            {"topVariant": "cap"},                     # gorra: no es peinado
            {"topVariant": None},                      # null solo en mejillas y barba
            {"skinColor": "#c99062"},                  # los colores van sin #
            {"skinColor": 5},
            {"topVariant": ["braids"]},
            {"eyesVariant": "braids"},                 # valor de otro rasgo
        ]
        for rasgos in malos:
            with self.subTest(rasgos=rasgos):
                self.assertIsNotNone(g.validar_rasgos(rasgos))

    def test_el_error_de_rasgos_no_repite_lo_que_mando_la_persona(self):
        self.assertNotIn("zzz@lumea.test", g.validar_rasgos({"topVariant": "zzz@lumea.test"}))
        self.assertNotIn("zzz@lumea.test", g.validar_rasgos({"zzz@lumea.test": "x"}))

    def test_capas_png_en_desuso_siguen_respondiendo(self):
        estado = g.estado_avatar_capas(g.progreso_vacio(1))
        self.assertEqual(estado["base"]["id"], config.BASE_POR_DEFECTO)
        self.assertEqual([c["tipo"] for c in estado["capas"]], ["base"])
        self.assertEqual(len(estado["bases"]), len(config.BASES_AVATAR))
        self.assertIn("imagen_lista", estado["base"])

    def test_sin_imagenes_responde_igual_con_los_nombres_de_archivo(self):
        with mock.patch.object(g, "imagen_lista", return_value=False):
            estado = g.estado_avatar_capas(g.progreso_vacio(1))
        self.assertFalse(estado["imagenes_listas"])
        self.assertEqual(estado["base"]["archivo"], "base_1.png")
        self.assertTrue(estado["base"]["url"].endswith("/static/avatar/base_1.png"))
        self.assertIn("url", estado["respaldo_dicebear"])

    def test_bloqueado_dice_cuantos_niveles_faltan(self):
        estado = g.estado_avatar_capas(progreso_con(0, None))
        for tipo, objetos in estado["objetos"].items():
            for o in objetos:
                with self.subTest(id=o["id"]):
                    self.assertEqual(o["desbloqueado"], o["nivel_requerido"] <= 1)
                    self.assertEqual(o["niveles_faltantes"], max(0, o["nivel_requerido"] - 1))

    def test_objeto_bloqueado_guardado_no_se_dibuja(self):
        # Solo pasaría si alguien sube el nivel de un objeto en el config.
        caro = max(config.OBJETOS_AVATAR, key=lambda o: o["nivel_requerido"])
        p = progreso_con(0, None, **{f'{caro["tipo"]}_id': caro["id"]})
        por_defecto = config.OBJETOS_POR_DEFECTO.get(caro["tipo"])
        puesto = g.estado_avatar_capas(p)["puesto"][caro["tipo"]]
        self.assertEqual(None if puesto is None else puesto["id"], por_defecto)

    def test_tipos_desconocidos_no_llegan_al_sql(self):
        self.assertEqual(g.columna_de_tipo("ropa"), "ropa_id")
        self.assertIsNone(g.columna_de_tipo("zapatos; DROP TABLE perfil"))


class TestCalcomaniasReglas(unittest.TestCase):
    """Las reglas de calcomanías son funciones puras: se prueban con
    "hechos" inventados, sin MySQL."""

    HECHOS_VACIOS = {
        "comidas_total": 0, "misiones_hechas": set(), "tiene_animo": False,
        "ayudo_ia": False, "racha_maxima": 0, "nivel_maximo": 1, "dias_ausente_max": 0,
    }

    def hechos(self, **cambios):
        return {**self.HECHOS_VACIOS, **cambios}

    def test_el_catalogo_tiene_10_con_regla_y_campos(self):
        ids = [c["id"] for c in config.CALCOMANIAS]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)
        self.assertEqual(set(ids), set(g.REGLAS_CALCOMANIAS))
        for c in config.CALCOMANIAS:
            self.assertEqual(set(c), {"id", "nombre", "descripcion", "como_se_gana", "rol", "umbral"})
            self.assertIn(c["rol"], {"comida", "mision", "emocion", "duda", "logro"})

    def test_sin_hechos_no_se_gana_ninguna(self):
        self.assertEqual(g.calcomanias_cumplidas(self.hechos()), [])

    def test_cada_regla_con_su_umbral(self):
        casos = [
            ("primera_foto", self.hechos(comidas_total=1), self.hechos(comidas_total=0)),
            ("diez_registros", self.hechos(comidas_total=10), self.hechos(comidas_total=9)),
            ("tres_al_dia", self.hechos(misiones_hechas={"tres_comidas"}), self.hechos(misiones_hechas={"fruta"})),
            ("fruta", self.hechos(misiones_hechas={"fruta"}), self.hechos(misiones_hechas={"tres_comidas"})),
            ("como_llegas", self.hechos(tiene_animo=True), self.hechos()),
            ("ayudaste_ia", self.hechos(ayudo_ia=True), self.hechos()),
            ("racha_3", self.hechos(racha_maxima=3), self.hechos(racha_maxima=2)),
            ("racha_7", self.hechos(racha_maxima=7), self.hechos(racha_maxima=6)),
            ("volviste", self.hechos(dias_ausente_max=3), self.hechos(dias_ausente_max=2)),
            ("nivel_5", self.hechos(nivel_maximo=5), self.hechos(nivel_maximo=4)),
        ]
        for calcomania_id, cumple, no_cumple in casos:
            with self.subTest(calcomania=calcomania_id):
                self.assertIn(calcomania_id, g.calcomanias_cumplidas(cumple))
                self.assertNotIn(calcomania_id, g.calcomanias_cumplidas(no_cumple))

    def test_nunca_se_otorga_dos_veces(self):
        hechos = self.hechos(comidas_total=12)
        self.assertEqual(g.calcomanias_por_otorgar(hechos, {}), ["primera_foto", "diez_registros"])
        self.assertEqual(g.calcomanias_por_otorgar(hechos, {"primera_foto": date.today()}), ["diez_registros"])
        self.assertEqual(g.calcomanias_por_otorgar(hechos, {"primera_foto": 1, "diez_registros": 1}), [])

    def test_ausencia_mas_larga(self):
        d = date(2026, 10, 1)
        self.assertEqual(g.dias_ausente_maximo([]), 0)
        self.assertEqual(g.dias_ausente_maximo([d]), 0)
        self.assertEqual(g.dias_ausente_maximo([d, d + timedelta(days=1)]), 0)  # días seguidos
        # 1 y 5 de octubre: 2, 3 y 4 sin actividad = 3 días de ausencia.
        self.assertEqual(g.dias_ausente_maximo([d + timedelta(days=4), d]), 3)

    def test_la_forma_publica_no_lleva_el_umbral(self):
        self.assertEqual(set(g.calcomania_publica(config.CALCOMANIAS[0])), {"id", "nombre", "descripcion", "rol"})


class TestDesbloqueosAlSubir(unittest.TestCase):
    def test_sin_subir_no_hay_desbloqueos(self):
        self.assertEqual(g.desbloqueos_al_subir(3, 3), [])

    def test_un_nivel_abre_lo_que_pide_ese_nivel(self):
        # Nivel 3 -> 4: en el config actual, el overol pide nivel 4. La prenda
        # trae sus `parametros` para dibujar a la persona con ella puesta.
        d = g.desbloqueos_al_subir(3, 4)
        self.assertEqual(d, [{"tipo": "ropa", "id": "overol", "nombre": "Overol de jardín", "nivel_requerido": 4,
                              "parametros": {"outfitVariant": "overalls"}}])

    def test_el_nivel_anterior_no_cuenta_y_el_nuevo_si(self):
        for d in g.desbloqueos_al_subir(1, 5):
            self.assertTrue(1 < d["nivel_requerido"] <= 5)
        ids = [(d["tipo"], d["id"]) for d in g.desbloqueos_al_subir(1, 5)]
        self.assertIn(("avatar", "montana"), ids)       # nivel 5
        self.assertNotIn(("ropa", "camiseta_lisa"), ids)   # nivel 1: ya estaba abierto

    def test_un_salto_de_varios_niveles_los_abre_todos_sin_repetir(self):
        todos = [d for d in g.desbloqueos_al_subir(1, len(config.NIVELES))]
        esperados = [e for e in config.AVATARES + config.OBJETOS_AVATAR if e["nivel_requerido"] > 1]
        self.assertEqual(len(todos), len(esperados))
        self.assertEqual(len({(d["tipo"], d["id"]) for d in todos}), len(todos))

    def test_cada_objeto_se_abre_en_un_solo_tramo(self):
        # Subiendo nivel por nivel, cada objeto aparece exactamente una vez.
        vistos = [(d["tipo"], d["id"]) for n in range(1, len(config.NIVELES)) for d in g.desbloqueos_al_subir(n, n + 1)]
        self.assertEqual(len(vistos), len(set(vistos)))


# ---------------------------------------------------------------------
# Con MySQL: lo mismo, pero pasando por las consultas SQL de verdad.
# ---------------------------------------------------------------------

USUARIO_PRUEBA = 2_000_000_001  # no existe en perfil; se borra al terminar


class _Db:
    """Lo mínimo que gamificacion.py necesita de BaseDatos: .conexion.
    No se instancia BaseDatos para no correr sus migraciones."""
    def __init__(self):
        self.conexion = conectar_mysql()
        if self.conexion is not None:
            self.conexion.cursor().execute("USE lumea_db")


class TestConMySQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = _Db()
        if cls.db.conexion is None:
            raise unittest.SkipTest("MySQL no está disponible")
        g.asegurar_tablas(cls.db.conexion)

    @classmethod
    def tearDownClass(cls):
        cls._borrar()
        cls.db.conexion.close()

    @classmethod
    def _borrar(cls):
        cursor = cls.db.conexion.cursor()
        for tabla in ("progreso_usuario", "eventos_xp", "actividad_diaria", "calcomanias_usuario", "historial_comida", "estado_animo"):
            cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (USUARIO_PRUEBA,))
        cls.db.conexion.commit()
        cursor.close()

    def _poner(self, **columnas):
        """Deja la fila del usuario de prueba con estos valores."""
        p = g.progreso_vacio(USUARIO_PRUEBA)
        p.update(columnas)
        cursor = self.db.conexion.cursor()
        g._guardar_progreso(cursor, p)
        self.db.conexion.commit()
        cursor.close()

    def setUp(self):
        self._borrar()

    @con_perdida_encendida
    def test_perdida_perezosa_una_sola_vez_y_nivel_intacto(self):
        hoy = date.today()
        # Nivel 3 con 90 XP; la última actividad fue hace 4 días (3 inactivos).
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=4))

        p = g.obtener_progreso(self.db, USUARIO_PRUEBA)
        self.assertEqual(p["xp_total"], 90 - 3 * XP_DIA)
        self.assertEqual(p["xp_perdido_desde_ultima_visita"], 3 * XP_DIA)
        self.assertEqual(p["mensaje_regreso"], config.MENSAJE_REGRESO)
        self.assertEqual(p["nivel"], 3)

        # Segunda visita el mismo día: no se descuenta nada más y el aviso ya se dio.
        p = g.obtener_progreso(self.db, USUARIO_PRUEBA)
        self.assertEqual(p["xp_total"], 90 - 3 * XP_DIA)
        self.assertEqual(p["xp_perdido_desde_ultima_visita"], 0)
        self.assertIsNone(p["mensaje_regreso"])

        # "Pasa un día" (se corre la última actividad un día atrás): solo el día nuevo.
        cursor = self.db.conexion.cursor()
        cursor.execute("UPDATE progreso_usuario SET ultima_fecha_actividad = %s WHERE usuario_id = %s",
                       (hoy - timedelta(days=5), USUARIO_PRUEBA))
        self.db.conexion.commit()
        p = g.obtener_progreso(self.db, USUARIO_PRUEBA)
        self.assertEqual(p["xp_perdido_desde_ultima_visita"], min(XP_DIA, TOPE - 3 * XP_DIA))
        self.assertEqual(p["nivel"], 3)

        # La pérdida queda anotada en eventos_xp (XP negativo).
        cursor.execute("SELECT COALESCE(SUM(xp), 0) FROM eventos_xp WHERE usuario_id = %s AND accion = 'perdida_inactividad'",
                       (USUARIO_PRUEBA,))
        self.assertEqual(int(cursor.fetchone()[0]), -(90 - p["xp_total"]))
        cursor.close()

    @con_perdida_encendida
    def test_registrar_despues_de_inactividad_descuenta_y_luego_suma(self):
        hoy = date.today()
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=3))
        resumen = g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="bien")
        xp_animo = config.ACCIONES["estado_animo"]["xp"] + g.mision_por_id("check_in_animo")["xp"]
        self.assertEqual(resumen["xp_ganado"], xp_animo)
        self.assertEqual(resumen["xp_total"], 90 - 2 * XP_DIA + xp_animo)
        self.assertEqual(resumen["nivel"], 3)
        self.assertFalse(resumen["subio_de_nivel"])
        # El aviso llega en la siguiente visita a /progreso, una sola vez.
        self.assertEqual(g.obtener_progreso(self.db, USUARIO_PRUEBA)["xp_perdido_desde_ultima_visita"], 2 * XP_DIA)
        self.assertEqual(g.obtener_progreso(self.db, USUARIO_PRUEBA)["xp_perdido_desde_ultima_visita"], 0)

    def test_objetos_por_nivel_maximo_aunque_el_xp_haya_bajado(self):
        # Nivel máximo 3, pero ya solo le quedan 10 XP.
        self._poner(xp_total=10, nivel_maximo=3, ultima_fecha_actividad=date.today())
        de_nivel_3 = next(o for o in config.OBJETOS_AVATAR if o["nivel_requerido"] == 3)
        ok, codigo, cuerpo = g.equipar(self.db, USUARIO_PRUEBA, de_nivel_3["tipo"], de_nivel_3["id"])
        self.assertEqual(codigo, 200, cuerpo)
        self.assertEqual(cuerpo["puesto"][de_nivel_3["tipo"]]["id"], de_nivel_3["id"])

        caro = max(config.OBJETOS_AVATAR, key=lambda o: o["nivel_requerido"])
        ok, codigo, cuerpo = g.equipar(self.db, USUARIO_PRUEBA, caro["tipo"], caro["id"])
        self.assertEqual(codigo, 403)
        self.assertEqual(cuerpo["niveles_faltantes"], caro["nivel_requerido"] - 3)

        ok, codigo, cuerpo = g.quitar(self.db, USUARIO_PRUEBA, de_nivel_3["tipo"])
        self.assertEqual(codigo, 200)
        self.assertIsNone(cuerpo["puesto"][de_nivel_3["tipo"]])

        ok, codigo, cuerpo = g.elegir_base(self.db, USUARIO_PRUEBA, "base_2")
        self.assertEqual(cuerpo["base"]["id"], "base_2")
        self.assertEqual(g.elegir_base(self.db, USUARIO_PRUEBA, "base_9")[1], 400)
        # Un id de las capas PNG (ya no existe) no se puede equipar.
        self.assertEqual(g.equipar(self.db, USUARIO_PRUEBA, "accesorio", "buzo_verde")[1], 400)

    def test_quitar_la_ropa_vuelve_a_la_camiseta_lisa(self):
        self._poner(xp_total=config.NIVELES[3], nivel_maximo=4, ultima_fecha_actividad=date.today())
        ok, codigo, cuerpo = g.equipar(self.db, USUARIO_PRUEBA, "ropa", "overol")
        self.assertEqual(cuerpo["persona"]["puesto"]["ropa"]["id"], "overol")
        ok, codigo, cuerpo = g.quitar(self.db, USUARIO_PRUEBA, "ropa")
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo["persona"]["puesto"]["ropa"]["id"], "camiseta_lisa")

    def test_guardar_rasgos_valida_mezcla_y_no_pide_etapa(self):
        # Nivel 1: los rasgos son libres, nunca se bloquean.
        ok, codigo, cuerpo = g.guardar_rasgos(self.db, USUARIO_PRUEBA, {"topVariant": "braids", "skinColor": "6a3d1f"})
        self.assertEqual(codigo, 200, cuerpo)
        self.assertEqual(cuerpo["persona"]["rasgos"]["topVariant"], "braids")
        # Mezcla: lo nuevo se suma a lo guardado, sin borrarlo.
        ok, codigo, cuerpo = g.guardar_rasgos(self.db, USUARIO_PRUEBA, {"beardVariant": "goatee", "cheeksVariant": None})
        self.assertEqual(codigo, 200)
        rasgos = cuerpo["persona"]["rasgos"]
        self.assertEqual((rasgos["topVariant"], rasgos["skinColor"], rasgos["beardVariant"]), ("braids", "6a3d1f", "goatee"))
        self.assertIsNone(rasgos["cheeksVariant"])
        # Y quedó guardado en MySQL, no solo en la respuesta.
        self.assertEqual(g.obtener_avatar_capas(self.db, USUARIO_PRUEBA)["persona"]["rasgos"], rasgos)
        # Se puede volver a "sin barba".
        self.assertIsNone(g.guardar_rasgos(self.db, USUARIO_PRUEBA, {"beardVariant": None})[2]["persona"]["rasgos"]["beardVariant"])

    def test_rasgos_invalidos_dan_400_y_no_cambian_nada(self):
        g.guardar_rasgos(self.db, USUARIO_PRUEBA, {"topVariant": "curly"})
        for malos in ({"topVariant": "cap"}, {"nada": "x"}, {"topVariant": "bob", "eyesVariant": "nope"}, {}):
            with self.subTest(rasgos=malos):
                ok, codigo, cuerpo = g.guardar_rasgos(self.db, USUARIO_PRUEBA, malos)
                self.assertEqual(codigo, 400)
                self.assertIn("error", cuerpo)
        # El válido que venía junto a uno malo tampoco se guardó.
        self.assertEqual(g.obtener_avatar_capas(self.db, USUARIO_PRUEBA)["persona"]["rasgos"]["topVariant"], "curly")

    def test_ids_viejos_guardados_en_mysql_no_rompen_el_avatar(self):
        self._poner(xp_total=0, nivel_maximo=1, ropa_id="buzo_verde", accesorio_id="gafas")
        estado = g.obtener_avatar_capas(self.db, USUARIO_PRUEBA)
        self.assertEqual(estado["persona"]["puesto"]["ropa"]["id"], "camiseta_lisa")
        self.assertIsNone(estado["persona"]["puesto"]["accesorio"])

    def test_puntos_v2_comidas_bonus_y_misiones(self):
        xp_comida = config.ACCIONES["comida_registrada"]["xp"]
        bonus = config.ACCIONES["bonus_registro"]["xp"]
        tope_bonus = config.ACCIONES["bonus_registro"]["maximo_por_dia"]
        xp_mision = {m["id"]: m["xp"] for m in config.MISIONES_DIARIAS}
        gaseosa = opcion_de_grupo("gaseosas_bebidas_azucaradas")

        # 1. Una fruta: comida + bonus por registro + misión "fruta".
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="banano", sellos=[])
        self.assertEqual(r["xp_ganado"], xp_comida + bonus + xp_mision["fruta"])
        self.assertEqual([m["id"] for m in r["misiones_cumplidas"]], ["fruta"])
        self.assertEqual({d["motivo"] for d in r["detalle_xp"]}, {"comida_registrada", "bonus_registro", "mision_fruta"})

        # 2. Otra fruta: la misión ya estaba cumplida hoy.
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="uva", sellos=[])
        self.assertEqual(r["xp_ganado"], xp_comida + bonus)

        # 3. Una bebida de paquete con sellos da el MISMO bonus que la fruta (sin castigo:
        #    la penalización está en 0) y, al ser la tercera comida, la misión "tres_comidas".
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo=gaseosa, sellos=["azucares"])
        self.assertEqual(r["xp_ganado"], xp_comida + bonus + xp_mision["tres_comidas"])

        # 4 y 5. Pasado el tope diario del bonus, queda solo el XP de la comida.
        self.assertEqual(tope_bonus, 3)  # si Isabella cambia el tope, ajustar los pasos 4 y 5
        for codigo in ("ajiaco", "pera"):
            r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo=codigo, sellos=[])
            self.assertEqual(r["xp_ganado"], xp_comida)

        p = g.obtener_progreso(self.db, USUARIO_PRUEBA)
        estado = {m["id"]: m["cumplida"] for m in p["misiones"]}
        self.assertEqual(estado, {"fruta": True, "tres_comidas": True, "check_in_animo": False})

    def test_penalizacion_activada_no_baja_el_nivel(self):
        self._poner(xp_total=31, nivel_maximo=2, ultima_fecha_actividad=date.today())
        dulce = opcion_de_grupo("dulces")
        with mock.patch.object(config, "XP_PENALIZACION_ULTRAPROCESADO", 50):
            r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo=dulce, sellos=["azucares"])
        # Gana 10 (41), el castigo de 50 lo deja en 0, nunca negativo, y el nivel queda en 2.
        self.assertEqual(r["xp_total"], 0)
        self.assertEqual(r["nivel"], 2)


    # ----- Camino del cuidado: ausencia, bonus por registro y etapas -----

    def test_dias_sin_actividad_no_quitan_nada_con_el_config_real(self):
        hoy = date.today()
        dias = 10
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=dias + 1))
        p = g.obtener_progreso(self.db, USUARIO_PRUEBA)
        esperado = perdida_real(dias)
        self.assertEqual(p["xp_total"], 90 - esperado)
        self.assertEqual(p["xp_perdido_desde_ultima_visita"], esperado)
        self.assertEqual(p["nivel"], 3)
        if config.XP_PERDIDO_POR_DIA_INACTIVO == 0 or config.TOPE_PERDIDA_POR_PERIODO == 0:
            self.assertEqual(p["xp_total"], 90)  # con la pérdida apagada no se pierde nada

    def test_mensaje_de_regreso_depende_de_los_dias_no_del_xp(self):
        hoy = date.today()
        umbral = config.DIAS_PARA_MENSAJE_REGRESO
        # Un día menos que el umbral (días COMPLETOS sin actividad): no hay mensaje.
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=umbral))
        self.assertIsNone(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"])
        # Justo el umbral: sale el mensaje de Isabella, una sola vez.
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=umbral + 1))
        self.assertEqual(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"], config.MENSAJE_REGRESO)
        self.assertIsNone(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"])
        # Registrar algo después de haberlo visto no lo repite.
        g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="bien")
        self.assertIsNone(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"])

    def test_mensaje_de_regreso_si_registra_antes_de_abrir_progreso(self):
        hoy = date.today()
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=config.DIAS_PARA_MENSAJE_REGRESO + 2))
        g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="bien")
        self.assertEqual(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"], config.MENSAJE_REGRESO)
        self.assertIsNone(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"])

    def test_una_ausencia_nueva_vuelve_a_dar_el_mensaje(self):
        hoy = date.today()
        dias = config.DIAS_PARA_MENSAJE_REGRESO + 1
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=dias))
        self.assertIsNotNone(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"])
        # La persona volvió y se va otra vez: su última actividad queda otra vez lejos.
        g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="bien")
        cursor = self.db.conexion.cursor()
        cursor.execute("UPDATE progreso_usuario SET ultima_fecha_actividad = %s WHERE usuario_id = %s",
                       (hoy - timedelta(days=dias + 10), USUARIO_PRUEBA))
        self.db.conexion.commit()
        cursor.close()
        self.assertIsNotNone(g.obtener_progreso(self.db, USUARIO_PRUEBA)["mensaje_regreso"])

    def test_el_bonus_por_registro_es_el_mismo_para_un_banano_y_un_producto_con_sellos(self):
        bonus = config.ACCIONES["bonus_registro"]["xp"]
        xp_comida = config.ACCIONES["comida_registrada"]["xp"]
        # Dos comidas distintas el mismo día, las dos dentro del tope del bonus.
        banano = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="banano", sellos=[])
        gaseosa = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada",
                                        alimento_codigo=opcion_de_grupo("gaseosas_bebidas_azucaradas"), sellos=["azucares", "edulcorantes"])
        for resumen in (banano, gaseosa):
            xp_bonus = [d["xp"] for d in resumen["detalle_xp"] if d["motivo"] == "bonus_registro"]
            self.assertEqual(xp_bonus, [bonus])
        # Y con sellos o sin ellos, lo que pasa del tope también es igual: 0.
        self.assertEqual(xp_comida + bonus, gaseosa["xp_ganado"] - sum(m["xp"] for m in gaseosa["misiones_cumplidas"]))

    def test_llegar_a_una_etapa_desbloquea_companeros_ropa_y_accesorios(self):
        # La primera etapa que abre un compañero (y todo lo demás que pida esa etapa).
        etapa = min(a["nivel_requerido"] for a in config.AVATARES if a["nivel_requerido"] > 1)
        esperados = {(e["tipo"], e["id"]) for e in
                     [{**a, "tipo": "avatar"} for a in config.AVATARES] + config.OBJETOS_AVATAR
                     if e["nivel_requerido"] == etapa}
        self.assertTrue(any(tipo == "avatar" for tipo, _ in esperados))
        # Un XP antes de la etapa, y una comida (da más de 1 XP) la alcanza.
        self._poner(xp_total=config.NIVELES[etapa - 1] - 1, nivel_maximo=etapa - 1, ultima_fecha_actividad=date.today())
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="ajiaco", sellos=[])
        self.assertEqual(r["nivel"], etapa)
        self.assertEqual({(d["tipo"], d["id"]) for d in r["desbloqueos"]}, esperados)
        # Y ya se puede elegir el compañero nuevo.
        companero = next(a for a in config.AVATARES if a["nivel_requerido"] == etapa)
        ok, codigo, _ = g.elegir_avatar(self.db, USUARIO_PRUEBA, companero["id"])
        self.assertEqual(codigo, 200)

    # ----- Calcomanías con MySQL -----

    def _insertar_comidas(self, cantidad, certeza=90.0):
        cursor = self.db.conexion.cursor()
        for _ in range(cantidad):
            cursor.execute(
                "INSERT INTO historial_comida (usuario_id, alimento_codigo, certeza_ia) VALUES (%s, 'banano', %s)",
                (USUARIO_PRUEBA, certeza),
            )
        self.db.conexion.commit()
        cursor.close()

    def _ids(self, lista):
        return [c["id"] for c in lista]

    def test_primera_foto_se_anuncia_una_sola_vez(self):
        self._insertar_comidas(1)
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="banano", sellos=[])
        self.assertIn("primera_foto", self._ids(r["calcomanias_nuevas"]))
        self.assertEqual(set(r["calcomanias_nuevas"][0]), {"id", "nombre", "descripcion", "rol"})
        self._insertar_comidas(1)
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="uva", sellos=[])
        self.assertNotIn("primera_foto", self._ids(r["calcomanias_nuevas"]))

    def test_misiones_y_animo_dan_sus_calcomanias(self):
        self._insertar_comidas(3)
        for codigo in ("banano", "uva", "pera"):
            r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo=codigo, sellos=[])
        ganadas = {c["id"] for c in g.obtener_calcomanias(self.db, USUARIO_PRUEBA)["calcomanias"] if c["ganada"]}
        self.assertTrue({"fruta", "tres_al_dia", "primera_foto"} <= ganadas)
        # El check-in de ánimo: la calcomanía aparece cuando ya hay un registro de ánimo.
        cursor = self.db.conexion.cursor()
        cursor.execute("INSERT INTO estado_animo (usuario_id, estado) VALUES (%s, 'mal')", (USUARIO_PRUEBA,))
        self.db.conexion.commit()
        cursor.close()
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="mal")
        self.assertEqual(self._ids(r["calcomanias_nuevas"]), ["como_llegas"])

    def test_ayudaste_ia_solo_con_confirmacion_manual(self):
        self._insertar_comidas(1)  # certeza 90: la IA decidió sola
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="banano", sellos=[])
        self.assertNotIn("ayudaste_ia", self._ids(r["calcomanias_nuevas"]))
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="banano",
                                  sellos=[], confirmacion_manual=True)
        self.assertEqual(self._ids(r["calcomanias_nuevas"]), ["ayudaste_ia"])

    @con_perdida_encendida
    def test_racha_nivel_y_volviste_en_vivo(self):
        hoy = date.today()
        # Racha máxima de 2 y último día hace 5 días; 100 XP; la ausencia resta 20 y el ánimo suma 5: con los niveles de abajo, 85 XP es el nivel 5.
        self._poner(xp_total=100, nivel_maximo=3, racha_actual=2, racha_maxima=2,
                    ultima_fecha_actividad=hoy - timedelta(days=5))
        cursor = self.db.conexion.cursor()
        cursor.execute("INSERT INTO actividad_diaria (usuario_id, fecha, xp_ganado) VALUES (%s, %s, 10)",
                       (USUARIO_PRUEBA, hoy - timedelta(days=5)))
        self.db.conexion.commit()
        cursor.close()
        with mock.patch.object(config, "NIVELES", [0, 10, 20, 30, 85, 400]):
            r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="bien")
        ids = self._ids(r["calcomanias_nuevas"])
        self.assertIn("volviste", ids)  # 4 días completos sin actividad (>= 3)
        self.assertIn("nivel_5", ids)
        self.assertNotIn("racha_3", ids)  # la racha se reinició en 1

    def test_calcomanias_retroactivas_en_silencio_y_sin_repetir(self):
        self._insertar_comidas(10, certeza=100.0)  # 10 comidas y confirmadas a mano
        self._poner(racha_maxima=7, nivel_maximo=5)
        res = g.obtener_calcomanias(self.db, USUARIO_PRUEBA)
        ganadas = {c["id"] for c in res["calcomanias"] if c["ganada"]}
        self.assertEqual(ganadas, {"primera_foto", "diez_registros", "ayudaste_ia", "racha_3", "racha_7", "nivel_5"})
        self.assertEqual((res["ganadas"], res["total"]), (6, 10))
        para_ganar = [c for c in res["calcomanias"] if not c["ganada"]]
        self.assertTrue(all(c["fecha"] is None and c["como_se_gana"] for c in para_ganar))
        # Una segunda consulta no cambia nada, y registrar algo no las vuelve a anunciar.
        self.assertEqual(g.obtener_calcomanias(self.db, USUARIO_PRUEBA)["ganadas"], 6)
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="ajiaco", sellos=[])
        self.assertEqual(r["calcomanias_nuevas"], [])


    def test_resumen_trae_nivel_anterior_y_desbloqueos(self):
        # 28 XP (nivel 1) + una comida (10) pasa a 38: nivel 2 (la camiseta de rayas pide nivel 2).
        self._poner(xp_total=28, nivel_maximo=1, ultima_fecha_actividad=date.today())
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="ajiaco", sellos=["sodio"])
        self.assertTrue(r["subio_de_nivel"])
        self.assertEqual((r["nivel_anterior"], r["nivel"]), (1, 2))
        self.assertEqual([(d["tipo"], d["id"], d["nombre"]) for d in r["desbloqueos"]],
                         [("ropa", "camiseta_rayas", "Camiseta de rayas")])
        # Otra comida sin subir: nivel_anterior = nivel y nada nuevo.
        r = g.registrar_actividad(self.db, USUARIO_PRUEBA, "comida_registrada", alimento_codigo="ajiaco", sellos=["sodio"])
        self.assertFalse(r["subio_de_nivel"])
        self.assertEqual((r["nivel_anterior"], r["nivel"], r["desbloqueos"]), (2, 2, []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
