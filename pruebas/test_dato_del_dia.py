"""
Pruebas de GET /dato-del-dia: la función pura (dato_del_dia.py) y el endpoint
con el cliente de pruebas de Flask. El endpoint necesita MySQL, pero no el
servidor corriendo.

    python3 pruebas/test_dato_del_dia.py
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import unittest
from datetime import date, datetime, timedelta
from unittest import mock

import app as servidor
import dato_del_dia as d

FILAS = [{"alimento_codigo": f"alimento_{i}", "nombre_pantalla": f"Alimento {i}", "dato_curioso": f"Dato {i}."}
         for i in range(7)]
HOY = date(2026, 10, 9)


class TestElegirDato(unittest.TestCase):
    def test_el_mismo_dia_da_el_mismo_dato_sin_importar_el_orden_de_las_filas(self):
        a = d.elegir_dato(FILAS, HOY)
        b = d.elegir_dato(list(reversed(FILAS)), HOY)
        self.assertEqual(a, b)
        self.assertEqual(a, d.elegir_dato(FILAS, HOY))

    def test_n_dias_seguidos_recorren_los_n_datos_sin_repetir(self):
        for inicio in (HOY, date(2026, 12, 25), date(2027, 3, 1)):
            with self.subTest(inicio=inicio):
                codigos = [d.elegir_dato(FILAS, inicio + timedelta(days=k))["alimento_codigo"] for k in range(len(FILAS))]
                self.assertEqual(len(set(codigos)), len(FILAS))
                # Y al día n + 1 vuelve a empezar por el primero.
                self.assertEqual(d.elegir_dato(FILAS, inicio + timedelta(days=len(FILAS)))["alimento_codigo"], codigos[0])

    def test_las_filas_sin_dato_no_cuentan(self):
        filas = FILAS + [{"alimento_codigo": "a", "nombre_pantalla": "A", "dato_curioso": None},
                         {"alimento_codigo": "b", "nombre_pantalla": "B", "dato_curioso": "   "},
                         {"alimento_codigo": "c", "nombre_pantalla": "C", "dato_curioso": ""}]
        vistos = {d.elegir_dato(filas, HOY + timedelta(days=k))["alimento_codigo"] for k in range(30)}
        self.assertEqual(vistos, {f["alimento_codigo"] for f in FILAS})

    def test_sin_datos_es_none(self):
        self.assertIsNone(d.elegir_dato([], HOY))
        self.assertIsNone(d.respuesta_del_dia([{"alimento_codigo": "a", "nombre_pantalla": "A", "dato_curioso": ""}], HOY))

    def test_la_respuesta_tiene_la_forma_del_contrato(self):
        r = d.respuesta_del_dia(FILAS, HOY)
        self.assertEqual(set(r), {"fecha", "alimento_codigo", "nombre", "dato_curioso"})
        self.assertEqual(r["fecha"], "2026-10-09")

    def test_el_dia_es_el_de_bogota_no_el_del_servidor(self):
        # 03:00 UTC del 10 de octubre todavía es el 9 en Bogotá (UTC-5).
        class FalsoDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 10, 3, 0, tzinfo=d.ZoneInfo("UTC")).astimezone(tz)
        with mock.patch.object(d, "datetime", FalsoDatetime):
            self.assertEqual(d.fecha_de_hoy(), date(2026, 10, 9))


class TestEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = servidor.app.test_client()

    def test_devuelve_el_dato_del_dia_con_el_contrato(self):
        r = self.cliente.get("/dato-del-dia")
        self.assertEqual(r.status_code, 200)
        cuerpo = r.get_json()
        self.assertEqual(set(cuerpo), {"fecha", "alimento_codigo", "nombre", "dato_curioso"})
        self.assertTrue(cuerpo["dato_curioso"].strip())
        self.assertEqual(cuerpo["fecha"], d.fecha_de_hoy().isoformat())

    def test_es_el_mismo_para_todos_y_no_depende_de_parametros(self):
        a = self.cliente.get("/dato-del-dia").get_json()
        b = self.cliente.get("/dato-del-dia", query_string={"email": "alguien@lumea.test"}).get_json()
        self.assertEqual(a, b)
        self.assertNotIn("alguien@lumea.test", str(b))

    def test_el_dato_es_de_tabla_alimentos(self):
        cuerpo = self.cliente.get("/dato-del-dia").get_json()
        info = servidor.db.obtener_informacion_alimento(cuerpo["alimento_codigo"])
        servidor.db.conexion.commit()
        self.assertEqual(info["dato_curioso"].strip(), cuerpo["dato_curioso"])
        self.assertEqual(info["nombre_pantalla"], cuerpo["nombre"])

    def test_sin_datos_404(self):
        with mock.patch.object(servidor.db, "obtener_datos_curiosos", return_value=[]):
            self.assertEqual(self.cliente.get("/dato-del-dia").status_code, 404)

    def test_sin_base_de_datos_503(self):
        with mock.patch.object(servidor.db, "obtener_datos_curiosos", return_value=None):
            self.assertEqual(self.cliente.get("/dato-del-dia").status_code, 503)

    def test_n_dias_seguidos_recorren_todos_los_datos_de_la_tabla(self):
        filas = servidor.db.obtener_datos_curiosos()
        self.assertGreater(len(filas), 100)
        codigos = [d.elegir_dato(filas, HOY + timedelta(days=k))["alimento_codigo"] for k in range(len(filas))]
        self.assertEqual(len(set(codigos)), len(filas))


if __name__ == "__main__":
    unittest.main(verbosity=2)
