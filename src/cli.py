import os
import sys
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.core.config import settings
from src.models.schemas import ReelGenerationTier, ReelScript, QuizPayload
from src.services.curriculum_resolver import curriculum_resolver
from src.agents.curriculum_agent import CurriculumAgent
from src.agents.script_agent import ScriptAgent
from src.agents.factcheck_agent import FactCheckAgent
from src.agents.quiz_agent import QuizAgent
from src.engines.tts.tts_engine import TTSFactory
from src.engines.render.subtitle_generator import SubtitleGenerator
from src.engines.render.card_renderer import CardRenderer
from src.engines.render.audio_mixer import AudioMixer
from src.engines.render.ffmpeg_compositor import FFmpegCompositor
from src.agents.publisher_agent import publisher_agent

console = Console()

@click.command()
@click.option("--topic", required=True, help="Curriculum topic (e.g. 'Newton\'s Third Law')")
@click.option("--class-level", default=9, type=int, help="Class grade level (6-12)")
@click.option("--subject", default="Physics", help="Subject name")
@click.option("--exam-type", default="SCHOOL", help="Exam type: SCHOOL, IIT_JEE, NEET, UPSC")
@click.option("--tier", default="DEFAULT", type=click.Choice(["DEFAULT", "PREMIUM"]), help="DEFAULT or PREMIUM mode")
@click.option("--publish", is_flag=True, default=False, help="Automatically publish to Conceptly Core API")
def generate_reel(topic, class_level, subject, exam_type, tier, publish):
    """Conceptly Studio CLI: Autonomously generate 9:16 vertical micro-learning reels."""
    console.print(Panel(
        f"[bold cyan]Conceptly Studio — Autonomous Reel Factory[/bold cyan]\n"
        f"Topic: [bold white]{topic}[/bold white] | Class: [bold yellow]{class_level}[/bold yellow] | "
        f"Subject: [bold magenta]{subject}[/bold magenta] | Tier: [bold green]{tier}[/bold green]",
        border_style="cyan"
    ))

    generation_tier = ReelGenerationTier(tier)
    run_dir = os.path.abspath(f"./output/cli_{topic.lower().replace(' ', '_')[:25]}")
    os.makedirs(run_dir, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        # 1. Resolve Topic
        t1 = progress.add_task("[cyan]1. Resolving topic in curriculum hierarchy...", total=1)
        resolved = curriculum_resolver.resolve_topic(topic, exam_type, class_level, subject)
        progress.update(t1, completed=1)

        # 2. Extract Concept
        t2 = progress.add_task("[cyan]2. Extracting core misconception & hook...", total=1)
        concept = CurriculumAgent.extract_concept(topic, exam_type, class_level, subject, tier=generation_tier)
        progress.update(t2, completed=1)

        # 3. Draft Script
        t3 = progress.add_task("[cyan]3. Synthesizing 4-act vertical screenplay...", total=1)
        script = ScriptAgent.generate_script(concept, tier=generation_tier)
        is_valid, report, script = FactCheckAgent.verify_and_clean_script(script)
        progress.update(t3, completed=1)

        # 4. Generate Quiz
        t4 = progress.add_task("[cyan]4. Producing 2 checkpoint concept MCQs...", total=1)
        quiz = QuizAgent.generate_quiz(script, topic_id=resolved["topic_id"], tier=generation_tier)
        progress.update(t4, completed=1)

        # 5. Synthesize Audio
        t5 = progress.add_task(f"[cyan]5. Synthesizing speech ({generation_tier.value} tier)...", total=1)
        full_text = " ".join(act.spoken_text for act in script.acts)
        speech_wav = os.path.join(run_dir, "speech.wav")
        tts_engine = TTSFactory.get_engine(generation_tier)
        word_timestamps = tts_engine.synthesize(full_text, speech_wav)
        progress.update(t5, completed=1)

        # 6. Generate Subtitles
        t6 = progress.add_task("[cyan]6. Compiling kinetic ASS bouncing subtitles...", total=1)
        ass_path = os.path.join(run_dir, "subtitles.ass")
        SubtitleGenerator.generate_ass(word_timestamps, ass_path)
        progress.update(t6, completed=1)

        # 7. Render Motion Cards
        t7 = progress.add_task("[cyan]7. Rendering 1080x1920 procedural motion cards...", total=1)
        frames_dir = os.path.join(run_dir, "frames")
        frame_paths = CardRenderer.render_reel_frames(script, subject, class_level, frames_dir)
        progress.update(t7, completed=1)

        # 8. Mix Audio
        t8 = progress.add_task("[cyan]8. Mixing speech and -22 dB lofi BGM with ducking...", total=1)
        mixed_audio = os.path.join(run_dir, "mixed_audio.wav")
        AudioMixer.mix_speech_and_bgm(speech_wav, mixed_audio)
        progress.update(t8, completed=1)

        # 9. FFmpeg Compositing
        t9 = progress.add_task("[cyan]9. Hardware-encoding 1080x1920 vertical MP4...", total=1)
        output_mp4 = os.path.join(run_dir, "final_reel.mp4")
        FFmpegCompositor.composite_reel(script, frame_paths, mixed_audio, ass_path, output_mp4)
        progress.update(t9, completed=1)

    console.print(f"\n[bold green]✅ Reel Generated Successfully![/bold green]")
    console.print(f"🎬 [bold white]Video Output:[/bold white] {output_mp4}")
    console.print(f"📝 [bold white]Spoken Words:[/bold white] {script.total_word_count} words (~45s)")
    console.print(f"❓ [bold white]Checkpoint MCQs:[/bold white] {len(quiz.questions)} questions generated")

    # Display Quiz in terminal table
    q_table = Table(title="Generated Checkpoint MCQs (CONTRACT.md Compliant)", border_style="blue")
    q_table.add_column("ID", style="cyan", width=5)
    q_table.add_column("Question", style="white")
    q_table.add_column("Correct Option", style="green", width=15)
    for q in quiz.questions:
        q_table.add_row(q.id, q.text, f"{q.correctOptionId.upper()})")
    console.print(q_table)

    if publish:
        console.print("[yellow]Syncing to live Conceptly backend...[/yellow]")
        from src.models.entities import ReelJob
        mock_job = ReelJob(
            id=resolved["topic_id"],
            topic_id=resolved["topic_id"],
            topic_title=topic,
            video_url=output_mp4,
            duration_sec=script.estimated_duration_sec,
            script_data=script.json(),
            quiz_data=quiz.json()
        )
        pub_res = publisher_agent.publish_reel(mock_job)
        console.print("[bold green]🚀 Published to Conceptly Core Live API![/bold green]")

if __name__ == "__main__":
    generate_reel()
