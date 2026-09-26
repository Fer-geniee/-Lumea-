"""
Pruebas de la confirmación manual (grupos_confusion.py + /predecir +
/confirmar-alimento), con el cliente de pruebas de Flask. No necesita el
servidor corriendo, pero sí MySQL.

    python3 test_confirmacion.py

La predicción de la IA se reemplaza por una falsa (el modelo "dice" cada
disparador con 99% de certeza): así se prueba la lógica de confirmación
de cada grupo sin depender de tener una foto de cada alimento. Las
confirmaciones se hacen con un correo de prueba y se borran al final.
"""

import io
import unittest

import app as servidor
from grupos_confusion import GRUPOS_CONFUSION, codigos_de_opciones, detalle_de_opciones
from sellos import SELLOS_VALIDOS

EMAIL_PRUEBA = "__test_confirmacion__@lumea.test"
CODIGOS_SOLO_AGRUPACION = {"sopas", "dulces"}  # nunca pueden ser opción (no tienen nutrición propia)
GRUPOS_CON_OTRO = {"tamal", "frituras_empaquetadas", "gaseosas_bebidas_azucaradas"}


def prediccion_falsa(codigo):
    return lambda imagen: {"alimento_codigo": codigo, "confianza_porcentaje": 99.0, "modelo_usado": "regional_26"}


class TestEstructuraDeGrupos(unittest.TestCase):
    def test_cada_opcion_tiene_los_4_campos(self):
        for grupo in GRUPOS_CONFUSION:
            for opcion in grupo["opciones"]:
                with self.subTest(grupo=grupo["id"], opcion=opcion.get("codigo")):
                    self.assertEqual(set(opcion), {"codigo", "nombre", "marca", "grupo"})
                    self.assertTrue(opcion["nombre"])

    def test_codigos_sin_repetir_dentro_de_cada_grupo(self):
        for grupo in GRUPOS_CONFUSION:
            codigos = codigos_de_opciones(grupo)
            self.assertEqual(len(codigos), len(set(codigos)), grupo["id"])

    def test_ningun_codigo_de_agrupacion_es_opcion(self):
        for grupo in GRUPOS_CONFUSION:
            self.assertFalse(CODIGOS_SOLO_AGRUPACION & set(codigos_de_opciones(grupo)), grupo["id"])

    def test_grupos_nuevos_tienen_opcion_otro_con_la_fila_generica(self):
        for grupo in GRUPOS_CONFUSION:
            if grupo["id"] not in GRUPOS_CON_OTRO:
                continue
            otros = [o for o in grupo["opciones"] if o["grupo"] == "otro"]
            with self.subTest(grupo=grupo["id"]):
                self.assertEqual(len(otros), 1)
                self.assertIn(otros[0]["codigo"], grupo["disparadores"])


class TestEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = servidor.app.test_client()
        cls.prediccion_original = servidor.predecir_alimento
        cls.cliente.post("/perfil", json={
            "nombre": "Prueba confirmación", "email": EMAIL_PRUEBA, "edad": 15, "genero": "otro",
            "peso": 55, "altura": 160, "objetivo": "comer_balanceado",
        })

    @classmethod
    def tearDownClass(cls):
        servidor.predecir_alimento = cls.prediccion_original
        cursor = servidor.db.conexion.cursor()
        cursor.execute("SELECT id FROM perfil WHERE email = %s", (EMAIL_PRUEBA,))
        for (usuario_id,) in cursor.fetchall():
            for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "historial_comida", "estado_animo"):
                cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
        servidor.db.conexion.commit()
        cursor.close()

    def test_predecir_fuerza_confirmacion_en_cada_disparador(self):
        for grupo in GRUPOS_CONFUSION:
            for disparador in sorted(grupo["disparadores"]):
                with self.subTest(grupo=grupo["id"], disparador=disparador):
                    servidor.predecir_alimento = prediccion_falsa(disparador)
                    r = self.cliente.post(
                        "/predecir", data={"file": (io.BytesIO(b"x"), "foto.jpg"), "email": EMAIL_PRUEBA},
                        content_type="multipart/form-data",
                    )
                    cuerpo = r.get_json()
                    self.assertEqual(r.status_code, 200)
                    self.assertFalse(cuerpo["success"])
                    self.assertTrue(cuerpo["seleccion_manual"])
                    self.assertFalse(cuerpo["guardado_baseDatos"])
                    # Contrato original intacto + campo nuevo coherente con él.
                    self.assertEqual(cuerpo["opciones_sugeridas"], codigos_de_opciones(grupo))
                    self.assertEqual(cuerpo["opciones_detalle"], detalle_de_opciones(grupo))
                    self.assertEqual([o["codigo"] for o in cuerpo["opciones_detalle"]], cuerpo["opciones_sugeridas"])

    def test_confirmar_acepta_cada_opcion_de_cada_grupo(self):
        for grupo in GRUPOS_CONFUSION:
            for codigo in codigos_de_opciones(grupo):
                with self.subTest(grupo=grupo["id"], codigo=codigo):
                    r = self.cliente.post("/confirmar-alimento", json={"alimento_codigo": codigo, "email": EMAIL_PRUEBA})
                    cuerpo = r.get_json()
                    self.assertEqual(r.status_code, 200, cuerpo)
                    self.assertTrue(cuerpo["guardado_baseDatos"])
                    self.assertEqual(cuerpo["alimento_codigo"], codigo)
                    # Los sellos vienen de tabla_alimentos y cuadran con es_saludable.
                    sellos = cuerpo["sellos_advertencia"]
                    self.assertIsInstance(sellos, list)
                    self.assertTrue(set(sellos) <= set(SELLOS_VALIDOS), sellos)
                    es_saludable = servidor.db.obtener_informacion_alimento(codigo)["es_saludable"]
                    self.assertEqual(es_saludable == 1, sellos == [], f"es_saludable={es_saludable}, sellos={sellos}")

    def test_confirmar_rechaza_codigos_de_agrupacion(self):
        for codigo in sorted(CODIGOS_SOLO_AGRUPACION):
            with self.subTest(codigo=codigo):
                r = self.cliente.post("/confirmar-alimento", json={"alimento_codigo": codigo, "email": EMAIL_PRUEBA})
                self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=1)
