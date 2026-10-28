import os
import asyncio
import wave
import struct
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel

from src.core.config import settings
from src.models.schemas import ReelGenerationTier
from src.engines.tts.phonetic_normalizer import AcousticTextNormalizer

class WordTimestamp(BaseModel):
    word: str
    start_sec: float
    end_sec: float

class BaseTTSEngine(ABC):
    @abstractmethod
    def synthesize(
        self,
        text: str,
        output_audio_path: str,
        voice: Optional[str] = None
    ) -> List[WordTimestamp]:
        """Synthesizes speech to an audio file and returns word timestamps."""
        pass

class EdgeTTSEngine(BaseTTSEngine):
    """
    Microsoft Azure Neural TTS (via edge-tts).
    100% Free, high fidelity, with native millisecond word boundary events.
    """
    DEFAULT_VOICE = "en-IN-NeerjaNeural"

    def synthesize(
        self,
        text: str,
        output_audio_path: str,
        voice: Optional[str] = None,
        rate: Optional[str] = "+0%",
        pitch: Optional[str] = "+0Hz"
    ) -> List[WordTimestamp]:
        import edge_tts
        import shutil
        import subprocess
        import hashlib
        import json
        
        target_voice = voice or settings.DEFAULT_EDGE_TTS_VOICE or self.DEFAULT_VOICE
        # Educational clarity rate (-4% gives ~138 wpm for effortless cognitive processing)
        target_rate = rate if rate and rate != "+0%" else "-4%"
        target_pitch = pitch or "+0Hz"
        os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)

        # 1. Phonetic and Acoustic Text Normalization (expands physics symbols, units, equations, and adds breath pauses)
        speech_text = AcousticTextNormalizer.normalize_for_speech(text)
        if not speech_text:
            speech_text = text

        # 2. Content-Addressed Audio Cache Lookup
        cache_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "cache", "tts_audio")
        os.makedirs(cache_dir, exist_ok=True)
        cache_key = hashlib.sha256(f"{speech_text.strip()}|{target_voice}|{target_rate}|{target_pitch}".encode("utf-8")).hexdigest()[:24]
        cache_audio_path = os.path.join(cache_dir, f"{cache_key}.wav")
        cache_meta_path = os.path.join(cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_audio_path) and os.path.getsize(cache_audio_path) > 1000 and os.path.exists(cache_meta_path):
            try:
                with open(cache_meta_path, "r", encoding="utf-8") as f_meta:
                    cached_words_data = json.load(f_meta)
                words = [WordTimestamp(**w) for w in cached_words_data]
                shutil.copyfile(cache_audio_path, output_audio_path)
                print(f"✨ [Audio Cache HIT] ({cache_key}): Reused cached TTS audio ({os.path.getsize(output_audio_path)} bytes) in 1ms.")
                return words
            except Exception as e_cache:
                print(f"⚠️ [Audio Cache Read Warning] {e_cache}. Proceeding with fresh synthesis.")
        
        words: List[WordTimestamp] = []
        audio_bytes = bytearray()

        async def _run():
            communicate = edge_tts.Communicate(
                text=speech_text,
                voice=target_voice,
                rate=target_rate,
                pitch=target_pitch
            )
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    offset_ticks = chunk.get("offset", 0)
                    duration_ticks = chunk.get("duration", 0)
                    word_text = chunk.get("text", "")
                    
                    # edge-tts ticks are in 100-nanosecond units (1 sec = 10,000,000 ticks)
                    start_sec = offset_ticks / 10_000_000.0
                    end_sec = (offset_ticks + duration_ticks) / 10_000_000.0
                    words.append(WordTimestamp(
                        word=word_text,
                        start_sec=round(start_sec, 3),
                        end_sec=round(end_sec, 3)
                    ))

        try:
            # Run async edge-tts in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            if loop.is_running():
                # Nested in running loop (e.g. inside FastAPI)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(_run()))
                    future.result(timeout=25)
            else:
                loop.run_until_complete(_run())

            # Write audio to disk: Transcode to true RIFF PCM WAV if path ends with .wav
            if output_audio_path.lower().endswith(".wav"):
                mp3_temp = output_audio_path + ".temp.mp3"
                with open(mp3_temp, "wb") as f:
                    f.write(audio_bytes)
                
                ffmpeg_bin = (
                    shutil.which("ffmpeg")
                    or "/opt/homebrew/bin/ffmpeg"
                    or "/usr/local/bin/ffmpeg"
                    or "/usr/bin/ffmpeg"
                )
                # Studio vocal mastering:
                # 1. Resample to 44.1kHz first to place Nyquist at 22.05kHz (prevents edge-tts 24kHz boundary ringing)
                # 2. 80Hz highpass cuts proximity rumble
                # 3. 400Hz EQ scoops boxy mid-mud
                # 4. 3.2kHz boost enhances consonant articulation (t, k, p, d, s)
                # 5. 7.2kHz notch softens harsh sibilants (de-essing)
                # 6. 9.5kHz lowpass brickwalls all ultrasonic/high-frequency digital whistles permanently
                # 7. Optical compressor levels dynamic range smoothly
                af_mastering = (
                    "aformat=sample_rates=44100,"
                    "highpass=f=80,"
                    "equalizer=f=400:t=q:w=1.2:g=-1.8,"
                    "equalizer=f=3200:t=q:w=1.4:g=3.2,"
                    "equalizer=f=7200:t=q:w=2.0:g=-3.0,"
                    "lowpass=f=9500,"
                    "acompressor=threshold=-18dB:ratio=2.8:attack=12:release=90:makeup=2.0dB"
                )
                conv_cmd = [
                    ffmpeg_bin, "-y",
                    "-i", mp3_temp,
                    "-af", af_mastering,
                    "-ar", "44100",
                    "-ac", "2",
                    "-c:a", "pcm_s16le",
                    output_audio_path
                ]
                res = subprocess.run(conv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(mp3_temp):
                    os.remove(mp3_temp)
                if res.returncode != 0:
                    with open(output_audio_path, "wb") as f:
                        f.write(audio_bytes)
            else:
                with open(output_audio_path, "wb") as f:
                    f.write(audio_bytes)

            # If word boundaries were sparse or empty, synthesize synthetic timestamps from total length
            if not words:
                words = MockTTSEngine.calculate_linear_word_timestamps(text, output_audio_path)

            # Persist to Content-Addressed TTS Cache
            try:
                shutil.copyfile(output_audio_path, cache_audio_path)
                dump_words = [w.model_dump() if hasattr(w, "model_dump") else w.dict() for w in words]
                with open(cache_meta_path, "w", encoding="utf-8") as f_meta:
                    json.dump(dump_words, f_meta)
                print(f"💾 [Audio Cache Saved] ({cache_key}): Cached {len(words)} word timestamps.")
            except Exception as e_save:
                print(f"⚠️ [Audio Cache Write Warning] {e_save}")

            return words

        except Exception as e:
            print(f"⚠️ EdgeTTS synthesis failed: {e}. Falling back to synthetic audio generator...")
            return MockTTSEngine().synthesize(text, output_audio_path, voice)

class ElevenLabsEngine(BaseTTSEngine):
    """
    ElevenLabs Neural Voice API (for Premium Tier).
    Ultra-expressive, cinematic human emotion with timestamp alignment.
    """
    def synthesize(
        self,
        text: str,
        output_audio_path: str,
        voice: Optional[str] = None
    ) -> List[WordTimestamp]:
        if not settings.ELEVENLABS_API_KEY:
            print("⚠️ ElevenLabs API key not set. Falling back to EdgeTTS...")
            return EdgeTTSEngine().synthesize(text, output_audio_path, voice)

        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            voice_id = voice or settings.DEFAULT_ELEVENLABS_VOICE_ID

            response = client.text_to_speech.convert_with_timestamps(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2"
            )

            # Write audio
            os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
            import base64
            audio_bytes = base64.b64decode(response.audio_base64)
            with open(output_audio_path, "wb") as f:
                f.write(audio_bytes)

            # Parse alignment timestamps
            words = []
            if hasattr(response, "alignment") and response.alignment:
                chars = response.alignment.characters
                starts = response.alignment.character_start_times_seconds
                ends = response.alignment.character_end_times_seconds
                
                # Group characters into words
                current_word = []
                w_start = 0.0
                for i, char in enumerate(chars):
                    if char.isspace() or i == len(chars) - 1:
                        if not char.isspace():
                            current_word.append(char)
                        if current_word:
                            w_text = "".join(current_word)
                            w_end = ends[i]
                            words.append(WordTimestamp(word=w_text, start_sec=w_start, end_sec=w_end))
                            current_word = []
                    else:
                        if not current_word:
                            w_start = starts[i]
                        current_word.append(char)

            if not words:
                words = MockTTSEngine.calculate_linear_word_timestamps(text, output_audio_path)
            return words

        except Exception as e:
            print(f"⚠️ ElevenLabs API failed: {e}. Falling back to EdgeTTS...")
            return EdgeTTSEngine().synthesize(text, output_audio_path, voice)

class GeminiTTSEngine(BaseTTSEngine):
    """Premium narration voice (Gemini TTS over REST). Spend goes through the reel's ledger; any failure falls back to EdgeTTS.

    The API returns audio without word timings, so timings are spread over the real duration in proportion to word length.
    """

    def __init__(self, ledger=None, transport=None):
        self.ledger, self.transport = ledger, transport

    @staticmethod
    def _weighted_timestamps(text: str, duration: float, lead: float = 0.15) -> List[WordTimestamp]:
        words = text.split()
        if not words:
            return []
        weights = [len(w.strip(".,!?;:")) + 2 for w in words]
        span = max(0.5, duration - lead); total = sum(weights); out, t = [], lead
        for w, wt in zip(words, weights):
            d = span * wt / total
            out.append(WordTimestamp(word=w, start_sec=round(t, 3), end_sec=round(t + d * 0.92, 3))); t += d
        return out

    def synthesize(self, text: str, output_audio_path: str, voice: Optional[str] = None, **_: object) -> List[WordTimestamp]:
        import base64
        from src.services.config_loader import load_json
        cfg = load_json("premium.json")["voice"]
        speech_text = AcousticTextNormalizer.normalize_for_speech(text) or text
        try:
            key = settings.GEMINI_API_KEY
            if not key and not self.transport:
                raise RuntimeError("GEMINI_API_KEY is not set")
            est_seconds = max(1.0, len(speech_text.split()) / 2.4)
            est = cfg["price_per_10s_usd"] * est_seconds / 10
            token = self.ledger.reserve("tts", cfg["model"], est, "narration") if self.ledger else None
            voice_name = voice if voice and "Neural" not in voice else cfg["voice_name"]
            body = {"contents": [{"parts": [{"text": speech_text}]}],
                    "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}}}}
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
            try:
                if self.transport:
                    status, payload = self.transport(url, body)
                else:
                    import httpx
                    from src.services.media.usage import check_live
                    check_live("Gemini TTS")
                    r = httpx.post(url, json=body, headers={"x-goog-api-key": key}, timeout=180)
                    status, payload = r.status_code, (r.json() if r.content else {})
                if status != 200:
                    raise RuntimeError(f"Gemini TTS returned {status}: {((payload or {}).get('error') or {}).get('message', '')[:120]}")
                part = next((p for p in (((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []) if p.get("inlineData") or p.get("inline_data")), None)
                if not part:
                    raise RuntimeError("Gemini TTS returned no audio")
                pcm = base64.b64decode((part.get("inlineData") or part.get("inline_data"))["data"])
            except Exception as exc:
                if token is not None:
                    self.ledger.release(token, str(exc))
                raise
            os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
            with wave.open(output_audio_path, "w") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(cfg["sample_rate"]); wav.writeframes(pcm)
            duration = len(pcm) / 2 / cfg["sample_rate"]
            if token is not None:
                self.ledger.commit(token, cfg["price_per_10s_usd"] * duration / 10, seconds=round(duration, 1))
            return self._weighted_timestamps(speech_text, duration)
        except Exception as e:
            print(f"⚠️ Gemini TTS failed: {e}. Falling back to EdgeTTS...")
            return EdgeTTSEngine().synthesize(text, output_audio_path)


class MockTTSEngine(BaseTTSEngine):
    """
    Offline Mock Audio Generator:
    Generates a valid audio WAV file and computes accurate linear word timestamps
    at 145 wpm conversational pacing. Perfect for offline dev, CI, and fast tests.
    """
    @classmethod
    def calculate_linear_word_timestamps(cls, text: str, audio_path: str) -> List[WordTimestamp]:
        words_raw = text.split()
        # Assume ~145 words per minute = ~2.4 words per second
        sec_per_word = 60.0 / 145.0
        timestamps = []
        cur_time = 0.2  # 200ms lead-in padding
        for w in words_raw:
            dur = max(0.18, len(w) * 0.05 + 0.1)
            timestamps.append(WordTimestamp(
                word=w,
                start_sec=round(cur_time, 3),
                end_sec=round(cur_time + dur, 3)
            ))
            cur_time += dur + 0.04
        return timestamps

    def synthesize(
        self,
        text: str,
        output_audio_path: str,
        voice: Optional[str] = None
    ) -> List[WordTimestamp]:
        os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
        timestamps = self.calculate_linear_word_timestamps(text, output_audio_path)
        total_duration = timestamps[-1].end_sec + 0.5 if timestamps else 5.0
        
        # Generate a clean audio WAV file
        sample_rate = 24000
        total_samples = int(sample_rate * total_duration)
        
        # Write clean WAV audio file
        wav_path = output_audio_path if output_audio_path.endswith(".wav") else output_audio_path.rsplit(".", 1)[0] + ".wav"
        with wave.open(wav_path, "w") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            # Write subtle ambient silence / 440Hz warm pad
            audio_frames = bytearray()
            for i in range(total_samples):
                # Low subtle tone so audio players recognize real audio
                val = int(800 * (i % 50 < 25)) if (i % sample_rate < sample_rate * 0.1) else 0
                audio_frames.extend(struct.pack("<h", val))
            wav_file.writeframes(audio_frames)

        # If MP3 was requested, use wav path or copy
        if output_audio_path.endswith(".mp3"):
            import shutil
            shutil.copyfile(wav_path, output_audio_path)

        return timestamps

class TTSFactory:
    @staticmethod
    def get_engine(tier: ReelGenerationTier = ReelGenerationTier.FREE, ledger=None) -> BaseTTSEngine:
        if tier in (ReelGenerationTier.PREMIUM, ReelGenerationTier.PREMIUM_VIDEO) and settings.GEMINI_API_KEY:
            from src.services.config_loader import load_json
            if load_json("premium.json")["voice"]["provider"] == "gemini_tts":
                return GeminiTTSEngine(ledger=ledger)
        if tier in (ReelGenerationTier.ULTRA, ReelGenerationTier.PREMIUM, ReelGenerationTier.PREMIUM_VIDEO) and settings.ELEVENLABS_API_KEY:
            return ElevenLabsEngine()
        return EdgeTTSEngine()
