---
description: Edita un vídeo hablado a cámara para Instagram (quita silencios, reencuadra, subtítulos, titular, tarjetas, 1.1x, −14 LUFS)
argument-hint: <ruta del vídeo>
---

Edita el vídeo `$ARGUMENTS` con el editor de este repositorio. Tú diriges; las herramientas ejecutan. El usuario no programa: cuéntale cada paso en una frase y no le enseñes código. Antes de empezar, lee `CLAUDE.md` (reglas de edición) y `PREFERENCIAS.md` (lo que el usuario ya te ha corregido).

## Reglas
- **Nunca borres ni modifiques el vídeo original.** Todo se escribe en `trabajos/<nombre>/` dentro de este repo.
- Si una herramienta falla, di cuál, en qué paso y por qué antes de seguir.
- Python: `.venv/bin/python -I`. Ejecuta todo desde la raíz del repositorio. Si `.venv` o `herramientas/caras` no existen, ejecuta primero `./instalar.sh`.

## Pasos
1. **Carpeta.** `<nombre>` = nombre del archivo en minúsculas, sin espacios ni tildes. Si ya existe una carpeta con receta, pregunta si se retoca esa o se empieza de cero.
2. **Análisis** (FFmpeg audio → Whisper large-v3 → Silero → Apple Vision):
   `.venv/bin/python -I herramientas/analizar.py "<vídeo>" trabajos/<nombre>`
3. **Receta inicial:** `.venv/bin/python -I herramientas/montar.py proponer trabajos/<nombre>` → `receta.json` con los cortes de silencios y el encuadre automático.
4. **Dirige.** Lee `transcripcion.json` (palabras con su segundo) y edita `receta.json`:
   - `cortes`: quita también tomas repetidas, frases a medias y errores (si dice algo dos veces, quédate con la última toma buena). Tiempos en segundos del ORIGINAL.
   - `titular`: `{linea1, linea2, inicio, fin}`. Línea 1 corta en blanco, línea 2 en cursiva de acento. Los 3-4 primeros segundos.
   - `subtitulos.resaltar`: solo palabras clave (números ya se resaltan solos). `correcciones`: `{"palabra_mal": "palabra_bien"}`; `""` la quita. Revisa nombres propios y marcas.
   - `tarjetas`: `{texto, subtexto, inicio, fin, posicion}` con `posicion` `pecho` (defecto), `arriba` o `centro`. Solo para cifras o ideas clave. Máximo una cada ~8 s.
   - `stickers`: `{contenido, inicio, fin, x, y, giro}`; texto corto en pastilla o un emoji. `y` 0.1 queda por encima de la cabeza.
   - `guion`: lista de tramos `{inicio, fin}` con las tomas buenas; luego `montar.py afinar trabajos/<nombre>` genera los `cortes` finos (quita «eh», huecos y silencios). Los bordes del guion son exactos.
   - `escenas`: animaciones que explican el concepto en pantalla partida. Tipos `embudo`, `comparativa` (con `columnas`), `flujo` (origen → opciones → destino), `ciclo` (con `centro`) y `lista`. Cada elemento con `en` = segundo en que lo nombra; `foco` para resaltar. Úsalas cuando explique un proceso, una comparación o una lista.
   - `musica`: `{archivo, desde, db_bajo_voz}`; por defecto `musica/mixkit-684.mp3` (ruta absoluta dentro de este repo) a 22 dB bajo la voz, nivel fijo.
   - `velocidad` (1.1: a 1.2 no se entiende), `lufs` (−14), `encuadre.zoom_alterno` (acercamiento en cada corte), `estilo` (`acento`, `subtitulosY`, `tamanoSubtitulos`, `mayusculas`).
   - No inventes datos: tarjetas y stickers solo con lo que dice el vídeo.
5. **Verifica los cortes** antes de dar nada por bueno. Regla de oro: primero que se entienda, después quitar «eh»; nunca cortar con voz sonando. Ejecuta `.venv/bin/python -I herramientas/revisar_cortes.py trabajos/<nombre>` y resuelve cada empalme dudoso (bordes comprobados con `exacto_inicio`/`exacto_fin`, aire con tramos `pausa: true`). La energía del audio cada 10 ms localiza toses y «eh»; cada empalme dudoso se monta y se transcribe en corto (la transcripción del montaje entero da falsos fallos).
6. **Borrador:** `.venv/bin/python -I herramientas/montar.py borrador trabajos/<nombre>` (mitad de resolución). Revisa fotogramas con `.venv/bin/python -I herramientas/hoja.py <vídeo> <salida.jpg> <segundos…>` antes de enseñarlo: que nada tape la cara y que los subtítulos se lean.
7. **Enséñaselo:** abre `borrador.mp4` con `open` y resume en una tabla corta qué cortas, el titular, las tarjetas y los stickers. Espera su visto bueno, salvo que pida que se lo dejes listo: entonces revísalo tú, haz el final y cópialo junto al original como «<nombre> - editado.mp4».
8. **Cambios:** tradúcelos a la receta y vuelve al paso 5. No rehagas el análisis. **Anota cada corrección nueva en `PREFERENCIAS.md`** (fecha, qué dijo, qué hacer).
9. **Final:** `.venv/bin/python -I herramientas/montar.py final trabajos/<nombre>` → `final.mp4` (H.264, 1080×1920, −14 LUFS en dos pasadas). Comprueba volumen con `ffmpeg -i final.mp4 -af loudnorm=print_format=summary -f null -` y ábrelo.
