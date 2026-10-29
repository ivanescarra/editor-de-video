"""Hoja de revisión: fotogramas de un vídeo en los segundos dados, en una cuadrícula.

Uso: python hoja.py <video> <salida.jpg> <seg1> <seg2> ...   (máximo 6 por fila)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

video, salida, tiempos = sys.argv[1], sys.argv[2], [float(t) for t in sys.argv[3:]]
with tempfile.TemporaryDirectory() as tmp:
    fotos = []
    for i, t in enumerate(tiempos):
        f = Path(tmp) / f"{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", video, "-frames:v", "1",
                        "-vf", f"scale=270:480,drawtext=text='{t:.1f}s':x=8:y=8:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6",
                        str(f)], check=True, stdin=subprocess.DEVNULL)
        fotos.append(f)
    n = len(fotos)
    disp = "|".join(f"{(k % 6) * 270}_{(k // 6) * 480}" for k in range(n))
    entradas = sum([["-i", str(f)] for f in fotos], [])
    filtro = "".join(f"[{k}:v]" for k in range(n)) + (f"xstack=inputs={n}:layout={disp}:fill=black" if n > 1 else "null")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *entradas, "-filter_complex", filtro, "-update", "1", salida],
                   check=True, stdin=subprocess.DEVNULL)
print(salida)
