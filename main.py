#!/usr/bin/env python3
"""
Project HER v2.0 – Main CLI Entry Point
Next-Gen AI Agent for Automated Article-to-Video Generation.

Features:
    - Themed video generation (cinematic, neon, minimal, playful, etc.)
    - Karaoke-style animated word captions
    - Procedural background music
    - Multiple transition effects
    - Hook generation & narrative arc
    - Async parallel image downloads

Usage:
    python main.py generate --text "Your article text here..."
    python main.py generate --url "https://example.com/article" --theme neon --captions pop
    python main.py generate --text "Story..." --tone storytelling --theme playful --voice ana_kid
    python main.py preview --text "Preview text..." --tone dramatic
    python main.py voices
    python main.py themes
    python main.py captions
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import print as rprint

import config

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    for logger_name in ["urllib3", "httpx", "openai", "moviepy", "PIL"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# ── CLI Group ──────────────────────────────────────────────


@click.group()
@click.version_option(version="2.0.0", prog_name="Project HER")
def cli():
    """
    🎬 Project HER v2.0 – Next-Gen AI Video Agent

    Converts articles & text into cinematic, engaging short videos
    with animated captions, background music, and themed visuals.
    """
    pass


# ── Generate Command ──────────────────────────────────────


@cli.command()
@click.option("--url", type=str, default=None, help="URL of the article to convert.")
@click.option("--text", type=str, default=None, help="Raw article text to convert.")
@click.option("--file", "text_file", type=click.Path(exists=True), default=None,
              help="Path to a text file with article content.")
@click.option("--tone",
              type=click.Choice(["informative", "storytelling", "social", "dramatic", "educational", "motivational", "explainer"]),
              default="informative", help="Tone/style of the narration.")
@click.option("--format", "video_format",
              type=click.Choice(["vertical", "horizontal", "square"]),
              default="vertical", help="Video format/orientation.")
@click.option("--voice", type=str, default=None,
              help="Narration voice (use 'voices' command to list).")
@click.option("--theme",
              type=click.Choice(list(config.THEMES.keys())),
              default=config.DEFAULT_THEME,
              help="Visual theme preset.")
@click.option("--captions",
              type=click.Choice(list(config.CAPTION_STYLES.keys())),
              default=config.DEFAULT_CAPTION_STYLE,
              help="Caption animation style.")
@click.option("--transition",
              type=click.Choice(config.AVAILABLE_TRANSITIONS),
              default=config.DEFAULT_TRANSITION,
              help="Transition effect between scenes.")
@click.option("--platform",
              type=click.Choice(config.AVAILABLE_PLATFORMS),
              default=None,
              help="Platform preset (auto-sets format, duration, bitrate). Overrides --format.")
@click.option("--quality",
              type=click.Choice(list(config.QUALITY_PRESETS.keys())),
              default=None,
              help="Export quality preset (draft/standard/high/ultra).")
@click.option("--points", type=click.IntRange(3, 15), default=None,
              help="Number of key points (3-15).")
@click.option("--output", type=click.Path(), default=None, help="Output directory.")
@click.option("--no-subtitles", is_flag=True, help="Disable subtitle/caption generation.")
@click.option("--watermark", type=str, default=None,
              help="Watermark text (e.g. '@myhandle'). Overrides WATERMARK_TEXT env var.")
@click.option("--speed", type=str, default=None,
              help="Voice speed adjustment (e.g. '+20%%', '-10%%'). Default: '+0%%'.")
@click.option("--color-grade", "color_grade",
              type=click.Choice(config.AVAILABLE_COLOR_GRADES),
              default=config.DEFAULT_COLOR_GRADE,
              help="Color grading/filter preset for the video.")
@click.option("--language", type=click.Choice(config.AVAILABLE_LANGUAGES),
              default=None,
              help="Language for narration voice (auto-selects voice). Overrides --voice.")
@click.option("--font", type=click.Path(exists=True), default=None,
              help="Path to a custom TTF/OTF font file for text overlays.")
@click.option("--bgm", type=click.Path(exists=True), default=None,
              help="Path to a custom background music file (mp3/wav/ogg).")
@click.option("--intro", type=click.Path(exists=True), default=None,
              help="Path to a custom intro clip (video or image).")
@click.option("--outro", type=click.Path(exists=True), default=None,
              help="Path to a custom outro clip (video or image).")
@click.option("--ai-images", "ai_images", is_flag=True,
              help="Use AI-generated images with Claymorphism style instead of Pexels.")
@click.option("--brand", type=str, default="",
              help="Brand name to display on the video (AI image mode).")
@click.option("--content-mode", type=click.Choice(config.AVAILABLE_CONTENT_MODES), default="article")
@click.option("--news-source-policy", type=click.Choice(["auto", "online", "supplied"]), default="auto")
@click.option("--renderer", type=click.Choice(["remotion", "moviepy"]), default=config.DEFAULT_RENDERER)
@click.option("--target-duration", type=click.IntRange(0, 600), default=0)
@click.option("--news-music", is_flag=True, help="Optional quiet, ducked music in News.")
@click.option("--visual-preset", type=click.Choice(["default", "reference_editorial"]), default="default")
@click.option("--editorial-text", type=click.Choice(["editorial", "complete"]), default="editorial")
@click.option("--editorial-assets", type=click.Choice(["auto", "stock", "ai", "local"]), default="auto")
@click.option("--local-assets", type=click.Path(exists=True), default=None, help="Editorial asset registry JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
def generate(url, text, text_file, tone, video_format, voice, theme, captions,
             transition, platform, quality, points, output, no_subtitles, watermark,
             speed, color_grade, language, font, bgm, intro, outro,
             ai_images, brand, content_mode, news_source_policy, renderer, target_duration, news_music, visual_preset, editorial_text, editorial_assets, local_assets, verbose):
    """Generate a cinematic video from an article URL or text."""
    setup_logging(verbose)

    if content_mode == "news" or visual_preset == "reference_editorial":
        source = "\n".join(v for v in (url, text) if v) or _resolve_input(url, text, text_file)
        if not source:
            raise click.ClickException("Provide --url, --text, or --file.")
        from agent.orchestrator import AgentOrchestrator
        fmt = config.PLATFORM_PRESETS.get(platform, {}).get("format", video_format)
        result = AgentOrchestrator().run(source, content_mode=content_mode, news_source_policy=news_source_policy,
            renderer=renderer, target_duration=target_duration, tone=tone, video_format=fmt,
            voice=config.LANGUAGE_VOICES.get(language, {}).get("voice", voice), language=language or "english",
            quality=quality or "high", speed=speed or "+0%", output_dir=Path(output) if output else None, brand_text=brand,
            news_music=news_music or bool(bgm), news_music_path=bgm,visual_preset=visual_preset,editorial_text=editorial_text,
            editorial_assets="ai" if ai_images else editorial_assets,local_assets=local_assets)
        console.print_json(data=result.news_details)
        if not result.success:
            raise click.ClickException("; ".join(result.errors))
        console.print(f"Video: {result.video_path} | Subtitles: {result.srt_path}")
        return

    # Apply platform preset (overrides individual settings if not explicitly set)
    if platform:
        preset = config.PLATFORM_PRESETS[platform]
        video_format = preset["format"]
        if theme == config.DEFAULT_THEME:
            theme = preset["recommended_theme"]
        if captions == config.DEFAULT_CAPTION_STYLE:
            captions = preset["recommended_captions"]
        if transition == config.DEFAULT_TRANSITION:
            transition = preset["recommended_transition"]
        if points is None:
            points = min(points or preset["max_points"], preset["max_points"])
        # Override config-level settings for this run
        config.TARGET_DURATION = preset["target_duration"]
        config.VIDEO_BITRATE = preset["bitrate"]
        config.FPS = preset["fps"]

    # Apply watermark override
    if watermark:
        config.WATERMARK_TEXT = watermark

    # Apply Phase 5 premium options
    if speed:
        config.VOICE_SPEED = speed
    if font:
        config.CUSTOM_FONT_PATH = font
    if bgm:
        config.CUSTOM_BGM_PATH = bgm
    if intro:
        config.CUSTOM_INTRO_PATH = intro
    if outro:
        config.CUSTOM_OUTRO_PATH = outro
    if language:
        lang_voice = config.LANGUAGE_VOICES.get(language, {}).get("voice")
        if lang_voice:
            voice = lang_voice

    # Apply quality preset (can stack with platform; quality takes priority)
    if quality:
        qp = config.QUALITY_PRESETS[quality]
        config.VIDEO_BITRATE = qp["bitrate"]
        config.FPS = qp["fps"]
        config.RENDER_THREADS = qp["threads"]

    # Validate input
    input_source = _resolve_input(url, text, text_file)
    if not input_source:
        console.print("[red]Error:[/red] Provide --url, --text, or --file as input.")
        sys.exit(1)

    # Validate API keys
    llm_key = config.GEMINI_API_KEY if config.LLM_PROVIDER in ("gemini", "google") else config.GROQ_API_KEY
    if not llm_key:
        console.print(
            f"[red]Error:[/red] API key for {config.LLM_PROVIDER} not set. "
            "Check GEMINI_API_KEY in your .env file."
        )
        sys.exit(1)
    if not config.PEXELS_API_KEY and not ai_images:
        console.print(
            "[red]Error:[/red] PEXELS_API_KEY not set. "
            "Get a free key at https://www.pexels.com/api/ "
            "(or use --ai-images for AI-generated visuals)"
        )
        sys.exit(1)

    # Show config panel
    fmt_info = config.VIDEO_FORMATS[video_format]
    theme_info = config.THEMES[theme]
    caption_info = config.CAPTION_STYLES[captions]

    console.print(
        Panel(
            f"[bold cyan]Tone:[/bold cyan] {tone}\n"
            f"[bold cyan]Format:[/bold cyan] {fmt_info['label']}\n"            f"[bold cyan]Platform:[/bold cyan] {config.PLATFORM_PRESETS[platform]['label'] if platform else 'Custom'}\n"            f"[bold cyan]Voice:[/bold cyan] {voice or 'default (Aria)'}\n"
            f"[bold cyan]Theme:[/bold cyan] {theme_info['label']} [dim]({theme})[/dim]\n"
            f"[bold cyan]Captions:[/bold cyan] {caption_info['label']} [dim]({captions})[/dim]\n"
            f"[bold cyan]Transition:[/bold cyan] {transition}\n"
            f"[bold cyan]Points:[/bold cyan] {points or 'auto'}\n"
            f"[bold cyan]Subtitles:[/bold cyan] {'No' if no_subtitles else 'Yes'}\n"
            f"[bold cyan]Color Grade:[/bold cyan] {color_grade}\n"
            f"[bold cyan]Language:[/bold cyan] {language or 'en (default)'}\n"
            f"[bold cyan]Voice Speed:[/bold cyan] {config.VOICE_SPEED}\n"
            f"[bold cyan]Custom Font:[/bold cyan] {font or 'default'}\n"
            f"[bold cyan]Custom BGM:[/bold cyan] {bgm or 'procedural'}\n"
            f"[bold cyan]Custom Intro:[/bold cyan] {intro or 'auto'}\n"
            f"[bold cyan]Custom Outro:[/bold cyan] {outro or 'auto'}\n"
            f"[bold cyan]AI Images:[/bold cyan] {'✅ Claymorphism' if ai_images else 'Off (Pexels)'}\n"
            f"[bold cyan]Brand:[/bold cyan] {brand or 'none'}",
            title="🎬 Project HER v2.0 – Video Generation",
            border_style="cyan",
        )
    )

    # Run pipeline with Rich progress tracking
    from agent.orchestrator import AgentOrchestrator
    from utils.progress import ProgressTracker, StageInfo, PIPELINE_STAGES
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

    output_dir = Path(output) if output else None

    # Setup Rich progress bar callback
    stage_icons = {"scrape": "📄", "analyze": "🧠", "visuals": "🖼️ ", "narrate": "🎙️ ", "compose": "🎬"}
    task_ids = {}

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30, complete_style="green", finished_style="green"),
        TextColumn("[dim]{task.fields[status]}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    for name, label in PIPELINE_STAGES:
        icon = stage_icons.get(name, "⏳")
        task_ids[name] = progress.add_task(f"{icon} {label}", total=100, status="pending")

    def cli_progress_callback(stage: StageInfo):
        tid = task_ids.get(stage.name)
        if tid is None:
            return
        if stage.status == "running":
            progress.update(tid, completed=int(stage.progress_pct * 100), status=stage.message)
        elif stage.status == "completed":
            progress.update(tid, completed=100, status=f"✅ {stage.message}")
        elif stage.status == "failed":
            progress.update(tid, completed=int(stage.progress_pct * 100), status=f"❌ {stage.message}")

    orchestrator = AgentOrchestrator()
    with progress:
        result = orchestrator.run(
            input_source=input_source,
            tone=tone,
            video_format=video_format,
            voice=voice,
            output_dir=output_dir,
            num_points=points,
            include_subtitles=not no_subtitles,
            theme=theme,
            caption_style=captions,
            transition=transition,
            color_grade=color_grade,
            progress_callback=cli_progress_callback,
            ai_images=ai_images,
            brand_text=brand,
            content_mode=content_mode,
            visual_preset=visual_preset,editorial_text=editorial_text,editorial_assets=editorial_assets,local_assets=local_assets,
            renderer=renderer,
            target_duration=target_duration,
        )

    # Show result
    if result.success:
        console.print()
        console.print(
            Panel(
                f"[green bold]Video generated successfully![/green bold]\n\n"
                f"[bold]Title:[/bold] {result.title}\n"
                f"[bold]Hook:[/bold] [italic]{result.hook}[/italic]\n"
                f"[bold]Video:[/bold] {result.video_path}\n"
                f"[bold]Subtitles:[/bold] {result.srt_path or 'N/A'}\n"
                f"[bold]Thumbnail:[/bold] {result.thumbnail_path or 'N/A'}\n"
                f"[bold]Duration:[/bold] {result.duration:.1f}s\n"
                f"[bold]Resolution:[/bold] {result.resolution}\n"
                f"[bold]Key Points:[/bold] {result.key_point_count}\n"
                f"[bold]Content Type:[/bold] {result.content_type}\n"
                f"[bold]Music Mood:[/bold] {result.mood}\n"
                f"[bold]Theme:[/bold] {result.theme} | [bold]Captions:[/bold] {result.caption_style}\n"
                f"[bold]Processing Time:[/bold] {result.processing_time:.1f}s",
                title="✅ Complete",
                border_style="green",
            )
        )
    else:
        console.print()
        console.print(
            Panel(
                f"[red bold]Video generation failed.[/red bold]\n\n"
                f"[bold]Errors:[/bold]\n"
                + "\n".join(f"  • {e}" for e in result.errors),
                title="❌ Failed",
                border_style="red",
            )
        )
        sys.exit(1)


# ── Preview Command ───────────────────────────────────────


@cli.command()
@click.option("--url", type=str, default=None, help="URL of the article.")
@click.option("--text", type=str, default=None, help="Raw article text.")
@click.option("--file", "text_file", type=click.Path(exists=True), default=None,
              help="Path to a text file.")
@click.option("--tone",
              type=click.Choice(["informative", "storytelling", "social", "dramatic", "educational", "motivational"]),
              default="informative")
@click.option("--points", type=click.IntRange(3, 6), default=None)
@click.option("--content-mode", type=click.Choice(config.AVAILABLE_CONTENT_MODES), default="article")
@click.option("--news-source-policy", type=click.Choice(["auto", "online", "supplied"]), default="auto")
@click.option("--verbose", "-v", is_flag=True)
def preview(url, text, text_file, tone, points, content_mode, news_source_policy, verbose):
    """Preview extracted key points, hook, and analysis without generating video."""
    setup_logging(verbose)

    input_source = _resolve_input(url, text, text_file)
    if not input_source:
        console.print("[red]Error:[/red] Provide --url, --text, or --file as input.")
        sys.exit(1)

    if content_mode != "news" and not config.GROQ_API_KEY:
        console.print("[red]Error:[/red] GROQ_API_KEY not set.")
        sys.exit(1)

    from agent.orchestrator import AgentOrchestrator

    console.print("[cyan]Analyzing article...[/cyan]")
    orchestrator = AgentOrchestrator()
    if content_mode == "news":
        from agent.news_pipeline import preview_news
        from agent.news_models import NewsError
        try:
            console.print_json(data=preview_news("\n".join(v for v in (url,text) if v) or input_source, source_policy=news_source_policy, tone=tone))
        except NewsError as exc:
            console.print_json(data=exc.response())
            raise click.ClickException(str(exc))
        return
    analysis = orchestrator.preview_analysis(input_source, tone=tone, num_points=points)

    # Display results
    console.print()

    # Analysis panel with hook
    info_text = f"[bold]{analysis.title}[/bold]\n\n"
    if analysis.hook:
        info_text += f"[yellow bold]Hook:[/yellow bold] [italic]{analysis.hook}[/italic]\n"
    info_text += f"[bold]Type:[/bold] {analysis.content_type} | [bold]Mood:[/bold] {analysis.mood}\n\n"
    info_text += analysis.summary

    console.print(
        Panel(info_text, title="📝 Analysis Result", border_style="cyan")
    )

    table = Table(title="Key Points (Narrative Arc)", show_lines=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Headline", style="bold")
    table.add_column("Narration", style="white")
    table.add_column("Emotion", style="yellow", width=10)
    table.add_column("Visual", style="dim")

    for kp in analysis.key_points:
        table.add_row(
            str(kp.index + 1),
            kp.headline,
            kp.narration,
            kp.emotion,
            kp.visual_query,
        )

    console.print(table)


# ── Voices Command ────────────────────────────────────────


@cli.command()
def voices():
    """List available narration voices."""
    console.print(
        Panel(
            "[bold]Built-in voice presets[/bold]\n"
            "Use shortcut names with --voice, e.g.: --voice aria",
            title="🎙️ Voices",
            border_style="cyan",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Shortcut", style="cyan bold")
    table.add_column("Voice ID", style="white")

    for shortcut, voice_id in config.AVAILABLE_VOICES.items():
        table.add_row(shortcut, voice_id)

    console.print(table)
    console.print(
        "[dim]Or provide a full edge-tts voice ID directly.[/dim]"
    )


# ── Themes Command ────────────────────────────────────────


@cli.command()
def themes():
    """List available visual themes."""
    console.print(
        Panel(
            "[bold]Visual theme presets[/bold]\n"
            "Use with --theme, e.g.: --theme neon",
            title="🎨 Themes",
            border_style="magenta",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Name", style="cyan bold", width=12)
    table.add_column("Label", style="bold")
    table.add_column("Accent", style="yellow", width=16)
    table.add_column("Vignette", width=8)
    table.add_column("Gradient", width=8)

    for name, t in config.THEMES.items():
        accent_str = f"RGB{t['accent_color']}"
        vig = "✓" if t.get("vignette") else "–"
        grad = "✓" if t.get("gradient_overlay") else "–"
        table.add_row(name, t["label"], accent_str, vig, grad)

    console.print(table)


# ── Captions Command ──────────────────────────────────────


@cli.command()
def captions():
    """List available caption animation styles."""
    console.print(
        Panel(
            "[bold]Caption animation presets[/bold]\n"
            "Use with --captions, e.g.: --captions karaoke",
            title="💬 Caption Styles",
            border_style="yellow",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Name", style="cyan bold", width=14)
    table.add_column("Label", style="bold")
    table.add_column("Description", style="dim")
    table.add_column("Font Size", width=10)

    for name, c in config.CAPTION_STYLES.items():
        table.add_row(
            name, c["label"], c["description"], str(c["font_size"])
        )

    console.print(table)


# ── Tones Command ─────────────────────────────────────────


@cli.command()
def tones():
    """List available narration tones."""
    console.print(
        Panel(
            "[bold]Narration tone presets[/bold]\n"
            "Use with --tone, e.g.: --tone dramatic",
            title="🎭 Tones",
            border_style="green",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Tone", style="cyan bold", width=16)
    table.add_column("Description", style="white")

    for name, desc in config.TONE_PRESETS.items():
        table.add_row(name, desc)

    console.print(table)


# ── Platforms Command ──────────────────────────────────────


@cli.command()
def platforms():
    """List available platform presets."""
    console.print(
        Panel(
            "[bold]Platform presets[/bold]\n"
            "Use with --platform, e.g.: --platform tiktok\n"
            "Auto-sets format, duration, bitrate, and recommended theme/captions.",
            title="📱 Platform Presets",
            border_style="blue",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Name", style="cyan bold", width=16)
    table.add_column("Label", style="bold")
    table.add_column("Format", width=12)
    table.add_column("Duration", width=10)
    table.add_column("FPS", width=5)
    table.add_column("Theme", width=12)
    table.add_column("Captions", width=12)

    for name, p in config.PLATFORM_PRESETS.items():
        dur = f"{p['target_duration'][0]}-{p['target_duration'][1]}s"
        table.add_row(
            name, p["label"], p["format"], dur, str(p["fps"]),
            p["recommended_theme"], p["recommended_captions"],
        )

    console.print(table)


# ── Color Grades Command ──────────────────────────────────


@cli.command()
def grades():
    """List available color grading/filter presets."""
    console.print(
        Panel(
            "[bold]Color grading presets[/bold]\n"
            "Use with --color-grade, e.g.: --color-grade cinematic",
            title="🎨 Color Grades",
            border_style="magenta",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Name", style="cyan bold", width=14)
    table.add_column("Brightness", width=12)
    table.add_column("Contrast", width=10)
    table.add_column("Saturation", width=12)
    table.add_column("Tint", width=18)

    for name, g in config.COLOR_GRADES.items():
        tint_str = f"RGBA{g['tint']}" if g.get("tint") else "None"
        table.add_row(
            name,
            str(g["brightness"]),
            str(g["contrast"]),
            str(g["saturation"]),
            tint_str,
        )

    console.print(table)


# ── Languages Command ─────────────────────────────────────


@cli.command()
def languages():
    """List available language presets for narration."""
    console.print(
        Panel(
            "[bold]Language presets[/bold]\n"
            "Use with --language, e.g.: --language hi\n"
            "Automatically selects the best voice for the language.",
            title="🌍 Languages",
            border_style="green",
        )
    )

    table = Table(show_lines=True)
    table.add_column("Code", style="cyan bold", width=8)
    table.add_column("Language", style="bold", width=20)
    table.add_column("Voice ID", style="dim")

    for code, info in config.LANGUAGE_VOICES.items():
        table.add_row(code, info["label"], info["voice"])

    console.print(table)


# ── Cache Command ─────────────────────────────────────────


@cli.command()
@click.option("--clear", is_flag=True, help="Clear all cached data.")
@click.option("--prefix", type=str, default=None,
              help="Only clear cache entries with this prefix (e.g. 'analysis').")
def cache(clear, prefix):
    """View or clear the pipeline cache."""
    from utils.cache import cache_stats, clear_cache

    if clear:
        count = clear_cache(prefix=prefix)
        console.print(f"[green]Cleared {count} cache entries.[/green]")
    else:
        stats = cache_stats()
        console.print(
            Panel(
                f"[bold cyan]Total entries:[/bold cyan] {stats['total_entries']}\n"
                f"[bold cyan]Total size:[/bold cyan] {stats['total_size_kb']} KB\n"
                f"[bold cyan]By type:[/bold cyan] {stats['by_prefix']}",
                title="📦 Pipeline Cache",
                border_style="cyan",
            )
        )


# ── Batch Export Command ──────────────────────────────────


@cli.command()
@click.option("--url", type=str, default=None, help="URL of the article to convert.")
@click.option("--text", type=str, default=None, help="Raw article text to convert.")
@click.option("--file", "text_file", type=click.Path(exists=True), default=None,
              help="Path to a text file with article content.")
@click.option("--tone",
              type=click.Choice(["informative", "storytelling", "social", "dramatic", "educational", "motivational"]),
              default="informative")
@click.option("--voice", type=str, default=None)
@click.option("--formats", type=str, default="vertical,horizontal,square",
              help="Comma-separated formats to export (vertical,horizontal,square).")
@click.option("--output", type=click.Path(), default=None, help="Output base directory.")
@click.option("--quality",
              type=click.Choice(list(config.QUALITY_PRESETS.keys())),
              default=None)
@click.option("--watermark", type=str, default=None)
@click.option("--verbose", "-v", is_flag=True)
def batch(url, text, text_file, tone, voice, formats, output, quality, watermark, verbose):
    """Export the same content as video in multiple formats at once."""
    setup_logging(verbose)

    input_source = _resolve_input(url, text, text_file)
    if not input_source:
        console.print("[red]Error:[/red] Provide --url, --text, or --file as input.")
        sys.exit(1)

    if not config.GROQ_API_KEY or not config.PEXELS_API_KEY:
        console.print("[red]Error:[/red] API keys not set. Check .env file.")
        sys.exit(1)

    if watermark:
        config.WATERMARK_TEXT = watermark
    if quality:
        qp = config.QUALITY_PRESETS[quality]
        config.VIDEO_BITRATE = qp["bitrate"]
        config.FPS = qp["fps"]
        config.RENDER_THREADS = qp["threads"]

    format_list = [f.strip() for f in formats.split(",") if f.strip() in config.VIDEO_FORMATS]
    if not format_list:
        console.print("[red]Error:[/red] No valid formats specified.")
        sys.exit(1)

    console.print(
        Panel(
            f"[bold cyan]Formats:[/bold cyan] {', '.join(format_list)}\n"
            f"[bold cyan]Tone:[/bold cyan] {tone}\n"
            f"[bold cyan]Quality:[/bold cyan] {quality or 'standard'}",
            title="📦 Batch Export",
            border_style="blue",
        )
    )

    import time as _time
    from agent.orchestrator import AgentOrchestrator

    base_dir = Path(output) if output else config.OUTPUT_DIR / f"batch_{_time.strftime('%Y%m%d_%H%M%S')}"

    orchestrator = AgentOrchestrator()
    results = []

    for fmt in format_list:
        console.print(f"\n[cyan]── Rendering {fmt} format ──[/cyan]")
        fmt_dir = base_dir / fmt

        result = orchestrator.run(
            input_source=input_source,
            tone=tone,
            video_format=fmt,
            voice=voice,
            output_dir=fmt_dir,
            include_subtitles=True,
            theme=config.DEFAULT_THEME,
            caption_style=config.DEFAULT_CAPTION_STYLE,
            transition=config.DEFAULT_TRANSITION,
        )
        results.append((fmt, result))

    # Summary
    console.print()
    table = Table(title="Batch Export Results", show_lines=True)
    table.add_column("Format", style="cyan bold")
    table.add_column("Status")
    table.add_column("Duration", width=10)
    table.add_column("Path", style="dim")

    for fmt, r in results:
        status = "[green]✓[/green]" if r.success else "[red]✗[/red]"
        dur = f"{r.duration:.1f}s" if r.success else "—"
        path = str(r.video_path) if r.success else ", ".join(r.errors[:1])
        table.add_row(fmt, status, dur, path)

    console.print(table)

    failed = sum(1 for _, r in results if not r.success)
    if failed:
        sys.exit(1)


# ── Helpers ───────────────────────────────────────────────


def _resolve_input(url, text, text_file) -> Optional[str]:
    """Resolve input source from CLI options."""
    if url:
        return url.strip()
    if text:
        return text.strip()
    if text_file:
        return Path(text_file).read_text(encoding="utf-8").strip()
    return None


# ── Daily Pipeline Command ────────────────────────────────


@cli.command("daily")
@click.option("--videos", type=int, default=5, help="Number of videos to generate (default: 5)")
@click.option("--tone", default="storytelling", help="Narration tone for all videos")
@click.option("--renderer", type=click.Choice(["remotion", "moviepy"]), default="remotion")
@click.option("--publish", "publish_strategy",
              type=click.Choice(["manual", "youtube_api", "macos_shortcuts", "browser"]),
              default="manual", help="Publishing strategy")
@click.option("--start-hour", type=int, default=17, help="Start posting at this hour (24h)")
@click.option("--interval", type=int, default=70, help="Minutes between video posts")
@click.option("--jitter", type=int, default=15, help="Random jitter ± minutes")
@click.option("--dry-run", is_flag=True, help="Don't actually publish — just generate")
@click.option("--platforms", multiple=True,
              default=["youtube_shorts", "tiktok", "instagram_reels", "facebook", "twitter"],
              help="Platforms to publish to")
@click.option("-v", "--verbose", is_flag=True)
def daily(videos, tone, renderer, publish_strategy, start_hour, interval, jitter,
          dry_run, platforms, verbose):
    """
    🤖 Run the daily agentic pipeline.

    Automatically curates stories, validates them, generates videos,
    and prepares them for publishing across social media platforms.

    Example:
        python main.py daily --videos 5 --publish manual
        python main.py daily --videos 3 --dry-run
        python main.py daily --publish browser --start-hour 18
    """
    setup_logging(verbose)

    from automation.daily_pipeline import DailyPipeline, DailyConfig

    cfg = DailyConfig(
        target_videos=videos,
        tone=tone,
        renderer=renderer,
        publish_strategy=publish_strategy,
        start_hour=start_hour,
        interval_minutes=interval,
        jitter_minutes=jitter,
        dry_run=dry_run,
        platforms=list(platforms),
    )

    console.print(Panel.fit(
        f"[bold cyan]🤖 Daily Pipeline[/bold cyan]\n"
        f"  Videos: {videos} | Tone: {tone} | Renderer: {renderer}\n"
        f"  Publish: {publish_strategy} | Start: {start_hour}:00\n"
        f"  Platforms: {', '.join(platforms)}\n"
        f"  {'[yellow]DRY RUN[/yellow]' if dry_run else '[green]LIVE[/green]'}",
        title="Configuration",
    ))

    def progress_cb(msg: str):
        console.print(f"  {msg}")

    pipeline = DailyPipeline(config=cfg)

    try:
        report = pipeline.run(progress_callback=progress_cb)
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        sys.exit(130)
    except SystemExit:
        console.print("\n[yellow]Pipeline exited early — check daily_report.json for details[/yellow]")
        # Report was already written by finally block
        return
    except Exception as e:
        console.print(f"\n[red]Pipeline error: {e}[/red]")
        return

    # Summary
    console.print()
    table = Table(title="Daily Pipeline Report", show_lines=True)
    table.add_column("Metric", style="cyan bold")
    table.add_column("Value")

    table.add_row("Date", report.date)
    table.add_row("Duration", f"{report.duration_minutes:.1f} min")
    table.add_row("Curation Rounds", str(report.curation_rounds))
    table.add_row("Stories Approved", f"[green]{report.stories_approved}[/green]")
    table.add_row("Stories Rejected", f"[red]{report.stories_rejected}[/red]")
    table.add_row("Videos Generated", f"[green]{report.videos_generated}[/green]")
    table.add_row("Videos Failed", f"[red]{report.videos_failed}[/red]" if report.videos_failed else "0")
    table.add_row("Posts Scheduled", str(report.posts_scheduled))
    table.add_row("Strategy", report.publish_strategy)
    console.print(table)

    if report.errors:
        console.print(f"\n[yellow]⚠ {len(report.errors)} error(s):[/yellow]")
        for err in report.errors:
            console.print(f"  [red]• {err[:100]}[/red]")

    if report.video_details:
        console.print("\n[bold]Generated Videos:[/bold]")
        for vd in report.video_details:
            console.print(
                f"  🎬 {vd['title'][:50]} → "
                f"{vd.get('duration', 0):.1f}s ({vd.get('processing_time', 0):.0f}s to render)"
            )

    if not report.videos_generated:
        sys.exit(1)


# ── Entry Point ───────────────────────────────────────────

if __name__ == "__main__":
    cli()
