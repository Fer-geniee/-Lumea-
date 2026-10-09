"""
Pruebas de POST /perfil y GET /perfil (sin peso ni altura; edad mínima y
aviso al acudiente), con el cliente de pruebas de Flask. No necesita el
servidor corriendo, pero sí MySQL.

    python3 pruebas/test_perfil.py

Usa correos de prueba y los borra al final.
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import unittest

import app as servidor

EMAIL_PRUEBA = "__test_perfil__@lumea.test"
BASE = {"nombre": "Prueba perfil", "email": EMAIL_PRUEBA, "edad": 15, "genero": "otro",
        "objetivo": "comer_balanceado", "contraseña": "prueba-123", "acudiente_sabe": True}


def _borrar_perfil_de_prueba():
    cursor = servidor.db.conexion.cursor()
    cursor.execute("DELETE FROM perfil WHERE email = %s", (EMAIL_PRUEBA,))
    servidor.db.conexion.commit()
    cursor.close()


class TestPerfil(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = servidor.app.test_client()

    def setUp(self):
        _borrar_perfil_de_prueba()

    @classmethod
    def tearDownClass(cls):
        _borrar_perfil_de_prueba()

    def crear(self, **cambios):
        cuerpo = {**BASE, **cambios}
        for clave in [k for k, v in cuerpo.items() if v == "__quitar__"]:
            del cuerpo[clave]
        return self.cliente.post("/perfil", json=cuerpo)

    # ---------- B1: sin peso ni altura ----------
    def test_crea_cuenta_sin_peso_ni_altura(self):
        self.assertEqual(self.crear().status_code, 200)

    def test_peso_y_altura_si_llegan_se_ignoran(self):
        self.assertEqual(self.crear(peso=60, altura=165).status_code, 200)
        cursor = servidor.db.conexion.cursor()
        cursor.execute("SELECT peso, altura FROM perfil WHERE email = %s", (EMAIL_PRUEBA,))
        self.assertEqual(cursor.fetchone(), (None, None))
        servidor.db.conexion.commit()
        cursor.close()

    def test_get_perfil_no_devuelve_peso_ni_altura_ni_hash(self):
        self.crear()
        perfil = self.cliente.get("/perfil", query_string={"email": EMAIL_PRUEBA}).get_json()["perfil"]
        for campo in ("peso", "altura", "password_hash"):
            self.assertNotIn(campo, perfil)

    def test_objetivos_solo_los_dos_de_crear_cuenta(self):
        for objetivo in ("comer_balanceado", "conocer_lo_que_como"):
            with self.subTest(objetivo=objetivo):
                _borrar_perfil_de_prueba()
                self.assertEqual(self.crear(objetivo=objetivo).status_code, 200)
        for objetivo in ("tomar_agua", "dormir_mejor", "moverse_mas", "adelgazar"):
            with self.subTest(objetivo=objetivo):
                _borrar_perfil_de_prueba()
                self.assertEqual(self.crear(objetivo=objetivo).status_code, 400)

    def test_perfil_viejo_con_otro_objetivo_se_lee_sin_error(self):
        self.crear()
        cursor = servidor.db.conexion.cursor()
        cursor.execute("UPDATE perfil SET objetivo = 'tomar_agua', peso = 50 WHERE email = %s", (EMAIL_PRUEBA,))
        servidor.db.conexion.commit()
        cursor.close()
        r = self.cliente.get("/perfil", query_string={"email": EMAIL_PRUEBA})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["perfil"]["objetivo"], "tomar_agua")
        self.assertNotIn("peso", r.get_json()["perfil"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
