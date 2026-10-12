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
    gemini_key = getattr(config, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_TTS_API_KEY", "")
    groq_key = getattr(config, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY", "")
    pexels_key = getattr(config, "PEXELS_API_KEY", None) or os.getenv("PEXELS_API_KEY", "")

    if not gemini_key and not groq_key:
        return False, "❌ No LLM API key found (GEMINI_API_KEY or GROQ_API_KEY). Set them in Space → Settings → Secrets."
    if not pexels_key:
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
    content_mode: str = "article",
    news_source_policy: str = "auto",
    renderer: str = "moviepy",
    target_duration: int = 0,
    news_music: bool = False,
    visual_preset: str = "default",
    editorial_text: str = "editorial",
    editorial_assets: str = "auto",
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

    if content_mode == "news":
        source = "\n".join(v for v in (input_url.strip(), input_text.strip()) if v)

    ready, msg = _ready()
    pexels_key = getattr(config, "PEXELS_API_KEY", None) or os.getenv("PEXELS_API_KEY", "")
    if pexels_key:
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
        idx = stage.index - 1
        total = stage.total
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
            renderer=renderer,
            content_mode=content_mode, news_source_policy=news_source_policy,
            target_duration=int(target_duration), quality="high", news_music=news_music,
            visual_preset=visual_preset,editorial_text=editorial_text,editorial_assets=editorial_assets,
        )

        if not result.success:
            err = "; ".join(result.errors) or "Unknown pipeline error"
            choices = " / ".join(result.news_details.get("choices", []))
            return None, f"❌ **Generation failed:** {err}" + (f"\n\nChoose an event/year and add it to your input: {choices}" if choices else "")

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

        if result.news_details:
            info=result.news_details.get("input", {})
            status_md += f"\n\n**News source:** {info.get('basis', '')} · {info.get('subject', '')} · {info.get('event_date') or 'Date unknown'}"
            status_md += "\n\n" + "\n".join(f"- [{src['title']}]({src['url']})" if src.get('url') else "- User-supplied account" for src in result.news_details.get('sources', []))
            status_md += "\n\n" + "\n".join(result.news_details.get('warnings', []))
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

            content_mode = gr.Dropdown(label="Content mode", choices=[(v["label"], k) for k,v in config.CONTENT_MODES.items() if k in ("article", "news")], value="article")
            news_source_policy = gr.Dropdown(label="News source", choices=[("Auto", "auto"), ("Online research", "online"), ("Use my account", "supplied")], value="auto", visible=False)
            news_note = gr.Markdown("Research or use your account, then create a paper-cutout news explainer. Fixed editorial cutouts, grey phrases and restrained motion.", visible=False)
            news_music = gr.Checkbox(label="Quiet News background music",value=False,visible=False)
            content_mode.change(lambda mode: (gr.update(visible=mode=="news"),gr.update(visible=mode=="news"),gr.update(visible=mode=="news")), inputs=content_mode, outputs=[news_source_policy,news_note,news_music])
            visual_preset = gr.Dropdown(label="News visual preset", choices=[("Classic cutouts", "default"),("Reference editorial · Remotion, vertical", "reference_editorial")], value="default", visible=False)
            editorial_text = gr.Dropdown(label="Editorial text",choices=[("Progressive editorial phrases", "editorial"),("Complete spoken captions", "complete")],value="editorial",visible=False)
            editorial_assets = gr.Dropdown(label="Editorial assets",choices=[("Automatic · portraits + AI cutouts", "auto"),("Prefer stock / credited references", "stock"),("AI supporting illustrations + portraits", "ai")],value="auto",visible=False)
            content_mode.change(lambda mode: tuple(gr.update(visible=mode=="news") for _ in range(3)), inputs=content_mode, outputs=[visual_preset,editorial_text,editorial_assets])
            with gr.Accordion("⚙️ Generation Options", open=False):
                renderer = gr.Dropdown(label="Renderer", choices=["moviepy", "remotion"], value="moviepy")
                target_duration = gr.Number(label="Target seconds (0 = in-depth adaptive ~60-90s)",value=0,minimum=0,maximum=600,precision=0)
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
                    value=not bool(getattr(config, "PEXELS_API_KEY", None) or os.getenv("PEXELS_API_KEY")),
                    info="Enabled automatically if PEXELS_API_KEY is not set",
                )

            news_preview_btn = gr.Button("Preview News script / sources")
            news_preview = gr.Markdown()
            def preview_news_ui(text, url, policy):
                from agent.news_pipeline import preview_news
                from agent.news_models import NewsError
                try:
                    p=preview_news("\n".join(v for v in (url.strip(),text.strip()) if v), source_policy=policy)
                    info=p["input"]
                    links="\n".join(f"- [{source['title']}]({source['url']})" if source['url'] else "- User-supplied account" for source in p['evidence']['sources'])
                    return f"**{info['subject']}** · {info['event_date'] or 'Date unknown'} · {info['basis']}\n\n{p['script']['narration']}\n\n{links}"
                except NewsError as exc:
                    return str(exc)+"\n\n"+" / ".join(exc.choices)
                except Exception as exc:
                    return str(exc)
            news_preview_btn.click(preview_news_ui, inputs=[input_text,input_url,news_source_policy], outputs=news_preview)
            generate_btn = gr.Button(
                "🎬  Generate Video",
                variant="primary",
                size="lg",
            )

        # ── Right column: Output ──────────────────────────────────────────────
        with gr.Column(scale=5):
            video_out = gr.Video(
                label="Generated Video",
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
            content_mode, news_source_policy, renderer, target_duration, news_music, visual_preset, editorial_text, editorial_assets,
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
