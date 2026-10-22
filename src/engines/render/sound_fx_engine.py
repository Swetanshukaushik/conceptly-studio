import math
import random
import wave
import struct
from typing import List, Optional, Dict, Any
from src.models.schemas import SceneBeat, Storyboard

class SoundFXEngine:
    """
    Cinematic Sound FX & Foley Engine (2026):
    Synthesizes and dynamically mixes impact booms, whoosh transitions,
    chimes, paper rustles, and rocket combustion rumbles into the audio track
    synchronized to exact scene beat timestamps.
    """

    @classmethod
    def synthesize_sfx(cls, name: str, sample_rate: int = 24000) -> List[int]:
        """
        Synthesizes high-fidelity 16-bit PCM acoustic sound effects mathematically.
        """
        name_upper = name.upper()

        if "BOOM" in name_upper or "IMPACT" in name_upper or "BASS" in name_upper:
            # Sub-bass cinematic impact drop (66Hz -> 26Hz sub-boom + initial transient punch)
            dur = 1.3
            num_samples = int(sample_rate * dur)
            samples = []
            for i in range(num_samples):
                t = i / sample_rate
                freq = 26.0 + 40.0 * math.exp(-3.5 * t)
                phase = 2 * math.pi * (26.0 * t - (40.0 / 3.5) * (math.exp(-3.5 * t) - 1.0))
                sub = math.sin(phase)
                # Punch transient
                trans = (random.random() * 2.0 - 1.0) * math.exp(-75.0 * t) if t < 0.04 else 0.0
                env = math.exp(-2.4 * t)
                val = (sub * 0.85 + trans * 0.25) * env
                samples.append(int(max(-32767, min(32767, val * 24000))))
            return samples

        elif "WHOOSH" in name_upper or "TRANSITION" in name_upper:
            # Cinematic transitional whoosh (filtered resonant noise sweep)
            dur = 0.7
            num_samples = int(sample_rate * dur)
            samples = []
            for i in range(num_samples):
                t = i / sample_rate
                fc = 280.0 + 2000.0 * math.sin(math.pi * (t / dur))
                env = math.sin(math.pi * (t / dur)) ** 1.8
                noise = (random.random() * 2.0 - 1.0)
                tone = math.sin(2 * math.pi * fc * t)
                val = (noise * 0.65 + tone * 0.35) * env
                samples.append(int(max(-32767, min(32767, val * 17000))))
            return samples

        elif "CHIME" in name_upper or "SPARK" in name_upper or "GLINT" in name_upper:
            # Crystal harmonic glint chimes (A6, C#7, E7, A7 arpeggio)
            dur = 0.95
            num_samples = int(sample_rate * dur)
            samples = []
            freqs = [1760.0, 2217.4, 2637.0, 3520.0]
            for i in range(num_samples):
                t = i / sample_rate
                val = 0.0
                for idx, f in enumerate(freqs):
                    delay = idx * 0.035
                    if t >= delay:
                        dt = t - delay
                        val += math.sin(2 * math.pi * f * dt) * math.exp(-5.0 * dt)
                samples.append(int(max(-32767, min(32767, val * 8500))))
            return samples

        elif "PAPER" in name_upper or "RUSTLE" in name_upper or "PAMPHLET" in name_upper:
            # Fluttering revolutionary paper leaflets / manuscript pages
            dur = 0.65
            num_samples = int(sample_rate * dur)
            samples = []
            for i in range(num_samples):
                t = i / sample_rate
                burst = math.sin(2 * math.pi * 16.0 * t) ** 2
                noise = (random.random() * 2.0 - 1.0) * burst * math.exp(-2.4 * t)
                samples.append(int(max(-32767, min(32767, noise * 13000))))
            return samples

        elif "ROCKET" in name_upper or "RUMBLE" in name_upper or "THRUST" in name_upper:
            # Low rumble rocket combustion roar
            dur = 1.4
            num_samples = int(sample_rate * dur)
            samples = []
            for i in range(num_samples):
                t = i / sample_rate
                rumble = math.sin(2 * math.pi * 42.0 * t) + 0.6 * math.sin(2 * math.pi * 78.0 * t)
                noise = (random.random() * 2.0 - 1.0) * 0.5
                env = math.sin(math.pi * (t / dur)) ** 0.8
                val = (rumble * 0.6 + noise * 0.4) * env
                samples.append(int(max(-32767, min(32767, val * 16000))))
            return samples

        elif "CLICK" in name_upper or "MECHANICAL" in name_upper or "CAMERA" in name_upper:
            # Sharp camera shutter / mechanical relay click
            dur = 0.18
            num_samples = int(sample_rate * dur)
            samples = []
            for i in range(num_samples):
                t = i / sample_rate
                click1 = math.sin(2 * math.pi * 1400.0 * t) * math.exp(-90.0 * t)
                click2 = math.sin(2 * math.pi * 1800.0 * (t - 0.04)) * math.exp(-90.0 * (t - 0.04)) if t >= 0.04 else 0.0
                val = click1 + click2
                samples.append(int(max(-32767, min(32767, val * 20000))))
            return samples

        # Default fallback to gentle whoosh
        return cls.synthesize_sfx("WHOOSH", sample_rate=sample_rate)

    @classmethod
    def overlay_storyboard_sfx(
        cls,
        base_samples: List[int],
        storyboard: Optional[Storyboard],
        sample_rate: int = 24000
    ) -> List[int]:
        """
        Dynamically overlays sound effects onto audio at each scene beat timestamp.
        """
        if not storyboard or not storyboard.scenes:
            return base_samples

        out = list(base_samples)
        total_len = len(out)

        for scene in storyboard.scenes:
            start_idx = int(scene.start_sec * sample_rate)
            if start_idx >= total_len:
                continue

            # Determine appropriate SFX
            sfx_name = scene.sound_effect
            text = f"{scene.visual_prompt} {scene.spoken_line}".lower()

            if not sfx_name or sfx_name == "NONE":
                if any(w in text for w in ["rocket", "exhaust", "propulsion", "thrust"]):
                    sfx_name = "ROCKET_RUMBLE"
                elif any(w in text for w in ["pamphlet", "leaflet", "paper", "jail", "writing"]):
                    sfx_name = "PAPER_RUSTLE"
                elif scene.scene_number == 1:
                    sfx_name = "BASS_BOOM"
                else:
                    sfx_name = "WHOOSH"

            sfx_samples = cls.synthesize_sfx(sfx_name, sample_rate=sample_rate)
            mix_len = min(len(sfx_samples), total_len - start_idx)

            for i in range(mix_len):
                orig_val = out[start_idx + i]
                sfx_val = sfx_samples[i]
                # Soft-clip mixing to preserve voice clarity
                combined = orig_val + int(sfx_val * 0.45)
                out[start_idx + i] = max(-32768, min(32767, combined))

        return out
