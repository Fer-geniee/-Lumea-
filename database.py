import os
import io
import csv
from datetime import date, timedelta
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import bcrypt  # Para hashing de contraseñas


# Carga las variables definidas en el archivo .env (mismo directorio que este script)
load_dotenv()


def conectar_mysql():
    """Establece la conexión inicial con el servidor MySQL.

    La contraseña NUNCA debe quedar escrita en el código fuente. Se lee desde
    una variable de entorno (archivo .env) que no se sube al repositorio.
    """
    password = os.getenv("MYSQL_PASSWORD", "")
    host = os.getenv("MYSQL_HOST", "127.0.0.1")  # Cambiar en .env el día de la sustentación
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")

    try:
        conexion = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",  # Necesario para nombres/columnas con tildes y eñes (p. ej. 'sueño')
        )
        if conexion.is_connected():
            return conexion
    except Error as e:
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
                    altura INT, 
                    password_hash CHAR(60) NULL,  -- hash de contraseña (bcrypt); NULL = perfil de antes de las contraseñas
                    objetivo VARCHAR(50)  -- metas de HÁBITO 
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
            # cada máquina el día de la presentación.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sueno (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATE DEFAULT (CURRENT_DATE),
                    horas_sueno FLOAT,
                    calidad_sueno VARCHAR(255)
                )
            ''')

            # 5. TABLA DE ACTIVIDAD FÍSICA # REVISIÓN: NO SE HA IMPLEMENTADO HASTA AHORA, PERO SE DEJA PORQUE ES PARTE DEL MVP. ADEMÁS, QUEDA COMO POSIBLE MEJORA
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

            # 7. TABLA DE ESTADO DE ÁNIMO (check-in diario, separado del perfil
            # porque cambia todo el tiempo -- el perfil se llena una sola vez)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS estado_animo (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    estado VARCHAR(20)
                )
            ''')

            # 8. TABLA DE PUNTOS Y RACHA (infraestructura de gamificación)
            # Diseño deliberadamente simple: solo el estado acumulado de cada
            # usuario. Cuántos puntos vale cada acción, niveles, insignias,
            # etc. NO están definidos todavía -- eso lo diseña el equipo
            # (ver registrar_actividad_puntos_racha, que por ahora suma
            # siempre 1 punto fijo). usuario_id es PRIMARY KEY porque cada
            # usuario tiene un único estado de puntos/racha, no un historial.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS puntos_racha (
                    usuario_id INT PRIMARY KEY,
                    puntos_totales INT DEFAULT 0,
                    racha_actual_dias INT DEFAULT 0,
                    ultima_fecha_actividad DATE
                )
            ''')

            self.conexion.commit()
            print("Estructura de tablas verificada en MySQL (lumea_db).")
            self._verificar_alimentos_poblados(cursor)
            self._asegurar_columna(cursor, "historial_comida", "alimento_codigo", "alimento_codigo VARCHAR(100) AFTER fecha")
            self._asegurar_columna(cursor, "perfil", "objetivo", "objetivo VARCHAR(50)")
            self._asegurar_columna(cursor, "tabla_alimentos", "dato_curioso", "dato_curioso TEXT")
            # Perfiles múltiples identificados por correo (ver DEFENSA_TECNICA_LUMEA.md
            # sección 5): cada fila de historial_comida/estado_animo queda ligada al
            # usuario que la generó.
            self._asegurar_columna(cursor, "historial_comida", "usuario_id", "usuario_id INT AFTER id")
            self._asegurar_columna(cursor, "estado_animo", "usuario_id", "usuario_id INT AFTER id")
            self._asegurar_indice_unico(cursor, "perfil", "email", "uq_perfil_email")
            # password_hash permite NULL: los perfiles creados antes de las
            # contraseñas no tienen hash (y no pueden iniciar sesión hasta crear
            # una). Con NOT NULL, MySQL no dejaba crear ni editar perfiles.
            self._asegurar_columna(cursor, "perfil", "password_hash", "password_hash CHAR(60) NULL AFTER objetivo")
            self._permitir_null_en_password_hash(cursor)
            self._permitir_null_en_peso_y_altura(cursor)
            # Aviso al acudiente (9 oct): casilla y fecha en que se marcó.
            self._asegurar_columna(cursor, "perfil", "acudiente_sabe", "acudiente_sabe TINYINT(1) NULL")
            self._asegurar_columna(cursor, "perfil", "acudiente_fecha", "acudiente_fecha DATETIME NULL")
            self.conexion.commit()

        except Error as e:
            print(f"Error al crear tablas en MySQL: {e}")
        finally:
            cursor.close()

    def _asegurar_columna(self, cursor, tabla, columna, definicion_sql):
        """Agrega una columna a una tabla existente si todavía no la tiene.

        CREATE TABLE IF NOT EXISTS NO modifica una tabla que ya existía --
        por eso los cambios de esquema (columnas nuevas) necesitan este paso
        aparte, revisando primero si la columna ya está antes de agregarla.
        """
        cursor.execute(
            """
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'lumea_db' AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """,
            (tabla, columna),
        )
        (existe,) = cursor.fetchone()
        if not existe:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {definicion_sql}")
            print(f"Columna agregada: {tabla}.{columna}")

    def _permitir_null_en_peso_y_altura(self, cursor):
        """peso y altura ya no se piden: si alguna base los creó NOT NULL,
        se cambian para aceptar NULL (idempotente; no borra las columnas)."""
        for columna, tipo in (("peso", "FLOAT"), ("altura", "INT")):
            cursor.execute(
                """
                SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'lumea_db' AND TABLE_NAME = 'perfil' AND COLUMN_NAME = %s
                """,
                (columna,),
            )
            fila = cursor.fetchone()
            if fila and fila[0] == "NO":
                cursor.execute(f"ALTER TABLE perfil MODIFY COLUMN {columna} {tipo} NULL")
                print(f"Columna reparada: perfil.{columna} ahora permite NULL")

    def _permitir_null_en_password_hash(self, cursor):
        """Repara las bases donde password_hash quedó como NOT NULL (la primera
        versión del login la creaba así). MySQL les puso '' a los perfiles que
        ya existían; '' no es un hash, así que se cambia por NULL."""
        cursor.execute(
            """
            SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'lumea_db' AND TABLE_NAME = 'perfil' AND COLUMN_NAME = 'password_hash'
            """
        )
        fila = cursor.fetchone()
        if fila and fila[0] == "NO":
            cursor.execute("ALTER TABLE perfil MODIFY COLUMN password_hash CHAR(60) NULL")
            print("Columna reparada: perfil.password_hash ahora permite NULL")
        cursor.execute("UPDATE perfil SET password_hash = NULL WHERE password_hash = ''")

    def _asegurar_indice_unico(self, cursor, tabla, columna, nombre_indice):
        """Agrega un índice UNIQUE a una tabla existente si todavía no lo tiene.

        Mismo motivo que _asegurar_columna: no hay forma de expresar "UNIQUE
        si no existe" dentro de CREATE TABLE IF NOT EXISTS para una tabla que
        ya estaba creada de una versión anterior sin esa restricción.
        """
        cursor.execute(
            """
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = 'lumea_db' AND TABLE_NAME = %s AND INDEX_NAME = %s
            """,
            (tabla, nombre_indice),
        )
        (existe,) = cursor.fetchone()
        if not existe:
            cursor.execute(f"ALTER TABLE {tabla} ADD UNIQUE KEY {nombre_indice} ({columna})")
            print(f"Índice único agregado: {tabla}.{columna}")

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
        except Error as e:
            print(f"No se pudo verificar tabla_alimentos: {e}")

    # ==== Exportar datos desde EXCEL/CSV ==== _> Metodo que se va a ELIMINAR porque es innecesario 
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
    # Valores válidos para 'objetivo': metas de HÁBITO, deliberadamente NO de
    # peso corporal (audiencia adolescente). Ver DEFENSA_TECNICA_LUMEA.md sección 5.
    # Son los mismos 'value' que envía crear-cuenta.html. Lumea no promete agua,
    # sueño ni ejercicio (no los mide), así que esos objetivos salieron el 9 oct.
    # Un perfil viejo con otro objetivo se sigue LEYENDO sin error: solo se valida
    # al guardar.
    OBJETIVOS_VALIDOS = {"comer_balanceado", "conocer_lo_que_como"}

    def guardar_perfil(self, nombre, email, edad, genero, objetivo=None, contraseña=None, acudiente_sabe=False):
        """Crea el perfil si el correo es nuevo, o actualiza el existente si ya
        existe -- 'email' es el identificador único de cada usuario (ver
        DEFENSA_TECNICA_LUMEA.md sección 5: perfiles múltiples con contraseña.
        Ya no hay un único perfil fijo en id=1.

        La contraseña llega ya validada desde app.py (largo mínimo y máximo).
        El hash solo se guarda si el perfil todavía no tenía uno: POST /perfil
        no puede CAMBIAR una contraseña, porque identifica a la persona solo
        por el correo y cualquiera podría reemplazar la de otro.

        Peso y altura ya no se piden (9 oct): las columnas siguen en la tabla
        por los perfiles viejos, pero aquí se guardan siempre como NULL, así
        que volver a guardar un perfil viejo también borra esos datos.

        acudiente_sabe: la persona marcó que su madre, padre o acudiente sabe
        que usa Lumea. Es un aviso, no una autorización verificada. La fecha
        se anota solo la primera vez que se marca; una edición posterior sin
        la casilla no la borra."""
        if not self.conexion or not self.conexion.is_connected():
            return False
        if objetivo is not None and objetivo not in self.OBJETIVOS_VALIDOS:
            print(f"Objetivo no reconocido: '{objetivo}'. Válidos: {self.OBJETIVOS_VALIDOS}")
            return False
        cursor = self.conexion.cursor()
        try:
            hash_contraseña = None
            if contraseña: 
                salt = bcrypt.gensalt()
                hash_contraseña = bcrypt.hashpw(contraseña.encode('utf-8'), salt).decode('utf-8')
            sql = '''
                INSERT INTO perfil (nombre, email, edad, genero, peso, altura, objetivo, password_hash,
                                    acudiente_sabe, acudiente_fecha)
                VALUES (%s, %s, %s, %s, NULL, NULL, %s, %s, %s, IF(%s, NOW(), NULL))
                ON DUPLICATE KEY UPDATE
                    nombre = VALUES(nombre), edad = VALUES(edad), genero = VALUES(genero),
                    peso = NULL, altura = NULL, objetivo = VALUES(objetivo), 
                    acudiente_fecha = IF(%s AND acudiente_fecha IS NULL, NOW(), acudiente_fecha),
                    acudiente_sabe = IF(%s, 1, acudiente_sabe),
                    password_hash = IFNULL(password_hash, VALUES(password_hash))  -- si ya tenía hash, se conserva; solo se pone si no tenía
            '''
            sabe = 1 if acudiente_sabe else 0
            cursor.execute(sql, (nombre, email, edad, genero, objetivo, hash_contraseña, sabe, sabe, sabe, sabe))
            self.conexion.commit()
            return True
        except Error as e:
            print(f"Error al guardar perfil: {e}")
            return False
        finally:
            cursor.close()

    def obtener_perfil_por_email(self, email):
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute('SELECT * FROM perfil WHERE email = %s', (email,))
            perfil = cursor.fetchone()
            if perfil:
                # No enviar el hash al cliente, ni peso y altura (Lumea ya no
                # los pide; los perfiles viejos aún pueden tenerlos guardados).
                for campo in ("password_hash", "peso", "altura"):
                    perfil.pop(campo, None)
            return perfil

        except Error as e:
            print(f"Error al obtener perfil: {e}")
            return None
        finally:
            cursor.close()

    def verificar_contraseña(self, email, contraseña):
        """Verifica si la contraseña proporcionada coincide con el hash almacenado."""
        if not self.conexion or not self.conexion.is_connected():
            return False
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute('SELECT password_hash FROM perfil WHERE email = %s', (email,))
            fila = cursor.fetchone()
            if fila is None or not fila['password_hash']:
                return False  # Usuario no encontrado, o perfil viejo sin contraseña (NULL o '')
            password_hash = fila['password_hash']

            return bcrypt.checkpw(contraseña.encode('utf-8'), password_hash.encode('utf-8'))
        except ValueError:
            # bcrypt lanza ValueError (no un Error de MySQL) si lo guardado no
            # es un hash válido. Para el login eso es "no coincide".
            return False
        except Error as e:
            print(f"Error al verificar contraseña: {e}")
            return False
        finally:
            cursor.close()


    def estado_contraseña(self, email):
        """Para POST /perfil: None si el correo no tiene perfil, True si el
        perfil ya tiene contraseña, False si es un perfil viejo sin ella."""
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute('SELECT password_hash FROM perfil WHERE email = %s', (email,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            return bool(fila['password_hash'])
        except Error as e:
            print(f"Error al consultar la contraseña del perfil: {e}")
            return None
        finally:
            cursor.close()

    def obtener_datos_login(self, email):
        """Método para obtener los datos de inicio de sesión del usuario de manera segura, sin exponer el hash de la contraseña."""
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute('SELECT id, nombre, email, objetivo FROM perfil WHERE email = %s', (email,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error al obtener datos de login: {e}")
            return None
        finally:
            cursor.close()  
    # ================= MÓDULO HISTORIAL Y ALIMENTOS =================
    def registrar_comida(self, alimento_codigo, nombre_amigable, certeza, calorias, balanceado, usuario_id=None):
        """Inserta un registro de comida procesada por la IA.

        `usuario_id=None` cuando la predicción se hace sin sesión iniciada
        (no se pudo resolver el correo a un perfil existente) -- el registro
        igual se guarda, solo que no aparece en el historial filtrado de nadie
        hasta que ese perfil exista.

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
                    (usuario_id, alimento_codigo, alimento_detectado, certeza_ia, calorias_aprox, balanceado)
                VALUES (%s, %s, %s, %s, %s, %s)
            '''
            cursor.execute(sql, (usuario_id, alimento_codigo, nombre_amigable, certeza, calorias, balanceado))
            self.conexion.commit()
            return True
        except Error as e:
            print(f"Error al insertar comida: {e}")
            return False
        finally:
            cursor.close()

    def obtener_historial_comida(self, usuario_id):
        if not self.conexion or not self.conexion.is_connected():
            return []
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute(
                'SELECT * FROM historial_comida WHERE usuario_id = %s ORDER BY id DESC',
                (usuario_id,),
            )
            return cursor.fetchall()
        except Error as e:
            print(f"Error al obtener historial: {e}")
            return []
        finally:
            cursor.close()

    def obtener_datos_curiosos(self):
        """Los alimentos que tienen dato curioso (para GET /dato-del-dia).
        None si no hay conexión o MySQL falla (la ruta responde 503); una
        lista vacía si la conexión funciona pero no hay ningún dato."""
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT alimento_codigo, nombre_pantalla, dato_curioso FROM tabla_alimentos "
                "WHERE dato_curioso IS NOT NULL AND TRIM(dato_curioso) <> ''"
            )
            return cursor.fetchall()
        except Error as e:
            print(f"Error al leer los datos curiosos: {e}")
            return None
        finally:
            cursor.close()
            self.conexion.commit()  # app.py usa UNA conexión: cerrar la transacción de lectura

    def obtener_informacion_alimento(self, codigo_alimento):
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            sql = "SELECT nombre_pantalla, calorias, es_saludable, dato_curioso FROM tabla_alimentos WHERE alimento_codigo = %s"
            cursor.execute(sql, (codigo_alimento,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error al consultar tabla_alimentos: {e}")
            return None
        finally:
            cursor.close()

    # ================= MÓDULO ESTADO DE ÁNIMO =================
    # Escala de 5 (no texto libre): más rápido de responder en celular, y
    # estándar en psicología (tipo Likert). Ver DEFENSA_TECNICA_LUMEA.md.
    ESTADOS_VALIDOS = {"muy_mal", "mal", "neutral", "bien", "muy_bien"}

    def registrar_estado_animo(self, estado, usuario_id):
        if estado not in self.ESTADOS_VALIDOS:
            print(f"Estado no reconocido: '{estado}'. Válidos: {self.ESTADOS_VALIDOS}")
            return False
        if not self.conexion or not self.conexion.is_connected():
            return False
        cursor = self.conexion.cursor()
        try:
            cursor.execute(
                "INSERT INTO estado_animo (usuario_id, estado) VALUES (%s, %s)",
                (usuario_id, estado),
            )
            self.conexion.commit()
            return True
        except Error as e:
            print(f"Error al registrar estado de ánimo: {e}")
            return False
        finally:
            cursor.close()

    def obtener_estado_animo_reciente(self, usuario_id, limite=30, dias=None):
        """Últimos `limite` registros de ánimo. Con `dias` (p. ej. 7) solo los
        de los últimos `dias` días, contando hoy: así la pantalla de Progreso
        recibe la semana completa aunque haya más de `limite` registros."""
        if not self.conexion or not self.conexion.is_connected():
            return []
        cursor = self.conexion.cursor(dictionary=True)
        try:
            filtro_dias = " AND fecha >= CURDATE() - INTERVAL %s DAY" if dias else ""
            parametros = (usuario_id, dias - 1, limite) if dias else (usuario_id, limite)
            cursor.execute(
                "SELECT id, fecha, estado FROM estado_animo WHERE usuario_id = %s" + filtro_dias
                + " ORDER BY id DESC LIMIT %s",
                parametros,
            )
            return cursor.fetchall()
        except Error as e:
            print(f"Error al obtener estado de ánimo: {e}")
            return []
        finally:
            cursor.close()

    # ================= MÓDULO PUNTOS Y RACHA (gamificación) =================
    # Infraestructura mínima a propósito: solo sumar puntos y llevar la
    # racha de días consecutivos. Cuántos puntos vale cada acción, niveles,
    # insignias, multiplicadores, etc. quedan pendientes del diseño de
    # gamificación del equipo -- no se inventan aquí.
    def obtener_puntos_racha(self, usuario_id):
        """Devuelve el estado de puntos/racha de un usuario, o None si
        todavía no tiene ninguna actividad registrada (usuario nuevo)."""
        if not self.conexion or not self.conexion.is_connected():
            return None
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT puntos_totales, racha_actual_dias, ultima_fecha_actividad "
                "FROM puntos_racha WHERE usuario_id = %s",
                (usuario_id,),
            )
            return cursor.fetchone()
        except Error as e:
            print(f"Error al consultar puntos/racha: {e}")
            return None
        finally:
            cursor.close()

    def registrar_actividad_puntos_racha(self, usuario_id):
        """Suma 1 punto fijo y actualiza la racha de días consecutivos.

        Se llama desde /predecir y /confirmar-alimento cuando guardan un
        registro de comida exitosamente, y solo si hay usuario_id (no tiene
        sentido acumular puntos para una predicción sin dueño). Lógica de
        racha mínima: si la última actividad fue HOY, la racha no cambia
        (ya contaba); si fue AYER, se extiende +1 día; en cualquier otro
        caso (más de un día de hueco, o primera vez) arranca/reinicia en 1.
        """
        if usuario_id is None:
            return False
        if not self.conexion or not self.conexion.is_connected():
            return False
        cursor = self.conexion.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT racha_actual_dias, ultima_fecha_actividad FROM puntos_racha WHERE usuario_id = %s",
                (usuario_id,),
            )
            fila = cursor.fetchone()

            hoy = date.today()
            if fila is None:
                nueva_racha = 1
            elif fila["ultima_fecha_actividad"] == hoy:
                nueva_racha = fila["racha_actual_dias"]
            elif fila["ultima_fecha_actividad"] == hoy - timedelta(days=1):
                nueva_racha = fila["racha_actual_dias"] + 1
            else:
                nueva_racha = 1

            cursor.execute(
                '''
                INSERT INTO puntos_racha (usuario_id, puntos_totales, racha_actual_dias, ultima_fecha_actividad)
                VALUES (%s, 1, %s, %s)
                ON DUPLICATE KEY UPDATE
                    puntos_totales = puntos_totales + 1,
                    racha_actual_dias = VALUES(racha_actual_dias),
                    ultima_fecha_actividad = VALUES(ultima_fecha_actividad)
                ''',
                (usuario_id, nueva_racha, hoy),
            )
            self.conexion.commit()
            return True
        except Error as e:
            print(f"Error al registrar puntos/racha: {e}")
            return False
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
        except Error as e:
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