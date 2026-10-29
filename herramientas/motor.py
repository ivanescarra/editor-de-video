"""Motor de voz: transcripción palabra a palabra y detección de tramos con voz.

Elige solo según el Mac:
- Chip Apple (M1 o superior): mlx-whisper large-v3 + Silero (torch). Rápido y el más preciso.
- Mac Intel: faster-whisper (CPU) + el Silero ONNX que ya trae faster-whisper. No usa torch.
  Modelo por defecto «medium»; se cambia con la variable MODELO_WHISPER_CPU (small, medium, large-v3).
Se puede forzar con MOTOR=apple o MOTOR=cpu.
"""
import os
import platform
import wave

import numpy as np

MODELO_APPLE = "mlx-community/whisper-large-v3-mlx"
MODELO_CPU = os.environ.get("MODELO_WHISPER_CPU", "medium")


def nombre():
    forzado = os.environ.get("MOTOR", "").lower()
    if forzado in ("apple", "cpu"):
        return forzado
    return "apple" if platform.machine() == "arm64" else "cpu"


def descripcion():
    return "Whisper large-v3 (chip Apple)" if nombre() == "apple" else f"Whisper {MODELO_CPU} (CPU, Mac Intel)"


def _leer_wav(ruta):
    with wave.open(str(ruta)) as f:
        return np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def tramos_voz(ruta_wav):
    """Lista de {'start','end'} en segundos con voz. El wav es mono a 16 kHz."""
    audio = _leer_wav(ruta_wav)
    if nombre() == "apple":
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad
        return get_speech_timestamps(torch.from_numpy(audio), load_silero_vad(), sampling_rate=16000,
                                     return_seconds=True, min_silence_duration_ms=250, speech_pad_ms=60)
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    trozos = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=250, speech_pad_ms=60))
    return [{"start": t["start"] / 16000, "end": t["end"] / 16000} for t in trozos]


_modelo_cpu = None


def transcribir(ruta_wav, pista=None):
    """Transcribe en español con palabras y su segundo. Devuelve {'text', 'segments': [{'words': [...]}]}
    con las palabras como {'word', 'start', 'end', 'probability'} (el mismo formato de mlx-whisper)."""
    if nombre() == "apple":
        import mlx_whisper
        extra = {"initial_prompt": pista} if pista else {}
        return mlx_whisper.transcribe(str(ruta_wav), path_or_hf_repo=MODELO_APPLE, language="es",
                                      word_timestamps=True, condition_on_previous_text=False, **extra)
    global _modelo_cpu
    if _modelo_cpu is None:
        from faster_whisper import WhisperModel
        _modelo_cpu = WhisperModel(MODELO_CPU, device="cpu", compute_type="int8")
    # se le pasa el audio ya leído: así no depende de la librería «av», que cambia entre versiones
    segs, _ = _modelo_cpu.transcribe(_leer_wav(ruta_wav), language="es", word_timestamps=True,
                                     condition_on_previous_text=False, initial_prompt=pista, vad_filter=False)
    segmentos = [{"words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                            for w in (s.words or [])], "text": s.text} for s in segs]
    return {"text": "".join(s["text"] for s in segmentos), "segments": segmentos}
