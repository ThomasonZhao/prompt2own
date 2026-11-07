"""Speech service for manim-voiceover.

Provider order (as specified): OpenAI TTS if OPENAI_API_KEY is set, else ElevenLabs if
ELEVENLABS_API_KEY is set, else local Kokoro (hexgrad/Kokoro-82M). Audio is cached in
demo/cache/voice/ keyed by (provider, voice, speed, spoken text), so rebuilds are free.

Subtitles always use the written text; only the audio uses `speakable()`, a small
pronunciation map for names TTS engines mangle (PoC, S1..S4, function names).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
from manim_voiceover.helper import remove_bookmarks, wav2mp3
from manim_voiceover.services.base import SpeechService

CACHE = Path(__file__).resolve().parent / "cache" / "voice"

KOKORO_VOICE = "af_heart"
KOKORO_SPEED = 1.1
KOKORO_SR = 24000

SAY = [
    (r"\bPrompt2Own\b", "Prompt to Own"),
    (r"\bCyberGym-E2E\b", "CyberGym E to E"),
    (r"\bPoC\b", "P O C"),
    (r"\bGLM\b", "G L M"),
    (r"\bS([1-4])\b", lambda m: "S " + "one two three four".split()[int(m.group(1)) - 1]),
    (r"\bspng_decode_image\b", "S P N G decode image"),
    (r"\bvalidate_past_idat\b", "validate past I-DAT"),
    (r"\blibspng\b", "lib S P N G"),
    (r"\bhtslib\b", "H T S lib"),
    (r"\bAddressSanitizer\b", "Address Sanitizer"),
    (r"\bSEGV\b", "segfault"),
    (r"\bOpus 4\.5\b", "Opus four point five"),
    (r"\b1\.00\b", "one point oh oh"),
    (r"(?<![\d.])0\.(\d)(\d)\b", lambda m: f"point {m.group(1)} {m.group(2)}"),
]


def speakable(text: str) -> str:
    for pat, rep in SAY:
        text = re.sub(pat, rep, text)
    return text


def provider() -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    return "kokoro"


class KokoroService(SpeechService):
    """Local Kokoro TTS. Writes mp3 (manim-voiceover measures duration with an mp3 parser)."""

    _pipe = None

    def __init__(self, voice: str = KOKORO_VOICE, speed: float = KOKORO_SPEED, **kw):
        CACHE.mkdir(parents=True, exist_ok=True)
        super().__init__(cache_dir=str(CACHE), **kw)
        self.cache_dir = CACHE
        self.voice, self.speed = voice, speed

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kw) -> dict:
        cache_dir = Path(cache_dir or self.cache_dir)
        spoken = speakable(remove_bookmarks(text))
        input_data = {"input_text": spoken, "service": "kokoro-0.9.4", "voice": self.voice,
                      "speed": self.speed}
        hit = self.get_cached_result(input_data, cache_dir)
        if hit is not None and (cache_dir / hit["original_audio"]).exists():
            return hit
        base = self.get_audio_basename(input_data)
        import soundfile as sf
        if KokoroService._pipe is None:
            from kokoro import KPipeline
            KokoroService._pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        chunks = [np.asarray(a) for _, _, a in KokoroService._pipe(spoken, voice=self.voice,
                                                                  speed=self.speed)]
        audio = np.concatenate(chunks + [np.zeros(int(0.25 * KOKORO_SR), dtype=np.float32)])
        wav = cache_dir / f"{base}.wav"
        sf.write(wav, audio, KOKORO_SR)
        wav2mp3(str(wav), str(cache_dir / f"{base}.mp3"))
        return {"input_text": text, "input_data": input_data, "original_audio": f"{base}.mp3"}


def make_service() -> SpeechService:
    p = provider()
    if p == "openai":
        from manim_voiceover.services.openai import OpenAIService
        return OpenAIService(voice="sage", model="gpt-4o-mini-tts", cache_dir=str(CACHE))
    if p == "elevenlabs":
        from manim_voiceover.services.elevenlabs import ElevenLabsService
        return ElevenLabsService(voice_name="Rachel", cache_dir=str(CACHE))
    return KokoroService()
