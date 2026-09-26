# Contrato de la confirmación manual (grupos de confusión)

Para quien construya el frontend. Los grupos y sus opciones viven en `Backend/grupos_confusion.py`. Las tablas de abajo se generaron desde ese archivo y desde `Backend/alimentos_confirmacion_fuentes.csv` (26 sep 2026). Si cambian, hay que regenerarlas.

## Cómo funciona

1. `POST /predecir` recibe la foto. Si la IA reconoce algo que pertenece a un **grupo de confusión** (alimentos o productos que se ven casi iguales), **no guarda nada**, sin importar la certeza. En cambio, devuelve las opciones para que el usuario elija.
2. El usuario toca una opción y el frontend llama `POST /confirmar-alimento` con ese `codigo`. Ahí sí se guarda en el historial, con la nutrición de ese producto específico.

## Respuesta de `/predecir` cuando hay que confirmar

Respuesta real (grupo `tamal`, predicción simulada):

```json
{
  "alimento": "Tamal (otro tipo)",
  "alimento_codigo": "tamal",
  "certeza": 96.4,
  "dato_curioso": null,
  "guardado_baseDatos": false,
  "mensaje": "Los tamales y los envueltos se ven muy parecidos -- confirma cuál es.",
  "modelo_usado": "regional_26",
  "opciones_detalle": [
    {
      "codigo": "tamal_tolimense",
      "grupo": "tamal",
      "marca": null,
      "nombre": "Tamal tolimense"
    },
    {
      "codigo": "envuelto_yuca",
      "grupo": "envuelto",
      "marca": null,
      "nombre": "Envuelto de yuca"
    },
    {
      "codigo": "envuelto_choclo_queso",
      "grupo": "envuelto",
      "marca": null,
      "nombre": "Envuelto de choclo con queso"
    },
    {
      "codigo": "tamal",
      "grupo": "otro",
      "marca": null,
      "nombre": "Otro tipo de tamal"
    }
  ],
  "opciones_sugeridas": [
    "tamal_tolimense",
    "envuelto_yuca",
    "envuelto_choclo_queso",
    "tamal"
  ],
  "seleccion_manual": true,
  "success": false
}
```

- `opciones_sugeridas`: lista de códigos. **Es el contrato original y no cambió**: el frontend actual sigue funcionando igual.
- `opciones_detalle` (**campo nuevo**): la misma lista en el mismo orden, pero cada opción trae `{codigo, nombre, marca, grupo}`:
  - `nombre`: texto corto para el botón.
  - `marca`: la marca comercial, o `null` (platos, genéricos). Sirve para **agrupar por marca** cuando hay muchas opciones (frituras tiene 17).
  - `grupo`: subcategoría para ordenar o separar en pantalla (`papas`, `maíz`, `plátano`, `gaseosa`, `té frío`, `energizante`, `jugo`, `tamal`, `envuelto`...). Siempre hay una opción con `grupo: "otro"` al final de los grupos nuevos: úsala para "No está en la lista".
- `alimento` / `alimento_codigo`: lo que vio la IA (la clase visual, p. ej. "Tamal (otro tipo)"), **no** la respuesta final. Mejor no mostrarlo como si lo fuera.

## `POST /confirmar-alimento`

Body (JSON): `{"alimento_codigo": "<codigo de una opción>", "email": "<correo>"}`

- Acepta el `codigo` de **cualquier** opción de la tabla de abajo (probado uno por uno en `test_confirmacion.py`).
- Rechaza con `400` los códigos de agrupación puros (`sopas`, `dulces`), que no son un alimento real.
- La respuesta trae `alimento_app` (nombre para mostrar), `certeza: 100.0` (fue una persona quien confirmó) y la clave `gamificacion` (ver `CONTRATO_GAMIFICACION.md`).

## Qué significa `es_saludable`

`es_saludable = 1` quiere decir **"no dispara ningún sello de advertencia de la Res. 810"** con los datos disponibles. No quiere decir "comida recomendada". Por ejemplo, varias frituras de paquete salen con 1 porque no pasan ninguno de los umbrales de la norma. Para los productos envasados se aplica la Tabla 17 completa del ABECÉ de MinSalud (p. 67): sólidos por 100 g, bebidas por 100 ml, razón sodio/kcal y edulcorantes. El detalle de cada fila (fuente, código de barras, correcciones, datos que faltan) está en `alimentos_confirmacion_fuentes.csv`.

## Grupos y opciones

### `sopas`

Disparadores: `ajiaco`, `mondongo`, `sancocho`, `sopas`. Mensaje: *Ajiaco, sancocho y mondongo se ven muy parecidos -- confirma cuál es.*

| codigo | nombre | marca | grupo |
|---|---|---|---|
| `ajiaco` | Ajiaco | — | sopa |
| `sancocho` | Sancocho | — | sopa |
| `mondongo` | Mondongo | — | sopa |

### `dulces`

Disparadores: `dulces`. Mensaje: *Hay varios dulces parecidos entre sí -- confirma cuál es.*

| codigo | nombre | marca | grupo |
|---|---|---|---|
| `nucita` | Nucita | Nucita | dulce |
| `barrilete` | Barrilete | Barrilete | dulce |
| `quipitos` | Quipitos | Quipitos | dulce |
| `chororamo` | Chocoramo | Chocoramo | dulce |
| `supercoco` | Super Coco | Super Coco | dulce |
| `bonbonbum` | Bon Bon Bum | Bon Bon Bum | dulce |
| `chocolatinas` | Chocolatina | — | dulce |

### `tamal`

Disparadores: `tamal`. Mensaje: *Los tamales y los envueltos se ven muy parecidos -- confirma cuál es.*

| codigo | nombre | marca | grupo | unidad | es_saludable | sellos | fuente |
|---|---|---|---|---|---|---|---|
| `tamal_tolimense` | Tamal tolimense | — | tamal | 100 g | 1 | ninguno | TCAC 2018 (ICBF) |
| `envuelto_yuca` | Envuelto de yuca | — | envuelto | 100 g | 1 | ninguno | TCAC 2018 (ICBF) |
| `envuelto_choclo_queso` | Envuelto de choclo con queso | — | envuelto | 100 g | 0 | grasas_saturadas | Estimación por receta |
| `tamal` | Otro tipo de tamal | — | otro | 100 g | 1 | — | Fila genérica existente |

### `frituras_empaquetadas`

Disparadores: `frituras_empaquetadas`. Mensaje: *Hay muchos paquetes parecidos -- confirma cuál es.*

| codigo | nombre | marca | grupo | unidad | es_saludable | sellos | fuente |
|---|---|---|---|---|---|---|---|
| `margarita_limon` | Margarita limón | Margarita | papas | 100 g | 0 | sodio,grasas_saturadas | OFF, sin foto (no verificado con la etiqueta) |
| `margarita_mayonesa` | Margarita mayonesa | Margarita | papas | 100 g | 0 | sodio,grasas_saturadas | OFF, sin foto (no verificado con la etiqueta) |
| `margarita_onduladas_tomate` | Margarita onduladas de tomate | Margarita | papas | 100 g | 0 | sodio,grasas_saturadas | OFF, sin foto (no verificado con la etiqueta) |
| `yupis` | Yupis | Yupi | maíz | 100 g | 0 | sodio,grasas_saturadas | OFF, verificado con foto de la etiqueta |
| `rizadas_limon` | Rizadas limón | Yupi | papas | 100 g | 0 | sodio,grasas_saturadas | OFF, verificado con foto de la etiqueta |
| `rizadas_mayonesa` | Rizadas mayonesa | Yupi | papas | 100 g | 0 | sodio,grasas_saturadas | OFF, verificado con foto de la etiqueta |
| `tosti_empanadas_limon` | Tosti empanadas limón | Yupi | maíz | 100 g | 0 | sodio,grasas_saturadas | OFF, verificado con foto de la etiqueta |
| `doritos_pizza` | Doritos pizza | Doritos | maíz | 100 g | 1 | ninguno | OFF, sin foto (no verificado con la etiqueta) |
| `doritos_bbq` | Doritos BBQ | Doritos | maíz | 100 g | 1 | ninguno | OFF, sin foto (no verificado con la etiqueta) |
| `natuchips_platano` | NatuChips plátano verde | NatuChips | plátano | 100 g | 1 | ninguno | OFF, verificado con foto de la etiqueta |
| `cheetos_boliqueso` | Cheetos Boliqueso | Cheetos | maíz | 100 g | 0 | sodio,grasas_saturadas | OFF, verificado con foto de la etiqueta |
| `cheetos_trissitos` | Cheetos Trissitos | Cheetos | maíz | 100 g | 0 | sodio,grasas_saturadas | OFF, sin foto (no verificado con la etiqueta) |
| `takis_intense_nacho` | Takis Intense Nacho | Takis | maíz | 100 g | 0 | sodio | OFF, sin foto (no verificado con la etiqueta) |
| `detodito_pollo_parrillero` | De Todito pollo parrillero | De Todito | mezcla | 100 g | 1 | ninguno | OFF, sin foto (no verificado con la etiqueta) |
| `superricas_papas_pollo` | Super Ricas papas pollo | Super Ricas | papas | 100 g | 1 | ninguno | OFF, verificado con foto de la etiqueta |
| `superricas_tajaditas_platano` | Super Ricas tajaditas de plátano | Super Ricas | plátano | 100 g | 1 | ninguno | OFF, sin foto (no verificado con la etiqueta) |
| `frituras_empaquetadas` | Otra marca | — | otro | 100 g | 0 | — | Fila genérica existente |

### `gaseosas_bebidas_azucaradas`

Disparadores: `gaseosas_bebidas_azucaradas`. Mensaje: *Muchas bebidas se ven parecidas -- confirma cuál es.*

| codigo | nombre | marca | grupo | unidad | es_saludable | sellos | fuente |
|---|---|---|---|---|---|---|---|
| `cocacola_original` | Coca-Cola Original | Coca-Cola | gaseosa | 100 ml | 0 | azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `pepsi` | Pepsi | Pepsi | gaseosa | 100 ml | 0 | azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `colombiana` | Colombiana | Postobón | gaseosa | 100 ml | 0 | azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `postobon_manzana` | Manzana Postobón | Postobón | gaseosa | 100 ml | 0 | azucares | OFF, sin foto (no verificado con la etiqueta) |
| `mr_tea` | Mr. Tea | Postobón | té frío | 100 ml | 0 | azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `speed_max` | Speed Max | Postobón | energizante | 100 ml | 0 | azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `vive100` | Vive100 | Vive 100 | energizante | 100 ml | 0 | sodio,azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `del_valle_fresh_citricas` | Del Valle Fresh cítricas | Del Valle | jugo | 100 ml | 0 | sodio,azucares,edulcorantes | OFF, verificado con foto de la etiqueta |
| `gaseosas_bebidas_azucaradas` | Otra bebida | — | otro | 100 ml | 0 | — | Fila genérica existente |


## Agregar o cambiar un grupo

1. Editar `Backend/grupos_confusion.py` (no hace falta tocar `app.py`).
2. Cargar la nutrición de las opciones nuevas en `tabla_alimentos` (ver `Pipelines de datos/importar_productos_confirmacion.py`).
3. Correr `Pipelines de datos/verificar_integridad_clases.py` (ninguna opción puede quedar sin fila) y `python3 test_confirmacion.py`.
4. Regenerar las tablas de este documento.
