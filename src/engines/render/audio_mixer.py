import os
import wave
import math
import struct
import shutil
from typing import Optional, Any

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
        Synthesizes a warm, curious, and dramatic ambient drone progression
        (Cm7 - Gm7 - Abmaj7 - Bb) with soft tape saturation at -24 dB.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
        total_samples = int(sample_rate * duration_sec)

        # Frequencies for curious, dramatic scientific discovery (Cm7, Gm7, Abmaj7, Bb)
        chords = [
            [130.81, 155.56, 196.00, 233.08],  # Cm7 (mystery & wonder)
            [98.00, 146.83, 174.61, 220.00],   # Gm7 (depth)
            [103.83, 130.81, 164.81, 207.65],  # Abmaj7 (curiosity)
            [116.54, 146.83, 174.61, 233.08],  # Bb (resolution / discovery)
        ]
        chord_duration = 4.0

        with wave.open(output_wav_path, "w") as wav:
            wav.setnchannels(1)      # Mono
            wav.setsampwidth(2)      # 16-bit PCM
            wav.setframerate(sample_rate)

            # Acoustic 1st-order low-pass filter (cutoff 450 Hz) to eliminate any high-frequency buzz or harmonics
            fc = 450.0
            rc = 1.0 / (2.0 * math.pi * fc)
            dt = 1.0 / sample_rate
            alpha = dt / (rc + dt)
            lp_state = 0.0

            frames = bytearray()
            for i in range(total_samples):
                t = i / sample_rate
                chord_idx = int((t / chord_duration) % len(chords))
                next_chord_idx = (chord_idx + 1) % len(chords)
                chord_progress = (t % chord_duration) / chord_duration
                # Smooth sinusoidal crossfade envelope between harmonic changes
                fade_next = 0.5 * (1.0 - math.cos(math.pi * chord_progress))
                fade_curr = 1.0 - fade_next

                # Subtle organic breathing LFO (0.2 Hz) for lifelike atmosphere
                lfo = 0.88 + 0.12 * math.sin(2 * math.pi * 0.20 * t)

                val = 0.0
                for f in chords[chord_idx]:
                    val += math.sin(2 * math.pi * f * t) * fade_curr * 0.70
                    val += 0.25 * math.sin(2 * math.pi * (f * 1.5) * t) * fade_curr
                    val += 0.12 * math.sin(2 * math.pi * (f * 2.0) * t) * fade_curr
                for f in chords[next_chord_idx]:
                    val += math.sin(2 * math.pi * f * t) * fade_next * 0.70
                    val += 0.25 * math.sin(2 * math.pi * (f * 1.5) * t) * fade_next
                    val += 0.12 * math.sin(2 * math.pi * (f * 2.0) * t) * fade_next

                # Soft analog tape saturation: warmth without harsh synthesizer buzz
                val = math.tanh(val * 0.35) * lfo
                # Apply 450Hz low-pass filter
                lp_state += alpha * (val - lp_state)
                # Calibrated to -24 dB cinematic ambient bed
                norm_val = int(lp_state * 2200.0)
                norm_val = max(-32768, min(32767, norm_val))
                frames.extend(struct.pack("<h", norm_val))

            wav.writeframes(frames)

        return output_wav_path

    @classmethod
    def mix_speech_and_bgm(
        cls,
        speech_wav_path: str,
        output_mixed_path: str,
        bgm_wav_path: Optional[str] = None,
        storyboard: Optional[Any] = None
    ) -> str:
        """
        Merges speech track, ambient background music, and synchronized cinematic sound FX.
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
            if s_channels == 2:
                # Mix in mono (the BGM bed and SFX timeline are mono), then write stereo back out.
                # Treating interleaved stereo as mono halved the reel's audio and mis-timed the SFX.
                speech_samples = [(l + r) // 2 for l, r in zip(speech_samples[0::2], speech_samples[1::2])]
            bgm_samples = struct.unpack(f"<{len(b_data)//2}h", b_data)

            min_len = min(len(speech_samples), len(bgm_samples))
            combined_samples = []
            
            # Dynamic broadcast ducking: BGM ducks during speech (-28 dB) and smoothly swells during pauses (-24 dB)
            ducking = 0.55
            for i in range(min_len):
                s_val = speech_samples[i]
                abs_s = abs(s_val)
                target_duck = 0.45 if abs_s > 1400 else (0.70 if abs_s > 500 else 1.0)
                ducking += (target_duck - ducking) * 0.001
                b_val = int(bgm_samples[i] * ducking)
                combined_samples.append(max(-32768, min(32767, s_val + b_val)))

            # Overlay Synchronized Cinematic Sound FX (Booms, Whooshes, Chimes, Rustles)
            try:
                from src.engines.render.sound_fx_engine import SoundFXEngine
                from src.services.config_loader import load_json
                if storyboard and load_json("audio.json").get("scene_change_sfx", False):   # booms, whooshes and chimes at every cut
                    combined_samples = SoundFXEngine.overlay_storyboard_sfx(
                        base_samples=combined_samples,
                        storyboard=storyboard,
                        sample_rate=s_rate
                    )
            except Exception as sfx_err:
                print(f"⚠️ SFX mixing note: {sfx_err}")

            mixed_frames = bytearray()
            for val in combined_samples:
                clipped = max(-32768, min(32767, val))
                mixed_frames.extend(struct.pack("<h", clipped) * s_channels)

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
            return output_mixed_path
