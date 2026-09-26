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

Los códigos de agrupación visual puros ("sopas", "dulces") son solo
disparadores: nunca aparecen como opción ni tienen fila en
tabla_alimentos (agregarles nutrición sería inventar un dato para algo
que no es un plato o producto específico). Distinto es el caso de
"tamal", "frituras_empaquetadas" y "gaseosas_bebidas_azucaradas": son
disparadores Y a la vez la opción "otro" de su grupo, porque ya tenían
una fila genérica con nutrición de referencia.

Todas las opciones deben tener fila en tabla_alimentos:
"Pipelines de datos/verificar_integridad_clases.py" lo comprueba.
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
    # Los 3 grupos de abajo tienen nutrición POR PRODUCTO (fuentes, unidad y
    # sellos de cada opción en Backend/alimentos_confirmacion_fuentes.csv,
    # generado por "Pipelines de datos/importar_productos_confirmacion.py").
    # Cada uno termina con una opción "otro" que usa la fila genérica que ya
    # existía, para que el usuario nunca quede sin una opción válida. Son
    # "productos comunes", NO "los más consumidos": no hay un dato de mercado
    # citable que respalde un ranking.
    {
        "id": "tamal",
        "disparadores": {"tamal"},
        "mensaje": "Los tamales y los envueltos se ven muy parecidos -- confirma cuál es.",
        "opciones": [
            {"codigo": "tamal_tolimense", "nombre": "Tamal tolimense", "marca": None, "grupo": "tamal"},
            {"codigo": "envuelto_yuca", "nombre": "Envuelto de yuca", "marca": None, "grupo": "envuelto"},
            {"codigo": "envuelto_choclo_queso", "nombre": "Envuelto de choclo con queso", "marca": None, "grupo": "envuelto"},
            {"codigo": "tamal", "nombre": "Otro tipo de tamal", "marca": None, "grupo": "otro"},
        ],
    },
    {
        "id": "frituras_empaquetadas",
        "disparadores": {"frituras_empaquetadas"},
        "mensaje": "Hay muchos paquetes parecidos -- confirma cuál es.",
        "opciones": [
            {"codigo": "margarita_limon", "nombre": "Margarita limón", "marca": "Margarita", "grupo": "papas"},
            {"codigo": "margarita_mayonesa", "nombre": "Margarita mayonesa", "marca": "Margarita", "grupo": "papas"},
            {"codigo": "margarita_onduladas_tomate", "nombre": "Margarita onduladas de tomate", "marca": "Margarita", "grupo": "papas"},
            {"codigo": "yupis", "nombre": "Yupis", "marca": "Yupi", "grupo": "maíz"},
            {"codigo": "rizadas_limon", "nombre": "Rizadas limón", "marca": "Yupi", "grupo": "papas"},
            {"codigo": "rizadas_mayonesa", "nombre": "Rizadas mayonesa", "marca": "Yupi", "grupo": "papas"},
            {"codigo": "tosti_empanadas_limon", "nombre": "Tosti empanadas limón", "marca": "Yupi", "grupo": "maíz"},
            {"codigo": "doritos_pizza", "nombre": "Doritos pizza", "marca": "Doritos", "grupo": "maíz"},
            {"codigo": "doritos_bbq", "nombre": "Doritos BBQ", "marca": "Doritos", "grupo": "maíz"},
            {"codigo": "natuchips_platano", "nombre": "NatuChips plátano verde", "marca": "NatuChips", "grupo": "plátano"},
            {"codigo": "cheetos_boliqueso", "nombre": "Cheetos Boliqueso", "marca": "Cheetos", "grupo": "maíz"},
            {"codigo": "cheetos_trissitos", "nombre": "Cheetos Trissitos", "marca": "Cheetos", "grupo": "maíz"},
            {"codigo": "takis_intense_nacho", "nombre": "Takis Intense Nacho", "marca": "Takis", "grupo": "maíz"},
            {"codigo": "detodito_pollo_parrillero", "nombre": "De Todito pollo parrillero", "marca": "De Todito", "grupo": "mezcla"},
            {"codigo": "superricas_papas_pollo", "nombre": "Super Ricas papas pollo", "marca": "Super Ricas", "grupo": "papas"},
            {"codigo": "superricas_tajaditas_platano", "nombre": "Super Ricas tajaditas de plátano", "marca": "Super Ricas", "grupo": "plátano"},
            {"codigo": "frituras_empaquetadas", "nombre": "Otra marca", "marca": None, "grupo": "otro"},
        ],
    },
    {
        "id": "gaseosas_bebidas_azucaradas",
        "disparadores": {"gaseosas_bebidas_azucaradas"},
        "mensaje": "Muchas bebidas se ven parecidas -- confirma cuál es.",
        "opciones": [
            {"codigo": "cocacola_original", "nombre": "Coca-Cola Original", "marca": "Coca-Cola", "grupo": "gaseosa"},
            {"codigo": "pepsi", "nombre": "Pepsi", "marca": "Pepsi", "grupo": "gaseosa"},
            {"codigo": "colombiana", "nombre": "Colombiana", "marca": "Postobón", "grupo": "gaseosa"},
            {"codigo": "postobon_manzana", "nombre": "Manzana Postobón", "marca": "Postobón", "grupo": "gaseosa"},
            {"codigo": "mr_tea", "nombre": "Mr. Tea", "marca": "Postobón", "grupo": "té frío"},
            {"codigo": "speed_max", "nombre": "Speed Max", "marca": "Postobón", "grupo": "energizante"},
            {"codigo": "vive100", "nombre": "Vive100", "marca": "Vive 100", "grupo": "energizante"},
            {"codigo": "del_valle_fresh_citricas", "nombre": "Del Valle Fresh cítricas", "marca": "Del Valle", "grupo": "jugo"},
            {"codigo": "gaseosas_bebidas_azucaradas", "nombre": "Otra bebida", "marca": None, "grupo": "otro"},
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
