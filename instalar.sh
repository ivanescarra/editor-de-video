#!/bin/bash
# Instala todo lo necesario para editar vídeos hablados. Seguro de repetir.
set -e
cd "$(dirname "$0")"
paso() { echo; echo "→ $1"; }

[ "$(uname -s)" = "Darwin" ] || { echo "Este editor solo funciona en Mac."; exit 1; }
[ "$(uname -m)" = "arm64" ] || { echo "Hace falta un Mac con chip Apple (M1 o superior): la transcripción usa mlx-whisper."; exit 1; }

paso "Herramientas de línea de comandos de Apple (Swift)"
if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install || true
  echo "Se ha abierto una ventana de Apple: acepta, espera a que termine y vuelve a ejecutar ./instalar.sh"
  exit 1
fi

# Solo se necesita Homebrew si falta algo. Pide la contraseña del Mac: hay que ejecutar este script en la app Terminal.
PY=""
for v in python3.12 python3.13 python3.11; do command -v $v >/dev/null 2>&1 && PY=$(command -v $v) && break; done
[ -z "$PY" ] && [ -x /opt/homebrew/bin/python3.12 ] && PY=/opt/homebrew/bin/python3.12
hace_falta_brew=0
command -v ffmpeg >/dev/null 2>&1 || hace_falta_brew=1
command -v node >/dev/null 2>&1 || hace_falta_brew=1
[ -z "$PY" ] && hace_falta_brew=1

if [ $hace_falta_brew = 1 ]; then
  paso "Homebrew (falta ffmpeg, Node o Python)"
  if ! command -v brew >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/brew ]; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  eval "$(/opt/homebrew/bin/brew shellenv)"
  command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
  command -v node >/dev/null 2>&1 || brew install node
  [ -z "$PY" ] && { brew install python@3.12; PY="$(brew --prefix python@3.12)/bin/python3.12"; }
fi
echo "ffmpeg: $(command -v ffmpeg) | node: $(command -v node) | python: $PY"

paso "Entorno de Python (Whisper, Silero)"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet mlx-whisper silero-vad torch numpy

paso "Descargo el modelo Whisper large-v3 (unos 3 GB, solo la primera vez)"
.venv/bin/python -I -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-mlx')"

paso "Remotion (npm)"
npm ci --loglevel=error

paso "Detección de caras y silueta (Swift)"
swiftc -O -suppress-warnings herramientas/caras.swift -o herramientas/caras
swiftc -O -suppress-warnings herramientas/silueta.swift -o herramientas/silueta

paso "Compruebo que todo responde"
ffmpeg -version | head -1
.venv/bin/python -I -c "import mlx_whisper, silero_vad, torch, numpy; print('Python OK')"
npx remotion versions 2>/dev/null | head -2 || true
[ -x herramientas/caras ] && echo "Caras OK"

echo
echo "Listo. Abre Claude Code en esta carpeta y escribe:  /editar ruta-del-vídeo.mov"
