# Imágenes del avatar por capas

Aquí van las 8 imágenes PNG del avatar diseñado en Figma (2 bases, 3 prendas
de ropa y 3 accesorios), con los nombres exactos de
`ESPECIFICACION_AVATARES_FIGMA.md` (carpeta `Backend/`).

Flask las sirve solo en `http://127.0.0.1:5002/static/avatar/<archivo>`.
Mientras falte alguna, `GET /avatar` responde igual, con `"imagen_lista": false`
para esa capa, y el frontend muestra un marcador. Nada se rompe.
