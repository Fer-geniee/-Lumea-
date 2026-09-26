"""
grupos_confusion.py -- Alimentos que la IA no debe decidir sola.

Cuando la predicción ganadora del ensamble cae en uno de los
"disparadores" de un grupo, /predecir fuerza confirmación manual SIN
IMPORTAR la certeza reportada: una certeza alta en una predicción
propensa a confundirse no es la misma garantía que en una clase sin ese
problema conocido. El usuario elige entre las "opciones" y la app lo
guarda con POST /confirmar-alimento.

Vive en su propio archivo (antes estaba dentro de app.py) para que:
- verificar_integridad_clases.py pueda revisar que TODA opción tenga fila
  en tabla_alimentos sin arrancar Flask ni TensorFlow;
- agregar o cambiar un grupo no obligue a tocar app.py.

Cada opción es un dict:
- codigo: alimento_codigo real. SIEMPRE tiene fila en tabla_alimentos.
- nombre: texto corto para el botón.
- marca: marca comercial, o None si no aplica (platos, genéricos).
- grupo: subcategoría para que el frontend pueda ordenar o agrupar las
  opciones cuando son muchas (p. ej. "papas", "gaseosa").

Los códigos de agrupación visual ("sopas", "dulces"...) son solo
disparadores: nunca aparecen como opción ni tienen fila en
tabla_alimentos (agregarles nutrición sería inventar un dato para algo
que no es un plato o producto específico).
"""

GRUPOS_CONFUSION = [
    {
        "id": "sopas",
        # El modelo reentrenado (35 clases) fusiona los 3 platos en la clase
        # "sopas". Los 3 códigos viejos se mantienen como disparadores por si
        # se vuelve al modelo anterior (26 clases), que los predecía por
        # separado; el modelo actual ya no los predice.
        "disparadores": {"sopas", "ajiaco", "sancocho", "mondongo"},
        "mensaje": "Ajiaco, sancocho y mondongo se ven muy parecidos -- confirma cuál es.",
        "opciones": [
            {"codigo": "ajiaco", "nombre": "Ajiaco", "marca": None, "grupo": "sopa"},
            {"codigo": "sancocho", "nombre": "Sancocho", "marca": None, "grupo": "sopa"},
            {"codigo": "mondongo", "nombre": "Mondongo", "marca": None, "grupo": "sopa"},
        ],
    },
    {
        "id": "dulces",
        # dataset/dulces/ tiene 7 subcarpetas (una por producto), que Keras
        # combina en una sola clase de visión al entrenar.
        "disparadores": {"dulces"},
        "mensaje": "Hay varios dulces parecidos entre sí -- confirma cuál es.",
        "opciones": [
            {"codigo": "nucita", "nombre": "Nucita", "marca": "Nucita", "grupo": "dulce"},
            {"codigo": "barrilete", "nombre": "Barrilete", "marca": "Barrilete", "grupo": "dulce"},
            {"codigo": "quipitos", "nombre": "Quipitos", "marca": "Quipitos", "grupo": "dulce"},
            {"codigo": "chororamo", "nombre": "Chocoramo", "marca": "Chocoramo", "grupo": "dulce"},
            {"codigo": "supercoco", "nombre": "Super Coco", "marca": "Super Coco", "grupo": "dulce"},
            {"codigo": "bonbonbum", "nombre": "Bon Bon Bum", "marca": "Bon Bon Bum", "grupo": "dulce"},
            {"codigo": "chocolatinas", "nombre": "Chocolatina", "marca": None, "grupo": "dulce"},
        ],
    },
]


def grupo_para(alimento_codigo):
    """El grupo cuyo disparador es `alimento_codigo`, o None."""
    return next((g for g in GRUPOS_CONFUSION if alimento_codigo in g["disparadores"]), None)


def codigos_de_opciones(grupo):
    """Lista de códigos (el campo opciones_sugeridas de siempre)."""
    return [opcion["codigo"] for opcion in grupo["opciones"]]


def detalle_de_opciones(grupo):
    """Lista de {codigo, nombre, marca, grupo} (campo opciones_detalle)."""
    return [dict(opcion) for opcion in grupo["opciones"]]


def todos_los_codigos_de_opciones():
    """Todos los códigos que un usuario puede confirmar, de todos los grupos."""
    return {opcion["codigo"] for grupo in GRUPOS_CONFUSION for opcion in grupo["opciones"]}
