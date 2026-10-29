"""Revisa cada empalme de una receta: ¿se corta voz? ¿se entiende lo que se dice a los dos lados?

Uso: python revisar_cortes.py <carpeta_trabajo> [--todos]

Para cada empalme:
- mide el volumen justo en el punto de corte (si ahí suena voz, el corte es brusco);
- monta 1,6 s a cada lado, acelerado como en el vídeo, lo transcribe con Whisper y lo compara
  con las palabras que se dicen en el original en esos tramos.
Saca solo los empalmes dudosos (o todos con --todos).
"""
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import montar  # noqa: E402

trabajo = Path(sys.argv[1]).expanduser().resolve()
todos = "--todos" in sys.argv
receta = montar.leer(trabajo / "receta.json")
cortes = receta["cortes"]
vel = receta.get("velocidad", 1)
palabras = [p for p in montar.leer(trabajo / "transcripcion.json")["palabras"]
            if not montar.es_muletilla(p) and p["fin"] - p["inicio"] >= 0.02]
db = montar.niveles_db(trabajo)
import numpy as np  # noqa: E402

umbral = float(np.percentile(db, 10)) + 15
voz = float(np.percentile(db, 50))

import motor  # noqa: E402


def limpia(t):
    return [w for w in re.sub(r"[^\wáéíóúüñ ]", " ", t.lower()).split() if w not in montar.MULETILLAS]


def esperadas(a, b):
    return [p["texto"] for p in palabras if a <= (p["inicio"] + p["fin"]) / 2 <= b]


malos = 0
with tempfile.TemporaryDirectory() as tmp:
    for i in range(len(cortes) - 1):
        c1, c2 = cortes[i], cortes[i + 1]
        # volumen en los 20 ms de cada lado del corte
        fin_db = float(db[max(0, int(c1["fin"] * 100) - 2):int(c1["fin"] * 100)].max())
        ini_db = float(db[int(c2["inicio"] * 100):int(c2["inicio"] * 100) + 2].max())
        brusco = fin_db > voz - 6 or ini_db > voz - 6  # suena casi a volumen de voz justo en el corte
        def en_silencio(desde, hasta, ultimo):
            sil = montar.tramos_silencio(db, umbral, desde, hasta)
            return (sil[-1][1] if ultimo else sil[0][0]) if sil else None
        a1, b1 = (en_silencio(c1["inicio"], c1["fin"] - 1.2, True) or max(c1["inicio"], c1["fin"] - 1.6)), c1["fin"]
        b2 = en_silencio(c2["inicio"] + 1.0, c2["fin"], False) or min(c2["fin"], c2["inicio"] + 1.6)
        a2 = c2["inicio"]
        wav = Path(tmp) / "e.wav"
        filtro = (f"[0:a]atrim={a1}:{b1},asetpts=PTS-STARTPTS,afade=t=out:st={b1 - a1 - 0.025:.3f}:d=0.025[x];"
                  f"[0:a]atrim={a2}:{b2},asetpts=PTS-STARTPTS,afade=t=in:d=0.025[y];"
                  f"[x][y]concat=n=2:v=0:a=1,atempo={vel}[o]")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(trabajo / "audio.wav"), "-filter_complex",
                        filtro, "-map", "[o]", str(wav)], check=True, stdin=subprocess.DEVNULL)
        oido = motor.transcribir(wav)["text"].strip()  # sin pista: con ella se inventa «eh» en las pausas
        quiero = " ".join(esperadas(a1, b1) + esperadas(a2, b2))
        parecido = difflib.SequenceMatcher(None, limpia(quiero), limpia(oido)).ratio()
        dudoso = brusco or parecido < 0.8
        malos += dudoso
        if dudoso or todos:
            marca = "✗" if dudoso else "✓"
            print(f"{marca} empalme {i + 1:2d} en {c1['fin']:.2f}→{c2['inicio']:.2f}  "
                  f"(volumen al cortar {fin_db:.0f}/{ini_db:.0f} dB, voz {voz:.0f})  parecido {parecido:.2f}")
            print(f"    se dice: {quiero}")
            print(f"    se oye:  {oido}")
print(f"{malos} empalmes dudosos de {len(cortes) - 1}")
