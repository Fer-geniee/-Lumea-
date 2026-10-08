"""
consejos.py -- El consejo que Lumea le da a la persona al reconocer un alimento.

Los TEXTOS están en consejos_config.py (los escribió y los aprobó Isabella);
aquí solo se decide cuál texto mostrar. Esto es lo único que hay que saber:

- datos/grupos_plato.csv dice, de cada alimento de tabla_alimentos, de qué
  `tipo` es (plato, fruta, bebida, paquete o postre) y qué grupos del plato
  contiene (cereales, frutas_verduras, lacteos, proteinas, grasas, azucares).
- consejo_para() arma la respuesta con esas dos cosas y los textos.

Lumea no califica el alimento: cuenta qué aporta, qué le falta al plato (solo
en las comidas principales) y, si tiene sellos de advertencia, un dato y una
idea. Ver CONTRATO_CONFIRMACION.md, sección "consejo".
"""

import csv
import os

import consejos_config as textos

RUTA_MAPA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "grupos_plato.csv")

# Los grupos que se revisan para "completar el plato", en este orden. Se
# ofrece el primero que le falte al plato.
ORDEN_PARA_COMPLETAR = ["frutas_verduras", "proteinas", "cereales"]


def _leer_mapa():
    """{alimento_codigo: {"tipo": "plato", "grupos": ["cereales", ...]}}"""
    mapa = {}
    with open(RUTA_MAPA, newline="", encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            grupos = [g for g in fila["grupos"].split(";") if g]
            mapa[fila["alimento_codigo"]] = {"tipo": fila["tipo"], "grupos": grupos}
    return mapa


# Se lee una sola vez, al importar el módulo.
MAPA = _leer_mapa()


def consejo_para(alimento_codigo, sellos):
    """El consejo del alimento, o None si no se puede dar.

    `sellos` es la lista de sellos de advertencia del alimento (la de
    sellos.obtener_sellos), [] si no tiene o None si no se sabe.

    Los códigos de agrupación visual que se confirman a mano ("sopas",
    "dulces") no tienen fila en el mapa a propósito: mientras la persona no
    confirme el alimento final no hay consejo (devuelve None).
    """
    datos = MAPA.get(alimento_codigo)
    if datos is None:
        return None

    grupos = datos["grupos"]
    propio = textos.ALIMENTOS.get(alimento_codigo, {})

    # Lo que aporta: el texto propio del alimento si lo hay; si no, el del
    # primer grupo. (Una aromática sin endulzar no tiene grupo: queda en None.)
    if "aporta" in propio:
        aporta = propio["aporta"]
    elif grupos:
        aporta = textos.GRUPOS[grupos[0]]["aporta"]
    else:
        aporta = None

    # Para completar: solo en los platos, el primer grupo que no tenga.
    para_completar = None
    if datos["tipo"] == "plato":
        for grupo in ORDEN_PARA_COMPLETAR:
            if grupo not in grupos:
                para_completar = textos.PARA_COMPLETAR[grupo]
                break

    # Una entrada por cada sello del alimento (los desconocidos se ignoran).
    lista_sellos = [
        {"sello": sello, "dato": textos.SELLOS[sello]["dato"], "idea": textos.SELLOS[sello]["idea"]}
        for sello in (sellos or [])
        if sello in textos.SELLOS
    ]

    return {
        "grupo": grupos[0] if grupos else None,
        "aporta": aporta,
        "para_completar": para_completar,
        "a_tener_en_cuenta": propio.get("a_tener_en_cuenta"),
        "sellos": lista_sellos,
    }
