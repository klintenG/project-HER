#!/usr/bin/env python3
"""
Project HER v2.0 – Web UI (Flask)
Interactive web interface for testing all video generation features.

Launch:  python web_ui.py
Opens:   http://localhost:7860
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
import queue
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, jsonify, send_from_directory, Response

import config
from utils.llm_client import get_provider_info

# ── Logging ───────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
for logger_name in ["urllib3", "httpx", "openai", "moviepy", "PIL", "httpcore"]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

logger = logging.getLogger("web_ui")

app = Flask(__name__, template_folder="templates", static_folder="output")

# ── SSE Progress Infrastructure ───────────────────────

# Active generation jobs: job_id → queue of SSE events
_active_jobs: dict[str, queue.Queue] = {}
_job_results: dict[str, dict] = {}
_job_lock = threading.Lock()


def _create_sse_callback(job_id: str):
    """Create a progress callback that pushes events to an SSE queue."""
    from utils.progress import StageInfo

    def callback(stage: StageInfo):
        q = _active_jobs.get(job_id)
        if q:
            event = {
                "stage": stage.name,
                "label": stage.label,
                "index": stage.index,
                "total": stage.total,
                "status": stage.status,
                "message": stage.message,
                "elapsed": round(stage.elapsed, 1),
                "progress_pct": round(stage.progress_pct, 3),
                "detail": stage.detail,
            }
            q.put(("progress", event))
    return callback


# ── Routes ────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main UI page."""
    return render_template(
        "index.html",
        themes=list(config.THEMES.keys()),
        theme_details=config.THEMES,
        captions=list(config.CAPTION_STYLES.keys()),
        caption_details=config.CAPTION_STYLES,
        transitions=config.AVAILABLE_TRANSITIONS,
        tones=list(config.TONE_PRESETS.keys()),
        tone_details=config.TONE_PRESETS,
        voices=config.AVAILABLE_VOICES,
        platforms=config.AVAILABLE_PLATFORMS,
        platform_details=config.PLATFORM_PRESETS,
        qualities=list(config.QUALITY_PRESETS.keys()),
        quality_details=config.QUALITY_PRESETS,
        formats=list(config.VIDEO_FORMATS.keys()),
        format_details=config.VIDEO_FORMATS,
        color_grades=config.AVAILABLE_COLOR_GRADES,
        color_grade_details=config.COLOR_GRADES,
        default_color_grade=config.DEFAULT_COLOR_GRADE,
        languages=config.AVAILABLE_LANGUAGES,
        language_details=config.LANGUAGE_VOICES,
        visual_styles=config.AVAILABLE_VISUAL_STYLES,
        visual_style_details=config.VISUAL_STYLES,
        default_visual_style=config.DEFAULT_VISUAL_STYLE,
        # ── Content Modes ──
        content_modes=config.CONTENT_MODES,
        available_content_modes=config.AVAILABLE_CONTENT_MODES,
        default_content_mode=config.DEFAULT_CONTENT_MODE,
        ghost_collab_voices=config.GHOST_COLLAB_VOICES,
        # ── Deep Dive ──
        deep_dive_voices=config.DEEP_DIVE_VOICES,
        deep_dive_max_sources=config.DEEP_DIVE_MAX_SOURCES,
        # ── LLM Providers ──
        llm_providers=config.LLM_PROVIDERS,
        llm_provider=config.LLM_PROVIDER,
        copilot_bridge_model=config.COPILOT_BRIDGE_MODEL,
        provider_info=get_provider_info(),
    )


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Run the full video generation pipeline with SSE progress support."""
    data = request.json

    input_url = data.get("url", "").strip()
    input_text = data.get("text", "").strip()
    input_source = input_url or input_text

    # Content mode handling
    content_mode = data.get("content_mode", "article")
    question = data.get("question", "").strip()
    character_name = data.get("character_name", "").strip()
    modern_topic = data.get("modern_topic", "").strip()
    voice_pair = data.get("voice_pair", "default")
    series_id = data.get("series_id", "").strip()
    episode_number = int(data.get("episode_number", 0) or 0)

    # Deep Dive mode: collect multiple sources
    deep_dive_sources = data.get("deep_dive_sources", [])
    deep_dive_text = data.get("deep_dive_text", "").strip()

    # For thought_experiment and ghost_collab, input_source is not required
    # but we need question or character_name
    if content_mode == "deep_dive":
        # Multi-source mode
        if not deep_dive_sources and not deep_dive_text and not input_source:
            return jsonify({"error": "Please provide at least one URL or text for Deep Dive."}), 400
        # Use deep_dive_text as fallback input_source
        if not input_source:
            input_source = deep_dive_text or "Deep Dive"
    elif content_mode == "thought_experiment":
        if not question:
            return jsonify({"error": "Please provide a question for the thought experiment."}), 400
        input_source = input_source or question  # use question as fallback input
    elif content_mode == "ghost_collab":
        if not character_name:
            return jsonify({"error": "Please provide a character name for Ghost Collaboration."}), 400
        input_source = input_source or f"Dialogue with {character_name}"
    elif not input_source:
        return jsonify({"error": "Please provide a URL or text content."}), 400

    ai_images = data.get("ai_images", False)
    brand_text = data.get("brand_text", "")

    # LLM provider override from UI
    llm_provider = data.get("llm_provider", "").strip() or None
    llm_model = data.get("llm_model", "").strip() or None

    # For thought_experiment, ghost_collab, and deep_dive, force AI images on
    if content_mode in ("thought_experiment", "ghost_collab", "deep_dive"):
        ai_images = True

    # Validate LLM API key for selected provider
    effective_provider = llm_provider or config.LLM_PROVIDER
    pinfo = get_provider_info(effective_provider)
    if not pinfo["ready"]:
        # For copilot_bridge, offer a helpful message about VS Code
        if effective_provider == "copilot_bridge":
            return jsonify({"error": (
                f"Copilot Bridge not reachable. Make sure VS Code is open "
                f"with the Copilot Bridge extension active ({config.COPILOT_BRIDGE_URL}). "
                "Or switch to a different LLM provider."
            )}), 400
        return jsonify({"error": f"API key not set for {pinfo['label']}. Check your .env file."}), 400
    if not config.PEXELS_API_KEY and not ai_images:
        return jsonify({"error": "PEXELS_API_KEY not set in .env (or enable AI Images mode)"}), 400

    tone = data.get("tone", "informative")
    video_format = data.get("format", "vertical")
    voice = data.get("voice", "")
    theme = data.get("theme", "cinematic")
    captions = data.get("captions", "karaoke")
    transition = data.get("transition", "fade")
    platform = data.get("platform", "")
    quality = data.get("quality", "standard")
    watermark = data.get("watermark", "")
    num_points = data.get("points", 0)
    include_subtitles = data.get("subtitles", True)
    color_grade = data.get("color_grade", config.DEFAULT_COLOR_GRADE)
    language = data.get("language", "")
    speed = data.get("speed", "")
    visual_style = data.get("visual_style", config.DEFAULT_VISUAL_STYLE)

    # Apply Phase 5 premium options
    if speed:
        config.VOICE_SPEED = speed
    if language and language in config.LANGUAGE_VOICES:
        lang_voice = config.LANGUAGE_VOICES[language]["voice"]
        voice = lang_voice

    # Apply platform preset
    if platform and platform not in ("", "(none)"):
        preset = config.PLATFORM_PRESETS[platform]
        video_format = preset["format"]
        theme = preset["recommended_theme"]
        captions = preset["recommended_captions"]
        transition = preset["recommended_transition"]
        config.TARGET_DURATION = preset["target_duration"]
        config.VIDEO_BITRATE = preset["bitrate"]
        config.FPS = preset["fps"]
        if not num_points:
            num_points = preset["max_points"]

    # Apply watermark
    config.WATERMARK_TEXT = watermark if watermark else ""

    # Apply quality
    if quality:
        qp = config.QUALITY_PRESETS.get(quality, config.QUALITY_PRESETS["standard"])
        config.VIDEO_BITRATE = qp["bitrate"]
        config.FPS = qp["fps"]
        config.RENDER_THREADS = qp["threads"]

    pts = int(num_points) if num_points and int(num_points) >= 3 else None

    # Create job for SSE progress tracking
    import uuid
    job_id = str(uuid.uuid4())[:8]

    with _job_lock:
        _active_jobs[job_id] = queue.Queue()

    progress_cb = _create_sse_callback(job_id)

    def _run_pipeline():
        try:
            from agent.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            result = orchestrator.run(
                input_source=input_source,
                tone=tone,
                video_format=video_format,
                voice=config.AVAILABLE_VOICES.get(voice, voice) if voice else None,
                num_points=pts,
                include_subtitles=include_subtitles,
                theme=theme,
                caption_style=captions,
                transition=transition,
                color_grade=color_grade,
                progress_callback=progress_cb,
                ai_images=ai_images,
                brand_text=brand_text,
                visual_style=visual_style,
                content_mode=content_mode,
                question=question,
                character_name=character_name,
                modern_topic=modern_topic,
                voice_pair=voice_pair,
                series_id=series_id,
                episode_number=episode_number,
                deep_dive_sources=deep_dive_sources,
                deep_dive_text=deep_dive_text,
                renderer=data.get("renderer", "moviepy"),
            )

            if not result.success:
                _job_results[job_id] = {"error": "; ".join(result.errors)}
                q = _active_jobs.get(job_id)
                if q:
                    q.put(("done", {"error": "; ".join(result.errors)}))
                return

            video_rel = str(Path(result.video_path).relative_to(config.OUTPUT_DIR)) if result.video_path else None
            thumb_rel = str(Path(result.thumbnail_path).relative_to(config.OUTPUT_DIR)) if result.thumbnail_path else None
            srt_rel = str(Path(result.srt_path).relative_to(config.OUTPUT_DIR)) if result.srt_path else None

            result_data = {
                "success": True,
                "title": result.title,
                "hook": result.hook,
                "duration": round(result.duration, 1),
                "resolution": result.resolution,
                "key_points": result.key_point_count,
                "content_type": result.content_type,
                "mood": result.mood,
                "theme": result.theme,
                "caption_style": result.caption_style,
                "processing_time": round(result.processing_time, 1),
                "video_url": f"/output/{video_rel}" if video_rel else None,
                "thumbnail_url": f"/output/{thumb_rel}" if thumb_rel else None,
                "srt_url": f"/output/{srt_rel}" if srt_rel else None,
            }
            _job_results[job_id] = result_data
            q = _active_jobs.get(job_id)
            if q:
                q.put(("done", result_data))

        except Exception as e:
            logger.error("Pipeline error: %s", e, exc_info=True)
            _job_results[job_id] = {"error": str(e)}
            q = _active_jobs.get(job_id)
            if q:
                q.put(("done", {"error": str(e)}))

    # Start pipeline in background thread
    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    """SSE endpoint for real-time pipeline progress updates."""
    def event_stream():
        q = _active_jobs.get(job_id)
        if not q:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        while True:
            try:
                event_type, data = q.get(timeout=120)
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                if event_type == "done":
                    # Cleanup
                    with _job_lock:
                        _active_jobs.pop(job_id, None)
                    break
            except queue.Empty:
                # Send keepalive
                yield ": keepalive\n\n"

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Run scrape + analyze only for quick preview."""
    data = request.json

    input_source = data.get("url", "").strip() or data.get("text", "").strip()
    if not input_source:
        return jsonify({"error": "Provide a URL or text."}), 400

    tone = data.get("tone", "informative")
    pts = data.get("points", 0)
    pts = int(pts) if pts and int(pts) >= 3 else None

    try:
        from agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        analysis = orchestrator.preview_analysis(input_source, tone=tone, num_points=pts)

        key_points = []
        for kp in analysis.key_points:
            key_points.append({
                "index": kp.index,
                "headline": kp.headline,
                "narration": kp.narration,
                "emotion": kp.emotion,
                "visual_query": kp.visual_query,
            })

        return jsonify({
            "title": analysis.title,
            "hook": analysis.hook,
            "content_type": analysis.content_type,
            "mood": analysis.mood,
            "summary": analysis.summary,
            "cta": analysis.cta,
            "key_points": key_points,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
def api_history():
    """List previous outputs."""
    output_dir = config.OUTPUT_DIR
    entries = []

    if output_dir.exists():
        for entry in sorted(output_dir.iterdir(), reverse=True):
            if entry.is_dir():
                mp4s = list(entry.glob("*.mp4"))
                thumbs = list(entry.glob("thumbnail.jpg"))
                srts = list(entry.glob("*.srt"))
                if mp4s:
                    rel = str(mp4s[0].relative_to(config.OUTPUT_DIR))
                    item = {
                        "name": entry.name,
                        "video": mp4s[0].name,
                        "video_url": f"/output/{rel}",
                        "size_kb": mp4s[0].stat().st_size // 1024,
                    }
                    if thumbs:
                        item["thumbnail_url"] = f"/output/{str(thumbs[0].relative_to(config.OUTPUT_DIR))}"
                    if srts:
                        item["srt_url"] = f"/output/{str(srts[0].relative_to(config.OUTPUT_DIR))}"
                    entries.append(item)

    return jsonify({"outputs": entries[:20]})


@app.route("/output/<path:filename>")
def serve_output(filename):
    """Serve files from the output directory."""
    return send_from_directory(config.OUTPUT_DIR, filename)


@app.route("/api/series")
def api_series():
    """List all available series."""
    series_dir = config.SERIES_DIR
    entries = []
    if series_dir.exists():
        for f in sorted(series_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entries.append({
                    "series_id": data.get("series_id", f.stem),
                    "last_episode": data.get("last_episode", 0),
                    "next_episode": data.get("next_episode", 1),
                    "last_title": data.get("last_title", ""),
                    "last_cliffhanger": data.get("last_cliffhanger", ""),
                    "content_mode": data.get("content_mode", "article"),
                    "updated_at": data.get("updated_at", ""),
                    "episode_count": len(data.get("episodes", [])),
                })
            except Exception:
                continue
    return jsonify({"series": entries})


# ── Effect Preview Cache (Remotion Studio) ────────────

_effect_preview_lock = threading.Lock()
_effect_preview_cache: dict[str, str] = {}  # "category:name" → relative path

PREVIEW_DIR = Path("remotion/public/previews")
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


@app.route("/api/effect-preview", methods=["POST"])
def api_effect_preview():
    """Render a short Remotion effect preview (cached).

    Input JSON: { "category": "text_entry", "name": "scale_bounce" }
    Returns:    { "url": "/effect-previews/text_entry__scale_bounce.mp4" }
    """
    import subprocess

    data = request.json or {}
    category = data.get("category", "").strip()
    name = data.get("name", "").strip()

    if not category or not name:
        return jsonify({"error": "category and name are required"}), 400

    cache_key = f"{category}__{name}"
    output_file = PREVIEW_DIR / f"{cache_key}.mp4"

    # Check cache
    if output_file.exists():
        return jsonify({"url": f"/effect-previews/{cache_key}.mp4"})

    # Render via Remotion CLI
    remotion_dir = Path("remotion")
    props = json.dumps({"effectCategory": category, "effectName": name})

    cmd = [
        "npx", "remotion", "render",
        "EffectPreview",
        str(output_file.resolve()),
        "--props", props,
        "--concurrency", "2",
    ]

    logger.info(f"Rendering effect preview: {category}/{name}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(remotion_dir.resolve()),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"Remotion render failed: {result.stderr[:500]}")
            return jsonify({"error": "Render failed", "details": result.stderr[:300]}), 500

        logger.info(f"Preview rendered: {output_file}")
        return jsonify({"url": f"/effect-previews/{cache_key}.mp4"})

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Render timed out"}), 504
    except Exception as e:
        logger.error(f"Preview render error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/effect-previews/<path:filename>")
def serve_effect_preview(filename):
    """Serve cached effect preview videos."""
    return send_from_directory(str(PREVIEW_DIR.resolve()), filename)


@app.route("/api/effect-catalog")
def api_effect_catalog():
    """Return the full catalog of available Remotion effects."""
    catalog = {
        "text_entry": {
            "label": "Text Entry Animations",
            "icon": "bi-type-bold",
            "description": "How text appears on screen",
            "effects": [
                {"name": "fade_in", "label": "Fade In", "desc": "Smooth opacity fade from transparent"},
                {"name": "slide_up", "label": "Slide Up", "desc": "Spring-powered slide from below"},
                {"name": "slide_down", "label": "Slide Down", "desc": "Spring-powered slide from above"},
                {"name": "scale_bounce", "label": "Scale Bounce", "desc": "Bouncy scale from small to normal"},
                {"name": "stamp_in", "label": "Stamp In", "desc": "Heavy impact with shake"},
                {"name": "elastic_drop", "label": "Elastic Drop", "desc": "Falls from top with elastic bounce"},
                {"name": "blur_reveal", "label": "Blur Reveal", "desc": "From blurry to sharp focus"},
                {"name": "zoom_blur_in", "label": "Zoom Blur In", "desc": "Distant zoom with blur"},
                {"name": "grow_from_center", "label": "Grow From Center", "desc": "Expands outward from center"},
                {"name": "curtain_reveal", "label": "Curtain Reveal", "desc": "Clip reveals from center outward"},
                {"name": "smoke_reveal", "label": "Smoke Reveal", "desc": "Opacity pulse with blur wobble"},
                {"name": "spiral_in", "label": "Spiral In", "desc": "Rotation + scale entrance"},
                {"name": "glitch_in", "label": "Glitch In", "desc": "Digital distortion entrance"},
                {"name": "flip_in_3d", "label": "3D Flip In", "desc": "Rotates from behind on Y axis"},
                {"name": "tilt_in_3d", "label": "3D Tilt In", "desc": "Rotates from below on X axis"},
                {"name": "typewriter", "label": "Typewriter", "desc": "Character-by-character reveal"},
                {"name": "slide_left", "label": "Slide Left", "desc": "Enter from left side"},
                {"name": "slide_right", "label": "Slide Right", "desc": "Enter from right side"},
                {"name": "card_flip_3d", "label": "3D Card Flip", "desc": "Flips like a card face-up"},
            ],
        },
        "text_exit": {
            "label": "Text Exit Animations",
            "icon": "bi-type-strikethrough",
            "description": "How text disappears from screen",
            "effects": [
                {"name": "fade_out", "label": "Fade Out", "desc": "Smooth opacity fade to transparent"},
                {"name": "slide_out_up", "label": "Slide Out Up", "desc": "Slides upward and fades"},
                {"name": "slide_out_down", "label": "Slide Out Down", "desc": "Slides downward and fades"},
                {"name": "dissolve_out", "label": "Dissolve Out", "desc": "Fade + slight scale + blur"},
                {"name": "evaporate", "label": "Evaporate", "desc": "Drifts up, fades and blurs"},
                {"name": "explode_out", "label": "Explode Out", "desc": "Rapid scale-up exit"},
                {"name": "swipe_wipe", "label": "Swipe Wipe", "desc": "Clips away from the side"},
                {"name": "scale_shrink", "label": "Scale Shrink", "desc": "Shrinks to nothing"},
                {"name": "blur_exit", "label": "Blur Exit", "desc": "Blur + fade"},
                {"name": "flick_off", "label": "Flick Off", "desc": "Quick slide to right with rotation"},
                {"name": "glitch_out", "label": "Glitch Out", "desc": "Digital distortion exit"},
                {"name": "vortex_out", "label": "Vortex Out", "desc": "Spins away while shrinking"},
                {"name": "flip_out_3d", "label": "3D Flip Out", "desc": "Flips away on Y axis"},
                {"name": "crumble", "label": "Crumble", "desc": "Breaks apart downward"},
            ],
        },
        "text_continuous": {
            "label": "Text Continuous Effects",
            "icon": "bi-infinity",
            "description": "Looping effects while text is displayed",
            "effects": [
                {"name": "none", "label": "None", "desc": "No continuous effect"},
                {"name": "breathe", "label": "Breathe", "desc": "Gentle scale pulse"},
                {"name": "glow_pulse", "label": "Glow Pulse", "desc": "Cycling text shadow glow"},
                {"name": "shake", "label": "Shake", "desc": "Nervous tremor vibration"},
                {"name": "wave_motion", "label": "Wave Motion", "desc": "Gentle up/down oscillation"},
                {"name": "float_drift", "label": "Float Drift", "desc": "Slow horizontal/vertical drift"},
                {"name": "flicker", "label": "Flicker", "desc": "Horror/suspense strobe"},
                {"name": "heartbeat", "label": "Heartbeat", "desc": "Rhythmic scale pulse"},
                {"name": "pendulum", "label": "Pendulum", "desc": "Gentle rotation swing"},
                {"name": "bounce", "label": "Bounce", "desc": "Rhythmic vertical bounce"},
                {"name": "fire_flicker", "label": "Fire Flicker", "desc": "Warm color shift + opacity"},
                {"name": "wobble_3d", "label": "3D Wobble", "desc": "Multi-axis rotation wobble"},
                {"name": "neon_flash", "label": "Neon Flash", "desc": "Pulsing neon glow"},
            ],
        },
        "image_entry": {
            "label": "Image Entry Animations",
            "icon": "bi-image",
            "description": "How images appear on screen",
            "effects": [
                {"name": "img_fade_in", "label": "Fade In", "desc": "Smooth opacity fade"},
                {"name": "img_scale_bounce", "label": "Scale Bounce", "desc": "Bouncy scale entrance"},
                {"name": "img_zoom_in", "label": "Zoom In", "desc": "Zoom from distance with blur"},
                {"name": "img_blur_reveal", "label": "Blur Reveal", "desc": "From blurry to sharp"},
                {"name": "img_slide_left", "label": "Slide Left", "desc": "Slides in from left"},
                {"name": "img_3d_entrance", "label": "3D Entrance", "desc": "Perspective rotation entrance"},
            ],
        },
        "image_treatment": {
            "label": "Image Treatments",
            "icon": "bi-magic",
            "description": "Ongoing effects while image is displayed",
            "effects": [
                {"name": "ken_burns", "label": "Ken Burns", "desc": "Slow zoom + pan (cinematic)"},
                {"name": "zoom_pulse", "label": "Zoom Pulse", "desc": "Rhythmic breathing zoom"},
                {"name": "parallax_2d", "label": "Parallax 2D", "desc": "Horizontal shift over time"},
                {"name": "brightness_pulse", "label": "Brightness Pulse", "desc": "Cycling brightness"},
                {"name": "color_shift", "label": "Color Shift", "desc": "Temperature shift over time"},
                {"name": "vignette", "label": "Vignette", "desc": "Dark edges framing"},
                {"name": "tilt_shift", "label": "Tilt Shift", "desc": "Blur top/bottom edges"},
                {"name": "sepia_blend", "label": "Sepia Blend", "desc": "Gradual sepia coloring"},
                {"name": "desaturate_to_color", "label": "Desaturate", "desc": "Gradual color drain"},
                {"name": "gentle_3d_tilt", "label": "3D Tilt", "desc": "Slow perspective rotation"},
                {"name": "film_grain", "label": "Film Grain", "desc": "Contrast + brightness tweak"},
                {"name": "cinematic_crop", "label": "Cinematic Crop", "desc": "Letterbox framing"},
            ],
        },
        "image_exit": {
            "label": "Image Exit Animations",
            "icon": "bi-image-alt",
            "description": "How images disappear from screen",
            "effects": [
                {"name": "img_fade_out", "label": "Fade Out", "desc": "Smooth opacity fade"},
                {"name": "img_zoom_out", "label": "Zoom Out", "desc": "Zooms out while fading"},
                {"name": "img_blur_out", "label": "Blur Out", "desc": "Blurs and fades out"},
            ],
        },
        "transition": {
            "label": "Scene Transitions",
            "icon": "bi-arrows-expand",
            "description": "How scenes change from one to the next",
            "effects": [
                {"name": "crossfade", "label": "Crossfade", "desc": "Simple opacity crossfade"},
                {"name": "flash_transition", "label": "Flash", "desc": "White flash between scenes"},
                {"name": "circle_wipe", "label": "Circle Wipe", "desc": "Expanding circle reveal"},
                {"name": "slide_horizontal", "label": "Slide Horizontal", "desc": "Push from right"},
                {"name": "wipe_left", "label": "Wipe Left", "desc": "Hard edge wipe left"},
                {"name": "wipe_right", "label": "Wipe Right", "desc": "Hard edge wipe right"},
                {"name": "wipe_down", "label": "Wipe Down", "desc": "Vertical wipe top to bottom"},
                {"name": "ink_bleed", "label": "Ink Bleed", "desc": "Organic blob-like mask"},
                {"name": "blur_transition", "label": "Blur Transition", "desc": "Blur out / blur in"},
                {"name": "pixelate_transition", "label": "Pixelate", "desc": "Pixelate out, sharpen in"},
                {"name": "zoom_in", "label": "Zoom In", "desc": "Zooms into next scene"},
                {"name": "zoom_out", "label": "Zoom Out", "desc": "Zooms out to next scene"},
                {"name": "elastic_bounce", "label": "Elastic Bounce", "desc": "Scene bounces into place"},
                {"name": "glitch_transition", "label": "Glitch", "desc": "Digital break between scenes"},
                {"name": "cube_rotate_3d", "label": "3D Cube Rotate", "desc": "Y-axis cube rotation"},
                {"name": "page_flip_3d", "label": "3D Page Flip", "desc": "Book page flip"},
                {"name": "dissolve", "label": "Dissolve", "desc": "Granular crossfade with blur"},
                {"name": "morph", "label": "Morph", "desc": "Scale + blur + crossfade"},
            ],
        },
        "overlay": {
            "label": "Overlays",
            "icon": "bi-layers",
            "description": "Visual layers on top of the scene",
            "effects": [
                {"name": "subtle_grain", "label": "Subtle Grain", "desc": "Film grain texture"},
                {"name": "bokeh_overlay", "label": "Bokeh", "desc": "Out-of-focus light orbs"},
                {"name": "fire_embers", "label": "Fire Embers", "desc": "Floating ember particles"},
                {"name": "sparkle_overlay", "label": "Sparkle", "desc": "Twinkling sparkle particles"},
                {"name": "dust_particles", "label": "Dust Particles", "desc": "Floating dust motes"},
                {"name": "scan_lines", "label": "Scan Lines", "desc": "CRT monitor scan lines"},
                {"name": "chromatic_aberration", "label": "Chromatic Aberration", "desc": "Color fringing effect"},
                {"name": "vhs_distortion", "label": "VHS Distortion", "desc": "Retro VHS static lines"},
                {"name": "rain_overlay", "label": "Rain", "desc": "Falling rain drops"},
            ],
        },
        "background": {
            "label": "Backgrounds",
            "icon": "bi-paint-bucket",
            "description": "Animated scene backgrounds",
            "effects": [
                {"name": "bg_color_breathe", "label": "Color Breathe", "desc": "Gentle color cycling"},
                {"name": "bg_gradient_shift", "label": "Gradient Shift", "desc": "Rotating gradient colors"},
                {"name": "bg_pulse", "label": "Pulse", "desc": "Radial darkness pulse"},
                {"name": "bg_particle_float", "label": "Particle Float", "desc": "Floating particles background"},
                {"name": "bg_aurora", "label": "Aurora", "desc": "Northern lights shimmer"},
                {"name": "bg_radial_pulse", "label": "Radial Pulse", "desc": "Concentric ring pulses"},
            ],
        },
    }

    # Add cached status
    for cat_key, cat_data in catalog.items():
        for eff in cat_data["effects"]:
            cache_file = PREVIEW_DIR / f"{cat_key}__{eff['name']}.mp4"
            eff["cached"] = cache_file.exists()

    return jsonify(catalog)


# ── Entry Point ───────────────────────────────────────

if __name__ == "__main__":
    print("\n🎬 Project HER v2.0 – Web UI")
    print("   Open: http://localhost:7860\n")
    app.run(host="0.0.0.0", port=7860, debug=False, threaded=True)
