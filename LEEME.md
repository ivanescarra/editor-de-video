# Editor de vídeo hablado

Edita un vídeo grabado a cámara: corta silencios y errores, pone subtítulos, titular, tarjetas y música, y lo deja en vertical a −14 LUFS.

## Instalar (una sola vez)
1. Necesitas un Mac con chip Apple (M1 o superior).
2. Instala Claude Code (o Codex) y abre esta carpeta con él.
3. Dile: **«Ejecuta ./instalar.sh y ve aceptando lo que haga falta»**. Tarda unos 15-30 minutos (descarga ~3 GB de modelo).

## Usar
Abre Claude Code en esta carpeta y escribe:

```
/editar /ruta/a/tu-vídeo.mov
```

(En Codex: «edita este vídeo: /ruta/a/tu-vídeo.mov».) Te enseñará un borrador; dile qué cambiar. Cada corrección queda apuntada en `PREFERENCIAS.md` para que el siguiente vídeo salga mejor.

El original no se toca nunca. Todo queda en `trabajos/<nombre>/`.
