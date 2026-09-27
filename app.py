#!/usr/bin/env python3
"""
Project HER v2.0 — Hugging Face Spaces (Gradio SDK)

This is the entry point for the HF Space.
Gradio wraps the existing AgentOrchestrator directly — no Flask needed.
The full pipeline (scrape → AI analyze → TTS → visuals → compose) runs here.

HF Spaces free tier:
  • sdk: gradio   (free, no Docker required)
  • 16 GB RAM, 2 vCPUs — sufficient for video composition
  • Port 7860 handled automatically by Gradio
  • Public URL: https://<owner>-<space-name>.hf.space
"""

from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Optional

import gradio as gr
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
for name in ["urllib3", "httpx", "openai", "moviepy", "PIL", "httpcore"]:
    logging.getLogger(name).setLevel(logging.WARNING)

logger = logging.getLogger("her_gradio")

# ── Helpers ───────────────────────────────────────────────────────────────────

TONES   = list(config.TONE_PRESETS.keys())
THEMES  = list(config.THEMES.keys())
CAPS    = list(config.CAPTION_STYLES.keys())
TRANS   = config.AVAILABLE_TRANSITIONS
VOICES  = list(config.AVAILABLE_VOICES.keys())
FORMATS = ["vertical", "horizontal", "square"]

TONE_LABELS   = {k: config.TONE_PRESETS[k][:60] + "…" if len(config.TONE_PRESETS[k]) > 60 else config.TONE_PRESETS[k] for k in TONES}
THEME_LABELS  = {k: config.THEMES[k].get("label", k) for k in THEMES}
CAP_LABELS    = {k: config.CAPTION_STYLES[k].get("label", k) for k in CAPS}


def _ready() -> tuple[bool, str]:
    """Check required API keys are present."""
    if not config.GEMINI_API_KEY and not config.GROQ_API_KEY:
        return False, "❌ No LLM API key found (GEMINI_API_KEY or GROQ_API_KEY). Set them in Space → Settings → Secrets."
    if not config.PEXELS_API_KEY:
        return False, "⚠️ PEXELS_API_KEY missing — AI-Images mode will be used as fallback."
    return True, "✅ Ready"


# ── Core generation function ──────────────────────────────────────────────────

def generate_video(
    input_text: str,
    input_url: str,
    tone: str,
    theme: str,
    video_format: str,
    captions: str,
    voice: str,
    transition: str,
    ai_images: bool,
    progress: gr.Progress = gr.Progress(track_tqdm=True),
) -> tuple[Optional[str], str]:
    """
    Runs the full Project HER pipeline and returns (video_path, status_md).
    Called by Gradio when the user clicks Generate.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    source = input_url.strip() if input_url.strip() else input_text.strip()
    if not source:
        return None, "❌ Please paste article text **or** enter a URL above."

    ready, msg = _ready()
    if config.PEXELS_API_KEY:
        pass  # fine
    elif not ai_images:
        # No pexels key, force AI images
        ai_images = True

    progress(0.0, desc="🚀 Starting pipeline…")

    # ── Stage tracking ────────────────────────────────────────────────────────
    stage_labels = {
        "scrape":   ("📰", "Scraping article"),
        "analyze":  ("🤖", "Analyzing with AI"),
        "visuals":  ("🖼️",  "Finding visuals"),
        "narrate":  ("🎙️", "Generating narration"),
        "compose":  ("🎬", "Composing video"),
    }
    stage_order = list(stage_labels.keys())

    def _progress_cb(stage):
        """Map StageInfo → Gradio progress."""
        icon, label = stage_labels.get(stage.name, ("⚙️", stage.label))
        idx   = stage_order.index(stage.name) if stage.name in stage_order else 0
        total = len(stage_order)
        # Overall progress = completed stages + fraction of current stage
        overall = (idx + stage.progress_pct) / total
        progress(overall, desc=f"{icon} {label}…")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        from agent.orchestrator import AgentOrchestrator

        voice_str = config.AVAILABLE_VOICES.get(voice, voice) if voice else None

        orchestrator = AgentOrchestrator()
        result = orchestrator.run(
            input_source=source,
            tone=tone,
            video_format=video_format,
            voice=voice_str,
            theme=theme,
            caption_style=captions,
            transition=transition,
            ai_images=ai_images,
            progress_callback=_progress_cb,
            renderer="moviepy",        # moviepy works on CPU; remotion needs Node.js
        )

        if not result.success:
            err = "; ".join(result.errors) or "Unknown pipeline error"
            return None, f"❌ **Generation failed:** {err}"

        progress(1.0, desc="✅ Done!")

        # Build result markdown
        duration   = f"{result.duration:.1f}s" if result.duration else "—"
        proc_time  = f"{result.processing_time:.0f}s" if result.processing_time else "—"
        resolution = result.resolution or "—"

        status_md = (
            f"### ✅ {result.title}\n\n"
            f"| | |\n|---|---|\n"
            f"| ⏱ Duration | {duration} |\n"
            f"| 📐 Resolution | {resolution} |\n"
            f"| 🎭 Theme | {theme} |\n"
            f"| 🔑 Key points | {result.key_point_count} |\n"
            f"| ⚡ Processing time | {proc_time} |\n\n"
            f"*Use the download button below the video to save it.*"
        )

        return str(result.video_path), status_md

    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        return None, f"❌ **Error:** {str(exc)}"


# ── Gradio UI ─────────────────────────────────────────────────────────────────

_READY, _READY_MSG = _ready()

CSS = """
.her-header { text-align: center; padding: 1rem 0 0.5rem; }
.pipeline-row { background: #1a1a2e; border-radius: 12px; padding: 0.75rem 1rem; margin-bottom: 0.75rem; }
.pipeline-row span { color: #a78bfa; font-weight: 600; margin-right: 0.5rem; }
footer { display: none !important; }
"""

with gr.Blocks(
    title="🎬 Project HER — AI Video Generator",
    theme=gr.themes.Soft(primary_hue="purple", neutral_hue="slate"),
    css=CSS,
) as demo:

    # ── Header ────────────────────────────────────────────────────────────────
    gr.Markdown(
        """
        <div class="her-header">

        # 🎬 Project HER
        ### AI Article-to-Video Agent

        Paste any article, news story, or URL — HER autonomously runs a full
        AI pipeline and produces a cinematic short-form video.

        </div>
        """,
    )

    # ── API key status banner ─────────────────────────────────────────────────
    if not _READY:
        gr.Warning(_READY_MSG)

    # ── Pipeline visual ───────────────────────────────────────────────────────
    gr.Markdown(
        """
        <div class="pipeline-row">
        <span>📰 Scrape</span>→ <span>🤖 LLM Script</span>→
        <span>🎙️ TTS Audio</span>→ <span>🖼️ Visuals</span>→ <span>🎬 Compose</span>
        </div>
        """
    )

    with gr.Row():
        # ── Left column: Inputs ───────────────────────────────────────────────
        with gr.Column(scale=5):
            input_url = gr.Textbox(
                label="🔗 Article URL  (paste a URL OR use the text box below)",
                placeholder="https://example.com/article…",
                max_lines=1,
            )
            input_text = gr.Textbox(
                label="📝 Article / Story Text",
                placeholder="Paste your article text here… (min ~200 words for best results)",
                lines=10,
            )

            with gr.Accordion("⚙️ Generation Options", open=False):
                with gr.Row():
                    tone = gr.Dropdown(
                        label="Tone",
                        choices=TONES,
                        value="informative",
                        info="Narration style",
                    )
                    theme = gr.Dropdown(
                        label="Theme",
                        choices=[(THEME_LABELS[k], k) for k in THEMES],
                        value="cinematic",
                        info="Visual style",
                    )
                with gr.Row():
                    video_format = gr.Dropdown(
                        label="Format",
                        choices=[
                            ("9:16 Vertical (Reels / Shorts)", "vertical"),
                            ("16:9 Horizontal (YouTube)", "horizontal"),
                            ("1:1 Square (Instagram)", "square"),
                        ],
                        value="vertical",
                    )
                    captions = gr.Dropdown(
                        label="Captions",
                        choices=[(CAP_LABELS[k], k) for k in CAPS],
                        value="karaoke",
                    )
                with gr.Row():
                    voice = gr.Dropdown(
                        label="Voice",
                        choices=VOICES,
                        value="aria",
                        info="TTS narrator voice",
                    )
                    transition = gr.Dropdown(
                        label="Transition",
                        choices=TRANS,
                        value="fade",
                    )
                ai_images = gr.Checkbox(
                    label="🤖 Use AI-generated images (HuggingFace)",
                    value=not bool(config.PEXELS_API_KEY),
                    info="Enabled automatically if PEXELS_API_KEY is not set",
                )

            generate_btn = gr.Button(
                "🎬  Generate Video",
                variant="primary",
                size="lg",
            )

        # ── Right column: Output ──────────────────────────────────────────────
        with gr.Column(scale=5):
            video_out = gr.Video(
                label="Generated Video",
                show_download_button=True,
                height=480,
            )
            status_out = gr.Markdown(
                value=(
                    "*Fill in the article text or URL on the left, then click* ***Generate Video***.\n\n"
                    "⏳ Generation takes **2–4 minutes** — the AI is writing a script, "
                    "recording narration, finding visuals, and compositing the video."
                )
            )

    # ── Footer note ───────────────────────────────────────────────────────────
    gr.Markdown(
        """
        ---
        *Built with Python · Flask · Gemini AI · Google TTS · Pexels · MoviePy*
        — [View portfolio](https://klinteng.com) · [GitHub](https://github.com/klintenG/project-her)
        """
    )

    # ── Wire up the generate button ───────────────────────────────────────────
    generate_btn.click(
        fn=generate_video,
        inputs=[
            input_text,
            input_url,
            tone,
            theme,
            video_format,
            captions,
            voice,
            transition,
            ai_images,
        ],
        outputs=[video_out, status_out],
        show_progress="full",
    )


# ── Launch ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )
