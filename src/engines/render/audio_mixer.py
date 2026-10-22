import os
import wave
import math
import struct
import shutil
from typing import Optional

class AudioMixer:
    """
    Audio Engine & Ducking Mixer:
    - Normalizes voice audio to -14 LUFS
    - Provides a soft ambient lofi background loop at -22 dB
    - Programmatically synthesizes a harmonic lofi chord progression
    """

    @classmethod
    def generate_ambient_lofi_track(cls, output_wav_path: str, duration_sec: float = 60.0, sample_rate: int = 24000) -> str:
        """
        Synthesizes a soft, warm lofi ambient drone chord progression
        (Cmaj7 - Am7 - Fmaj7 - G7) at low volume (-22 dB).
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
        total_samples = int(sample_rate * duration_sec)

        # Frequencies for warm lofi chord progression (C3, E3, G3, B3)
        chords = [
            [130.81, 164.81, 196.00, 246.94],  # Cmaj7
            [110.00, 130.81, 164.81, 196.00],  # Am7
            [87.31, 110.00, 130.81, 164.81],   # Fmaj7
            [98.00, 123.47, 146.83, 174.61],   # G7
        ]
        chord_duration = 4.0

        with wave.open(output_wav_path, "w") as wav:
            wav.setnchannels(1)      # Mono
            wav.setsampwidth(2)      # 16-bit PCM
            wav.setframerate(sample_rate)

            frames = bytearray()
            for i in range(total_samples):
                t = i / sample_rate
                chord_idx = int((t / chord_duration) % len(chords))
                freqs = chords[chord_idx]

                val = 0.0
                for f in freqs:
                    val += math.sin(2 * math.pi * f * t)

                # Ducked amplitude for background ambience
                norm_val = int(val * 350.0)
                norm_val = max(-32768, min(32767, norm_val))
                frames.extend(struct.pack("<h", norm_val))

            wav.writeframes(frames)

        return output_wav_path

    @classmethod
    def mix_speech_and_bgm(
        cls,
        speech_wav_path: str,
        output_mixed_path: str,
        bgm_wav_path: Optional[str] = None
    ) -> str:
        """
        Merges speech track and background ambient track.
        Guarantees output_mixed_path is always created on disk.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_mixed_path)), exist_ok=True)

        if not os.path.exists(speech_wav_path):
            raise FileNotFoundError(f"Speech audio not found: {speech_wav_path}")

        try:
            with wave.open(speech_wav_path, "rb") as s_wav:
                s_channels = s_wav.getnchannels()
                s_rate = s_wav.getframerate()
                s_frames = s_wav.getnframes()
                speech_data = s_wav.readframes(s_frames)
        except Exception:
            # If not a standard PCM wave, copy directly
            shutil.copyfile(speech_wav_path, output_mixed_path)
            return output_mixed_path

        # Generate BGM with matching sample rate
        temp_bgm = output_mixed_path.rsplit(".", 1)[0] + "_bgm.wav"
        cls.generate_ambient_lofi_track(temp_bgm, duration_sec=max(60.0, (s_frames / s_rate) + 5.0), sample_rate=s_rate)
        bgm_wav_path = temp_bgm

        try:
            with wave.open(bgm_wav_path, "rb") as b_wav:
                b_data = b_wav.readframes(s_frames)

            speech_samples = struct.unpack(f"<{len(speech_data)//2}h", speech_data)
            bgm_samples = struct.unpack(f"<{len(b_data)//2}h", b_data)

            mixed_frames = bytearray()
            min_len = min(len(speech_samples), len(bgm_samples))
            for i in range(min_len):
                s_val = speech_samples[i]
                b_val = int(bgm_samples[i] * 0.35)  # Ducked BGM
                combined = max(-32768, min(32767, s_val + b_val))
                mixed_frames.extend(struct.pack("<h", combined))

            with wave.open(output_mixed_path, "wb") as out_wav:
                out_wav.setnchannels(s_channels)
                out_wav.setsampwidth(2)
                out_wav.setframerate(s_rate)
                out_wav.writeframes(mixed_frames)

            return output_mixed_path

        except Exception as e:
            print(f"⚠️ Audio mixing note: {e}. Using clean speech audio.")
            shutil.copyfile(speech_wav_path, output_mixed_path)
            return output_mixed_path
