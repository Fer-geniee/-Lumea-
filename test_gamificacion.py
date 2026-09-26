"""
Pruebas de la lógica de gamificación que NO necesita servidor ni MySQL:
racha entre días, niveles, topes diarios, URLs de avatares y que el
config sea coherente. Correr con:

    python3 test_gamificacion.py

Las pruebas de los endpoints (con servidor y base de datos) están en
test_api.py.
"""

import unittest
from datetime import date, timedelta

import gamificacion as g
import gamificacion_config as config
from database import BaseDatos

# Valores válidos de DiceBear avataaars 9.x, copiados del esquema oficial
# (@dicebear/avataaars 9.4.2, lib/schema.js) el 26 sep 2026. Si alguien
# pone en el config una expresión que no existe, DiceBear responde 400 y
# el avatar no se ve: esta prueba lo detecta antes.
DICEBEAR_VALIDOS = {
    "mouth": {"concerned", "default", "disbelief", "eating", "grimace", "sad", "screamOpen",
              "serious", "smile", "tongue", "twinkle", "vomit"},
    "eyes": {"closed", "cry", "default", "eyeRoll", "happy", "hearts", "side", "squint",
             "surprised", "winkWacky", "wink", "xDizzy"},
    "eyebrows": {"angryNatural", "defaultNatural", "flatNatural", "frownNatural",
                 "raisedExcitedNatural", "sadConcernedNatural", "unibrowNatural", "upDownNatural",
                 "angry", "default", "raisedExcited", "sadConcerned", "upDown"},
}

HOY = date(2026, 9, 26)
AYER = HOY - timedelta(days=1)


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
        self.assertEqual(g.avatar_por_id(config.AVATAR_POR_DEFECTO)["xp_requerido"], 0)

    def test_hay_expresion_para_cada_estado_de_animo_valido(self):
        self.assertEqual(set(config.EXPRESION_POR_ESTADO), BaseDatos.ESTADOS_VALIDOS)

    def test_expresiones_existen_en_dicebear(self):
        for estado, expresion in [("neutra", config.EXPRESION_NEUTRA), *config.EXPRESION_POR_ESTADO.items()]:
            for parametro, valor in expresion.items():
                with self.subTest(estado=estado, parametro=parametro):
                    self.assertIn(valor, DICEBEAR_VALIDOS[parametro])


class TestUrlAvatar(unittest.TestCase):
    def test_usa_la_semilla_del_catalogo_y_la_expresion(self):
        avatar = g.avatar_por_id("sol")
        url = g.url_avatar(avatar, "muy_bien")
        self.assertTrue(url.startswith(config.DICEBEAR_URL + "?"))
        self.assertIn("seed=lumea-sol", url)
        self.assertIn("mouth=smile", url)
        self.assertIn("eyes=happy", url)

    def test_sin_estado_usa_expresion_neutra(self):
        url = g.url_avatar(g.avatar_por_id("sol"))
        self.assertIn(f"mouth={config.EXPRESION_NEUTRA['mouth']}", url)

    def test_ningun_avatar_depende_de_datos_del_usuario(self):
        # La semilla sale del catálogo; nunca debe parecer un correo.
        for avatar in config.AVATARES:
            self.assertNotIn("@", avatar["semilla"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
