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

import unittest
from datetime import date, timedelta
from unittest import mock

import gamificacion as g
import gamificacion_config as config
from database import BaseDatos, conectar_mysql

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
XP_DIA = config.XP_PERDIDO_POR_DIA_INACTIVO
TOPE = config.TOPE_PERDIDA_POR_PERIODO


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
        self.assertIn("extrañamos", mensaje)
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
                # Nombre exacto que se le pidió a la diseñadora:
                # <tipo>_<id>.png (ESPECIFICACION_AVATARES_FIGMA.md).
                self.assertEqual(objeto["archivo"], f'{objeto["tipo"]}_{objeto["id"]}.png')
        for base in config.BASES_AVATAR:
            self.assertEqual(base["archivo"], f'{base["id"]}.png')

    def test_hay_algo_para_estrenar_desde_el_nivel_1(self):
        self.assertTrue(any(o["nivel_requerido"] == 1 for o in config.OBJETOS_AVATAR))

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
    def test_usuario_nuevo_tiene_la_base_por_defecto_y_nada_puesto(self):
        estado = g.estado_avatar_capas(g.progreso_vacio(1))
        self.assertEqual(estado["base"]["id"], config.BASE_POR_DEFECTO)
        self.assertEqual(estado["puesto"], {tipo: None for tipo in config.TIPOS_OBJETO})
        self.assertEqual([c["tipo"] for c in estado["capas"]], ["base"])

    def test_capas_en_orden_base_ropa_accesorio(self):
        ropa = next(o for o in config.OBJETOS_AVATAR if o["tipo"] == "ropa")
        accesorio = next(o for o in config.OBJETOS_AVATAR if o["tipo"] == "accesorio")
        p = progreso_con(config.NIVELES[-1], HOY, avatar_base="base_2", ropa_id=ropa["id"], accesorio_id=accesorio["id"])
        estado = g.estado_avatar_capas(p)
        self.assertEqual([c["tipo"] for c in estado["capas"]], ["base", *config.TIPOS_OBJETO])
        self.assertEqual(estado["capas"][0]["archivo"], "base_2.png")

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
        self.assertIsNone(g.estado_avatar_capas(p)["puesto"][caro["tipo"]])

    def test_tipos_desconocidos_no_llegan_al_sql(self):
        self.assertEqual(g.columna_de_tipo("ropa"), "ropa_id")
        self.assertIsNone(g.columna_de_tipo("zapatos; DROP TABLE perfil"))


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
        for tabla in ("progreso_usuario", "eventos_xp", "actividad_diaria"):
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

    def test_registrar_despues_de_inactividad_descuenta_y_luego_suma(self):
        hoy = date.today()
        self._poner(xp_total=90, nivel_maximo=3, ultima_fecha_actividad=hoy - timedelta(days=3))
        resumen = g.registrar_actividad(self.db, USUARIO_PRUEBA, "estado_animo", estado_animo="bien")
        xp_animo = config.ACCIONES["estado_animo"]["xp"]
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
        self.assertEqual(g.equipar(self.db, USUARIO_PRUEBA, "accesorio", "buzo_verde")[1], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
