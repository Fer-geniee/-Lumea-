#!/bin/bash
# =====================================================================
# organizar_backend.sh  ·  Lumea
# Guarda la versión de la feria en una rama, y luego ordena Backend/
# en carpetas SIN romper los imports. Se corre UNA vez, desde la
# terminal de tu Mac, parada en la carpeta Backend:
#
#     cd ~/Python_proyects/Lumea/Backend
#     bash organizar_backend.sh
#
# No borra nada: solo mueve (git mv) y edita rutas. Si algo sale mal,
#     git switch main
# te devuelve exactamente a la versión de la feria.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"
[ -f app.py ] || { echo "ERROR: corre esto dentro de Backend/"; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null

PRINCIPAL=$(git symbolic-ref --short HEAD)
echo "Rama actual: $PRINCIPAL"

# ---------------------------------------------------------------------
# 1) Privacidad: las fotos de prueba tienen caras -> nunca a GitHub
# ---------------------------------------------------------------------
if ! grep -qxF 'fotos_prueba/' .gitignore; then
  printf '\n# Fotos de la prueba de campo (salen personas): nunca a GitHub\nfotos_prueba/\n' >> .gitignore
fi

# ---------------------------------------------------------------------
# 2) Rama + etiqueta con la versión de la feria (tal cual está hoy)
# ---------------------------------------------------------------------
RAMA_FERIA="feria-2026-10-02"
if git show-ref --verify --quiet "refs/heads/$RAMA_FERIA"; then
  echo "La rama $RAMA_FERIA ya existe: no la toco."
else
  git switch -c "$RAMA_FERIA"
  git add -A
  git commit -m "Feria de ciencias (2 oct 2026): regla en cascada, ruta /camara, diagnóstico de fotos" || echo "(nada nuevo que guardar)"
  git tag -a v-feria -m "Versión presentada en la feria de ciencias, 2 oct 2026" 2>/dev/null || echo "(la etiqueta v-feria ya existía)"
  git switch "$PRINCIPAL"
  git merge --ff-only "$RAMA_FERIA"
fi

# ---------------------------------------------------------------------
# 3) Rama nueva para reorganizar (main queda intacta hasta que pruebes)
# ---------------------------------------------------------------------
git switch -c reorganizacion-carpetas
mkdir -p pruebas entrenamiento herramientas datos docs historico/diagnostico_keras2

mover () {  # mover <archivo> <carpeta>  (usa git mv si git ya lo conoce)
  [ -e "$1" ] || { echo "  (no existe: $1)"; return 0; }
  if git ls-files --error-unmatch "$1" >/dev/null 2>&1; then git mv "$1" "$2/"; else mv "$1" "$2/"; fi
  echo "  $1 -> $2/"
}

echo "Moviendo archivos..."
for f in test_api.py test_confirmacion.py test_flujo_completo.py test_gamificacion.py test_login.py; do mover "$f" pruebas; done
for f in ia_comida.py limpiar_dataset.py recolectar_candidatos.py revisar_candidatos.py openimages.py puntuar_candidatas.py; do mover "$f" entrenamiento; done
for f in verificar_modelo.py evaluar_modelos.py evaluar_modelo_real.py diagnostico_fotos.py resumen_prueba_campo.py check_env.py; do mover "$f" herramientas; done
for f in alimentos_*.csv; do mover "$f" datos; done
for f in CONTRATO_CONFIRMACION.md CONTRATO_GAMIFICACION.md GUIA_FRONTEND_SARA.md ESPECIFICACION_AVATARES_FIGMA.md Lumea.postman_collection.json; do mover "$f" docs; done
for f in check_modelo.py comparar_nombre_capas.py explorar_estructura.py inspeccionar_pesos.py verificar_batchnorm.py verificar_pesos_nan.py rebuild_model.py; do mover "$f" historico/diagnostico_keras2; done
mover predict_antes.py historico
mover lumea.db historico            # SQLite de la etapa 1 (lo ignora git: *.db)

# Etapa 1 (app de escritorio CustomTkinter): copia como evidencia en GitHub.
# La carpeta original ../Frontend NO se toca.
if [ -d ../Frontend ] && [ ! -d historico/etapa1_frontend_escritorio ]; then
  cp -R ../Frontend historico/etapa1_frontend_escritorio
  find historico/etapa1_frontend_escritorio -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  echo "  ../Frontend copiada en historico/etapa1_frontend_escritorio/"
fi

# ---------------------------------------------------------------------
# 4) Ajustar rutas para que todo siga funcionando desde la carpeta nueva
# ---------------------------------------------------------------------
python3 - <<'PY'
import ast, glob, os, re

RAIZ = os.getcwd()  # Backend/
MODULOS = {os.path.splitext(f)[0] for f in os.listdir(RAIZ) if f.endswith(".py")}
EXPR = re.compile(r"(?<!dirname\()os\.path\.dirname\(os\.path\.abspath\(__file__\)\)")
NUEVA = "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))"
SHIM = ("import os as _os, sys as _sys  # (reorganización) para importar los módulos de Backend/\n"
        "_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))\n")

for ruta in sorted(glob.glob("pruebas/*.py") + glob.glob("entrenamiento/*.py") + glob.glob("herramientas/*.py")):
    s = open(ruta, encoding="utf-8").read()
    original = s
    # a) la "carpeta base" ahora es la de arriba (Backend/), no la del script
    s = EXPR.sub(NUEVA, s)
    # b) si importa módulos de la app (predict, database, app...), agregar Backend/ al sys.path
    arbol = ast.parse(s)
    importa = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            importa |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            importa.add(n.module.split(".")[0])
    if importa & MODULOS and "_sys.path.insert(0" not in s:
        lineas = s.splitlines(keepends=True)
        pos = 0
        if arbol.body and isinstance(arbol.body[0], ast.Expr) and isinstance(getattr(arbol.body[0], "value", None), ast.Constant) and isinstance(arbol.body[0].value.value, str):
            pos = arbol.body[0].end_lineno          # justo después del docstring
        lineas.insert(pos, SHIM)
        s = "".join(lineas)
    if s != original:
        open(ruta, "w", encoding="utf-8").write(s)
        print("  rutas ajustadas:", ruta)

# c) los importadores de "Pipelines de datos" escriben/leen los CSV en Backend/datos/
pip = os.path.join(os.path.dirname(RAIZ), "Pipelines de datos")
if os.path.isdir(pip):
    for ruta in sorted(glob.glob(os.path.join(pip, "*.py"))):
        s = open(ruta, encoding="utf-8").read()
        n = s.replace('os.path.join(BACKEND_DIR, "alimentos_', 'os.path.join(BACKEND_DIR, "datos", "alimentos_')
        if n != s:
            open(ruta, "w", encoding="utf-8").write(n)
            print("  CSV -> datos/:", os.path.relpath(ruta, os.path.dirname(RAIZ)))
PY

# ---------------------------------------------------------------------
# 5) Verificación automática (sintaxis + que cada import se pueda resolver)
# ---------------------------------------------------------------------
python3 - <<'PY'
import ast, glob, os, py_compile, sys
RAIZ = os.getcwd()
mods_raiz = {os.path.splitext(f)[0] for f in os.listdir(RAIZ) if f.endswith(".py")}
errores = 0
for ruta in sorted(glob.glob("*.py") + glob.glob("pruebas/*.py") + glob.glob("entrenamiento/*.py") + glob.glob("herramientas/*.py")):
    try:
        py_compile.compile(ruta, doraise=True)
    except py_compile.PyCompileError as e:
        print("  ✗ SINTAXIS", ruta, e); errores += 1; continue
    s = open(ruta, encoding="utf-8").read()
    carpeta = os.path.dirname(ruta)
    mods_carpeta = {os.path.splitext(f)[0] for f in os.listdir(carpeta or ".") if f.endswith(".py")}
    for n in ast.walk(ast.parse(s)):
        nombres = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else \
                  [n.module.split(".")[0]] if isinstance(n, ast.ImportFrom) and n.module else []
        for m in nombres:
            if m in mods_raiz and carpeta and "_sys.path.insert(0" not in s and m not in mods_carpeta:
                print(f"  ✗ {ruta} importa '{m}' pero no ve Backend/"); errores += 1
print("Verificación:", "OK, sin errores" if errores == 0 else f"{errores} errores")
sys.exit(1 if errores else 0)
PY

# ---------------------------------------------------------------------
# 6) README del backend + actualizar las rutas en ../CLAUDE.md
# ---------------------------------------------------------------------
if [ ! -f README.md ]; then
cat > README.md <<'README'
# Lumea · Backend

API REST en Flask que recibe la foto de un alimento, la reconoce con dos redes
MobileNetV2 (transfer learning), consulta su información nutricional en MySQL y
responde en JSON. También maneja perfiles con login (bcrypt), estado de ánimo,
historial y gamificación.

## Cómo correrlo

```bash
cd Backend
pip install -r requirements.txt
python3 app.py            # http://127.0.0.1:5002  ·  demo de cámara: /camara
```

Necesita MySQL encendido y un archivo `.env` (nunca se sube) con `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `USDA_API_KEY`.

**Todo se ejecuta desde esta carpeta** (`python3 pruebas/test_api.py`, no desde
dentro de `pruebas/`): algunos scripts usan rutas relativas como `dataset/`.

## Estructura

```
Backend/
├── app.py                 Rutas de la API (Flask). Orquesta; no tiene lógica de IA.
├── predict.py             Carga los dos modelos y decide en cascada (primero el regional).
├── database.py            Toda la capa MySQL (consultas parametrizadas, migraciones suaves).
├── gamificacion.py        XP, niveles, rachas, misiones y avatar (Blueprint de Flask).
├── gamificacion_config.py Todos los números de la gamificación, en un solo lugar.
├── grupos_confusion.py    Alimentos que siempre piden confirmación humana.
├── sellos.py              Sellos de advertencia (Res. 810 de 2021).
├── camara.html            Demo de la cámara (servida por la ruta /camara).
├── static/                Imágenes de avatares.
├── modelo_lumea_comida.keras + clases.json      Modelo regional (35 clases).
├── modelo_lumea101.keras + clases_101.json      Modelo Food-101 (101 clases).
├── pruebas/               Pruebas automáticas de la API, login, gamificación y confirmación.
├── entrenamiento/         Entrenamiento del modelo regional y limpieza/recolección del dataset.
├── herramientas/          Evaluación y diagnóstico del modelo (incluye la prueba de campo).
├── datos/                 Tablas nutricionales en CSV con sus fuentes (USDA, ICBF, receta).
├── docs/                  Contratos de la API, guía del frontend, colección de Postman.
└── historico/             Evidencia de etapas anteriores (ver abajo). No se usa en producción.
```

Los modelos y `clases*.json` viven en la raíz a propósito: `predict.py` los carga
y `entrenamiento/ia_comida.py` los escribe ahí.

## Etapas del proyecto (`historico/`)

- `etapa1_frontend_escritorio/`: la primera versión, una app de escritorio en
  Python. Su base de datos local SQLite (`lumea.db`) también está aquí, fuera de git.
- `diagnostico_keras2/`: scripts del incidente de compatibilidad Keras 2 → 3
  (pesos corruptos en BatchNorm). Apuntan a archivos `.h5` que ya no existen; se
  conservan como evidencia del método de diagnóstico.
- `predict_antes.py`: la regla de decisión anterior ("gana el modelo más seguro"),
  reemplazada por la cascada tras la prueba de campo del 1 de octubre de 2026.

Detalle completo: `DEFENSA_TECNICA_LUMEA.md`, sección 10.
README
echo "  README.md creado"
fi

if [ -f ../CLAUDE.md ]; then
python3 - <<'PY'
import os
ruta = os.path.join(os.path.dirname(os.getcwd()), "CLAUDE.md")
s = open(ruta, encoding="utf-8").read()
cambios = {
    "`python3 test_": "`python3 pruebas/test_",
    "`python3 verificar_modelo.py": "`python3 herramientas/verificar_modelo.py",
    "`Backend/Lumea.postman_collection.json`": "`Backend/docs/Lumea.postman_collection.json`",
    "`Backend/CONTRATO_CONFIRMACION.md`": "`Backend/docs/CONTRATO_CONFIRMACION.md`",
    "`Backend/CONTRATO_GAMIFICACION.md`": "`Backend/docs/CONTRATO_GAMIFICACION.md`",
    "`Backend/GUIA_FRONTEND_SARA.md`": "`Backend/docs/GUIA_FRONTEND_SARA.md`",
}
for a, b in cambios.items():
    s = s.replace(a, b)
aviso = ("\n## Estructura de carpetas (reorganizada el 3 oct 2026)\n\n"
         "Backend/ quedó en carpetas: núcleo de la app en la raíz (app.py, predict.py, database.py, "
         "gamificacion*.py, grupos_confusion.py, sellos.py, modelos y clases*.json); `pruebas/` (test_*.py), "
         "`entrenamiento/` (ia_comida.py, limpiar_dataset.py, recolección de candidatos), `herramientas/` "
         "(verificar_modelo.py, evaluar_*.py, diagnostico_fotos.py, resumen_prueba_campo.py, check_env.py), "
         "`datos/` (alimentos_*.csv), `docs/` (contratos, guía del frontend, Postman) e `historico/`. "
         "Cuando este documento nombre un script suelto, búscalo en esas carpetas. TODO se ejecuta desde "
         "Backend/ (rutas relativas como dataset/). Los scripts movidos suben un nivel su carpeta base y "
         "agregan Backend/ al sys.path. Mapa completo: Backend/README.md.\n")
if "## Estructura de carpetas (reorganizada" not in s:
    s = s.replace("\n## Arquitectura del backend", aviso + "\n## Arquitectura del backend", 1)
open(ruta, "w", encoding="utf-8").write(s)
print("  ../CLAUDE.md actualizado")
PY
fi

mover organizar_backend.sh historico   # el propio script queda como evidencia

git add -A
git commit -m "Reorganiza Backend/: pruebas, entrenamiento, herramientas, datos, docs e historico (sin cambiar la lógica)"

cat <<'FIN'

=====================================================================
LISTO. Ahora, en este orden:

 1. Prueba que todo sigue vivo (MySQL encendido):
      python3 app.py                         # y abre http://127.0.0.1:5002/camara
      python3 pruebas/test_flujo_completo.py # en otra terminal
      python3 herramientas/diagnostico_fotos.py fotos_prueba

 2. Si todo funciona, únelo a main y súbelo:
      git switch main
      git merge reorganizacion-carpetas
      git push -u origin main feria-2026-10-02 --tags

    Y guarda también los cambios del repo de la raíz (CLAUDE.md, Pipelines):
      cd .. && git add CLAUDE.md "Pipelines de datos" DEFENSA_TECNICA_LUMEA.md && git commit -m "Rutas tras reorganizar Backend/"

 3. Si algo falla: copia el error y mándamelo. main sigue intacta.
=====================================================================
FIN
