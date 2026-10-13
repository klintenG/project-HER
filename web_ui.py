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
import re
import time
import threading
import queue
import urllib.parse
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, jsonify, send_from_directory, Response, send_file
import io


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

# The main creation studio has a fixed editorial configuration. Keep it shared
# between its page, preview and generation; classic/API callers keep their modes.
STUDIO_GENERATION_DEFAULTS = {
    'tone':'informative', 'format':'vertical', 'visual_style':'claymorphism',
    'target_duration':0, 'content_mode':'news', 'renderer':'remotion',
    'visual_preset':'reference_editorial', 'editorial_text':'editorial',
    'editorial_assets':'auto', 'news_source_policy':'auto',
    'tts_provider':'replicate', 'news_music':False,
}


def _studio_request(data):
    if data.get('ui_profile')=='editorial_studio':
        return {**data,**STUDIO_GENERATION_DEFAULTS,'platform':'','local_assets':None}
    return data

# ── Allow CORS and iframe embedding ──────────────────────────────────────────
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        res = Response()
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
        res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Range, X-Requested-With"
        return res


@app.after_request
def allow_cors_and_framing(response):
    """Allow klinteng.com portfolio and local apps to access API and embed."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Range, X-Requested-With"
    response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Content-Disposition"
    response.headers.pop("X-Frame-Options", None)
    response.headers["Content-Security-Policy"] = (
        "frame-ancestors 'self' http://localhost:* http://127.0.0.1:* "
        "https://klinteng.com https://www.klinteng.com "
        "https://*.huggingface.co https://*.hf.space;"
    )
    if request.path in ("/api/generate", "/api/preview") and response.is_json:
        payload = response.get_json(silent=True) or {}
        if payload.get("error"):
            data = request.get_json(silent=True) or {}
            status = payload.get("status", "error")
            level = logging.WARNING if status == "needs_clarification" else logging.ERROR
            logger.log(level, "%s %s failed | mode=%s | HTTP %s | status=%s | %s",
                request.method, request.path, data.get("content_mode", "article"),
                response.status_code, status, payload["error"])
    native_cors=app.extensions.get('her_portfolio_cors')
    return native_cors(response) if native_cors else response

# ── SSE Progress Infrastructure & Concurrency Tracking ───────────────────────

# Concurrency tracking: job_id → dict with metadata (started: float, thread: Optional[Thread])
_active_jobs: dict[str, dict] = {}
# SSE progress event queues: job_id → queue.Queue
_progress_queues: dict[str, queue.Queue] = {}
_job_results: dict[str, dict] = {}
_job_lock = threading.Lock()


def _prune_active_jobs():
    """Remove finished workers and abandoned reservations; retain live jobs."""
    now = time.time()
    with _job_lock:
        for jid in list(_active_jobs.keys()):
            meta = _active_jobs[jid]
            th = meta.get("thread") if isinstance(meta, dict) else None
            started = meta.get("started", 0) if isinstance(meta, dict) else 0
            if (th is not None and not th.is_alive()) or (th is None and now - started > 600) or (jid in _job_results):
                _active_jobs.pop(jid, None)


def _create_sse_callback(job_id: str):
    """Create a progress callback that pushes events to an SSE queue."""
    from utils.progress import StageInfo

    def callback(stage: StageInfo):
        with _job_lock:
            job = _active_jobs.get(job_id)
            if job is not None:
                job["stage"] = stage.name
        q = _progress_queues.get(job_id)
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


def _log_job_failure(job_id, content_mode, error, status="error", *, exc_info=False):
    """Mirror the UI error in server logs, including failures returned as results."""
    with _job_lock:
        stage = _active_jobs.get(job_id, {}).get("stage", "initializing")
    level = logging.INFO if status == "cancelled" else logging.WARNING if status == "needs_clarification" else logging.ERROR
    logger.log(level, "Job %s | mode=%s | stage=%s | status=%s | %s",
        job_id, content_mode, stage, status, error, exc_info=exc_info)



# ── Routes ────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main UI page."""
    return render_template(
        "index.html",
        studio_defaults=STUDIO_GENERATION_DEFAULTS,
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
        gemini_model=config.GEMINI_MODEL,
        provider_info=get_provider_info(),
    )


@app.route("/backup")
@app.route("/classic")
def backup_ui():
    """Serve the original full UI page for backward compatibility / reference."""
    return render_template(
        "index_backup.html",
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
        content_modes=config.CONTENT_MODES,
        available_content_modes=config.AVAILABLE_CONTENT_MODES,
        default_content_mode=config.DEFAULT_CONTENT_MODE,
        ghost_collab_voices=config.GHOST_COLLAB_VOICES,
        deep_dive_voices=config.DEEP_DIVE_VOICES,
        deep_dive_max_sources=config.DEEP_DIVE_MAX_SOURCES,
        llm_providers=config.LLM_PROVIDERS,
        llm_provider=config.LLM_PROVIDER,
        gemini_model=config.GEMINI_MODEL,
        provider_info=get_provider_info(),
    )


# ── Public-demo usage limits (protect API quota / free hosting) ───────
# Set a value to 0 to disable that limit (e.g. for local development).
DAILY_VIDEO_CAP = int(os.environ.get("DAILY_VIDEO_CAP", "10"))
PER_VISITOR_DAILY_CAP = int(os.environ.get("PER_VISITOR_DAILY_CAP", "2"))
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "1"))

_usage_lock = threading.Lock()
_usage = {"day": "", "total": 0, "per_ip": {}}


def _is_deployed_env() -> bool:
    """Check if the application is running in a deployed cloud environment."""
    return any([
        os.environ.get("RAILWAY_ENVIRONMENT"),
        os.environ.get("RAILWAY_STATIC_URL"),
        os.environ.get("RAILWAY_PUBLIC_DOMAIN"),
        os.environ.get("K_SERVICE"),           # Google Cloud Run
        os.environ.get("RENDER"),              # Render
        os.environ.get("SPACE_ID"),            # Hugging Face Spaces
        os.environ.get("DYNO"),                # Heroku
        os.environ.get("VERCEL"),              # Vercel
        os.environ.get("FLY_APP_NAME"),        # Fly.io
        os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod", "staging", "deployed"),
        os.environ.get("ENV", "").lower() in ("production", "prod", "staging", "deployed"),
    ])


def _is_local_request() -> bool:
    """Check if the incoming HTTP request is strictly local (localhost / 127.0.0.1)."""
    # If forwarded through an external proxy, check original client IP
    fwd = request.headers.get("X-Forwarded-For", "").strip()
    if fwd:
        first_ip = fwd.split(",")[0].strip()
        if first_ip not in ("127.0.0.1", "::1", "localhost"):
            return False

    host = (request.host or "").split(":")[0].lower()
    local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver"}
    remote_ip = request.remote_addr or ""
    is_loopback_ip = remote_ip in ("127.0.0.1", "::1", "localhost", "0.0.0.0")

    return is_loopback_ip and (host in local_hosts or host.endswith(".local"))


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")


def _check_and_reserve_quota() -> Optional[str]:
    """Return an error message if the request is over a limit, else reserve a slot.

    Daily video caps only apply to public visitors on deployed URLs.
    Local workspace development has unlimited generations (concurrency limit still applies).
    """
    # Concurrency limit prevents simultaneous ffmpeg renders from clashing
    _prune_active_jobs()
    with _job_lock:
        active_count = len(_active_jobs)
    if MAX_CONCURRENT_JOBS and active_count >= MAX_CONCURRENT_JOBS:
        return "Another video is being generated right now. Please try again in a few minutes."

    # Bypass daily caps in local development workspace unless explicitly forced
    force_limits = os.environ.get("FORCE_DEMO_LIMITS", "").lower() in ("true", "1", "yes")
    is_local = ((not _is_deployed_env()) or _is_local_request()) and not force_limits
    if is_local:
        return None

    today = time.strftime("%Y-%m-%d")
    ip = _client_ip()
    with _usage_lock:
        if _usage["day"] != today:
            _usage.update(day=today, total=0, per_ip={})
        if DAILY_VIDEO_CAP and _usage["total"] >= DAILY_VIDEO_CAP:
            return "Today's free demo limit has been reached. Please come back tomorrow!"
        if PER_VISITOR_DAILY_CAP and _usage["per_ip"].get(ip, 0) >= PER_VISITOR_DAILY_CAP:
            return f"Demo limit reached ({PER_VISITOR_DAILY_CAP} videos per visitor per day)."
        _usage["total"] += 1
        _usage["per_ip"][ip] = _usage["per_ip"].get(ip, 0) + 1
    return None


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Run the full video generation pipeline with SSE progress support."""
    data = _studio_request(request.json)

    limit_error = _check_and_reserve_quota()
    if limit_error:
        return jsonify({"error": limit_error}), 429

    input_url = data.get("url", "").strip()
    input_text = data.get("text", "").strip()
    input_source = input_url or input_text

    # Content mode handling
    content_mode = data.get("content_mode", "article")
    if content_mode == "news":
        return _start_news_job(data, "\n".join(v for v in (input_url, input_text) if v))
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
    elif content_mode == "kids_story":
        if not input_source:
            return jsonify({"error": "Please paste or write a story for Kids Story mode."}), 400
    elif not input_source:
        return jsonify({"error": "Please provide a URL or text content."}), 400

    ai_images = data.get("ai_images", True)
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
        return jsonify({"error": f"API key not set for {pinfo['label']}. Check GEMINI_API_KEY in your .env file."}), 400
    if not config.PEXELS_API_KEY and not ai_images:
        return jsonify({"error": "PEXELS_API_KEY not set in .env (or enable AI Images mode)"}), 400

    tone = data.get("tone", "explainer")
    video_format = data.get("format", "vertical")
    voice = data.get("voice", "")
    theme = data.get("theme", "cinematic")
    captions = data.get("captions", "karaoke")
    transition = data.get("transition", "fade")
    platform = data.get("platform", "")
    quality = data.get("quality", "standard")
    watermark = data.get("watermark", "")
    num_points = data.get("points", 0)
    target_duration = int(data.get("target_duration", 0) or 0)
    include_subtitles = data.get("subtitles", True)
    color_grade = data.get("color_grade", config.DEFAULT_COLOR_GRADE)
    language = data.get("language", "")
    speed = data.get("speed", "")
    visual_style = data.get("visual_style", config.DEFAULT_VISUAL_STYLE)

    # Apply Phase 5 premium options
    if speed:
        import re
        speed_str = str(speed).strip()
        if re.match(r"^[+-]\d+%$", speed_str):
            config.VOICE_SPEED = speed_str
        elif re.match(r"^\d+%$", speed_str):
            config.VOICE_SPEED = f"+{speed_str}"
        else:
            try:
                mult = float(speed_str.replace("x", ""))
                pct = int(round((mult - 1.0) * 100))
                config.VOICE_SPEED = f"{'+' if pct >= 0 else ''}{pct}%"
            except ValueError:
                config.VOICE_SPEED = "+0%"
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

    # Apply watermark (only override if user explicitly typed something;
    # otherwise keep .env / config.py default)
    if watermark:
        config.WATERMARK_TEXT = watermark

    # Apply quality
    if quality:
        qp = config.QUALITY_PRESETS.get(quality, config.QUALITY_PRESETS["standard"])
        config.VIDEO_BITRATE = qp["bitrate"]
        config.FPS = qp["fps"]
        config.RENDER_THREADS = qp["threads"]

    pts = int(num_points) if num_points and int(num_points) >= 3 else None

    # Create job for SSE progress tracking and concurrency control
    import uuid
    job_id = str(uuid.uuid4())[:8]

    with _job_lock:
        _progress_queues[job_id] = queue.Queue()
        _active_jobs[job_id] = {"started": time.time(), "thread": None}

    progress_cb = _create_sse_callback(job_id)

    def _run_pipeline():
        try:
            from agent.orchestrator import AgentOrchestrator

            # Override TTS provider from UI selection (only for Generate tab)
            tts_provider = data.get("tts_provider", "")
            if tts_provider and content_mode != "kids_story":
                config.TTS_PROVIDER = tts_provider

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
                visual_preset=data.get("visual_preset", "default"),
                question=question,
                character_name=character_name,
                modern_topic=modern_topic,
                voice_pair=voice_pair,
                series_id=series_id,
                episode_number=episode_number,
                deep_dive_sources=deep_dive_sources,
                deep_dive_text=deep_dive_text,
                renderer=(data.get("renderer") or getattr(config, "DEFAULT_RENDERER", "remotion")).strip(),
                target_duration=target_duration,
            )

            if not result.success:
                err_msg = "; ".join(result.errors) or "Generation failed"
                _log_job_failure(job_id, content_mode, err_msg)
                _job_results[job_id] = {"error": err_msg}
                q = _progress_queues.get(job_id)
                if q:
                    q.put(("done", {"error": err_msg}))
                return

            video_rel = None
            if result.video_path:
                try:
                    video_rel = str(Path(result.video_path).resolve().relative_to(config.OUTPUT_DIR.resolve()))
                except Exception:
                    try:
                        video_rel = str(Path(result.video_path).relative_to(config.OUTPUT_DIR))
                    except Exception:
                        video_rel = Path(result.video_path).name

            thumb_rel = None
            if result.thumbnail_path:
                try:
                    thumb_rel = str(Path(result.thumbnail_path).resolve().relative_to(config.OUTPUT_DIR.resolve()))
                except Exception:
                    thumb_rel = Path(result.thumbnail_path).name

            srt_rel = None
            if result.srt_path:
                try:
                    srt_rel = str(Path(result.srt_path).resolve().relative_to(config.OUTPUT_DIR.resolve()))
                except Exception:
                    srt_rel = Path(result.srt_path).name

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
                # Direct in-memory download — works even on ephemeral cloud hosts
                "download_url": f"/api/download/{job_id}" if video_rel else None,
            }
            _job_results[job_id] = result_data
            q = _progress_queues.get(job_id)
            if q:
                q.put(("done", result_data))

        except Exception as e:
            _log_job_failure(job_id, content_mode, str(e), exc_info=True)
            _job_results[job_id] = {"error": str(e)}
            q = _progress_queues.get(job_id)
            if q:
                q.put(("done", {"error": str(e)}))

        finally:
            # Concurrency slot is ALWAYS freed immediately when pipeline thread finishes
            with _job_lock:
                _active_jobs.pop(job_id, None)

    # Start pipeline in background thread
    thread = threading.Thread(target=_run_pipeline, daemon=True)
    with _job_lock:
        if job_id in _active_jobs:
            _active_jobs[job_id]["thread"] = thread
    thread.start()

    return jsonify({"job_id": job_id})


def _start_news_job(data, input_source):
    """News settings stay inside the job; legacy UI settings are untouched."""
    if not input_source:
        return jsonify({"error": "Provide a URL, event query, or supplied account."}), 400
    if data.get("news_source_policy", "auto") not in ("auto", "online", "supplied"):
        return jsonify({"error": "News source policy must be auto, online, or supplied."}), 400
    import uuid
    news_tts_provider = data.get("tts_provider") or config.TTS_PROVIDER
    cancel_event = threading.Event()
    job_id = uuid.uuid4().hex[:12]
    with _job_lock:
        _progress_queues[job_id] = queue.Queue()
        _active_jobs[job_id] = {"started": time.time(), "thread": None, "news": True, "cancel_event": cancel_event}
    def work():
        try:
            from agent.news_pipeline import run_news
            from agent.news_script import NewsLLM
            platform = config.PLATFORM_PRESETS.get(data.get("platform"), {})
            result = run_news(input_source,
                visual_preset=data.get("visual_preset", "default"),subtitle_mode=data.get("editorial_text", "editorial"),
                asset_mode=data.get("editorial_assets", "auto"),local_assets=data.get("local_assets") or None,
                source_policy=data.get("news_source_policy", "auto"),
                tone=data.get("tone", "informative"), language=data.get("language", "english"),
                target_duration=int(data.get("target_duration", 0) or 0),
                video_format=platform.get("format", data.get("format", "vertical")),
                renderer=data.get("renderer", config.DEFAULT_RENDERER),
                voice=data.get("voice"), tts_provider=news_tts_provider,
                speed=data.get("speed", "+0%"), quality=data.get("quality", "high"), music=bool(data.get("news_music", config.NEWS_MUSIC)),
                brand_text=data.get("brand_text", ""), progress_callback=_create_sse_callback(job_id), cancel_event=cancel_event,
                llm=NewsLLM(data.get("llm_provider") or None, data.get("llm_model") or None))
            if not result.success:
                payload={"error": "; ".join(result.errors) or "Generation failed", **result.news_details}
                _log_job_failure(job_id, "news", payload["error"], payload.get("status", "error"))
            else:
                def link(path):
                    return "/output/"+str(Path(path).resolve().relative_to(config.OUTPUT_DIR.resolve())) if path else None
                payload={"success":True,"title":result.title,"hook":result.hook,"duration":round(result.duration,2),
                    "resolution":result.resolution,"content_type":"news","theme":result.theme,"caption_style":result.caption_style,
                    "key_points":result.key_point_count,"processing_time":round(result.processing_time,1),
                    "video_url":link(result.video_path),"thumbnail_url":link(result.thumbnail_path),"srt_url":link(result.srt_path),
                    "download_url":f"/api/download/{job_id}","news_details":result.news_details,
                    "manifest_url":link(result.news_details["manifest"])}
            _job_results[job_id]=payload
            _progress_queues[job_id].put(("done",payload))
        except Exception as exc:
            _log_job_failure(job_id, "news", str(exc), exc_info=True)
            payload={"error":str(exc)}
            _job_results[job_id]=payload
            _progress_queues[job_id].put(("done",payload))
        finally:
            with _job_lock:
                _active_jobs.pop(job_id,None)
    thread=threading.Thread(target=work,daemon=True)
    with _job_lock:
        _active_jobs[job_id]["thread"]=thread
    thread.start()
    return jsonify({"job_id":job_id})


@app.route("/api/news/cancel/<job_id>", methods=["POST"])
def cancel_news_job(job_id):
    with _job_lock:
        job=_active_jobs.get(job_id)
        if not job or not job.get("news"):
            return jsonify({"error":"No active News job found."}),404
        job["cancel_event"].set()
    return jsonify({"status":"cancelling"})


@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    """SSE endpoint for real-time pipeline progress updates."""
    def event_stream():
        q = _progress_queues.get(job_id)
        if not q:
            # If job already finished, return done result immediately
            if job_id in _job_results:
                yield f"event: done\ndata: {json.dumps(_job_results[job_id])}\n\n"
                return
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        while True:
            try:
                event_type, data = q.get(timeout=10)
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                if event_type == "done":
                    # Cleanup progress queue
                    with _job_lock:
                        _progress_queues.pop(job_id, None)
                    break
            except queue.Empty:
                if job_id in _job_results:
                    yield f"event: done\ndata: {json.dumps(_job_results[job_id])}\n\n"
                    with _job_lock:
                        _progress_queues.pop(job_id, None)
                    break
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


@app.route("/api/result/<job_id>")
def api_result(job_id):
    """Fallback polling endpoint — returns the job result if available."""
    result = _job_results.get(job_id)
    if result is None:
        _prune_active_jobs()
        with _job_lock:
            is_running = job_id in _active_jobs
        if is_running:
            return jsonify({"status": "running"}), 202
        return jsonify({"error": "Job not found"}), 404
    return jsonify(result)


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Run scrape + analyze only for quick preview."""
    data = _studio_request(request.json)

    if data.get("content_mode") == "news":
        from agent.news_pipeline import preview_news
        from agent.news_script import NewsLLM
        from agent.news_models import NewsError
        try:
            preview = preview_news("\n".join(v for v in (data.get("url", "").strip(), data.get("text", "").strip()) if v),
                source_policy=data.get("news_source_policy", "auto"), tone=data.get("tone", "informative"),
                language=data.get("language", "english"), target_duration=int(data.get("target_duration", 0) or 0),
                llm=NewsLLM(data.get("llm_provider") or None, data.get("llm_model") or None))
            return jsonify(preview)
        except NewsError as exc:
            return jsonify(exc.response()), 409 if exc.status == "needs_clarification" else 422
        except Exception as exc:
            logger.exception("News script preview failed: %s", exc)
            return jsonify({"error": str(exc)}), 422
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
        logger.exception("Script preview failed | mode=%s | %s", data.get("content_mode", "article"), e)
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
    """Serve files from the output directory with HTTP 206 Partial Content range support."""
    import urllib.parse
    filename = urllib.parse.unquote(filename)
    root=config.OUTPUT_DIR.resolve()
    file_path=(root/filename).resolve()
    if not file_path.is_relative_to(root) or not file_path.is_file():
        return jsonify({"error": "Output file not found or expired."}),404
    return send_from_directory(file_path.parent, file_path.name, conditional=True)


@app.route("/api/download/<job_id>")
def api_download_video(job_id):
    """Stream the generated video directly from disk into RAM and send to client.

    This endpoint works on ephemeral cloud hosts (Railway, Render) where the
    output/ folder may be wiped on redeploy. The file is read immediately after
    generation — as long as the request comes before a restart, the video is
    streamed successfully.
    """
    result = _job_results.get(job_id)
    if not result or result.get("error"):
        return jsonify({"error": "Job result not found or generation failed"}), 404

    video_url = result.get("video_url")  # e.g. "/output/run_abc123/video.mp4"
    if not video_url:
        return jsonify({"error": "No video in result"}), 404

    # Safely reconstruct absolute path from relative URL without string stripping traps
    if video_url.startswith("/output/"):
        rel_path = video_url[len("/output/"):]
    elif video_url.startswith("output/"):
        rel_path = video_url[len("output/"):]
    else:
        rel_path = video_url.lstrip("/")
    root=config.OUTPUT_DIR.resolve()
    video_path=(root/rel_path).resolve()
    if not video_path.is_relative_to(root) or not video_path.is_file():
        return jsonify({"error": "Video file not found or expired."}),404

    try:
        # Read into memory buffer so the file handle is closed cleanly
        buf = io.BytesIO(video_path.read_bytes())
        buf.seek(0)
        filename = video_path.name
        return send_file(
            buf,
            mimetype="video/mp4",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        logger.error("Video download error: %s", e)
        return jsonify({"error": str(e)}), 500




@app.route("/daily-output/<path:filename>")
def serve_daily_output(filename):
    """Serve files from the daily runs directory."""
    daily_dir = Path(config.BASE_DIR) / "data" / "daily_runs"
    return send_from_directory(daily_dir, filename)


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


# ── Daily Pipeline API ────────────────────────────────

@app.route("/api/daily-pipeline", methods=["POST"])
def api_daily_pipeline():
    """
    Trigger the daily agentic pipeline.
    Curates stories → validates → generates videos → schedules publishing.
    """
    from automation.daily_pipeline import DailyPipeline, DailyConfig

    data = request.json or {}
    job_id = f"daily_{int(time.time())}"

    # Override TTS provider if specified in Daily Pipeline UI
    tts_provider = data.get("tts_provider", "")
    if tts_provider:
        config.TTS_PROVIDER = tts_provider

    cfg = DailyConfig(
        target_videos=int(data.get("target_videos", 5)),
        tone=data.get("tone", "storytelling"),
        renderer=data.get("renderer", "remotion"),
        publish_strategy=data.get("publish_strategy", "manual"),
        start_hour=int(data.get("start_hour", 17)),
        interval_minutes=int(data.get("interval_minutes", 70)),
        jitter_minutes=int(data.get("jitter_minutes", 15)),
        dry_run=data.get("dry_run", False),
        platforms=data.get("platforms", [
            "youtube_shorts", "tiktok", "instagram_reels", "facebook", "twitter"
        ]),
    )

    # Create SSE queue for progress and track active job
    with _job_lock:
        _progress_queues[job_id] = queue.Queue()
        _active_jobs[job_id] = {"started": time.time(), "thread": None}

    def _run_pipeline():
        try:
            q = _progress_queues.get(job_id)

            def progress_cb(msg: str):
                if q:
                    q.put(("log", {"message": msg}))

            pipeline = DailyPipeline(config=cfg)
            report = pipeline.run(progress_callback=progress_cb)

            result = {
                "success": report.videos_generated > 0,
                "date": report.date,
                "duration_minutes": report.duration_minutes,
                "stories_approved": report.stories_approved,
                "stories_rejected": report.stories_rejected,
                "videos_generated": report.videos_generated,
                "videos_failed": report.videos_failed,
                "posts_scheduled": report.posts_scheduled,
                "errors": report.errors,
                "video_details": report.video_details,
            }

            with _job_lock:
                _job_results[job_id] = result
            if q:
                q.put(("complete", result))

        except Exception as e:
            logger.error("Daily pipeline failed: %s", e, exc_info=True)
            result = {"success": False, "error": str(e)}
            with _job_lock:
                _job_results[job_id] = result
            q = _progress_queues.get(job_id)
            if q:
                q.put(("error", result))

        finally:
            with _job_lock:
                _active_jobs.pop(job_id, None)

    thread = threading.Thread(target=_run_pipeline, daemon=True)
    with _job_lock:
        if job_id in _active_jobs:
            _active_jobs[job_id]["thread"] = thread
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"})


@app.route("/api/daily-pipeline/stream/<job_id>")
def api_daily_pipeline_stream(job_id):
    """SSE stream for daily pipeline progress."""
    def event_stream():
        q = _progress_queues.get(job_id)
        if not q:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        while True:
            try:
                event_type, data = q.get(timeout=120)
                yield f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"
                if event_type in ("complete", "error"):
                    with _job_lock:
                        _progress_queues.pop(job_id, None)
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/daily-pipeline/history")
def api_daily_pipeline_history():
    """Get story history and recent runs."""
    from automation.story_history import StoryHistory
    history = StoryHistory()
    return jsonify({
        "total_stories": len(history.all_stories),
        "published": len(history.published_stories),
        "today_count": history.get_today_count(),
        "recent_stories": history.all_stories[-20:],  # last 20
    })


# ── Entry Point ───────────────────────────────────────

from agent.portfolio_api import install as install_portfolio_api
install_portfolio_api(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print("\n🎬 Project HER v2.0 – Web UI")
    print(f"   Open: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
