import os
from typing import List
from src.engines.tts.tts_engine import WordTimestamp

class SubtitleGenerator:
    """
    Advanced SubStation Alpha (.ass) Kinetic Subtitle Generator.
    - Anchors subtitles at Y = 1400px (MarginV = 480px from bottom)
    - Groups words into punchy 3-5 word phrases (vertical reel safe zone)
    - High-contrast typography with Amber (#F59E0B) active word highlighting
    """

    ASS_HEADER_TEMPLATE = """[Script Info]
Title: Conceptly Studio Kinetic Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KineticSub,Arial,64,&H00FFFFFF,&H000B9EF5,&H00090D16,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,2.0,2,80,80,480,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Converts float seconds to ASS timestamp format: H:MM:SS.CC"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int(round((seconds - int(seconds)) * 100))
        if centisecs >= 100:
            centisecs = 99
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    @classmethod
    def generate_ass(
        cls,
        words: List[WordTimestamp],
        output_ass_path: str,
        highlight_color_ass: str = "&H000B9EF5&",  # Amber in BGR: #F59E0B
        normal_color_ass: str = "&H00FFFFFF&"      # Crisp White
    ) -> str:
        """
        Takes word timestamps, chunks them into 3-5 word phrases,
        and generates frame-accurate word highlighting events.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_ass_path)), exist_ok=True)
        
        if not words:
            with open(output_ass_path, "w", encoding="utf-8") as f:
                f.write(cls.ASS_HEADER_TEMPLATE)
            return output_ass_path

        # 1. Group words into 3-5 word dialogue chunks
        chunks = []
        current_chunk = []
        for w in words:
            current_chunk.append(w)
            # Break chunk on punctuation or every 4 words
            if len(current_chunk) >= 4 or w.word.endswith((".", "?", "!", ",")):
                chunks.append(current_chunk)
                current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        dialogue_lines = []

        # 2. For each chunk, create an event for each word where that specific word is highlighted
        for chunk in chunks:
            chunk_start = chunk[0].start_sec
            chunk_end = chunk[-1].end_sec

            for i, target_word in enumerate(chunk):
                w_start = target_word.start_sec
                # Word display lasts until next word starts (or chunk ends)
                w_end = chunk[i + 1].start_sec if i + 1 < len(chunk) else chunk_end

                if w_end <= w_start:
                    w_end = w_start + 0.15

                # Build text string with target_word highlighted in Amber
                formatted_words = []
                for j, w in enumerate(chunk):
                    if j == i:
                        # Highlight active word + slight bold/uppercase emphasis
                        formatted_words.append(f"{{\\c{highlight_color_ass}\\b1}}{w.word.upper()}{{\\c{normal_color_ass}\\b0}}")
                    else:
                        formatted_words.append(w.word)

                text_line = " ".join(formatted_words)
                start_str = cls._format_time(w_start)
                end_str = cls._format_time(w_end)
                
                # Dialogue event
                event_line = f"Dialogue: 0,{start_str},{end_str},KineticSub,,0,0,0,,{text_line}"
                dialogue_lines.append(event_line)

        # 3. Write final .ass file
        content = cls.ASS_HEADER_TEMPLATE + "\n".join(dialogue_lines) + "\n"
        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_ass_path
