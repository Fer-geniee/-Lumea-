"""
cargar_datos_curiosos.py -- carga la columna dato_curioso de tabla_alimentos
desde datos/datos_curiosos.csv (alimento_codigo, dato_curioso).

    python3 herramientas/cargar_datos_curiosos.py              # carga
    python3 herramientas/cargar_datos_curiosos.py --comprobar  # solo compara, no escribe
    python3 herramientas/cargar_datos_curiosos.py otro.csv     # otro archivo

Solo hace UPDATE sobre alimentos que ya existen en tabla_alimentos (nunca crea
filas) y es idempotente: correrlo dos veces deja el mismo resultado. Las líneas
que empiezan por '#' (el encabezado honesto: contenido generado con IA, revisado
por Isabella, sin verificación individual contra una fuente científica) se ignoran.
Antes hay que cargar la tabla de alimentos (ver README.md). No crea tablas ni
migra el esquema: usa conectar_mysql(), no BaseDatos().
"""
import os as _os, sys as _sys  # para importar los módulos de Backend/
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import csv

from database import conectar_mysql

RUTA_POR_DEFECTO = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "datos", "datos_curiosos.csv")


def leer_filas(ruta_csv):
    with open(ruta_csv, encoding="utf-8") as f:
        lineas = [linea for linea in f if not linea.lstrip('"').startswith("#")]
    return [(f["alimento_codigo"].strip(), f["dato_curioso"].strip())
            for f in csv.DictReader(lineas) if (f.get("alimento_codigo") or "").strip() and (f.get("dato_curioso") or "").strip()]


def main():
    args = [a for a in _sys.argv[1:] if not a.startswith("--")]
    solo_comprobar = "--comprobar" in _sys.argv
    filas = leer_filas(args[0] if args else RUTA_POR_DEFECTO)

    conexion = conectar_mysql()
    if conexion is None:
        raise SystemExit("MySQL no está disponible: enciéndelo y vuelve a correr.")
    cursor = conexion.cursor()
    cursor.execute("USE lumea_db")
    cargadas, distintas, desconocidas = 0, 0, []
    for codigo, dato in filas:
        cursor.execute("SELECT dato_curioso FROM tabla_alimentos WHERE alimento_codigo = %s", (codigo,))
        actual = cursor.fetchone()
        if actual is None:
            desconocidas.append(codigo)
            continue
        if (actual[0] or "").strip() != dato:
            distintas += 1
            if not solo_comprobar:
                cursor.execute("UPDATE tabla_alimentos SET dato_curioso = %s WHERE alimento_codigo = %s", (dato, codigo))
        cargadas += 1
    conexion.commit()
    cursor.close()
    conexion.close()

    if solo_comprobar:
        print(f"{cargadas} filas del CSV existen en tabla_alimentos; {distintas} difieren de lo que hay en MySQL.")
    else:
        print(f"{cargadas} datos curiosos revisados; {distintas} actualizados en tabla_alimentos.")
    if desconocidas:
        print(f"Códigos que NO existen en tabla_alimentos (ignorados): {desconocidas}")


if __name__ == "__main__":
    main()
