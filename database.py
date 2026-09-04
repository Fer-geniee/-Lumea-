import os
import io
import csv
import mysql.connector
from venv import load_dotenv

load_dotenv()


def conectar_mysql():
    """Establece la conexión inicial con el servidor MySQL.

    La contraseña NUNCA debe quedar escrita en el código fuente. Se lee desde
    una variable de entorno (archivo .env) que no se sube al repositorio.
    """
    password = os.getenv("MYSQL_PASSWORD", "")
    host = os.getenv("MYSQL_HOST", "127.0.0.1")  # Cambiar en .env el día de la sustentación IMPORTANTE 
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")

    try:
        conexion = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",  # Tildes y eñes 
        )
        if conexion.is_connected():
            return conexion
    except mysql.connector.Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None


class BaseDatos:
    def __init__(self):
        self.conexion = conectar_mysql()
        if self.conexion is None:
            print("No se pudo conectar a MySQL.")
        else:
            self.crear_tablas()

    def crear_tablas(self):
        """Crea la base de datos 'lumea_db' y las tablas necesarias."""
        if not self.conexion or not self.conexion.is_connected():
            return

        cursor = self.conexion.cursor()
        try:
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS lumea_db "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute("USE lumea_db")

            # 1. TABLA DE TRACKER DE COMIDA
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historial_comida (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATE DEFAULT (CURRENT_DATE),
                    alimento_codigo VARCHAR(100),
                    alimento_detectado VARCHAR(255),
                    certeza_ia FLOAT,
                    calorias_aprox INT,
                    balanceado INT -- 1 para Sí, 0 para No
                )
            ''')

            # 2. TABLA DE PERFIL DE USUARIO
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS perfil (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100),
                    email VARCHAR(100),
                    edad INT,
                    genero VARCHAR(20),
                    peso FLOAT,
                    altura INT
                )
            ''')

            # 3. TABLA DE HIDRATACIÓN
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hidratacion (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATE DEFAULT (CURRENT_DATE),
                    cantidad_mL INT
                )
            ''')

            # 4. TABLA DE SUEÑO
            # Nota: renombrada de 'sueño' a 'sueno' (sin eñe) para evitar problemas
            # de identificador según el charset/collation del cliente MySQL que use
            # cada máquina el día de la presentación. Ver explicación en el chat.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sueno (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATE DEFAULT (CURRENT_DATE),
                    horas_sueno FLOAT,
                    calidad_sueno VARCHAR(255)
                )
            ''')

            # 5. TABLA DE ACTIVIDAD FÍSICA
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS actividad_fisica (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATE DEFAULT (CURRENT_DATE),
                    tipo_actividad VARCHAR(200),
                    duracion_minutos INT,
                    intensidad VARCHAR(50)
                )
            ''')

            # 6. TABLA MAESTRA DE ALIMENTOS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tabla_alimentos (
                    alimento_codigo VARCHAR(100) PRIMARY KEY,
                    nombre_pantalla VARCHAR(100),
                    calorias INT,
                    es_saludable INT
                )
            ''')

            self.conexion.commit()
            print("Estructura de tablas verificada en MySQL (lumea_db).")
            self._verificar_alimentos_poblados(cursor)

        except mysql.connector.Error as e:
            print(f"Error al crear tablas en MySQL: {e}")
        finally:
            cursor.close()

    def _verificar_alimentos_poblados(self, cursor):
        """Avisa si 'tabla_alimentos' está vacía.

        Antes este método (_poblar_alimentos_iniciales) intentaba insertar datos
        nutricionales por defecto, pero no existía en el código y además yo no
        tengo cifras nutricionales verificadas para tus 127 clases — inventarlas
        sería peor que dejarlo vacío. Por eso solo avisa; la carga real debe
        venir de cargar_alimentos_desde_csv() con una fuente verificada
        (ver discusión sobre USDA/ICBF).
        """
        try:
            cursor.execute("SELECT COUNT(*) FROM tabla_alimentos")
            (total,) = cursor.fetchone()
            if total == 0:
                print(
                    "tabla_alimentos está vacía. Ejecuta cargar_alimentos_desde_csv() "
                    "con tu fuente de datos nutricionales antes de usar /predecir en producción."
                )
        except csv.Error as e:
            print(f"No se pudo verificar tabla_alimentos: {e}")

    # ==== Exportar datos desde EXCEL/CSV ====
    def cargar_alimentos_desde_csv(self, texto_csv):
        """Carga los alimentos desde un CSV a la tabla maestra.
        Columnas esperadas: alimento_codigo, nombre_pantalla, calorias, es_saludable
        """
        if not self.conexion or not self.conexion.is_connected():
            return False, "Sin conexión a MySQL"
        cursor = self.conexion.cursor()
        try:
            stream = io.StringIO(texto_csv, newline=None)
            lector = csv.DictReader(stream)
            registros = []
            for fila in lector:
                codigo = fila.get('alimento_codigo', '').strip()
                nombre = fila.get('nombre_pantalla', '').strip()
                calorias = int(fila.get('calorias', 0) or 0)
                es_saludable = int(fila.get('es_saludable', 0) or 0)
                if codigo:
                    registros.append((codigo, nombre, calorias, es_saludable))
            if not registros:
                return False, "CSV vacío o sin encabezados correctos"
            sql = '''
                INSERT INTO tabla_alimentos (alimento_codigo, nombre_pantalla, calorias, es_saludable)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    nombre_pantalla = VALUES(nombre_pantalla),
                    calorias = VALUES(calorias),
                    es_saludable = VALUES(es_saludable)
            '''
            cursor.executemany(sql, registros)
            self.conexion.commit()
            return True, f"{len(registros)} registros insertados/actualizados en tabla_alimentos."
        except Exception as e:
            return False, f"Error al cargar alimentos desde CSV: {e}"
        finally:
            cursor.close()

    # ================= MÓDULO PERFIL =================
    def guardar_perfil(self, nombre, email, edad, genero, peso, altura):
        if not self.conexion or not self.conexion.is_connected():
            return False
        cursor = self.conexion.cursor()
        try:
            sql = '''
                REPLACE INTO perfil (id, nombre, email, edad, genero, peso, altura)
                VALUES (1, %s, %s, %s, %s, %s, %s)
            '''
            cursor.execute(sql, (nombre, email, edad, genero, peso, altura))
            self.conexion.commit()
            return True
        except mysql.connector.Error as e:
            print(f"Error al guardar perfil: {e}")
            return False
        finally:
            cursor.close()

    def obtener_perfil(self):
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute('SELECT * FROM perfil WHERE id = 1')
            return cursor.fetchone()
        except csv.Error as e:
            print(f"Error al obtener perfil: {e}")
            return None
        finally:
            cursor.close()

    # ================= MÓDULO HISTORIAL Y ALIMENTOS =================
    def registrar_comida(self, alimento_codigo, nombre_amigable, certeza, calorias, balanceado):
        """Inserta un registro de comida procesada por la IA.

        Antes esta función recibía 4 parámetros pero app.py la llamaba con 5
        argumentos en otro orden (guardaba el nombre bonito en la columna de
        certeza). Ahora recibe explícitamente el código técnico (para trazabilidad
        con tabla_alimentos) y el nombre amigable (lo que ve el usuario).
        """
        if not self.conexion or not self.conexion.is_connected():
            print("No hay conexión activa a MySQL.")
            return False
        cursor = self.conexion.cursor()
        try:
            sql = '''
                INSERT INTO historial_comida
                    (alimento_codigo, alimento_detectado, certeza_ia, calorias_aprox, balanceado)
                VALUES (%s, %s, %s, %s, %s)
            '''
            cursor.execute(sql, (alimento_codigo, nombre_amigable, certeza, calorias, balanceado))
            self.conexion.commit()
            return True
        except mysql.connector.Error as e:
            print(f"Error al insertar comida: {e}")
            return False
        finally:
            cursor.close()

    def obtener_historial_comida(self):
        if not self.conexion or not self.conexion.is_connected():
            return []
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute('SELECT * FROM historial_comida ORDER BY id DESC')
            return cursor.fetchall()
        except csv.Error as e:
            print(f"Error al obtener historial: {e}")
            return []
        finally:
            cursor.close()

    def obtener_informacion_alimento(self, codigo_alimento):
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            sql = "SELECT nombre_pantalla, calorias, es_saludable FROM tabla_alimentos WHERE alimento_codigo = %s"
            cursor.execute(sql, (codigo_alimento,))
            return cursor.fetchone()
        except mysql.connector.Error as e:
            print(f"Error al consultar tabla_alimentos: {e}")
            return None
        finally:
            cursor.close()

    # ================= MÓDULOS SALUD =================
    def registrar_hidratacion(self, cantidad_ml):
        if not self.conexion or not self.conexion.is_connected():
            return False
        cursor = self.conexion.cursor()
        try:
            cursor.execute("INSERT INTO hidratacion (cantidad_mL) VALUES (%s)", (cantidad_ml,))
            self.conexion.commit()
            return True
        except csv.Error as e:
            print(f"Error en hidratación: {e}")
            return False
        finally:
            cursor.close()


if __name__ == "__main__":
    print("Iniciando prueba de conexión a MySQL...")
    db = BaseDatos()
    if db.conexion and db.conexion.is_connected():
        print("Base de datos lista")
    else:
        print("Verifica que el servidor esté activo y que exista el archivo .env con MYSQL_PASSWORD")