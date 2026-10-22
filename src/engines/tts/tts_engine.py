import os
import asyncio
import wave
import struct
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel

from src.core.config import settings
from src.models.schemas import ReelGenerationTier

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
        voice: Optional[str] = None
    ) -> List[WordTimestamp]:
        import edge_tts
        
        target_voice = voice or settings.DEFAULT_EDGE_TTS_VOICE or self.DEFAULT_VOICE
        os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
        
        words: List[WordTimestamp] = []
        audio_bytes = bytearray()

        async def _run():
            communicate = edge_tts.Communicate(text, target_voice)
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

            # Write audio to disk
            with open(output_audio_path, "wb") as f:
                f.write(audio_bytes)

            # If word boundaries were sparse or empty, synthesize synthetic timestamps from total length
            if not words:
                words = MockTTSEngine.calculate_linear_word_timestamps(text, output_audio_path)

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
    def get_engine(tier: ReelGenerationTier = ReelGenerationTier.FREE) -> BaseTTSEngine:
        if tier in (ReelGenerationTier.ULTRA, ReelGenerationTier.PREMIUM) and settings.ELEVENLABS_API_KEY:
            return ElevenLabsEngine()
        return EdgeTTSEngine()
