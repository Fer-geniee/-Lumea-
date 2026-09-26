"""
sellos.py -- Sellos de advertencia (Res. 810 de 2021 / 2492 de 2022) de
cada alimento, para /predecir y /confirmar-alimento.

La columna tabla_alimentos.sellos_advertencia la crea y la llena
"Pipelines de datos/cargar_sellos.py" a partir de lo que ya calcularon
los importadores (criterio_saludable.py): texto con los códigos separados
por coma, '' si no se activa ninguno, NULL si no se ha calculado.

Aquí solo se lee. Si la columna todavía no existe (base recién creada y
cargar_sellos.py sin correr) o el alimento no tiene fila, se devuelve
None: "no se sabe", que el frontend debe mostrar distinto de "sin sellos".

Ver CONTRATO_CONFIRMACION.md, sección "sellos_advertencia", para cómo
debe mostrarlos el frontend (nunca como "saludable").
"""

# Códigos posibles, en el orden en que los calcula criterio_saludable.py.
SELLOS_VALIDOS = ("sodio", "azucares", "grasas_saturadas", "grasas_trans", "edulcorantes")


def lista_de_sellos(texto):
    """'sodio,grasas_saturadas' -> ['sodio', 'grasas_saturadas']; '' -> [];
    None -> None."""
    if texto is None:
        return None
    return [s for s in (parte.strip() for parte in texto.split(",")) if s]


def obtener_sellos(db, alimento_codigo):
    """Lista de sellos del alimento, [] si no tiene ninguno, o None si no se
    sabe. Nunca lanza: un error aquí no debe impedir registrar la comida."""
    conexion = getattr(db, "conexion", None)
    if not conexion or not conexion.is_connected():
        return None
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT sellos_advertencia FROM tabla_alimentos WHERE alimento_codigo = %s", (alimento_codigo,))
        fila = cursor.fetchone()
        return lista_de_sellos(fila[0]) if fila else None
    except Exception as e:  # p. ej. la columna aún no existe
        print(f"No se pudieron leer los sellos de {alimento_codigo}: {e}")
        return None
    finally:
        cursor.close()
