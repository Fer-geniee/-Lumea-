"""
Peticiones simultáneas: app.py usa UNA sola conexión MySQL, y Flask atiende cada petición en su propio
hilo. Si dos peticiones usan la conexión a la vez, mysql-connector se corrompe ("MySQL Connection not
available") y el servidor puede caerse con un segmentation fault. Las pantallas de Progreso y Avatar
piden 3 cosas a la vez, así que esto pasa en la vida real.

    python3 pruebas/test_concurrencia.py

Usa el cliente de pruebas de Flask (sin servidor, con MySQL) y un correo de prueba que se borra al final.
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import threading
import unittest

import app as servidor

EMAIL_PRUEBA = "__test_concurrencia__@lumea.test"
RUTAS = ["/progreso", "/historial", "/estado-animo", "/calcomanias", "/avatar"]
RONDAS = 15


class TestPeticionesSimultaneas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = servidor.app.test_client()
        cls.cliente.post("/perfil", json={
            "nombre": "Prueba concurrencia", "email": EMAIL_PRUEBA, "edad": 15, "acudiente_sabe": True, "genero": "otro",
            "objetivo": "comer_balanceado", "contraseña": "prueba-123",
        })

    @classmethod
    def tearDownClass(cls):
        cursor = servidor.db.conexion.cursor()
        cursor.execute("SELECT id FROM perfil WHERE email = %s", (EMAIL_PRUEBA,))
        for (usuario_id,) in cursor.fetchall():
            for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "calcomanias_usuario", "historial_comida", "estado_animo"):
                cursor.execute(f"DELETE FROM {tabla} WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM perfil WHERE id = %s", (usuario_id,))
        servidor.db.conexion.commit()
        cursor.close()

    def test_varias_peticiones_a_la_vez_no_rompen_la_conexion(self):
        codigos = []

        def pedir(ruta):
            r = servidor.app.test_client().get(ruta, query_string={"email": EMAIL_PRUEBA})
            codigos.append((ruta, r.status_code))

        for _ in range(RONDAS):
            hilos = [threading.Thread(target=pedir, args=(ruta,)) for ruta in RUTAS]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
        malas = [(ruta, codigo) for ruta, codigo in codigos if codigo != 200]
        self.assertEqual(malas, [], f"{len(malas)} de {len(codigos)} peticiones fallaron")
        # Y la conexión sigue sirviendo después
        self.assertEqual(self.cliente.get("/progreso", query_string={"email": EMAIL_PRUEBA}).status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
