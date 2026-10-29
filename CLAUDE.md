# Editor de vídeo hablado

Este repositorio edita vídeos hablados a cámara (vertical 1080×1920, Instagram/TikTok) a partir de una grabación en bruto. Cuando el usuario diga «edita este vídeo», ejecuta `/editar <ruta>` (pasos en `.claude/commands/editar.md`). Si algo no está instalado, ejecuta `./instalar.sh`.

**Cómo hablar con el usuario:** en español de España, directo, sin enseñar código, una sola pregunta por respuesta. Cuéntale cada paso en una frase. Opinión sin rodeos.

## Qué hay

- `herramientas/analizar.py` — audio → Whisper large-v3 (mlx, palabra a palabra) + Silero (voz) + Apple Vision (caras).
- `herramientas/montar.py` — receta → cortes, Remotion (subtítulos, titular, tarjetas, escenas), mezcla de audio −14 LUFS.
- `herramientas/revisar_cortes.py`, `hoja.py` — verificación de empalmes y hojas de fotogramas.
- `herramientas/caras`, `silueta` — binarios Swift (Apple Vision) que `instalar.sh` compila. Solo Mac.
- `src/Composition.tsx` — la composición Remotion.
- `trabajos/<nombre>/` — todo lo de cada vídeo (receta.json, transcripción, borrador, final). Nunca se toca el original.
- `PREFERENCIAS.md` — correcciones del usuario. **Léelo antes de editar y añade ahí cada corrección nueva.**

## Reglas de edición (de partida; el usuario puede cambiarlas)

Salen de cientos de correcciones sobre vídeos reales. Respétalas hasta que el usuario diga otra cosa.

**Cortes**
- **Primero que se entienda, después quitar «eh».** Nunca cortar con voz sonando. Cada corte, en silencio real (por debajo de ~−45 dB, al menos ~0,08 s; los bordes de un tramo piden ≥150 ms de silencio). Un valle entre dos palabras seguidas NO vale como corte.
- Si no hay silencio, se alarga la frase hasta la siguiente pausa de verdad. Si no se puede llevar un corte a silencio, díselo al usuario al entregar.
- **No puedes oír el vídeo.** Whisper reconstruye palabras cortadas, así que «Whisper la oye entera» no prueba que el corte suene bien: mandan la energía del audio y el silencio.
- Pausas naturales de ~0,2 s entre frases. Entre pregunta y respuesta (dos personas) tiene que quedar un respiro.
- Cortar las tomas malas con mucho cuidado y revisarlo tú antes de enviarlo: el usuario quiere recibirlo ya listo.
- Velocidad 1.1, nunca 1.2 (a 1.2 las palabras cortas dejan de entenderse).
- Whisper engaña al revisar: con música se salta palabras cortas y con una pista de «eh, em» se inventa muletillas. Revisa sin pista y compara la energía antes de tocar nada.
- El reel acaba cuando acaba la idea; un número nunca se corta. Comprueba el final con Whisper sobre la mezcla final.
- El último fotograma nunca negro: la duración de la composición = los fotogramas reales del vídeo base.

**Imagen**
- Tarjetas, rótulos y stickers **nunca encima de la cara** (se colocan solos según `caras.json`; revisa fotogramas de cada tarjeta).
- **Nunca recortar a la persona ni cambiarle el fondo** con máscara. El plano grabado es parte del vídeo.
- Subtítulos: Montserrat, sin efecto pop; la frase entra con fundido y cada palabra se ilumina al decirla. Sombra suave, sin contorno.
- Animaciones (escenas) para explicar un proceso, comparación o lista; son un añadido, no el protagonista. Mientras una animación está visible debe moverse la mayor parte del tiempo; si espera a una palabra, vuelve la persona a pantalla completa.
- Rótulos y tachones clave, visibles ~1,5 s para dar tiempo a leerlos.
- **Color iPhone:** los .MOV del iPhone vienen en HEVC 10 bits HLG (`color_transfer=arib-std-b67`). Sin conversión salen grises/lavados. Con `ffprobe` comprueba el vídeo; si es HLG, convierte con `zscale … npl=100, tonemap=hable:desat=0` y un ajuste suave (`eq=gamma=1.0:saturation=1.1:contrast=1.1`). **Nunca subir el gamma para «dar luz»**: quema la piel.

**Audio**
- Música **muy leve, siempre de fondo, a nivel fijo** (~22 dB por debajo de la voz), sin ducking, que nunca tape ni compita con la voz.
- Efectos de sonido, si los hay, al menos ~20 dB por debajo de la voz. Un solo sonido por cosa que aparece.
- Voz final a −14 LUFS en dos pasadas. Remotion se renderiza `--muted`: la voz sale siempre de `base.mp4`.
- Si montas muchas piezas unidas, construye el audio aparte con muestras exactas y comprueba que audio y vídeo duran lo mismo (`ffprobe`): un `-frames:v` recorta audio y el desfase se acumula.

**Criterio**
- Antes de editar, di de qué **tipo** es el vídeo (opinión a cámara, conversación/podcast, storytelling…). Cada tipo tiene su ritmo y sus reglas: no las mezcles.
- Elige el estilo para ese vídeo, no copies el de la pieza anterior. Si las dos últimas piezas llevan el mismo, cambia. Dile al usuario en una línea qué estilo eliges y por qué.
- Sé proactivo: si ves que una escena o tarjeta mejora el vídeo, hazla y avisa de lo que cambiaste.
- No inventes datos: cifras y nombres solo si los dice el vídeo.
- Contenido para el público: nada de música con tensión en una marca elegante; música distinta por pieza (propón tres y que decida el usuario de oído).

## Cómo aprender del usuario
Cada vez que el usuario corrija algo («eso no me gusta», «así sí»), añade una línea fechada a `PREFERENCIAS.md` con la regla y por qué. En el siguiente vídeo, léela antes de empezar.
