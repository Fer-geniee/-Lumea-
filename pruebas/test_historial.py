"""
Pruebas de GET /historial: los campos `grupo` y `sellos` de cada ítem, con el
cliente de pruebas de Flask. No necesita el servidor corriendo, pero sí MySQL.

    python3 pruebas/test_historial.py

Crea un perfil de prueba con algunas comidas y lo borra al final.
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import unittest

import app as servidor
from consejos import consejo_para, grupo_de
from sellos import obtener_sellos

EMAIL_PRUEBA = "__test_historial__@lumea.test"
# (código, qué se espera de su grupo)
COMIDAS = ["arepa", "banano", "aromatica", "cocacola_original", "sopas", "codigo_que_no_existe"]


class TestHistorialGrupoYSellos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = servidor.app.test_client()
        cls._borrar()
        r = cls.cliente.post("/perfil", json={
            "nombre": "Prueba historial", "email": EMAIL_PRUEBA, "edad": 16, "acudiente_sabe": True,
            "genero": "otro", "objetivo": "comer_balanceado", "contraseña": "prueba-123",
        })
        assert r.status_code == 200, r.get_json()
        usuario_id = servidor.db.obtener_perfil_por_email(EMAIL_PRUEBA)["id"]
        for codigo in COMIDAS:
            servidor.db.registrar_comida(codigo, codigo, 90.0, 100, 1, usuario_id)
        cls.historial = cls.cliente.get("/historial", query_string={"email": EMAIL_PRUEBA}).get_json()["historial"]

    @classmethod
    def tearDownClass(cls):
        cls._borrar()

    @classmethod
    def _borrar(cls):
        cursor = servidor.db.conexion.cursor()
        cursor.execute("SELECT id FROM perfil WHERE email = %s", (EMAIL_PRUEBA,))
        for (usuario_id,) in cursor.fetchall():
            for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "calcomanias_usuario", "historial_comida", "estado_animo"):
                cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
        servidor.db.conexion.commit()
        cursor.close()

    def item(self, codigo):
        return next(x for x in self.historial if x["alimento_codigo"] == codigo)

    def test_trae_todos_los_registros(self):
        self.assertEqual(len(self.historial), len(COMIDAS))

    def test_cada_item_trae_grupo_y_sellos(self):
        for x in self.historial:
            with self.subTest(codigo=x["alimento_codigo"]):
                self.assertIn("grupo", x)
                self.assertIsInstance(x["sellos"], list)

    def test_grupo_es_el_de_grupos_plato_csv_o_null(self):
        self.assertEqual(self.item("arepa")["grupo"], "cereales")
        self.assertEqual(self.item("banano")["grupo"], "frutas_verduras")
        self.assertIsNone(self.item("aromatica")["grupo"])           # sin grupo en el mapa
        self.assertIsNone(self.item("sopas")["grupo"])               # agrupación visual: sin fila
        self.assertIsNone(self.item("codigo_que_no_existe")["grupo"])

    def test_grupo_coincide_con_el_del_consejo(self):
        for x in self.historial:
            consejo = consejo_para(x["alimento_codigo"], x["sellos_advertencia"])
            with self.subTest(codigo=x["alimento_codigo"]):
                self.assertEqual(x["grupo"], consejo["grupo"] if consejo else None)
                self.assertEqual(x["grupo"], grupo_de(x["alimento_codigo"]))

    def test_sellos_traen_dato_e_idea_de_cada_sello_de_advertencia(self):
        gaseosa = self.item("cocacola_original")
        esperados = obtener_sellos(servidor.db, "cocacola_original")
        servidor.db.conexion.commit()
        self.assertTrue(esperados)
        self.assertEqual([s["sello"] for s in gaseosa["sellos"]], esperados)
        self.assertEqual(gaseosa["sellos_advertencia"], esperados)       # el campo de antes no cambia
        for s in gaseosa["sellos"]:
            self.assertTrue(s["dato"] and s["idea"])

    def test_sin_sellos_es_lista_vacia(self):
        self.assertEqual(self.item("banano")["sellos"], [])
        self.assertEqual(self.item("sopas")["sellos"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
