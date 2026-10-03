"""
test_login.py -- Pruebas del login con contraseña, escritas ANTES que el
código (para Isabella).

Se llaman "pruebas primero" (en inglés, TDD): primero se escribe qué debe
pasar, y después se programa hasta que todas las pruebas digan OK. Hoy
(27 sep 2026) se espera que FALLEN: /login todavía no existe en el código
commiteado y POST /perfil todavía no guarda contraseñas. Cada vez que
avances, córrelas: las que pasen a OK te dicen que esa parte ya funciona.

Cómo correrlas:
    1. Enciende el backend:        python3 app.py
    2. En otra terminal:           python3 test_login.py

Qué se asume del diseño (si decides otra cosa, cambia solo las constantes
de abajo, no las pruebas):
- Registro: POST /perfil con los datos de siempre MÁS la contraseña.
- Login: POST /login con {"email": ..., "contraseña": ...}.
- La contraseña se guarda como hash de bcrypt en perfil.password_hash.

Las pruebas crean perfiles con correos __test_login_<hora>_...__@lumea.test
y al final los borran (solo esos).
"""
import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import re
import time
import unittest

import requests

from database import conectar_mysql  # solo la conexión: NO se crea BaseDatos()

BASE_URL = "http://127.0.0.1:5002"
CAMPO_CONTRASENA = "contraseña"  # como lo llama tu /login en app.py
CONTRASENA = "Lumea-prueba-2026"
MARCA = str(int(time.time()))
PATRON_EMAIL = "__test_login_%__@lumea.test"

# Un hash de bcrypt siempre se ve así: $2b$12$ + 53 caracteres = 60 en total.
FORMA_BCRYPT = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")

HEADERS = {"User-Agent": "curl/8.7.1"}  # igual que test_api.py


def email_para(nombre):
    return PATRON_EMAIL.replace("%", f"{MARCA}_{nombre}")


def registrar(email, contrasena=CONTRASENA):
    datos = {
        "nombre": "Prueba login", "email": email, "edad": 15, "genero": "otro",
        "peso": 55.0, "altura": 160, "objetivo": "comer_balanceado",
    }
    if contrasena is not None:
        datos[CAMPO_CONTRASENA] = contrasena
    return requests.post(f"{BASE_URL}/perfil", json=datos, headers=HEADERS)


def login(email, contrasena):
    return requests.post(f"{BASE_URL}/login", json={"email": email, CAMPO_CONTRASENA: contrasena}, headers=HEADERS)


def sql(consulta, parametros=()):
    """Consulta directa a MySQL (sin pasar por el backend)."""
    conexion = conectar_mysql()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("USE lumea_db")
        cursor.execute(consulta, parametros)
        filas = cursor.fetchall() if cursor.with_rows else None
        conexion.commit()
        return filas
    finally:
        conexion.close()


class TestLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            requests.get(f"{BASE_URL}/alimentos", headers=HEADERS, timeout=5)
        except requests.ConnectionError:
            raise unittest.SkipTest(f"El backend no está encendido en {BASE_URL}: corre python3 app.py")

    @classmethod
    def tearDownClass(cls):
        """Borra los perfiles de prueba (y lo que hayan dejado en otras tablas)."""
        filas = sql("SELECT id FROM perfil WHERE email LIKE %s", (PATRON_EMAIL,))
        for fila in filas:
            for tabla in ("eventos_xp", "actividad_diaria", "progreso_usuario", "historial_comida", "estado_animo"):
                sql(f"DELETE FROM {tabla} WHERE usuario_id = %s", (fila["id"],))
            sql("DELETE FROM perfil WHERE id = %s", (fila["id"],))

    # ------------------------------------------------------------------
    # 1. Registro
    # ------------------------------------------------------------------

    def test_1_registro_guarda_hash_y_nunca_la_contrasena(self):
        """QUÉ COMPRUEBA: al registrarse con contraseña, la base de datos
        guarda un hash de bcrypt (no la contraseña), y la respuesta no
        devuelve ni la contraseña ni el hash.

        POR QUÉ IMPORTA: si alguien llega a ver la base de datos (o una
        respuesta del servidor), no debe poder leer las contraseñas. Con el
        hash no se puede sacar la contraseña original; solo se puede
        comprobar si una contraseña coincide."""
        email = email_para("registro")
        respuesta = registrar(email)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.assertNotIn(CONTRASENA, respuesta.text, "La respuesta del registro no debe repetir la contraseña")
        self.assertNotIn("$2b$", respuesta.text, "La respuesta del registro no debe incluir el hash")

        try:
            filas = sql("SELECT password_hash FROM perfil WHERE email = %s", (email,))
        except Exception as error:
            self.fail(f"No se pudo leer perfil.password_hash (¿ya existe la columna?): {error}")
        self.assertTrue(filas, "El perfil no quedó guardado")
        guardado = filas[0]["password_hash"]
        self.assertIsNotNone(guardado, "No se guardó nada en password_hash (¿POST /perfil ya recibe la contraseña?)")
        self.assertNotEqual(guardado, CONTRASENA, "¡La contraseña quedó en texto plano!")
        self.assertRegex(guardado, FORMA_BCRYPT, "password_hash no tiene la forma de un hash de bcrypt")

    def test_2_actualizar_el_perfil_sin_contrasena_no_la_borra(self):
        """QUÉ COMPRUEBA (extra): si el perfil se vuelve a guardar SIN
        contraseña (por ejemplo, al editar la edad), la contraseña de antes
        sigue sirviendo.

        POR QUÉ IMPORTA: POST /perfil también sirve para editar el perfil.
        Si editar la edad borrara la contraseña, la persona ya no podría
        entrar. (Tu IFNULL en guardar_perfil va justo en esta dirección.)"""
        email = email_para("editar")
        registrar(email)
        registrar(email, contrasena=None)
        self.assertEqual(login(email, CONTRASENA).status_code, 200)

    # ------------------------------------------------------------------
    # 2. Login
    # ------------------------------------------------------------------

    def test_3_login_correcto_da_200_y_no_devuelve_el_hash(self):
        """QUÉ COMPRUEBA: con el correo y la contraseña correctos, /login
        responde 200 y trae los datos del perfil, pero sin password_hash.

        POR QUÉ IMPORTA: es el camino feliz. Y el hash tampoco debe salir
        aquí: el frontend no lo necesita para nada."""
        email = email_para("correcto")
        registrar(email)
        respuesta = login(email, CONTRASENA)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.assertNotIn("password_hash", respuesta.text)
        self.assertNotIn("$2b$", respuesta.text)
        self.assertNotIn(CONTRASENA, respuesta.text)
        self.assertIn(email, respuesta.text, "La respuesta debería decir con qué perfil se entró")

    def test_4_contrasena_incorrecta_da_401(self):
        """QUÉ COMPRUEBA: con una contraseña equivocada, /login responde
        401 ("no autorizado").

        POR QUÉ IMPORTA: si respondiera 200, cualquiera podría entrar a la
        cuenta de otra persona escribiendo lo que sea."""
        email = email_para("incorrecta")
        registrar(email)
        respuesta = login(email, "otra-contraseña")
        self.assertEqual(respuesta.status_code, 401, respuesta.text)

    def test_5_correo_inexistente_da_401_con_el_mismo_mensaje(self):
        """QUÉ COMPRUEBA: con un correo que no está registrado, /login
        responde 401 con EXACTAMENTE el mismo mensaje que cuando la
        contraseña está mal.

        POR QUÉ IMPORTA: si los mensajes fueran distintos ("ese correo no
        existe" vs. "contraseña incorrecta"), alguien podría probar correos
        para averiguar quién usa Lumea. Con el mismo mensaje no se sabe si
        falló el correo o la contraseña."""
        email = email_para("mensaje")
        registrar(email)
        mal_contrasena = login(email, "otra-contraseña")
        no_existe = login(email_para("nadie_registrado"), CONTRASENA)
        self.assertEqual(no_existe.status_code, 401, no_existe.text)
        self.assertEqual(no_existe.json(), mal_contrasena.json(),
                         "Correo inexistente y contraseña incorrecta deben responder igual")

    def test_6_perfil_viejo_sin_contrasena_da_401_y_no_500(self):
        """QUÉ COMPRUEBA: un perfil creado ANTES de que existieran las
        contraseñas (password_hash vacío) no puede entrar: /login responde
        401 con el mismo mensaje de siempre, sin romperse (no 500).

        POR QUÉ IMPORTA: en la base de datos puede haber perfiles viejos
        (por ejemplo, en el computador de la sustentación). No deben poder
        entrar sin contraseña, pero tampoco deben tumbar el servidor:
        bcrypt lanza un error si le pasas un hash vacío.

        Si esta prueba falla al CREAR el perfil viejo, lo más probable es
        que la columna password_hash esté como NOT NULL: así los perfiles
        viejos no pueden existir (ver REVISION_CODIGO_ISABELLA.md)."""
        email = email_para("viejo")
        try:
            sql("INSERT INTO perfil (nombre, email) VALUES (%s, %s)", ("Perfil viejo", email))
        except Exception as error:
            self.fail(f"No se pudo crear un perfil sin contraseña: {error}")
        respuesta = login(email, "cualquier-cosa")
        self.assertNotEqual(respuesta.status_code, 500, "El servidor se rompió con un perfil sin contraseña")
        self.assertEqual(respuesta.status_code, 401, respuesta.text)
        referencia = login(email_para("nadie_registrado"), CONTRASENA)
        self.assertEqual(respuesta.json(), referencia.json())

    def test_7_faltan_datos_da_400(self):
        """QUÉ COMPRUEBA (extra): sin correo o sin contraseña, /login
        responde 400 ("petición mal hecha").

        POR QUÉ IMPORTA: así el frontend sabe que le faltó mandar algo, y
        el servidor no intenta buscar un correo vacío."""
        self.assertEqual(requests.post(f"{BASE_URL}/login", json={"email": email_para("x")}, headers=HEADERS).status_code, 400)
        self.assertEqual(requests.post(f"{BASE_URL}/login", json={CAMPO_CONTRASENA: CONTRASENA}, headers=HEADERS).status_code, 400)

    # ------------------------------------------------------------------
    # 3. Perfil
    # ------------------------------------------------------------------

    def test_8_get_perfil_nunca_devuelve_password_hash(self):
        """QUÉ COMPRUEBA: GET /perfil?email=... trae el perfil pero NUNCA el
        campo password_hash (ni el hash escondido en otro campo).

        POR QUÉ IMPORTA: GET /perfil no pide contraseña, así que cualquiera
        que sepa un correo puede llamarlo. Si devolviera el hash, lo
        estaríamos regalando. (Pista: en obtener_perfil_por_email, fíjate
        en qué orden están el 'return' y el 'del'.)"""
        email = email_para("get_perfil")
        registrar(email)
        respuesta = requests.get(f"{BASE_URL}/perfil", params={"email": email}, headers=HEADERS)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        perfil = respuesta.json().get("perfil", {})
        self.assertNotIn("password_hash", perfil)
        self.assertNotIn("$2b$", respuesta.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
