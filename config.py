"""
Project HER v2.0 - Configuration
Central configuration for the Next-Gen AI Article-to-Video Agent.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
SFX_DIR = ASSETS_DIR / "sfx"

# Ensure directories exist
for d in [OUTPUT_DIR, TEMP_DIR, ASSETS_DIR, FONTS_DIR, MUSIC_DIR, SFX_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API Keys ───────────────────────────────────────────
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_TTS_API_KEY", "")
)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# ── LLM Provider Selection ─────────────────────────────
# Options: "gemini" (Google AI Studio - Gemini Pro) | "groq" (Groq AI)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# ── Google Gemini AI Settings ─────────────────────────
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# ── Groq AI Settings ──────────────────────────────────
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.1-8b-instant"

# ── Resolved LLM Settings (auto-set based on provider) ─
if LLM_PROVIDER in ("gemini", "google"):
    LLM_MODEL = GEMINI_MODEL
    LLM_BASE_URL = GEMINI_BASE_URL
    LLM_API_KEY = GEMINI_API_KEY
else:
    LLM_MODEL = GROQ_MODEL
    LLM_BASE_URL = GROQ_BASE_URL
    LLM_API_KEY = GROQ_API_KEY

LLM_TEMPERATURE = 0.75
LLM_MAX_TOKENS = 3000

# Available LLM providers for UI dropdown
LLM_PROVIDERS = {
    "gemini": {
        "label": "Google AI Studio (Gemini Pro)",
        "description": "Gemini 2.5 Pro — premium reasoning, rich narrative, excellent JSON adherence",
        "requires": "GEMINI_API_KEY",
    },
    "groq": {
        "label": "Groq AI (Free)",
        "description": "Llama 3.1 8B — fast, free, good for testing",
        "requires": "GROQ_API_KEY",
    },
}
AVAILABLE_LLM_PROVIDERS = list(LLM_PROVIDERS.keys())

# ── Content Analysis ──────────────────────────────────
MIN_KEY_POINTS = 3
MAX_KEY_POINTS = 5

TONE_PRESETS = {
    "informative": "Write in a neutral, informative, news-anchor style.",
    "storytelling": "Write in an engaging storytelling style with narrative flow, building tension and resolution.",
    "social": "Write in a punchy, social-media-friendly style with short impactful sentences and hooks.",
    "dramatic": "Write in a dramatic, cinematic style with powerful phrases and emotional intensity.",
    "educational": "Write in a clear, educational style as if explaining to a curious learner.",
    "motivational": "Write in an uplifting, motivational style that inspires action and positivity.",
    "explainer": (
        "Write in a calm, neutral, educational tone as if narrating a documentary or explainer video. "
        "Break the content into chronological narrative units based on conceptual shifts. "
        "Each key point should represent a distinct idea or phase — not just a topic. "
        "Use concise, clear phrases suitable for progressive on-screen text reveal. "
        "Keep narration measured and paced for easy comprehension."
    ),
}

# ── Video Settings ─────────────────────────────────────
VIDEO_FORMATS = {
    "vertical": {"width": 1080, "height": 1920, "label": "9:16 (Reels/Shorts/TikTok)"},
    "horizontal": {"width": 1920, "height": 1080, "label": "16:9 (YouTube)"},
    "square": {"width": 1080, "height": 1080, "label": "1:1 (Instagram)"},
}

DEFAULT_VIDEO_FORMAT = os.getenv("DEFAULT_VIDEO_FORMAT", "vertical")
TARGET_DURATION = (35, 62)  # seconds (min, max) — sweet spot 50-60s for short-form
FPS = 30  # style guide mandates 30fps for Reels/Shorts/TikTok
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
VIDEO_BITRATE = "5000k"
DEFAULT_RENDERER = os.getenv("DEFAULT_RENDERER", "remotion")
AVAILABLE_RENDERERS = ["remotion", "moviepy"]


# ── Platform Presets ───────────────────────────────────
# Each preset bundles format, duration, bitrate, and recommended settings
# so users can just say --platform tiktok instead of manual config.
PLATFORM_PRESETS = {
    "tiktok": {
        "label": "TikTok",
        "format": "vertical",
        "target_duration": (15, 60),
        "bitrate": "5000k",
        "fps": 30,
        "recommended_theme": "neon",
        "recommended_captions": "karaoke",
        "recommended_transition": "slide_left",
        "max_points": 4,
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "format": "vertical",
        "target_duration": (30, 58),
        "bitrate": "6000k",
        "fps": 30,
        "recommended_theme": "cinematic",
        "recommended_captions": "pop",
        "recommended_transition": "zoom_in",
        "max_points": 5,
    },
    "instagram_reels": {
        "label": "Instagram Reels",
        "format": "vertical",
        "target_duration": (15, 60),
        "bitrate": "5000k",
        "fps": 30,
        "recommended_theme": "neon",
        "recommended_captions": "glow",
        "recommended_transition": "wipe",
        "max_points": 4,
    },
    "youtube": {
        "label": "YouTube (Landscape)",
        "format": "horizontal",
        "target_duration": (45, 90),
        "bitrate": "8000k",
        "fps": 24,
        "recommended_theme": "cinematic",
        "recommended_captions": "classic",
        "recommended_transition": "fade",
        "max_points": 6,
    },
    "twitter": {
        "label": "Twitter / X",
        "format": "square",
        "target_duration": (15, 45),
        "bitrate": "4000k",
        "fps": 30,
        "recommended_theme": "minimal",
        "recommended_captions": "bold_impact",
        "recommended_transition": "slide_up",
        "max_points": 3,
    },
    "linkedin": {
        "label": "LinkedIn",
        "format": "square",
        "target_duration": (30, 60),
        "bitrate": "5000k",
        "fps": 24,
        "recommended_theme": "corporate",
        "recommended_captions": "classic",
        "recommended_transition": "fade",
        "max_points": 5,
    },
    "explainer": {
        "label": "Explainer Video",
        "format": "horizontal",
        "target_duration": (45, 90),
        "bitrate": "6000k",
        "fps": 24,
        "recommended_theme": "explainer",
        "recommended_captions": "reveal",
        "recommended_transition": "fade",
        "max_points": 6,
    },
}

AVAILABLE_PLATFORMS = list(PLATFORM_PRESETS.keys())

# ── Visual Settings ────────────────────────────────────
IMAGE_SEARCH_COUNT = 5
USE_VIDEO_BROLL = True  # Try Pexels video API for B-roll

# ── Narration Settings ─────────────────────────────────
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "en-US-AriaNeural")
NARRATION_RATE = "+0%"
NARRATION_VOLUME = "+0%"
VOICE_SPEED = os.getenv("VOICE_SPEED", "+0%")  # e.g. "+20%", "-10%"
SCENE_PADDING = 0.4  # seconds of silence between scenes

# ── ElevenLabs TTS (Generate tab — premium narration) ──
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# ── Google AI Studio TTS (free, high-quality voices) ──
GOOGLE_TTS_API_KEY = (
    os.getenv("GOOGLE_TTS_API_KEY")
    or os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or GEMINI_API_KEY
)
# TTS provider: "google_tts" | "elevenlabs" | "replicate" | "edge_tts"
# - google_tts: Free via Gemini API (8 voices, high quality, default)
# - elevenlabs: Premium quality, free tier 10k chars, then paid
# - replicate: Kokoro-82m via Replicate, ~$0.003/video (ultra cheap)
# - edge_tts: Free (Microsoft), always used for Kids Story
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "google_tts")

# ── Enhanced Pipeline Flags ────────────────────────────
# These enhancements only apply to the Generate tab (non-kids_story modes).
# Kids Story tab is unaffected — it uses the original pipeline settings.
ENHANCED_PIPELINE = True          # master switch for all v2.1 enhancements
ENHANCED_IMAGE_PORTRAIT = True    # generate 9:16 images (768×1344)
ENHANCED_FULL_BLEED = True        # full-screen images with text overlay
ENHANCED_SILENCE_GAPS = True      # 300ms silence between scenes
ENHANCED_TRANSITION_SFX = True    # whoosh/pop on scene transitions
ENHANCED_VARIABLE_PACING = True   # variable transition durations per mood
ENHANCED_CHAR_CONSISTENCY = True  # anchor character descriptions across screens
ENHANCED_VISUAL_VOCAB = True      # consistent effect theme per video
SCENE_SILENCE_MS = 300            # milliseconds of silence between scenes

# Portrait image dimensions for enhanced pipeline
AI_IMAGE_PORTRAIT_WIDTH = 768
AI_IMAGE_PORTRAIT_HEIGHT = 1344

# Negative prompts for AI image quality
AI_IMAGE_NEGATIVE_PROMPT = (
    "text, watermark, logo, blurry, deformed, distorted, disfigured, "
    "bad anatomy, extra limbs, ugly, low quality, pixelated, cropped, "
    "out of frame, duplicate, morbid, mutilated"
)

AVAILABLE_VOICES = {
    "aria": "en-US-AriaNeural",
    "guy": "en-US-GuyNeural",
    "jenny": "en-US-JennyNeural",
    "christopher": "en-US-ChristopherNeural",
    "emma": "en-US-EmmaNeural",
    "brian": "en-US-BrianNeural",
    "ana_kid": "en-US-AnaNeural",
    "ava": "en-US-AvaNeural",
    "sonia_uk": "en-GB-SoniaNeural",
    "ryan_uk": "en-GB-RyanNeural",
    "maisie_uk": "en-GB-MaisieNeural",
    "natasha_au": "en-AU-NatashaNeural",
    "neerja_in": "en-IN-NeerjaExpressiveNeural",
}

# ── Transition Types ──────────────────────────────────
TRANSITION_DURATION = 0.5
ZOOM_FACTOR = 1.08

AVAILABLE_TRANSITIONS = [
    "fade",
    "slide_left",
    "slide_up",
    "zoom_in",
    "wipe",
]

DEFAULT_TRANSITION = "fade"

# ── Caption Styles (Modern Animated Captions) ─────────
CAPTION_STYLES = {
    "karaoke": {
        "label": "Karaoke Highlight",
        "description": "Words highlight as spoken (TikTok style)",
        "font_size": 52,
        "active_color": (255, 255, 0),
        "inactive_color": (255, 255, 255),
        "bg_opacity": 180,
        "position": 0.72,
        "words_per_group": 4,
    },
    "pop": {
        "label": "Pop In",
        "description": "Words pop in with scale animation",
        "font_size": 56,
        "active_color": (0, 255, 136),
        "inactive_color": (255, 255, 255),
        "bg_opacity": 200,
        "position": 0.70,
        "words_per_group": 3,
    },
    "glow": {
        "label": "Neon Glow",
        "description": "Glowing text with neon effect",
        "font_size": 50,
        "active_color": (0, 200, 255),
        "inactive_color": (200, 200, 200),
        "bg_opacity": 160,
        "position": 0.73,
        "words_per_group": 5,
    },
    "bold_impact": {
        "label": "Bold Impact",
        "description": "Large bold words with high contrast",
        "font_size": 60,
        "active_color": (255, 60, 60),
        "inactive_color": (255, 255, 255),
        "bg_opacity": 220,
        "position": 0.68,
        "words_per_group": 3,
    },
    "classic": {
        "label": "Classic Subtitles",
        "description": "Traditional subtitle style",
        "font_size": 38,
        "active_color": (255, 255, 255),
        "inactive_color": (255, 255, 255),
        "bg_opacity": 160,
        "position": 0.78,
        "words_per_group": 6,
    },
    "reveal": {
        "label": "Progressive Reveal",
        "description": "Clean progressive text reveal for explainer videos",
        "font_size": 42,
        "active_color": (40, 40, 45),
        "inactive_color": (120, 120, 130),
        "bg_opacity": 0,
        "position": 0.55,
        "words_per_group": 5,
    },
}

DEFAULT_CAPTION_STYLE = os.getenv("DEFAULT_CAPTION_STYLE", "karaoke")

# ── Theme Presets ─────────────────────────────────────
THEMES = {
    "cinematic": {
        "label": "Cinematic Dark",
        "bg_color": (10, 10, 20),
        "accent_color": (255, 200, 50),
        "text_color": (255, 255, 255),
        "overlay_opacity": 0.40,
        "title_font_size": 64,
        "headline_font_size": 48,
        "vignette": True,
        "gradient_overlay": True,
    },
    "neon": {
        "label": "Neon Vibes",
        "bg_color": (5, 0, 20),
        "accent_color": (0, 255, 200),
        "text_color": (255, 255, 255),
        "overlay_opacity": 0.35,
        "title_font_size": 62,
        "headline_font_size": 46,
        "vignette": True,
        "gradient_overlay": True,
    },
    "minimal": {
        "label": "Clean Minimal",
        "bg_color": (245, 245, 245),
        "accent_color": (30, 30, 30),
        "text_color": (40, 40, 40),
        "overlay_opacity": 0.15,
        "title_font_size": 56,
        "headline_font_size": 42,
        "vignette": False,
        "gradient_overlay": False,
    },
    "playful": {
        "label": "Playful & Fun",
        "bg_color": (255, 240, 220),
        "accent_color": (255, 100, 50),
        "text_color": (60, 30, 80),
        "overlay_opacity": 0.25,
        "title_font_size": 66,
        "headline_font_size": 50,
        "vignette": False,
        "gradient_overlay": True,
    },
    "news": {
        "label": "News Broadcast",
        "bg_color": (15, 25, 60),
        "accent_color": (220, 40, 40),
        "text_color": (255, 255, 255),
        "overlay_opacity": 0.30,
        "title_font_size": 58,
        "headline_font_size": 44,
        "vignette": False,
        "gradient_overlay": True,
    },
    "retro": {
        "label": "Retro Wave",
        "bg_color": (20, 0, 40),
        "accent_color": (255, 0, 128),
        "text_color": (255, 200, 255),
        "overlay_opacity": 0.35,
        "title_font_size": 60,
        "headline_font_size": 46,
        "vignette": True,
        "gradient_overlay": True,
    },
    "corporate": {
        "label": "Professional",
        "bg_color": (20, 40, 80),
        "accent_color": (0, 120, 255),
        "text_color": (255, 255, 255),
        "overlay_opacity": 0.35,
        "title_font_size": 56,
        "headline_font_size": 42,
        "vignette": False,
        "gradient_overlay": True,
    },
    "explainer": {
        "label": "Explainer (Clean & Minimal)",
        "bg_color": (248, 245, 240),
        "accent_color": (80, 120, 160),
        "text_color": (40, 40, 45),
        "overlay_opacity": 0.0,
        "title_font_size": 54,
        "headline_font_size": 40,
        "vignette": False,
        "gradient_overlay": False,
        "explainer_mode": True,
        "canvas_padding": 80,
        "content_area_ratio": 0.85,
        "image_max_ratio": 0.45,
        "text_reveal_fade": 0.4,
        "secondary_text_color": (100, 100, 110),
        "divider_color": (200, 195, 185),
    },
}

DEFAULT_THEME = os.getenv("DEFAULT_THEME", "cinematic")

# ── Custom Font ───────────────────────────────────────
# Path to a custom TTF/OTF font file. Leave empty to use system fonts.
CUSTOM_FONT_PATH = os.getenv("CUSTOM_FONT_PATH", "")

# ── Custom Intro/Outro ────────────────────────────────
# Path to image/video files for custom intro/outro cards.
# If set, these replace the auto-generated hook/outro cards.
CUSTOM_INTRO_PATH = os.getenv("CUSTOM_INTRO_PATH", "")  # .mp4, .jpg, .png
CUSTOM_OUTRO_PATH = os.getenv("CUSTOM_OUTRO_PATH", "")  # .mp4, .jpg, .png
CUSTOM_INTRO_DURATION = 3.0  # seconds (for image intros)
CUSTOM_OUTRO_DURATION = 4.0  # seconds (for image outros)

# ── Background Music ──────────────────────────────────
BGM_VOLUME = 0.12
BGM_FADE_DURATION = 2.0
# Path to a custom audio file for background music.
# If set, this replaces the procedural BGM.
CUSTOM_BGM_PATH = os.getenv("CUSTOM_BGM_PATH", "")  # .mp3, .wav, .ogg

MUSIC_MOODS = {
    "upbeat": "Energetic, positive, motivational",
    "dramatic": "Intense, cinematic, epic",
    "calm": "Peaceful, ambient, relaxing",
    "suspenseful": "Tension-building, mysterious",
    "playful": "Fun, lighthearted, cheerful",
    "inspirational": "Uplifting, emotional, hopeful",
    "neutral": "Soft ambient background",
}

# ── Sound Effects ─────────────────────────────────────
SFX_ENABLED = True
SFX_VOLUME = 0.3

# ── Watermark / Branding ──────────────────────────────
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "Klin10 Creations")     # Brand name watermark
WATERMARK_IMAGE = os.getenv("WATERMARK_IMAGE", "")   # path to PNG logo
WATERMARK_OPACITY = 0.35
WATERMARK_POSITION = "anti_crop"  # "anti_crop" = right-center + bottom-center
WATERMARK_FONT_SIZE = 22
WATERMARK_MARGIN = 30

# ── Color Grading / Filters ────────────────────────────
# Post-processing film look presets.
COLOR_GRADES = {
    "none": {
        "label": "None",
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "tint": None,  # (R, G, B, alpha) overlay
    },
    "warm": {
        "label": "Warm Film",
        "brightness": 1.05,
        "contrast": 1.08,
        "saturation": 1.15,
        "tint": (255, 180, 100, 20),
    },
    "cool": {
        "label": "Cool Tone",
        "brightness": 1.0,
        "contrast": 1.05,
        "saturation": 0.90,
        "tint": (100, 150, 255, 20),
    },
    "vintage": {
        "label": "Vintage",
        "brightness": 0.95,
        "contrast": 1.15,
        "saturation": 0.70,
        "tint": (220, 190, 140, 25),
    },
    "cinematic": {
        "label": "Cinematic Teal-Orange",
        "brightness": 0.98,
        "contrast": 1.12,
        "saturation": 1.05,
        "tint": (200, 160, 100, 15),
    },
    "bw": {
        "label": "Black & White",
        "brightness": 1.0,
        "contrast": 1.20,
        "saturation": 0.0,
        "tint": None,
    },
    "vibrant": {
        "label": "Vibrant Pop",
        "brightness": 1.08,
        "contrast": 1.10,
        "saturation": 1.40,
        "tint": None,
    },
}

DEFAULT_COLOR_GRADE = "none"
AVAILABLE_COLOR_GRADES = list(COLOR_GRADES.keys())

# ── Multi-Language Support ────────────────────────────
# Mapping of language codes to edge-tts voices.
# Users can specify --language to auto-select a non-English voice.
LANGUAGE_VOICES = {
    "en": {"voice": "en-US-AriaNeural", "label": "English (US)"},
    "en-gb": {"voice": "en-GB-SoniaNeural", "label": "English (UK)"},
    "en-in": {"voice": "en-IN-NeerjaExpressiveNeural", "label": "English (India)"},
    "hi": {"voice": "hi-IN-SwaraNeural", "label": "Hindi"},
    "es": {"voice": "es-ES-ElviraNeural", "label": "Spanish"},
    "fr": {"voice": "fr-FR-DeniseNeural", "label": "French"},
    "de": {"voice": "de-DE-KatjaNeural", "label": "German"},
    "pt": {"voice": "pt-BR-FranciscaNeural", "label": "Portuguese (Brazil)"},
    "ja": {"voice": "ja-JP-NanamiNeural", "label": "Japanese"},
    "ko": {"voice": "ko-KR-SunHiNeural", "label": "Korean"},
    "zh": {"voice": "zh-CN-XiaoxiaoNeural", "label": "Chinese (Mandarin)"},
    "ar": {"voice": "ar-SA-ZariyahNeural", "label": "Arabic"},
    "ta": {"voice": "ta-IN-PallaviNeural", "label": "Tamil"},
    "te": {"voice": "te-IN-ShrutiNeural", "label": "Telugu"},
    "bn": {"voice": "bn-IN-TanishaaNeural", "label": "Bengali"},
    "mr": {"voice": "mr-IN-AarohiNeural", "label": "Marathi"},
}

AVAILABLE_LANGUAGES = list(LANGUAGE_VOICES.keys())

# ── Text Overlay ───────────────────────────────────────
FONT_SIZE_TITLE = 60
FONT_SIZE_BODY = 44
FONT_SIZE_SUBTITLE = 36
FONT_COLOR = "white"
FONT_STROKE_COLOR = "black"
FONT_STROKE_WIDTH = 2
TEXT_MARGIN = 60

# ── Retry / Resilience ────────────────────────────────
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5
API_TIMEOUT = 20

# ── Export Quality Presets ────────────────────────────
QUALITY_PRESETS = {
    "draft": {
        "label": "Draft (fast preview)",
        "bitrate": "1500k",
        "fps": 15,
        "threads": 2,
    },
    "standard": {
        "label": "Standard",
        "bitrate": "5000k",
        "fps": 24,
        "threads": min(os.cpu_count() or 4, 8),
    },
    "high": {
        "label": "High Quality",
        "bitrate": "8000k",
        "fps": 30,
        "threads": min(os.cpu_count() or 4, 8),
    },
    "ultra": {
        "label": "Ultra (slow, best quality)",
        "bitrate": "12000k",
        "fps": 30,
        "threads": min(os.cpu_count() or 4, 8),
    },
}

DEFAULT_QUALITY = "standard"

# ── AI Image Generation (Claymorphism Mode) ───────────
AI_IMAGES_ENABLED = False  # Toggle: True → AI images, False → Pexels
AI_IMAGE_PROVIDER = "replicate"  # "replicate" (paid, best) | "huggingface" (free) | "pollinations" (free, no key)

# Replicate (paid, unlimited, best quality + reliability)
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")  # https://replicate.com/account/api-tokens
REPLICATE_MODEL = "black-forest-labs/flux-1.1-pro"  # best quality, $0.04/img
REPLICATE_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # fast + cheap, $0.003/img
REPLICATE_USE_SCHNELL = True  # True = use Schnell ($0.003), False = use Pro ($0.04)

# HuggingFace Inference API (free, reliable, high quality)
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")  # free at https://huggingface.co/settings/tokens
HF_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"  # fast, high quality
HF_IMAGE_API_URL = "https://router.huggingface.co/hf-inference/models/"

# Pollinations.ai fallback (free, no API key, less reliable)
AI_IMAGE_BASE_URL = "https://image.pollinations.ai/prompt"
AI_IMAGE_POLLINATIONS_MODEL = "flux"

# Shared image settings
AI_IMAGE_WIDTH = 1024
AI_IMAGE_HEIGHT = 1024
AI_IMAGE_TIMEOUT = 90  # seconds per image (HF can be slow on cold start)
AI_IMAGE_MAX_RETRIES = 3
AI_IMAGE_CONCURRENT = 2  # max concurrent image generations

# Claymorphism design tokens
CLAY_STYLE = {
    # Background — radial gradient, center-lit with vignette
    "bg_type": "radial",                    # "radial" (documentary) | "linear" (classic)
    "bg_center_color": (240, 238, 236),     # #F0EEEC — warm near-white (centre)
    "bg_edge_color": (200, 196, 192),       # #C8C4C0 — medium warm grey (edges)
    "bg_gradient_start": (245, 238, 230),   # kept for linear fallback
    "bg_gradient_end": (235, 225, 215),
    "bg_gradient_center_x": 0.50,           # radial centre X (0.0–1.0)
    "bg_gradient_center_y": 0.45,           # slightly above vertical centre
    "bg_vignette": True,                    # darken edges
    "bg_vignette_strength": 0.20,           # 20% darker at corners
    "bg_accent_blob": False,                # disabled for clean look

    # Cards / containers
    "card_bg": (255, 252, 248),             # near-white
    "card_radius": 28,
    "card_shadow_color": (96, 96, 96, 70),  # #606060 shadow, 27% opacity
    "card_inner_glow": (255, 255, 255, 120),

    # Colors — single text colour for premium documentary feel
    "primary": (61, 61, 61),          # #3D3D3D — main text colour
    "secondary": (200, 130, 160),     # muted pink (accent only)
    "accent": (160, 200, 140),        # muted green (accent only)
    "warm": (240, 180, 120),          # muted orange (accent only)
    "text_dark": (61, 61, 61),        # #3D3D3D dark charcoal
    "text_medium": (100, 95, 110),    # medium gray
    "text_light": (160, 155, 170),    # light gray
    "text_emphasis": (61, 61, 61),    # same as primary (no flashy emphasis)
    "highlight_bg": None,             # disabled — no colored boxes behind words

    # Typography
    "title_size_ratio": 0.048,        # relative to screen height (bigger for impact)
    "body_size_ratio": 0.036,
    "emphasis_size_ratio": 0.054,     # large for text-only screens
    "brand_size_ratio": 0.024,
    "setup_size_ratio": 0.040,        # regular weight "setup" line (was 0.038)
    "subject_size_ratio": 0.054,      # bold weight "subject" line — bigger for solid look (was 0.050)
    "caption_size_ratio": 0.030,      # small captions (was 0.028)
    "karaoke_size_ratio": 0.035,      # narration text — bigger, solid font (was 0.030)

    # Screen zones — Y ranges from the Universal Style Guide
    # Upper text zone Y:15–32%, Lower Y:62–80%, Centre Y:42–55% for text-only
    "zone_brand_top": 0.10,           # top branding strip (0–10%)
    "zone_upper_text": 0.17,          # upper text zone (15–32% Y)
    "zone_narrative_top": 0.17,       # alias for upper text zone
    "zone_narrative": 0.17,           # legacy compat
    "zone_content": 0.40,             # main visual/image centre (28–68%)
    "zone_lower_text": 0.18,          # lower text zone (62–80% Y)
    "zone_narrative_bottom": 0.18,    # alias
    "zone_bottom": 0.10,              # bottom watermark (90–100%)

    # Animation / timing — FAST PACING (change every 2-3s)
    "screen_duration_default": 3.0,   # faster default (was 3.5)
    "screen_duration_max": 5.0,       # tighter max (was 7.0)
    "intro_duration": 2.0,            # snappy hook (was 2.5)
    "outro_duration": 4.0,            # tighter outro (was 5.0)
    "bridge_duration_min": 1.5,       # text-only bridge minimum
    "bridge_duration_max": 2.5,       # tighter bridge (was 3.0)
    "fade_duration": 0.35,            # slightly faster transitions (was 0.4)
    "pop_in_duration": 0.3,           # snappier pop-in (was 0.5)
    "text_anim_duration": 0.25,       # faster text entry (was 0.35)
    "text_reveal_stagger": 0.4,       # tighter stagger (was 0.5)
    "entry_scale_start": 0.92,        # more dramatic scale pop (was 0.95)
    "entry_scale_end": 1.0,           # object end scale
    "min_text_on_screen": 0.6,        # faster text (was 0.8)
    "min_image_on_screen": 1.2,       # faster image cycling (was 1.5)

    # Float / idle animation (images only) — enhanced wiggle
    "float_enabled": True,            # subtle vertical drift on images
    "float_amplitude": 4,             # pixels of total movement (was 3)
    "float_period": 3.0,              # faster cycle for energy (was 4.0)

    # Image presentation
    "image_corner_radius": 32,        # generous rounded corners for clay feel
    "image_shadow_direction": 140,    # degrees — lower-left per document
    "image_shadow_blur": 14,          # crisp shadow (was 35)
    "image_shadow_opacity": 0.22,     # subtle, not heavy (was 0.30)
    "image_shadow_color": (60, 60, 60),  # darker for definition
    "image_shadow_offset": (4, 6),    # consistent with VFX engine
    "image_max_ratio": 1.10,          # 1.2x — large but not oversized
    "image_border_width": 0,          # no border — cleaner floating cut-out
    "image_border_color": (255, 252, 248, 200),
    "image_bottom_fade": True,        # fade bottom of images into background
    "image_bottom_fade_start": 0.65,  # start fade at 65% of image height
    "image_bottom_fade_end": 0.92,    # fully transparent at 92%

    # Image colour treatment
    "image_desaturation": 0.10,       # 10% desaturation for warm-grey cohesion

    # Text safety rules (Universal Style Guide §4 / §9)
    "max_text_lines": 3,              # never more than 3 lines per scene
    "prevent_all_caps": True,          # convert ALL CAPS → Title Case
}

# Screen splitting settings — FAST PACING
CLAY_SCREEN_MIN_DURATION = 2.0       # tighter minimum (was 2.5)
CLAY_SCREEN_MAX_DURATION = 5.0       # tighter maximum (was 7.0)
CLAY_SCREEN_DEFAULT_DURATION = 3.0   # faster default (was 3.5)
CLAY_MULTI_ITEM_EXTRA_TIME = 1.0     # less extra time for multi (was 1.5)

# AI image prompt style suffix (legacy — used when style is "claymorphism")
CLAY_IMAGE_STYLE_SUFFIX = (
    "claymorphism style, soft 3D clay render, pastel colors, thick rounded shapes, "
    "puffy inflated look, soft diffused shadows, matte clay finish, warm studio lighting, "
    "smooth clay texture, miniature diorama feel, depth of field blur, "
    "cute and polished, Pixar-quality clay illustration, no text, no watermark"
)

# ── Visual Styles ─────────────────────────────────────
# Each style defines colours, backgrounds, AI prompt suffix, and design tokens.
# The compositor adapts rendering based on the selected style.

VISUAL_STYLES = {
    "claymorphism": {
        "label": "Claymorphism",
        "description": "Soft 3D clay render with pastel colors and puffy shapes",
        "image_prompt_suffix": (
            "claymorphism style, soft 3D clay render, pastel colors, thick rounded shapes, "
            "puffy inflated look, soft diffused shadows, matte clay finish, warm studio lighting, "
            "smooth clay texture, miniature diorama feel, depth of field blur, "
            "cute and polished, Pixar-quality clay illustration, no text, no watermark"
        ),
        "bg_type": "radial",
        "bg_center_color": (240, 238, 236),
        "bg_edge_color": (200, 196, 192),
        "bg_vignette": True,
        "bg_vignette_strength": 0.20,
        "text_dark": (61, 61, 61),
        "text_medium": (100, 95, 110),
        "text_light": (160, 155, 170),
        "primary": (61, 61, 61),
        "secondary": (200, 130, 160),
        "accent": (160, 200, 140),
        "highlight_color": (255, 136, 0),
        "highlight_text": (255, 255, 255),
        "card_bg": (255, 252, 248),
        "card_radius": 28,
        "image_corner_radius": 24,
    },
    "glassmorphism": {
        "label": "Glassmorphism",
        "description": "Frosted glass layers with transparency and light refraction",
        "image_prompt_suffix": (
            "glassmorphism style, frosted translucent glass panels, soft light refraction, "
            "ethereal glow, layered transparency, subtle iridescent reflections, "
            "clean modern aesthetic, cool blue and white tones, diffused bokeh background, "
            "elegant and refined, studio lighting, no text, no watermark"
        ),
        "bg_type": "radial",
        "bg_center_color": (220, 230, 245),
        "bg_edge_color": (160, 175, 210),
        "bg_vignette": True,
        "bg_vignette_strength": 0.18,
        "text_dark": (30, 40, 70),
        "text_medium": (70, 85, 130),
        "text_light": (130, 145, 185),
        "primary": (30, 40, 70),
        "secondary": (100, 140, 220),
        "accent": (0, 180, 255),
        "highlight_color": (0, 140, 255),
        "highlight_text": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "card_radius": 20,
        "image_corner_radius": 20,
    },
    "skeuomorphism": {
        "label": "Skeuomorphism",
        "description": "Realistic textures, depth, and tactile material surfaces",
        "image_prompt_suffix": (
            "skeuomorphism style, hyper-realistic textures, rich material surfaces, "
            "leather and metal accents, embossed details, realistic shadows and highlights, "
            "warm natural lighting, glossy reflections, tactile depth, "
            "premium craftsmanship feel, photorealistic quality, no text, no watermark"
        ),
        "bg_type": "linear",
        "bg_gradient_start": (235, 225, 210),
        "bg_gradient_end": (210, 195, 175),
        "bg_center_color": (235, 225, 210),
        "bg_edge_color": (195, 180, 160),
        "bg_vignette": True,
        "bg_vignette_strength": 0.25,
        "text_dark": (50, 40, 30),
        "text_medium": (90, 80, 65),
        "text_light": (140, 130, 115),
        "primary": (50, 40, 30),
        "secondary": (160, 100, 50),
        "accent": (200, 140, 60),
        "highlight_color": (180, 100, 30),
        "highlight_text": (255, 255, 255),
        "card_bg": (248, 242, 230),
        "card_radius": 12,
        "image_corner_radius": 12,
    },
    "neo_brutalism": {
        "label": "Neo-Brutalism",
        "description": "Bold outlines, raw shapes, high contrast with playful chaos",
        "image_prompt_suffix": (
            "neo-brutalism style, bold graphic illustration, thick black outlines, "
            "flat vivid colors, raw unpolished geometry, playful chaotic composition, "
            "Memphis design influence, hand-drawn energy, pop art vibes, "
            "high contrast, paper cutout feel, no text, no watermark"
        ),
        "bg_type": "radial",
        "bg_center_color": (255, 248, 220),
        "bg_edge_color": (255, 230, 180),
        "bg_vignette": False,
        "bg_vignette_strength": 0.0,
        "text_dark": (20, 20, 20),
        "text_medium": (60, 60, 60),
        "text_light": (120, 120, 120),
        "primary": (20, 20, 20),
        "secondary": (255, 60, 60),
        "accent": (0, 200, 100),
        "highlight_color": (255, 220, 0),
        "highlight_text": (20, 20, 20),
        "card_bg": (255, 255, 255),
        "card_radius": 0,
        "image_corner_radius": 0,
    },
    "minimalism": {
        "label": "Minimalism",
        "description": "Clean lines, generous whitespace, and restrained elegance",
        "image_prompt_suffix": (
            "minimalist style, clean simple composition, generous negative space, "
            "muted neutral color palette, subtle shadows, elegant simplicity, "
            "Scandinavian design influence, refined and understated, "
            "soft natural light, monochromatic tones, no text, no watermark"
        ),
        "bg_type": "radial",
        "bg_center_color": (250, 250, 250),
        "bg_edge_color": (235, 235, 235),
        "bg_vignette": False,
        "bg_vignette_strength": 0.0,
        "text_dark": (40, 40, 40),
        "text_medium": (120, 120, 120),
        "text_light": (180, 180, 180),
        "primary": (40, 40, 40),
        "secondary": (100, 100, 100),
        "accent": (60, 60, 60),
        "highlight_color": (40, 40, 40),
        "highlight_text": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "card_radius": 8,
        "image_corner_radius": 8,
    },
    "liquid_glass": {
        "label": "Liquid Glass",
        "description": "Flowing translucent surfaces with liquid chrome reflections",
        "image_prompt_suffix": (
            "liquid glass style, flowing translucent chrome surfaces, liquid metal reflections, "
            "iridescent color shifts, holographic sheen, smooth flowing organic forms, "
            "futuristic glass morphing, rainbow light dispersion, "
            "glossy wet surface, cinematic studio lighting, no text, no watermark"
        ),
        "bg_type": "radial",
        "bg_center_color": (200, 210, 230),
        "bg_edge_color": (140, 150, 180),
        "bg_vignette": True,
        "bg_vignette_strength": 0.22,
        "text_dark": (220, 225, 240),
        "text_medium": (170, 180, 200),
        "text_light": (120, 130, 155),
        "primary": (220, 225, 240),
        "secondary": (180, 120, 255),
        "accent": (0, 220, 200),
        "highlight_color": (120, 80, 255),
        "highlight_text": (255, 255, 255),
        "card_bg": (30, 35, 50),
        "card_radius": 24,
        "image_corner_radius": 24,
    },
    "hyper_realistic": {
        "label": "Hyper-Realistic",
        "description": "Photorealistic imagery with cinematic lighting and detail",
        "image_prompt_suffix": (
            "hyper-realistic photographic style, ultra-detailed 8K resolution, "
            "cinematic dramatic lighting, shallow depth of field bokeh, "
            "professional DSLR quality, lifelike textures and materials, "
            "volumetric light rays, photojournalistic composition, "
            "National Geographic quality, no text, no watermark"
        ),
        "bg_type": "radial",
        "bg_center_color": (25, 25, 30),
        "bg_edge_color": (10, 10, 15),
        "bg_vignette": True,
        "bg_vignette_strength": 0.30,
        "text_dark": (240, 240, 240),
        "text_medium": (180, 180, 185),
        "text_light": (120, 120, 128),
        "primary": (240, 240, 240),
        "secondary": (255, 200, 80),
        "accent": (255, 140, 50),
        "highlight_color": (255, 180, 50),
        "highlight_text": (20, 20, 20),
        "card_bg": (40, 40, 48),
        "card_radius": 16,
        "image_corner_radius": 16,
    },
}

DEFAULT_VISUAL_STYLE = os.getenv("DEFAULT_VISUAL_STYLE", "claymorphism")
AVAILABLE_VISUAL_STYLES = list(VISUAL_STYLES.keys())

# ── Content Modes ─────────────────────────────────────
# Defines the different content generation modes available in the pipeline.
# Each mode changes how input is interpreted and how the story is structured.

CONTENT_MODES = {
    "article": {
        "label": "Article / URL",
        "description": "Convert an article, URL, or text into a narrated video",
        "requires_url_or_text": True,
        "icon": "bi-newspaper",
    },
    "deep_dive": {
        "label": "Deep Dive ✨",
        "description": "NotebookLM-style: two hosts discuss your sources in a natural podcast conversation",
        "requires_url_or_text": True,  # needs at least one URL/text
        "icon": "bi-broadcast",
    },
    "thought_experiment": {
        "label": "Thought Experiment",
        "description": "Generate a philosophical 'what if' video from a question",
        "requires_url_or_text": False,  # just needs a question
        "icon": "bi-lightbulb",
    },
    "ghost_collab": {
        "label": "Ghost Collaboration",
        "description": "Simulate a conversation with a historical or fictional figure",
        "requires_url_or_text": False,
        "icon": "bi-chat-left-quote",
    },
    "kids_story": {
        "label": "Kids Story ✨",
        "description": "Viral short-form kids story with curiosity hooks and fast pacing",
        "requires_url_or_text": True,
        "icon": "bi-book",
    },
}

DEFAULT_CONTENT_MODE = "article"
AVAILABLE_CONTENT_MODES = list(CONTENT_MODES.keys())

# ── Kids Story Settings (Viral Short-Form) ───────────
KIDS_STORY_DURATION = (35, 55)           # target seconds — short & punchy for viral
KIDS_STORY_SCREENS = (6, 12)             # screen count range
KIDS_STORY_HOOK_STYLES = [
    "mystery",        # "This kitten tried to catch the moon… but something impossible happened."
    "emotional",      # "Everyone ignored this little bear… until one night changed everything."
    "danger",         # "This tiny penguin got lost in the desert… but then THIS happened."
    "reverse_story",  # "A turtle flying in the sky?! Let me explain…"
    "question",       # "What would happen if a turtle tried to fly?"
]

# ── Thought Experiment Settings ───────────────────────
THOUGHT_EXPERIMENT_DURATION = (45, 75)  # target seconds - slightly shorter, punchy
THOUGHT_EXPERIMENT_SCREENS = (8, 14)    # screen count range
THOUGHT_EXPERIMENT_TONE = "dramatic"    # default tone for thought experiments

# ── Deep Dive Settings (NotebookLM-inspired) ──────
DEEP_DIVE_DURATION = (55, 90)        # target seconds — longer for discussion format
DEEP_DIVE_SCREENS = (10, 18)         # screen count range (more turns for conversation)
DEEP_DIVE_MAX_SOURCES = 5            # max URLs/texts to combine
DEEP_DIVE_MAX_CONTEXT_CHARS = 15000  # max combined source text sent to LLM
# Deep Dive voice pairs: two hosts with distinct personalities
DEEP_DIVE_VOICES = {
    "default": {
        "label": "Alex & Sam (Warm + Curious)",
        "host_a": "en-US-AriaNeural",       # warm, lead host
        "host_b": "en-US-GuyNeural",        # curious, asks questions
    },
    "energetic": {
        "label": "Emma & Brian (High Energy)",
        "host_a": "en-US-EmmaNeural",
        "host_b": "en-US-BrianNeural",
    },
    "british": {
        "label": "Sonia & Ryan (BBC Style)",
        "host_a": "en-GB-SoniaNeural",
        "host_b": "en-GB-RyanNeural",
    },
    "storytellers": {
        "label": "Jenny & Christopher (Documentary)",
        "host_a": "en-US-JennyNeural",
        "host_b": "en-US-ChristopherNeural",
    },
}

# ── Ghost Collaboration Settings ──────────────────────
# Voice mapping: maps character "type" to a contrasting narrator voice
# so the two voices in a dialogue are distinguishable.
GHOST_COLLAB_VOICES = {
    # (narrator_voice, character_voice) pairs for dialogue
    "default": {
        "narrator": "en-US-AriaNeural",       # warm female narrator
        "character": "en-US-GuyNeural",        # contrasting male character
    },
    "female_character": {
        "narrator": "en-US-GuyNeural",         # male narrator
        "character": "en-US-JennyNeural",      # female character
    },
    "british": {
        "narrator": "en-US-AriaNeural",
        "character": "en-GB-RyanNeural",       # British accent for character
    },
    "scholarly": {
        "narrator": "en-US-AriaNeural",
        "character": "en-US-ChristopherNeural",  # deep, authoritative
    },
}

GHOST_COLLAB_MAX_TURNS = 8           # max dialogue turns (narrator + character combined)
GHOST_COLLAB_TURN_DURATION = (3, 6)  # seconds per dialogue turn

# ── Series / Chain Mode Settings ──────────────────────
SERIES_DIR = BASE_DIR / "series"
SERIES_DIR.mkdir(parents=True, exist_ok=True)
SERIES_MAX_EPISODES = 20
SERIES_CLIFFHANGER_ENABLED = True

# Performance ───────────────────────────────────────
RENDER_THREADS = min(os.cpu_count() or 4, 8)
ENABLE_CACHE = True
CACHE_DIR = TEMP_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Default video render engine ("remotion" or "claymorphism")
DEFAULT_RENDERER = os.getenv("DEFAULT_RENDERER", "remotion")
