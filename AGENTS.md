# Instrucciones para Codex

Este repositorio es un editor de vídeo hablado (vertical, para Instagram). Las instrucciones completas están en `CLAUDE.md` y los pasos en `.claude/commands/editar.md`. Léelos y síguelos tal cual: los pasos son los mismos aunque no tengas el comando `/editar`.

Cuando el usuario diga «edita este vídeo <ruta>», ejecuta el flujo de `.claude/commands/editar.md` con `$ARGUMENTS` = la ruta. Usa siempre `.venv/bin/python -I` para Python. Anota cada corrección del usuario en `PREFERENCIAS.md`.
