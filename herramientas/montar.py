"""Monta un vídeo a partir de su receta.

Uso:
  python montar.py proponer <carpeta_trabajo>   → escribe receta.json inicial a partir del análisis
  python montar.py afinar <carpeta_trabajo>     → rehace los cortes finos a partir del «guion» de la receta
  python montar.py borrador <carpeta_trabajo>   → borrador rápido (mitad de resolución, sin volumen)
  python montar.py final <carpeta_trabajo>      → render final listo para Instagram

Todos los tiempos de la receta van en segundos del vídeo ORIGINAL. Este script los
convierte al vídeo final (quitando cortes y aplicando la velocidad).
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent.parent
MULETILLAS = {"eh", "em", "emm", "ehm", "mm", "mmm", "ah", "eeh", "hmm"}


def es_muletilla(p):
    return re.sub(r"[^\wáéíóúñ]", "", p["texto"].lower()) in MULETILLAS

ESTILO_DEFECTO = {"acento": "#F5C542", "subtitulosY": 0.68, "subtitulosYEscena": 0.88, "tamanoSubtitulos": 70,
                  "mayusculas": False}


def leer(p):
    return json.loads(Path(p).read_text())


def escribir(p, datos):
    Path(p).write_text(json.dumps(datos, indent=1, ensure_ascii=False))


def paso(msg):
    print(f"→ {msg}", flush=True)


# ---------- proponer ----------

def unir(intervalos, hueco):
    out = []
    for a, b in sorted(intervalos):
        if out and a - out[-1][1] <= hueco:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def energia(trabajo: Path):
    """Volumen del audio en ventanas de 10 ms, para cortar en el punto más silencioso."""
    import wave

    import numpy as np
    with wave.open(str(trabajo / "audio.wav")) as f:
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(x) // 160
    return np.sqrt((x[: n * 160].reshape(n, 160) ** 2).mean(axis=1) + 1e-12)


def niveles_db(trabajo: Path):
    """Volumen del audio en dB cada 10 ms."""
    import numpy as np
    return 20 * np.log10(energia(trabajo))


def tramos_silencio(db, umbral, desde, hasta, minimo=0.04):
    """Silencios reales (por debajo del umbral al menos `minimo` s) entre dos segundos: [(ini, fin)]."""
    out, i, fin_i = [], max(0, int(desde * 100)), min(len(db), int(hasta * 100))
    while i < fin_i:
        if db[i] < umbral:
            j = i
            while j < len(db) and db[j] < umbral:
                j += 1
            if (j - i) / 100 >= minimo:
                out.append((i / 100, j / 100))
            i = j
        i += 1
    return out


def borde_inicio(db, umbral, t, limite):
    """Dónde empezar un tramo cuya primera palabra arranca hacia t.

    Busca hacia atrás (hasta 0,5 s, sin pasar de `limite`) el silencio real más cercano y empieza
    0,06 s antes de que acabe. Si no lo hay, corta en el punto de menos energía muy cerca de t,
    nunca dentro de la sílaba (el cierre de una «c» o una «p» sirve). Devuelve (segundo, limpio).
    """
    # vale el silencio que contiene t (Whisper a veces marca el arranque antes de tiempo)
    sil = [s for s in tramos_silencio(db, umbral, max(limite, t - 0.5), t + 0.06) if s[1] <= t + 0.6]
    if sil:
        ini, fin = sil[-1]
        return max(ini, fin - 0.06), True
    a, b = max(limite, t - 0.10), t + 0.03
    i0 = min(max(int(a * 100), 0), len(db) - 1)
    i1 = min(max(i0 + 1, int(b * 100)), len(db))
    return (i0 + int(db[i0:i1].argmin())) / 100, False


def borde_fin(db, umbral, t, limite, fin_frase):
    """Dónde acabar un tramo cuya última palabra termina hacia t. Deja caer la palabra entera:
    busca hacia delante el primer silencio real y deja 0,12 s de cola (0,2 s si acaba frase)."""
    # vale el silencio que contiene t (Whisper a veces alarga la palabra más de la cuenta)
    sil = [s for s in tramos_silencio(db, umbral, t - 0.6, min(limite, t + 0.5)) if s[1] >= t - 0.06]
    if sil:
        ini, fin = sil[0]
        return min(fin, ini + (0.20 if fin_frase else 0.12)), True
    a, b = t - 0.03, min(limite, t + 0.12)
    i0 = min(max(int(a * 100), 0), len(db) - 1)
    i1 = min(max(i0 + 1, int(b * 100)), len(db))
    return (i0 + int(db[i0:i1].argmin())) / 100, False


def afinar(trabajo: Path, guion, hueco_max=0.3):
    """Convierte tramos del guion en cortes finos que no se coman ninguna palabra.

    Primero que se entienda, después quitar lo que sobra:
    - Dentro de cada tramo se quitan los huecos de más de hueco_max entre palabras y los «eh».
    - Todo corte cae en un silencio real del audio. Si no lo hay, en el punto de menos energía
      pegado a la palabra; y si ni así queda limpio, ese hueco no se corta (mejor un «eh» que
      media palabra).
    - Entre frases queda una pausa natural (~0,2 s).
    """
    import numpy as np
    palabras = leer(trabajo / "transcripcion.json")["palabras"]
    db = niveles_db(trabajo)
    umbral = float(np.percentile(db, 10)) + 15  # silencio = hasta 15 dB por encima del ruido de la sala
    piezas = []
    for g in guion:
        if g.get("pausa"):  # silencio de la propia sala para dar aire donde hace falta
            piezas.append([g["inicio"], g["fin"], True, True])
            continue
        def cae(p):  # la palabra es del tramo si su centro cae dentro o al menos el 40 % de ella
            dur = max(p["fin"] - p["inicio"], 0.01)
            solape = min(p["fin"], g["fin"]) - max(p["inicio"], g["inicio"])
            return g["inicio"] <= (p["inicio"] + p["fin"]) / 2 <= g["fin"] or solape >= 0.4 * dur
        dentro = [p for p in palabras if cae(p) and not es_muletilla(p) and p["fin"] - p["inicio"] >= 0.02]
        if not dentro:
            print(f"  aviso: el tramo {g['inicio']}–{g['fin']} no tiene palabras de Whisper; se incluye tal cual")
            piezas.append([g["inicio"], g["fin"], True, True])
            continue
        grupos = [[dentro[0]]]
        for p1, p2 in zip(dentro, dentro[1:]):
            if p2["inicio"] - p1["fin"] > hueco_max:
                grupos.append([])
            grupos[-1].append(p2)
        for k, gr in enumerate(grupos):
            lim_ini = g["inicio"] - 0.25 if k == 0 else grupos[k - 1][-1]["fin"]
            lim_fin = g["fin"] + 0.25 if k == len(grupos) - 1 else grupos[k + 1][0]["inicio"]
            a, limpio_a = borde_inicio(db, umbral, max(gr[0]["inicio"], g["inicio"] - 0.1), lim_ini)
            fin_frase = bool(re.search(r"[.?!]$", gr[-1]["texto"]))
            b, limpio_b = borde_fin(db, umbral, min(gr[-1]["fin"], g["fin"] + 0.1), lim_fin, fin_frase)
            # Bordes comprobados a oído: se respetan tal cual
            if k == 0 and g.get("exacto_inicio"):
                a, limpio_a = g["inicio"], True
            if k == len(grupos) - 1 and g.get("exacto_fin"):
                b, limpio_b = g["fin"], True
            piezas.append([a, b, limpio_a, limpio_b])
    # Un hueco interior que no se puede cortar limpio por ningún lado no se corta: se unen las piezas
    out = []
    for a, b, la, lb in piezas:
        if out and a >= out[-1][0] and (a <= out[-1][1] + 0.02 or (not la and not out[-1][3] and 0 < a - out[-1][1] < 0.8)):
            out[-1][1] = max(out[-1][1], b)
            out[-1][3] = lb
        else:
            out.append([a, b, la, lb])
    # Silencios largos dentro de lo que se queda: se acortan dejando una pausa natural
    final = []
    for a, b, _, _ in out:
        ini = a
        for s0, s1 in tramos_silencio(db, umbral, a + 0.2, b - 0.2, minimo=0.45):
            final.append([ini, s0 + 0.15])
            ini = s1 - 0.10
        final.append([ini, b])
    return [{"inicio": round(a, 3), "fin": round(b, 3)} for a, b in final if b - a > 0.15]


def proponer(trabajo: Path):
    info = leer(trabajo / "info.json")
    voz = leer(trabajo / "voz.json")
    dur = info["duracion"]
    # Guion inicial: todo lo que Silero oye como voz. Claude lo recorta luego quitando tomas malas
    guion = [{"inicio": round(max(0, v["inicio"] - 0.2), 3), "fin": round(min(dur, v["fin"] + 0.2), 3)} for v in voz]
    cortes = afinar(trabajo, guion)

    receta = {
        "version": 1,
        "video": info["video"],
        "velocidad": 1.2,
        "lufs": -14,
        "salida": {"ancho": 1080, "alto": 1920, "fps": 30},
        "hueco_max": 0.3,
        "guion": guion,
        "cortes": cortes,
        "encuadre": {"modo": "auto", "zoom_alterno": True, "zoom": 1.12},
        "titular": None,
        "subtitulos": {"palabras_por_bloque": 3, "resaltar": [], "resaltar_numeros": True,
                       "quitar_puntuacion": True, "correcciones": {}},
        "tarjetas": [],
        "stickers": [],
        "estilo": ESTILO_DEFECTO,
    }
    escribir(trabajo / "receta.json", receta)
    quitado = dur - sum(c["fin"] - c["inicio"] for c in cortes)
    print(f"✓ Receta inicial: {len(cortes)} tramos, se quitan {quitado:.1f} s de silencios")


# ---------- utilidades de tiempo ----------

class Mapa:
    """Convierte segundos del original a segundos del vídeo final."""

    def __init__(self, cortes, vel):
        self.cortes, self.vel = cortes, vel
        self.acum, t = [], 0.0
        for c in cortes:
            self.acum.append(t)
            t += c["fin"] - c["inicio"]
        self.total = t / vel

    def __call__(self, s):
        for c, a in zip(self.cortes, self.acum):
            if s < c["inicio"]:
                return a / self.vel  # cae en un hueco quitado: salta al siguiente tramo
            if s <= c["fin"]:
                return (a + s - c["inicio"]) / self.vel
        return self.total

    def dentro(self, s):
        return any(c["inicio"] <= s <= c["fin"] for c in self.cortes)


def mediana(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


def encuadres(receta, trabajo, info):
    """Un recorte fijo por tramo: los saltos de encuadre caen siempre en un corte."""
    W, H = info["ancho"], info["alto"]
    sw, sh = receta["salida"]["ancho"], receta["salida"]["alto"]
    enc = receta.get("encuadre") or {}
    if isinstance(enc, list):
        return enc
    muestras = leer(trabajo / "caras.json")["muestras"] if (trabajo / "caras.json").exists() else []
    res = []
    for i, c in enumerate(receta["cortes"]):
        caras = [m for m in muestras if "x" in m and c["inicio"] <= m["t"] <= c["fin"]]
        cx = mediana([m["x"] + m["w"] / 2 for m in caras]) or 0.5
        cy = mediana([m["y"] + m["h"] / 2 for m in caras]) or 0.4
        zoom = enc.get("zoom", 1.12) if enc.get("zoom_alterno") and i % 2 == 1 else 1.0
        res.append({"centro_x": round(cx, 3), "centro_y": round(cy, 3), "zoom": zoom})
    return res


def recorte(e, W, H, sw, sh):
    # Mayor rectángulo con la proporción de salida, reducido por el zoom y centrado en la cara
    ratio = sw / sh
    cw, ch = (H * ratio, H) if W / H > ratio else (W, W / ratio)
    cw, ch = cw / e.get("zoom", 1), ch / e.get("zoom", 1)
    x = min(max(e["centro_x"] * W - cw / 2, 0), W - cw)
    y = min(max(e["centro_y"] * H - ch * 0.4, 0), H - ch)  # cara un poco por encima del centro
    par = lambda v: int(v) // 2 * 2
    return par(cw), par(ch), par(x), par(y)


def cara_en_salida(receta, trabajo, info, t):
    """Arriba y abajo de la cara (0-1 del alto del vídeo final) en el segundo t del original."""
    W, H = info["ancho"], info["alto"]
    sw, sh = receta["salida"]["ancho"], receta["salida"]["alto"]
    cortes = receta["cortes"]
    i = next((k for k, c in enumerate(cortes) if t <= c["fin"]), len(cortes) - 1)
    e = encuadres(receta, trabajo, info)[i]
    cw, ch, x, y = recorte(e, W, H, sw, sh)
    c = cortes[i]
    muestras = leer(trabajo / "caras.json")["muestras"] if (trabajo / "caras.json").exists() else []
    caras = [m for m in muestras if "x" in m and c["inicio"] - 0.5 <= m["t"] <= c["fin"] + 0.5]
    if not caras:
        return 0.2, 0.6
    # Se toma la cara más alta y la más baja del tramo, con margen para pelo y barbilla
    arriba = min(m["y"] for m in caras) * H
    abajo = max(m["y"] + m["h"] for m in caras) * H
    arriba -= 0.25 * (abajo - arriba)
    abajo += 0.08 * (abajo - arriba)
    return max(0, (arriba - y) / ch), min(1, (abajo - y) / ch)


def colocar(receta, trabajo, info, estilo):
    """Pone tarjetas y stickers sin posición fija donde no tapen la cara ni los subtítulos."""
    sub_y = estilo["subtitulosY"]
    for t in receta.get("tarjetas", []):
        if t.get("y") is not None or t.get("posicion") == "centro":
            continue
        arriba, abajo = cara_en_salida(receta, trabajo, info, (t["inicio"] + t["fin"]) / 2)
        alto = 0.1 if t.get("subtexto") else 0.065
        if t.get("posicion") != "arriba" and abajo + 0.015 + alto <= sub_y - 0.01:
            t["y"] = round(abajo + 0.015, 3)  # pecho, entre la barbilla y los subtítulos
        else:
            t["y"] = round(max(0.04, arriba - 0.015 - alto), 3)  # encima de la cabeza
    for k in receta.get("stickers", []):
        if k.get("y") is not None:
            continue
        arriba, _ = cara_en_salida(receta, trabajo, info, (k["inicio"] + k["fin"]) / 2)
        k["y"] = round(max(0.06, arriba - 0.04), 3)


# ---------- subtítulos ----------

def bloques_subtitulos(receta, trabajo, mapa):
    cfg = receta.get("subtitulos") or {}
    n = cfg.get("palabras_por_bloque", 3)
    corr = cfg.get("correcciones", {})
    resaltar = {r.lower().strip(".,¡!¿?") for r in cfg.get("resaltar", [])}
    palabras = leer(trabajo / "transcripcion.json")["palabras"]
    sel = []
    for p in palabras:
        if not mapa.dentro((p["inicio"] + p["fin"]) / 2) or es_muletilla(p) or p["fin"] - p["inicio"] < 0.02:
            # las palabras de duración cero son repeticiones fantasma de Whisper
            continue
        texto = corr.get(f"{p['texto']}@{p['inicio']}", corr.get(p["texto"], p["texto"]))
        if not texto.strip():
            continue  # corrección vacía = palabra eliminada de los subtítulos
        corta = bool(re.search(r"[.,;:?!]$", texto))
        if cfg.get("quitar_puntuacion", True):
            texto = texto.rstrip(".,;:")
        limpio = texto.lower().strip("¡!¿?")
        res = limpio in resaltar or (cfg.get("resaltar_numeros", True) and any(ch.isdigit() for ch in texto))
        sel.append({"texto": texto, "inicio": round(mapa(p["inicio"]), 3), "fin": round(mapa(p["fin"]), 3),
                    "resaltar": res, "corta": corta})
    bloques, actual = [], []
    for i, p in enumerate(sel):
        actual.append(p)
        sig = sel[i + 1] if i + 1 < len(sel) else None
        largo = sum(len(x["texto"]) + 1 for x in actual)
        if (not sig or len(actual) >= n or p["corta"] or largo > 18 or sig["inicio"] - p["fin"] > 0.45):
            bloques.append(actual)
            actual = []
    out = []
    for i, b in enumerate(bloques):
        fin = b[-1]["fin"] + 0.25
        if i + 1 < len(bloques):
            fin = min(fin, bloques[i + 1][0]["inicio"])
        out.append({"inicio": b[0]["inicio"], "fin": round(max(fin, b[0]["inicio"] + 0.2), 3),
                    "palabras": [{k: x[k] for k in ("texto", "inicio", "fin", "resaltar")} for x in b]})
    return out


# ---------- montaje ----------

def base(receta, trabajo, info, publico, borrador):
    """FFmpeg: quita lo que no va, reencuadra y acelera. Deja publico/base.mp4

    Cada tramo se corta en su propio archivo (en paralelo) y luego se unen sin recomprimir.
    Con decenas de tramos en una sola orden FFmpeg descuadraba la duración.
    """
    from concurrent.futures import ThreadPoolExecutor
    W, H = info["ancho"], info["alto"]
    sw, sh = receta["salida"]["ancho"], receta["salida"]["alto"]
    if borrador:
        sw, sh = sw // 2, sh // 2
    fps, vel = receta["salida"]["fps"], receta.get("velocidad", 1)
    encs = encuadres(receta, trabajo, info)
    tramos = trabajo / "tramos"
    shutil.rmtree(tramos, ignore_errors=True)
    tramos.mkdir()

    def cortar(i):
        c, e = receta["cortes"][i], encs[i]
        cw, ch, x, y = recorte(e, W, H, receta["salida"]["ancho"], receta["salida"]["alto"])
        d = c["fin"] - c["inicio"]
        # Tiempos en unidad fina antes de acelerar: OBS graba en 1/30 s y al dividir se duplicaban fotogramas
        vf = (f"trim=duration={d:.3f},setpts=PTS-STARTPTS,crop={cw}:{ch}:{x}:{y},scale={sw}:{sh}:flags=lanczos,"
              + ("unsharp=5:5:0.6:5:5:0," if sw / cw > 2.5 else "")  # enfoque si se amplía mucho
              + f"setsar=1,settb=1/90000,setpts=PTS/{vel},fps={fps}")
        af = (f"atrim=duration={d:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.025,"
              f"afade=t=out:st={max(d - 0.025, 0):.3f}:d=0.025,atempo={vel},aresample=48000")
        # -t de salida: sin él FFmpeg rellena el final repitiendo el último fotograma
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{c['inicio']:.3f}",
                        "-i", receta["video"], "-vf", vf, "-af", af, "-t", f"{d / vel:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26" if borrador else "16",
                        "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(tramos / f"{i:03d}.mov")],
                       check=True, stdin=subprocess.DEVNULL)

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(cortar, range(len(receta["cortes"]))))
    lista = tramos / "lista.txt"
    lista.write_text("".join(f"file '{f.name}'\n" for f in sorted(tramos.glob("*.mov"))))
    publico.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(publico / "base.mp4")],
                   check=True, stdin=subprocess.DEVNULL)
    shutil.rmtree(tramos, ignore_errors=True)


def escena(e, mapa):
    """Pasa a tiempos del vídeo final una escena explicativa y todo lo que lleva dentro."""
    m = lambda x: round(mapa(x), 3)
    out = {**e, "inicio": m(e["inicio"]), "fin": m(e["fin"])}
    out["items"] = [{**i, "en": m(i["en"])} for i in e.get("items", [])]
    if "columnas" in e:
        out["columnas"] = [{**c, "en": m(c["en"])} for c in e["columnas"]]
    if "foco" in e:
        out["foco"] = [{**c, "en": m(c["en"])} for c in e["foco"]]
    if e.get("centro"):
        out["centro"] = {**e["centro"], "en": m(e["centro"]["en"])}
    return out


def lufs_de(archivo, desde=0.0, dur=None):
    args = ["ffmpeg", "-hide_banner", "-ss", str(desde)] + (["-t", str(dur)] if dur else []) + [
        "-i", str(archivo), "-af", "loudnorm=print_format=json", "-f", "null", "-"]
    err = subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    return float(json.loads(err[err.rindex("{"):err.rindex("}") + 1])["input_i"])


def mezclar(entrada, voz_de, salida, receta, duracion):
    """Voz a nivel fijo en el objetivo y música a nivel fijo muy por debajo. Sin ducking ni loudnorm
    sobre la mezcla, que bombean. Un limitador solo para que ningún pico pase de −1,5 dB."""
    objetivo = receta.get("lufs", -14)
    mus = receta["musica"]
    voz = lufs_de(voz_de)
    desde = mus.get("desde", 0)
    musica = lufs_de(mus["archivo"], desde, duracion)
    gv = objetivo - voz
    gm = (objetivo - mus.get("db_bajo_voz", 20)) - musica
    fade = max(duracion - 2.5, 0)
    filtro = (f"[1:a]volume={gv:.2f}dB[v];"
              f"[2:a]atrim=start={desde},asetpts=PTS-STARTPTS,volume={gm:.2f}dB,"
              f"afade=t=in:d=1.5,afade=t=out:st={fade:.2f}:d=2.5[m];"
              f"[v][m]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.84:level=false,aresample=48000[a]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(entrada), "-i", str(voz_de),
                    "-stream_loop", "-1", "-i", mus["archivo"],
                    "-filter_complex", filtro, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart", str(salida)], check=True, stdin=subprocess.DEVNULL)
    return voz, musica, gv, gm


def montar(trabajo: Path, borrador: bool):
    t0 = time.time()
    receta = leer(trabajo / "receta.json")
    info = leer(trabajo / "info.json")
    if not Path(receta["video"]).exists():
        sys.exit(f"✗ No encuentro el vídeo original: {receta['video']}")
    vel = receta.get("velocidad", 1)
    mapa = Mapa(receta["cortes"], vel)
    publico = trabajo / "publico"

    paso("FFmpeg: quito silencios, reencuadro y acelero")
    base(receta, trabajo, info, publico, borrador)

    estilo = {**ESTILO_DEFECTO, **receta.get("estilo", {})}
    colocar(receta, trabajo, info, estilo)
    f = lambda o: {**o, "inicio": round(mapa(o["inicio"]), 3), "fin": round(mapa(o["fin"]), 3)}
    props = {
        "video": "base.mp4",
        "duracion": round(mapa.total, 3),
        "ancho": receta["salida"]["ancho"],
        "alto": receta["salida"]["alto"],
        "fps": receta["salida"]["fps"],
        "titular": f(receta["titular"]) if receta.get("titular") else None,
        "subtitulos": bloques_subtitulos(receta, trabajo, mapa),
        "tarjetas": [f(t) for t in receta.get("tarjetas", [])],
        "stickers": [f(s) for s in receta.get("stickers", [])],
        "escenas": [escena(e, mapa) for e in receta.get("escenas", [])],
        "estilo": estilo,
    }
    escribir(trabajo / "props.json", props)

    paso("Remotion: dibujo titular, subtítulos, escenas, tarjetas y stickers")
    salida_remotion = trabajo / ("borrador.mp4" if borrador else "render.mp4")
    cmd = ["npx", "remotion", "render", "src/index.ts", "Edicion", str(salida_remotion),
           f"--props={trabajo / 'props.json'}", f"--public-dir={publico}", "--log=error", "--muted"]
    # Remotion solo dibuja la imagen: al reprocesar el audio de la base se saltaba trozos de voz
    if borrador:
        cmd += ["--scale=0.5", "--crf=28"]  # mitad de resolución: tarda bastante menos
    subprocess.run(cmd, cwd=PROYECTO, check=True)

    if receta.get("musica"):
        paso(f"FFmpeg: voz a {receta.get('lufs', -14)} LUFS y música {receta['musica'].get('db_bajo_voz', 20)} dB por debajo, a nivel fijo")
        destino = trabajo / ("borrador.mp4" if borrador else "final.mp4")
        temporal = trabajo / "sin_musica.mp4"
        salida_remotion.replace(temporal)
        mezclar(temporal, publico / "base.mp4", destino, receta, mapa.total)
        temporal.unlink(missing_ok=True)
        print(f"✓ {'Borrador' if borrador else 'Final'} listo en {time.time() - t0:.0f} s: {destino}  ({mapa.total:.1f} s de vídeo)")
        return

    if borrador:
        mudo = trabajo / "sin_voz.mp4"
        salida_remotion.replace(mudo)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mudo), "-i", str(publico / "base.mp4"),
                        "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        str(salida_remotion)], check=True, stdin=subprocess.DEVNULL)
        mudo.unlink(missing_ok=True)
        print(f"✓ Borrador listo en {time.time() - t0:.0f} s: {salida_remotion}  ({mapa.total:.1f} s de vídeo)")
        return

    paso(f"FFmpeg: volumen a {receta.get('lufs', -14)} LUFS en dos pasadas y archivo final")
    lufs = receta.get("lufs", -14)
    medida = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(publico / "base.mp4"), "-af",
                             f"loudnorm=I={lufs}:TP=-2:LRA=11:print_format=json", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
    m = json.loads(medida[medida.rindex("{"):medida.rindex("}") + 1])
    filtro = (f"loudnorm=I={lufs}:TP=-2:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    final = trabajo / "final.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(salida_remotion), "-i", str(publico / "base.mp4"),
                    "-map", "0:v", "-map", "1:a", "-af", filtro, "-ar", "48000", "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)], check=True)
    (salida_remotion).unlink(missing_ok=True)
    print(f"✓ Final listo en {time.time() - t0:.0f} s: {final}  ({mapa.total:.1f} s de vídeo)")


if __name__ == "__main__":
    orden, carpeta = sys.argv[1], Path(sys.argv[2]).expanduser().resolve()
    if orden == "proponer":
        proponer(carpeta)
    elif orden == "afinar":
        r = leer(carpeta / "receta.json")
        r["cortes"] = afinar(carpeta, r["guion"], r.get("hueco_max", 0.3))
        escribir(carpeta / "receta.json", r)
        print(f"✓ {len(r['cortes'])} cortes finos, {sum(c['fin'] - c['inicio'] for c in r['cortes']):.1f} s de vídeo antes de acelerar")
    elif orden in ("borrador", "final"):
        montar(carpeta, orden == "borrador")
    else:
        sys.exit(__doc__)
