"""
consejos_config.py -- Lo que Lumea le cuenta a la persona después de reconocer un alimento.

Autoría: BORRADOR de Claude (8 oct 2026), escrito con las fuentes de abajo.
Isabella lo revisa, lo corrige y lo aprueba antes de cargarlo. Nada de este
archivo se muestra en la app hasta que ella haga su commit.

Fundamento
----------
Lumea no califica alimentos sueltos: ayuda a completar el plato. Seguimos
las Guías Alimentarias Basadas en Alimentos para la población colombiana
mayor de 2 años (GABA, ICBF), que describen un plato saludable con seis
grupos. Por eso los consejos son de tres tipos:
  1. qué aporta el grupo del alimento (o el alimento, si es de la demo);
  2. qué le falta al plato para estar completo (solo en comidas principales);
  3. si el alimento tiene sellos de advertencia (Resolución 810 de 2021,
     modificada por la 2492 de 2022): un dato y una idea, sin regaños.

Reglas de estilo (las mismas de MARCA.md y de la defensa técnica)
------------------------------------------------------------------
- Una o dos frases, en segunda persona, en tono amable.
- Nunca "bueno", "malo", "evita", "prohibido" ni "saludable/no saludable"
  como juicio sobre la persona o la comida.
- Sin emojis.
- Toda cifra lleva su fuente en el comentario de al lado.
- Nada de peso, cuerpo ni calorías "quemadas".

Fuentes
-------
[GABA]  ICBF. Guías Alimentarias Basadas en Alimentos para la población
        colombiana mayor de 2 años. https://www.icbf.gov.co/taxonomy/term/7154
[OMS]   Organización Mundial de la Salud. Healthy diet (nota descriptiva).
        https://www.who.int/news-room/fact-sheets/detail/healthy-diet
        (consultada el 8 oct 2026)
[TCAC]  ICBF. Tabla de Composición de Alimentos Colombianos, 2018.
        Los valores por alimento están en Backend/datos/alimentos_*_fuentes.csv.
[USDA]  USDA FoodData Central (el código de cada alimento está en el mismo
        CSV de fuentes).
[R810]  Ministerio de Salud. Resolución 810 de 2021 (etiquetado frontal),
        modificada por la Resolución 2492 de 2022.
"""

# =========================================================================
# 1. Los seis grupos del plato (GABA) y lo que aporta cada uno
# =========================================================================
# Los ids no se cambian: el mapa alimento -> grupo (datos/grupos_plato.csv)
# los usa.
GRUPOS = {
    "cereales": {
        "nombre": "Cereales, raíces, tubérculos y plátanos",
        # [GABA]; la OMS pide que los carbohidratos vengan sobre todo de
        # granos integrales, verduras, frutas y leguminosas [OMS].
        "aporta": "Es la principal fuente de energía del plato: sus carbohidratos son el combustible "
                  "que usan tu cerebro y tus músculos. Las versiones integrales suman fibra.",
    },
    "frutas_verduras": {
        "nombre": "Frutas y verduras",
        # 400 g al día desde los 10 años [OMS]; en todas las comidas [GABA].
        "aporta": "Aportan vitaminas, minerales, fibra y agua. La OMS recomienda al menos 400 g de "
                  "frutas y verduras al día a partir de los 10 años.",
    },
    "lacteos": {
        "nombre": "Leche y productos lácteos",
        # [GABA]
        "aporta": "Aportan proteína y calcio, el mineral que tu cuerpo usa para formar huesos y dientes.",
    },
    "proteinas": {
        "nombre": "Carnes, huevos, leguminosas secas, frutos secos y semillas",
        # Leguminosas al menos dos veces por semana [GABA].
        "aporta": "Aportan proteína para construir y reparar tus tejidos, y hierro, que ayuda a llevar "
                  "oxígeno por la sangre. El fríjol, la lenteja y el garbanzo también son de este grupo.",
    },
    "grasas": {
        "nombre": "Grasas",
        # Preferir aguacate, maní y nueces [GABA].
        "aporta": "Dan energía y ayudan a absorber las vitaminas A, D, E y K. Las Guías del ICBF "
                  "proponen preferir las del aguacate, el maní y las nueces.",
    },
    "azucares": {
        "nombre": "Azúcares",
        # Azúcares libres < 10 % de la energía, idealmente < 5 % [OMS].
        "aporta": "Dan energía rápida, pero casi nada más. La OMS recomienda que los azúcares libres "
                  "sean menos del 10 % de la energía del día, e idealmente menos del 5 %.",
    },
}

# =========================================================================
# 2. Para completar el plato (solo en comidas principales)
# =========================================================================
# Se muestra el primero que falte, en este orden. Nunca en bebidas, frutas
# sueltas ni productos de paquete: ahí no se arma un plato.
PARA_COMPLETAR = {
    # "en todas las comidas" [GABA]
    "frutas_verduras": "Súmale una fruta o una verdura: las Guías del ICBF "
                       "las recomiendan en todas las comidas.",
    "proteinas": "Súmale una proteína: huevo, fríjol, lenteja, pollo o pescado.",
    "cereales": "Súmale algo que dé energía: arroz, arepa, papa, yuca o plátano.",
}

# =========================================================================
# 3. Sellos de advertencia: un dato y una idea
# =========================================================================
# Mismas claves que SELLOS_VALIDOS de cargar_sellos.py.
SELLOS = {
    "sodio": {
        # < 5 g de sal = 2 g de sodio al día en adultos [OMS]; reducir sal,
        # embutidos, enlatados y productos de paquete [GABA].
        "dato": "Tiene sodio alto para su porción. La OMS recomienda menos de 2 g de sodio al día "
                "(unos 5 g de sal) en adultos.",
        "idea": "Si hoy lo comes, acompáñalo con agua y con frutas o verduras frescas, sin agregarle más sal.",
    },
    "azucares": {
        # 10 % de 2.000 kcal = 200 kcal = 50 g de azúcar [OMS].
        "dato": "Tiene azúcar añadida alta. La OMS sugiere que los azúcares libres sean menos del 10 % "
                "de la energía del día: unos 50 g para alguien que come 2.000 kcal.",
        "idea": "Si otro día quieres algo dulce, una fruta entera trae su propio azúcar junto con fibra y agua.",
    },
    "grasas_saturadas": {
        # < 10 % de la energía [OMS]; preferir aguacate, maní y nueces [GABA].
        "dato": "Tiene grasas saturadas altas. La OMS recomienda que no pasen del 10 % de la energía del día.",
        "idea": "Las Guías del ICBF proponen preferir grasas como las del aguacate, el maní o las nueces.",
    },
    "grasas_trans": {
        # < 1 % de la energía [OMS].
        "dato": "Contiene grasas trans. La OMS recomienda que no pasen del 1 % de la energía del día.",
        "idea": "En la tabla nutricional del empaque puedes ver cuántos gramos trae.",
    },
    "edulcorantes": {
        # Leyenda de edulcorantes en el etiquetado frontal [R810].
        "dato": "Contiene edulcorantes. En Colombia el empaque debe advertirlo, y no se recomienda para niños.",
        "idea": "Si quieres algo para tomar, el agua con fruta picada es otra opción.",
    },
}

# =========================================================================
# 4. Alimentos de la demo: lo que aporta y algo a tener en cuenta
# =========================================================================
# Reemplazan el texto del grupo para estos alimentos. Las cifras salen de
# Backend/datos/alimentos_*_fuentes.csv (TCAC 2018 o USDA), por 100 g.
ALIMENTOS = {
    # [USDA] Banana, raw: 97 kcal; azúcares naturales de fruta cruda.
    "banano": {
        "aporta": "Trae carbohidratos que dan energía y potasio, un mineral que usan tus músculos y nervios.",
        "a_tener_en_cuenta": "Sus azúcares son naturales y vienen con fibra. Maduro es más dulce porque "
                             "su almidón se convierte en azúcar.",
    },
    # [USDA] Apple, raw: 61 kcal.
    "manzana": {
        "aporta": "Aporta fibra y agua; buena parte de la fibra está en la cáscara.",
        "a_tener_en_cuenta": "Entera te llena más que en jugo, porque conserva la fibra.",
    },
    # [USDA] Mango, raw: 60 kcal.
    "mango": {
        "aporta": "Aporta vitamina C y betacaroteno, que tu cuerpo convierte en vitamina A.",
        "a_tener_en_cuenta": "Sus azúcares son naturales; entero o en trozos conserva la fibra.",
    },
    # [USDA] Strawberries, raw: 36 kcal.
    "fresa": {
        "aporta": "Es de las frutas con más vitamina C por porción.",
        "a_tener_en_cuenta": "Tiene mucha agua y pocas calorías: 36 kcal por cada 100 g.",
    },
    # [TCAC] A004, arepa paisa sin relleno: 163 kcal, 188 mg de sodio.
    "arepa": {
        "aporta": "Es del grupo que da energía: su maíz aporta carbohidratos.",
        "a_tener_en_cuenta": "Lleva sal: 188 mg de sodio por cada 100 g, según la Tabla de Composición "
                             "de Alimentos Colombianos. Con una proteína y una verdura arma un plato completo.",
    },
    # [TCAC] S001: 82 kcal, 248 mg de sodio.
    "ajiaco": {
        "aporta": "Reúne varios grupos en un solo plato: papa y mazorca para la energía, y pollo para la proteína.",
        "a_tener_en_cuenta": "El aguacate que lo acompaña aporta grasas de las que recomiendan las Guías "
                             "del ICBF. Una fruta de postre completa el plato.",
    },
    # [TCAC] S004: 212 kcal, 282 mg de sodio, 1,9 g de grasa saturada.
    "bandeja_paisa": {
        "aporta": "Combina casi todos los grupos: fríjol y carne (proteína), arroz y arepa (energía) y aguacate.",
        "a_tener_en_cuenta": "Es un plato abundante y muy completo: escucha tu hambre para decidir cuánto comer.",
    },
    # [TCAC] A009: 161 kcal, 4 mg de sodio.
    "arroz": {
        "aporta": "Es la base de energía de muchos almuerzos colombianos.",
        "a_tener_en_cuenta": "Con fríjol o lenteja forma una proteína más completa, porque se complementan.",
    },
    # [TCAC] J003: 145 kcal, 3,1 g de grasa saturada.
    "huevo": {
        "aporta": "Es una proteína completa: trae todos los aminoácidos que tu cuerpo no puede fabricar.",
        "a_tener_en_cuenta": "Con una arepa y una fruta arma un desayuno completo.",
    },
    # [TCAC] F088, pechuga sin piel frita: 178 kcal.
    "pollo_frito": {
        "aporta": "Aporta proteína para construir y reparar tus músculos y tejidos.",
        "a_tener_en_cuenta": "Asado o cocido conserva la misma proteína, sin la grasa que suma la fritura.",
    },
    # Estimación por receta (alimentos_icbf_ingredientes.csv): 201 kcal.
    "patacon": {
        "aporta": "El plátano es del grupo que da energía y aporta potasio.",
        "a_tener_en_cuenta": "Al freírse absorbe aceite; asado o cocido es otra forma de comer plátano.",
    },
    # Estimación por receta: 227 kcal, 519 mg de sodio, 4,7 g de grasa saturada.
    "frito": {
        "aporta": "Es un plato típico de Nariño que combina cerdo (proteína) con papa o maíz (energía).",
        "a_tener_en_cuenta": "La fritura le suma sodio y grasa; una ensalada o una fruta completan el plato.",
    },
    # Estimación por receta: 269 kcal, 576 mg de sodio, 6,4 g de grasa saturada.
    "hornado": {
        "aporta": "Es cerdo horneado, típico de Nariño: aporta proteína.",
        "a_tener_en_cuenta": "Tiene bastante sodio (576 mg por cada 100 g en nuestra estimación por receta). "
                             "Acompáñalo con verduras y agua.",
    },
    # [USDA] cola regular: 42 kcal y 9,94 g de azúcar por 100 ml.
    # Lata de 355 ml = 35 g; 5 % de 2.000 kcal = 25 g [OMS].
    "gaseosas_bebidas_azucaradas": {
        "aporta": "Aporta agua y energía rápida del azúcar, pero no trae vitaminas, minerales ni fibra.",
        "a_tener_en_cuenta": "Una lata de 355 ml trae unos 35 g de azúcar, más que los 25 g que la OMS "
                             "sugiere como ideal para todo el día.",
    },
    # [USDA] Snack cake, chocolate: 399 kcal, 37,8 g de azúcar, 332 mg de sodio.
    "chororamo": {
        "aporta": "Da energía rápida: es un ponqué de paquete.",
        "a_tener_en_cuenta": "Un ponqué de chocolate como este trae unos 38 g de azúcar por cada 100 g. "
                             "Para la lonchera, una fruta y un lácteo son otra opción.",
    },
    # [USDA] Potato chips: 571 kcal, 482 mg de sodio.
    "frituras_empaquetadas": {
        "aporta": "Dan energía, sobre todo por la grasa de la fritura.",
        "a_tener_en_cuenta": "Unas papas de paquete traen unos 480 mg de sodio por cada 100 g. Si te provoca "
                             "algo crujiente, el maní sin sal o las palomitas hechas en casa son otra opción.",
    },
    # [USDA] 2706924: 263 kcal, 487 mg de sodio, 3,6 g de grasa saturada.
    "hamburger": {
        "aporta": "Reúne pan (energía) y carne (proteína); con lechuga y tomate suma verduras.",
        "a_tener_en_cuenta": "Una hamburguesa comercial trae unos 490 mg de sodio por cada 100 g. Comerla "
                             "de vez en cuando con amigos está bien; súmale una fruta o una ensalada.",
    },
    # [USDA] PIZZA: 238 kcal, 401 mg de sodio, 3,1 g de grasa saturada.
    "pizza": {
        "aporta": "Combina masa (energía) y queso (lácteo), y según lo que lleve encima, verduras o carne.",
        "a_tener_en_cuenta": "El queso y los embutidos le suben el sodio; una ensalada al lado completa el plato.",
    },
        "aromatica": {
        "aporta": "Es una bebida caliente que hidrata; sin endulzar, casi no aporta calorías.",
        "a_tener_en_cuenta": "Si la endulzas, el azúcar o la panela le suman energía; puedes probarla primero sin endulzar.",
    },
}
