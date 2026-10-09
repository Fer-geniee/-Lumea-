> **EN DESUSO (9 oct 2026).** Estas imágenes por capas no llegaron a tiempo: la persona de Lumea ahora es un avatar
> **voxel-art de DiceBear** que el frontend dibuja en el navegador, y cada etapa desbloquea una prenda que cambia a la
> persona (ver `CONTRATO_GAMIFICACION.md`, «La persona: avatar voxel-art y armario por etapas»). Este documento se
> conserva como historia del proyecto y por si algún día se vuelve a las ilustraciones propias.

# Avatar de Lumea por capas: qué dibujar en Figma (para Laura)

Hola, Laura. Esta guía explica qué imágenes necesita la app para el avatar del
perfil, cómo deben ser y cómo exportarlas desde Figma. No hace falta saber
programar.

## La idea en una frase

El avatar se arma **como una muñeca de papel**: primero va el cuerpo (la
**base**), encima una prenda (**ropa**) y encima un **accesorio**. Cada una es
una imagen aparte. La app las pone una encima de otra y, si están bien
alineadas, encajan solas.

Cuando la persona sube de nivel usando la app, se desbloquean prendas y
accesorios nuevos para ponerle a su avatar.

La cara que cambia con el estado de ánimo **no** la tienes que hacer: esa ya
existe (la hace un servicio llamado DiceBear). Tu avatar tiene una sola
expresión, tranquila y amable.

## Lista completa: 8 imágenes

| # | Nombre del archivo (exacto) | Qué es | Se desbloquea en |
|---|---|---|---|
| 1 | `base_1.png` | Base 1 | Desde el inicio |
| 2 | `base_2.png` | Base 2 | Desde el inicio |
| 3 | `ropa_buzo_verde.png` | Buzo (sudadera) verde | Nivel 1 |
| 4 | `ropa_camiseta_lumea.png` | Camiseta con el logo o el nombre de Lumea | Nivel 3 |
| 5 | `ropa_ruana.png` | Ruana | Nivel 6 |
| 6 | `accesorio_gafas.png` | Gafas | Nivel 2 |
| 7 | `accesorio_audifonos.png` | Audífonos (de diadema, sobre la cabeza) | Nivel 4 |
| 8 | `accesorio_sombrero_vueltiao.png` | Sombrero vueltiao | Nivel 8 |

2 bases + 3 ropas + 3 accesorios = **8 imágenes**.

Los nombres tienen que ser **exactamente** esos: en minúsculas, sin tildes, sin
espacios, con guion bajo (`_`) y terminados en `.png`. La app busca cada archivo
por su nombre; si dice `Base_1.png` o `base 1.png`, no lo encuentra.

¿Quieres cambiar alguna prenda o accesorio (por ejemplo, una gorra en vez de las
gafas)? Se puede, pero avísale antes a Isabella para que cambie el nombre en el
backend.

## Las 4 reglas para que las capas encajen

### 1. Todas del mismo tamaño: 512 × 512 píxeles

Las 8 imágenes deben ser cuadradas y de **512 × 512**, aunque el dibujo ocupe
solo una parte. Por ejemplo, las gafas son pequeñas, pero su imagen también mide
512 × 512: las gafas van en el sitio exacto de los ojos y el resto queda
transparente.

### 2. Fondo transparente, en PNG

Nada de fondo blanco ni de color: todo lo que no sea el dibujo tiene que ser
**transparente**. Si no, al poner la ropa encima, taparía la base con un cuadro
blanco. Por eso el formato es **PNG** (JPG no permite transparencia).

### 3. Alineadas: cada cosa en su sitio exacto

Cada prenda y accesorio se dibuja **encima de la base**, en la posición en que
debe quedar. La app no mueve nada: solo apila las imágenes. Si las gafas quedan
un poco más arriba en tu archivo, en la app también quedarán más arriba. El
método de exportar de abajo lo resuelve solo.

### 4. Las 2 bases con la misma silueta y la misma postura

Las dos bases pueden cambiar el **tono de piel, el pelo y la cara**, pero deben
tener **la misma forma de cuerpo, el mismo tamaño y la misma postura**. Así cada
prenda y cada accesorio sirve para las dos. Si las bases fueran distintas, habría
que dibujar cada prenda dos veces (16 imágenes en vez de 8).

Un truco: dibuja la base 1, duplícala y sobre la copia cambia solo el color de
piel, el peinado y los rasgos de la cara.

## Cómo dibujar cada tipo

- **Bases:** medio cuerpo (cabeza, cuello, hombros y torso, hasta la cintura
  más o menos), de frente, con los brazos a los lados. Deben llevar ya una
  **camiseta básica sencilla**, porque la persona puede quitarse la ropa del
  juego y el avatar tiene que seguir vestido.
- **Ropa:** cubre el torso y los brazos, y tapa por completo la camiseta básica
  de la base (que no se asome por los bordes).
- **Accesorios:** van en la cabeza o la cara. Como el sombrero y los audífonos
  van encima del pelo, que el pelo de las dos bases no sea muy voluminoso, para
  que ambos encajen.
- **Estilo:** colores planos y contornos limpios. Si quieres combinar con la
  app, sus verdes son `#1E5E3A` (el principal), `#2D6A4F` y `#B7E4C7`.
- **Importante:** la app la usan estudiantes de colegio. Nada que resalte el
  cuerpo ni la figura, sin maquillaje exagerado. El avatar es un personaje
  amigable, no un cuerpo.

## Paso a paso en Figma

### A. Preparar el lienzo (una sola vez)

1. Crea un archivo nuevo en Figma.
2. Presiona la tecla **F** (herramienta Frame) y haz clic en el lienzo.
3. En el panel de la derecha escribe **W: 512** y **H: 512**.
4. Ponle al frame el nombre `avatar` (doble clic sobre su nombre en el panel de
   capas de la izquierda).
5. **Quita el fondo blanco:** con el frame seleccionado, en el panel de la
   derecha busca **Fill** y haz clic en el signo **−** que está al lado del
   color blanco. El fondo del frame debe verse como un tablero de cuadritos
   grises (eso significa "transparente").

### B. Dibujar todo dentro del mismo frame

6. Dibuja la base 1 dentro del frame `avatar`. Cuando termines, selecciona todas
   sus piezas y presiona **Ctrl + G** (en Mac, **Cmd + G**) para agruparlas.
   Ponle al grupo el nombre `base_1`.
7. Haz la base 2 igual (grupo `base_2`), en la misma posición que la base 1.
8. Dibuja cada prenda y cada accesorio **encima de la base 1**, dentro del mismo
   frame, y agrupa cada uno con su nombre: `ropa_buzo_verde`,
   `ropa_camiseta_lumea`, `ropa_ruana`, `accesorio_gafas`,
   `accesorio_audifonos`, `accesorio_sombrero_vueltiao`.
9. Para ver cómo queda una combinación, oculta o muestra grupos con el
   **ojito** que aparece al pasar el mouse sobre cada capa. Prueba cada prenda y
   cada accesorio con **las dos bases**.

Al final, el frame `avatar` debe tener 8 grupos, uno por imagen.

### C. Exportar las 8 imágenes

10. Selecciona el frame `avatar` y presiona **Ctrl + D** (Mac: **Cmd + D**)
    **siete veces**. Quedan 8 copias idénticas del frame, con todo en el mismo
    sitio.
11. Cambia el nombre de cada copia por uno de los 8 nombres de la lista (sin
    `.png`): `base_1`, `base_2`, `ropa_buzo_verde`, etc. Figma usa el nombre del
    frame como nombre del archivo.
12. Dentro de cada copia, **borra todos los grupos menos el suyo**. Por ejemplo,
    en el frame `accesorio_gafas` solo queda el grupo `accesorio_gafas`. (No
    muevas nada: solo borra.)
13. Selecciona los 8 frames a la vez (clic en el primero y **Shift + clic** en
    los demás, en el panel de capas).
14. En el panel de la derecha, abajo, en **Export**, haz clic en **+**.
    Deja **1x** y **PNG**.
15. Clic en **Export 8 layers** (o "Exportar"). Figma descarga los 8 archivos
    con sus nombres.

### D. Revisar antes de entregar

- [ ] Son 8 archivos y los nombres coinciden **letra por letra** con la tabla.
- [ ] Cada archivo mide **512 × 512**. En Mac: ábrelo con Vista Previa →
      Herramientas → Ajustar tamaño. En Windows: clic derecho → Propiedades →
      Detalles.
- [ ] El fondo es transparente (en Vista Previa o en el navegador se ven
      cuadritos o el color de fondo de la ventana, no blanco).
- [ ] Cada prenda y accesorio encaja sobre **las dos** bases.

## Dónde van y a quién se las das

Entrégale los 8 archivos a **Isabella** (por Drive o en un .zip). Ella los pone en
la carpeta **`Backend/static/avatar/`** del proyecto y la app los empieza a usar
sola, sin cambiar nada de código.

Si falta alguna imagen, la app no se daña: muestra un recuadro de "próximamente"
en su lugar. Así que puedes entregar primero las 2 bases y después lo demás. Si
al final no alcanzas a terminarlas, la app usa los avatares de DiceBear que ya
tiene.

Si te surge una duda (otra prenda, otro tamaño, otro estilo), pregúntale a
Isabella antes de dibujar todo: cambiar un nombre o una medida al final obliga a
exportar todo de nuevo.
