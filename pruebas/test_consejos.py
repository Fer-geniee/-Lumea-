"""
Pruebas de los consejos al reconocer un alimento (consejos.py,
consejos_config.py, datos/grupos_plato.csv y el campo `consejo` de
/predecir y /confirmar-alimento).

    python3 pruebas/test_consejos.py

Las pruebas de la función y de los textos no necesitan nada. Las del mapa
contra tabla_alimentos y las de los endpoints usan MySQL (se saltan si está
apagado) y el cliente de pruebas de Flask, sin servidor.
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import csv
import glob
import io
import re
import unittest

import consejos
import consejos_config as textos
from grupos_confusion import GRUPOS_CONFUSION, codigos_de_opciones

BACKEND = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
EMAIL_PRUEBA = "__test_consejos__@lumea.test"
TIPOS_VALIDOS = {"plato", "fruta", "bebida", "paquete", "postre"}
SELLOS_DE_PRUEBA = ["sodio", "azucares", "grasas_saturadas", "grasas_trans", "edulcorantes"]
# Las reglas de estilo de Isabella: ningún texto juzga la comida ni a la persona.
PALABRAS_PROHIBIDAS = ["bueno", "malo", "evita", "prohibido", "saludable"]


def todos_los_textos(valor):
    """Todas las cadenas de un diccionario/lista anidado de consejos_config."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from todos_los_textos(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from todos_los_textos(v)


def codigos_de_los_csv():
    """Los alimentos que entran a tabla_alimentos: todos los datos/alimentos_*.csv
    que tienen nombre_pantalla (los *_fuentes y *_ingredientes no)."""
    codigos = set()
    for ruta in glob.glob(_os.path.join(BACKEND, "datos", "alimentos_*.csv")):
        with open(ruta, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f)
            if "nombre_pantalla" in (lector.fieldnames or []):
                codigos |= {fila["alimento_codigo"] for fila in lector}
    return codigos


class TestFuncionConsejo(unittest.TestCase):
    def test_cada_alimento_de_la_demo_devuelve_su_texto_propio(self):
        for codigo, propio in textos.ALIMENTOS.items():
            with self.subTest(codigo=codigo):
                c = consejos.consejo_para(codigo, [])
                self.assertEqual(c["aporta"], propio["aporta"])
                self.assertEqual(c["a_tener_en_cuenta"], propio["a_tener_en_cuenta"])

    def test_sin_texto_propio_usa_el_del_primer_grupo(self):
        c = consejos.consejo_para("pad_thai", [])  # cereales; proteinas; frutas_verduras
        self.assertEqual(c["grupo"], "cereales")
        self.assertEqual(c["aporta"], textos.GRUPOS["cereales"]["aporta"])
        self.assertIsNone(c["a_tener_en_cuenta"])

    def test_la_respuesta_siempre_trae_las_cinco_claves(self):
        for codigo in consejos.MAPA:
            with self.subTest(codigo=codigo):
                c = consejos.consejo_para(codigo, [])
                self.assertEqual(set(c), {"grupo", "aporta", "para_completar", "a_tener_en_cuenta", "sellos"})

    def test_fruta_y_bebida_no_devuelven_para_completar(self):
        for codigo in ("banano", "mango", "cocacola_original", "gaseosas_bebidas_azucaradas"):
            with self.subTest(codigo=codigo):
                self.assertIsNone(consejos.consejo_para(codigo, [])["para_completar"])

    def test_paquete_y_postre_tampoco_devuelven_para_completar(self):
        for codigo, datos in consejos.MAPA.items():
            if datos["tipo"] in ("paquete", "postre"):
                with self.subTest(codigo=codigo):
                    self.assertIsNone(consejos.consejo_para(codigo, [])["para_completar"])

    def test_plato_sin_verdura_pide_verdura_primero(self):
        # arepa: solo cereales -> falta primero frutas_verduras
        self.assertEqual(consejos.consejo_para("arepa", [])["para_completar"], textos.PARA_COMPLETAR["frutas_verduras"])

    def test_plato_con_verdura_pide_proteina_y_luego_cereal(self):
        # beet_salad: solo frutas_verduras -> falta proteinas
        self.assertEqual(consejos.consejo_para("beet_salad", [])["para_completar"], textos.PARA_COMPLETAR["proteinas"])
        # El orden sigue: verdura, proteína, cereal.
        mapa_original = consejos.MAPA
        consejos.MAPA = {"x": {"tipo": "plato", "grupos": ["frutas_verduras", "proteinas"]}}
        try:
            self.assertEqual(consejos.consejo_para("x", [])["para_completar"], textos.PARA_COMPLETAR["cereales"])
        finally:
            consejos.MAPA = mapa_original

    def test_plato_completo_devuelve_null(self):
        self.assertIsNone(consejos.consejo_para("ajiaco", [])["para_completar"])

    def test_una_entrada_por_cada_sello_con_los_textos_de_isabella(self):
        c = consejos.consejo_para("chicharron", SELLOS_DE_PRUEBA)
        self.assertEqual([s["sello"] for s in c["sellos"]], SELLOS_DE_PRUEBA)
        for entrada in c["sellos"]:
            self.assertEqual(entrada["dato"], textos.SELLOS[entrada["sello"]]["dato"])
            self.assertEqual(entrada["idea"], textos.SELLOS[entrada["sello"]]["idea"])

    def test_sin_sellos_o_sellos_desconocidos_la_lista_es_vacia(self):
        self.assertEqual(consejos.consejo_para("banano", [])["sellos"], [])
        self.assertEqual(consejos.consejo_para("banano", None)["sellos"], [])
        self.assertEqual(consejos.consejo_para("banano", ["algo_raro"])["sellos"], [])

    def test_codigos_de_agrupacion_sin_confirmar_devuelven_null(self):
        for codigo in ("sopas", "dulces", "no_existe", None):
            with self.subTest(codigo=codigo):
                self.assertIsNone(consejos.consejo_para(codigo, []))

    def test_las_opciones_de_confirmacion_si_tienen_consejo(self):
        for grupo in GRUPOS_CONFUSION:
            for codigo in codigos_de_opciones(grupo):
                with self.subTest(grupo=grupo["id"], codigo=codigo):
                    self.assertIsNotNone(consejos.consejo_para(codigo, []))

    def test_aromatica_no_tiene_grupo_pero_usa_su_texto_propio(self):
        # Sin grupo en el mapa, el "aporta" sale del texto propio que escribió
        # Isabella (la clave de consejos_config.py es "aromatica", sin tilde,
        # igual que el código del alimento).
        c = consejos.consejo_para("aromatica", [])
        self.assertIsNone(c["grupo"])
        self.assertEqual(c["aporta"], textos.ALIMENTOS["aromatica"]["aporta"])


class TestTextosYMapa(unittest.TestCase):
    def test_ningun_texto_usa_palabras_que_juzgan(self):
        todos = list(todos_los_textos([textos.GRUPOS, textos.PARA_COMPLETAR, textos.SELLOS, textos.ALIMENTOS]))
        self.assertGreater(len(todos), 30)  # que de verdad se estén revisando los textos
        for texto in todos:
            for palabra in PALABRAS_PROHIBIDAS:
                with self.subTest(palabra=palabra, texto=texto[:40]):
                    self.assertIsNone(re.search(rf"\b{palabra}\w*", texto, re.IGNORECASE))

    def test_ningun_texto_lleva_emojis(self):
        for texto in todos_los_textos([textos.GRUPOS, textos.PARA_COMPLETAR, textos.SELLOS, textos.ALIMENTOS]):
            self.assertFalse(any(ord(c) > 0x2BFF for c in texto), texto[:40])

    def test_cada_texto_de_alimentos_apunta_a_un_alimento_del_mapa(self):
        for codigo in textos.ALIMENTOS:
            self.assertIn(codigo, consejos.MAPA)

    def test_los_sellos_de_los_textos_son_los_sellos_validos(self):
        from sellos import SELLOS_VALIDOS
        self.assertEqual(set(textos.SELLOS), set(SELLOS_VALIDOS))

    def test_el_mapa_cubre_todos_los_csv_con_tipos_y_grupos_validos(self):
        faltan = codigos_de_los_csv() - set(consejos.MAPA)
        self.assertEqual(faltan, set(), f"sin fila en grupos_plato.csv: {sorted(faltan)}")
        for codigo, datos in consejos.MAPA.items():
            with self.subTest(codigo=codigo):
                self.assertIn(datos["tipo"], TIPOS_VALIDOS)
                for grupo in datos["grupos"]:
                    self.assertIn(grupo, textos.GRUPOS)

    def test_el_mapa_no_tiene_filas_de_mas(self):
        self.assertEqual(set(consejos.MAPA) - codigos_de_los_csv(), set())

    def test_frutas_solo_tienen_frutas_verduras(self):
        for codigo, datos in consejos.MAPA.items():
            if datos["tipo"] == "fruta":
                self.assertEqual(datos["grupos"], ["frutas_verduras"], codigo)

    def test_los_codigos_de_agrupacion_visual_no_estan_en_el_mapa(self):
        self.assertNotIn("sopas", consejos.MAPA)
        self.assertNotIn("dulces", consejos.MAPA)


class TestConMySQLYEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as servidor
        cls.servidor = servidor
        if not servidor.db.conexion or not servidor.db.conexion.is_connected():
            raise unittest.SkipTest("MySQL apagado")
        cls.cliente = servidor.app.test_client()
        cls.prediccion_original = servidor.predecir_alimento
        cls.cliente.post("/perfil", json={
            "nombre": "Prueba consejos", "email": EMAIL_PRUEBA, "edad": 15, "acudiente_sabe": True, "genero": "otro",
            "objetivo": "comer_balanceado", "contraseña": "prueba-123",
        })

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "cliente"):
            return
        cls.servidor.predecir_alimento = cls.prediccion_original
        conexion = cls.servidor.db.conexion
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM perfil WHERE email = %s", (EMAIL_PRUEBA,))
        for (usuario_id,) in cursor.fetchall():
            for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "calcomanias_usuario", "historial_comida", "estado_animo"):
                cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
        conexion.commit()
        cursor.close()

    def _predecir(self, codigo, certeza=99.0):
        self.servidor.predecir_alimento = lambda imagen: {
            "alimento_codigo": codigo, "confianza_porcentaje": certeza, "modelo_usado": "regional_26"}
        r = self.cliente.post("/predecir", data={"file": (io.BytesIO(b"x"), "foto.jpg"), "email": EMAIL_PRUEBA},
                              content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def test_todo_codigo_de_tabla_alimentos_tiene_fila_en_el_mapa(self):
        cursor = self.servidor.db.conexion.cursor()
        cursor.execute("SELECT alimento_codigo FROM tabla_alimentos")
        codigos = {fila[0] for fila in cursor.fetchall()}
        cursor.close()
        self.servidor.db.conexion.commit()  # una lectura sin commit deja una transacción abierta
        self.assertGreater(len(codigos), 100)
        self.assertEqual(codigos - set(consejos.MAPA), set())
        self.assertEqual(set(consejos.MAPA) - codigos, set())

    def test_predecir_seguro_trae_el_consejo_con_los_sellos_de_la_respuesta(self):
        cuerpo = self._predecir("banano")
        self.assertTrue(cuerpo["success"])
        self.assertEqual(cuerpo["consejo"], consejos.consejo_para("banano", cuerpo["sellos_advertencia"]))
        self.assertIsNone(cuerpo["consejo"]["para_completar"])
        # No se tocaron los campos de antes.
        self.assertIn("dato_curioso", cuerpo)
        self.assertIn("mensaje_educativo", cuerpo)

    def test_predecir_con_sellos_trae_una_entrada_por_sello(self):
        cuerpo = self._predecir("chicharron")
        self.assertTrue(cuerpo["sellos_advertencia"])
        self.assertEqual([s["sello"] for s in cuerpo["consejo"]["sellos"]], cuerpo["sellos_advertencia"])

    def test_predecir_pidiendo_confirmacion_no_trae_consejo(self):
        for codigo, certeza in (("sopas", 99.0), ("banano", 40.0)):
            with self.subTest(codigo=codigo, certeza=certeza):
                cuerpo = self._predecir(codigo, certeza)
                self.assertTrue(cuerpo["seleccion_manual"])
                self.assertNotIn("consejo", cuerpo)

    def test_confirmar_alimento_trae_el_consejo(self):
        for codigo in ("banano", "gaseosas_bebidas_azucaradas", "bandeja_paisa"):
            with self.subTest(codigo=codigo):
                r = self.cliente.post("/confirmar-alimento", json={"alimento_codigo": codigo, "email": EMAIL_PRUEBA})
                cuerpo = r.get_json()
                self.assertEqual(r.status_code, 200)
                self.assertEqual(cuerpo["consejo"], consejos.consejo_para(codigo, cuerpo["sellos_advertencia"]))
                self.assertEqual([s["sello"] for s in cuerpo["consejo"]["sellos"]], cuerpo["sellos_advertencia"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
