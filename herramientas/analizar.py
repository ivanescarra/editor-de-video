"""Analiza un vídeo: audio, transcripción palabra a palabra, tramos con voz y cara.

Uso: python analizar.py <video> <carpeta_trabajo>
Deja en la carpeta: audio.wav, transcripcion.json, voz.json, caras.json, info.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERRAMIENTAS = Path(__file__).resolve().parent
sys.path.insert(0, str(HERRAMIENTAS))
import motor  # noqa: E402


def paso(msg):
    print(f"→ {msg}", flush=True)


def main():
    video = Path(sys.argv[1]).expanduser().resolve()
    trabajo = Path(sys.argv[2]).expanduser().resolve()
    trabajo.mkdir(parents=True, exist_ok=True)
    audio = trabajo / "audio.wav"

    # Datos básicos del vídeo
    sonda = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
         "-show_format", "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout)
    st = sonda["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    rot = 0
    for sd in st.get("side_data_list", []):
        rot = int(sd.get("rotation", rot))
    rot = int(st.get("tags", {}).get("rotate", rot))
    w, h = st["width"], st["height"]
    if abs(rot) == 90:
        w, h = h, w
    info = {"video": str(video), "ancho": w, "alto": h,
            "fps": round(int(num) / int(den), 3), "duracion": float(sonda["format"]["duration"])}
    (trabajo / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))

    # 1. FFmpeg: audio mono a 16 kHz
    t0 = time.time()
    paso("Saco el audio (FFmpeg)")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vn", "-ac", "1",
                    "-ar", "16000", "-c:a", "pcm_s16le", str(audio)], check=True)

    # 2. Silero: tramos con voz
    paso("Busco los tramos con voz (Silero)")
    tramos = motor.tramos_voz(audio)
    (trabajo / "voz.json").write_text(json.dumps(
        [{"inicio": round(t["start"], 3), "fin": round(t["end"], 3)} for t in tramos], indent=1))

    # 3. Whisper: cada palabra con su segundo, por trozos cortos según los tramos con voz.
    # En una pasada larga Whisper se salta los «eh» y las repeticiones; por trozos los escribe.
    paso(f"Transcribo palabra a palabra ({motor.descripcion()})")
    trozos = []
    for t in tramos:
        if trozos and t["end"] - trozos[-1][0] <= 25:
            trozos[-1][1] = t["end"]
        else:
            trozos.append([t["start"], t["end"]])
    palabras, textos = [], []
    pieza = trabajo / "trozo.wav"
    for ini, fin in trozos:
        ini, fin = max(0, ini - 0.3), fin + 0.3
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{ini:.3f}", "-to", f"{fin:.3f}",
                        "-i", str(audio), str(pieza)], check=True)
        res = motor.transcribir(pieza, pista="Eh, em, mmm, o sea, bueno, eh.")
        textos.append(res["text"].strip())
        for seg in res["segments"]:
            for p in seg.get("words", []):
                palabras.append({"texto": p["word"].strip(), "inicio": round(p["start"] + ini, 3),
                                 "fin": round(p["end"] + ini, 3), "prob": round(p.get("probability", 1), 3)})
    pieza.unlink(missing_ok=True)
    (trabajo / "transcripcion.json").write_text(json.dumps(
        {"texto": " ".join(textos), "palabras": palabras}, indent=1, ensure_ascii=False))

    # 4. Apple Vision: la cara cuadro a cuadro
    paso("Localizo la cara (Apple Vision)")
    subprocess.run([str(HERRAMIENTAS / "caras"), str(video), str(trabajo / "caras.json"), "5"], check=True)

    print(f"✓ Análisis listo en {time.time() - t0:.0f} s: {len(palabras)} palabras, {len(tramos)} tramos con voz")


if __name__ == "__main__":
    main()
