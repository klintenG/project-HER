# 🎬 Project HER v2.0 – AI Article-to-Video Agent

> Turn any article, URL, or text story into a polished, cinematic short video — fully automated, AI-powered, zero editing required.

---

## What It Does

Project HER takes text input (a URL, article, or raw story) and produces a ready-to-upload short-form video with AI narration, visuals, animated captions, transitions, and background music — all in one command.

---

## Core Features

### Input
- **URL scraping** – Paste any article/blog URL; content is auto-extracted
- **Raw text** – Pass a story or article directly as text
- **File input** – Load content from a `.txt` file

### AI Content Engine
- **Groq AI analysis** – Llama 3.1 extracts 3–6 key points, generates a hook, title, and narration script
- **7 tone presets** – informative · storytelling · social · dramatic · educational · motivational · explainer
- **Automatic story splitting** – AI breaks long stories into screen-level segments with visual type hints

### Visuals
- **Pexels stock images** – Auto-fetched royalty-free images matching each key point
- **AI-generated images (Claymorphism mode)** – Toggle `--ai-images` to generate unique visuals using:
  - **Replicate** (primary, paid) – FLUX Schnell ($0.003/img) or FLUX Pro ($0.04/img), unlimited
  - **HuggingFace** (free fallback) – FLUX.1-schnell via Inference API
  - **Pollinations.ai** (final fallback) – No API key required
  - 3-tier automatic fallback chain with retry logic and credit depletion detection
- **Ken Burns effect** – Slow zoom/pan on images for cinematic motion
- **Claymorphism design system** – Soft 3D clay-rendered style with pastel palette, rounded cards, and warm lighting

### Narration
- **15+ voices** – Microsoft Edge TTS (free), including US, UK, Australian, and Indian English
- **Word-level timing** – Karaoke-style lip-sync accuracy for animated captions
- **Speed control** – Adjustable narration rate (`--speed "+20%"`)
- **12+ languages** – English, Hindi, Spanish, French, German, Portuguese, Japanese, Korean, Chinese, Arabic, Tamil, Telugu, Bengali, Marathi

### Video Composition
- **3 formats** – Vertical 9:16 (Reels/Shorts/TikTok) · Horizontal 16:9 (YouTube) · Square 1:1 (Instagram)
- **8 visual themes** – cinematic · neon · minimal · playful · news · retro · corporate · explainer
- **6 caption styles** – karaoke · pop · glow · bold_impact · classic · reveal
- **5 transitions** – fade · slide_left · slide_up · zoom_in · wipe
- **7 color grades** – none · warm · cool · vintage · cinematic · b&w · vibrant
- **Procedural background music** – Auto-generated BGM with mood matching
- **SRT subtitles** – Exported alongside every video
- **Thumbnail generation** – Auto-generated poster frame

### Platform Presets
One flag sets format, duration, bitrate, FPS, and recommended theme:

| `--platform` | Format | Duration | FPS | Bitrate |
|---|---|---|---|---|
| `tiktok` | 9:16 | 15–60s | 30 | 5 Mbps |
| `youtube_shorts` | 9:16 | 30–58s | 30 | 6 Mbps |
| `instagram_reels` | 9:16 | 15–60s | 30 | 5 Mbps |
| `youtube` | 16:9 | 45–90s | 24 | 8 Mbps |
| `twitter` | 1:1 | 15–45s | 30 | 4 Mbps |
| `linkedin` | 1:1 | 30–60s | 24 | 5 Mbps |
| `explainer` | 16:9 | 45–90s | 24 | 6 Mbps |

### Premium Options
- **Watermark** – Text or image branding on every frame
- **Custom font** – Use your own TTF/OTF
- **Custom intro/outro** – Image or video cards
- **Custom BGM** – Replace procedural music with a file
- **Quality presets** – draft · standard · high · ultra (up to 12 Mbps, 30 FPS)
- **Brand overlay** – Display brand name in AI image mode (`--brand "YourBrand"`)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│              CLI (main.py) / Web UI (web_ui.py)                    │
├────────────────────────────────────────────────────────────────────┤
│                   Orchestrator (orchestrator.py)                    │
│               Standard Pipeline │ AI Image Pipeline                │
├─────────┬───────────┬───────────┬────────────┬────────────────────┤
│ Scraper │ Analyzer  │ Visuals   │ Narration  │ Compositor         │
│ URL /   │ Groq AI   │ Pexels /  │ Edge-TTS   │ MoviePy (standard) │
│ Text    │ Llama 3.1 │ AI Images │ 15+ voices │ Clay (AI mode)     │
├─────────┴───────────┼───────────┴────────────┼────────────────────┤
│                     │ Story Splitter         │ Clay Compositor     │
│                     │ (AI image mode)        │ (Claymorphism)      │
└─────────────────────┴────────────────────────┴────────────────────┘
```

### Module Breakdown

| Module | File | Role |
|---|---|---|
| CLI | `main.py` | Command-line interface with Click |
| Web UI | `web_ui.py` | Flask app at `localhost:7860` with SSE progress |
| Orchestrator | `agent/orchestrator.py` | Pipeline coordination, 5-stage workflow |
| Scraper | `agent/scraper.py` | URL extraction + raw text handling |
| Analyzer | `agent/analyzer.py` | Groq AI content analysis |
| Visuals | `agent/visuals.py` | Pexels image fetching |
| AI Visuals | `agent/ai_visuals.py` | Replicate/HF/Pollinations image generation |
| Story Splitter | `agent/story_splitter.py` | AI screen segmentation for Claymorphism |
| Narration | `agent/narration.py` | Edge-TTS with word-level timing |
| Compositor | `agent/compositor.py` | Standard video rendering (MoviePy) |
| Clay Compositor | `agent/clay_compositor.py` | Claymorphism video rendering (Pillow frames) |
| Audio Engine | `agent/audio_engine.py` | Procedural BGM + SFX |
| Config | `config.py` | Central settings (620+ lines) |

---

## Quick Start

### Prerequisites
- Python 3.9+
- FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

### Install

```bash
cd project-HER
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your keys:
#   GROQ_API_KEY        (required)  – https://console.groq.com
#   PEXELS_API_KEY      (required)  – https://www.pexels.com/api/
#   REPLICATE_API_TOKEN (optional)  – https://replicate.com/account/api-tokens
#   HF_API_TOKEN        (optional)  – https://huggingface.co/settings/tokens
```

### Generate

```bash
# From a URL
python main.py generate --url "https://example.com/article" --tone informative

# From text (standard Pexels mode)
python main.py generate --text "Your story here..." --theme neon --captions karaoke

# AI-generated images (Claymorphism mode)
python main.py generate --text "Your story here..." --ai-images --brand "MyBrand"

# Platform preset
python main.py generate --url "https://..." --platform tiktok

# Full options
python main.py generate --text "..." --tone dramatic --theme cinematic \
    --captions pop --transition zoom_in --color-grade warm \
    --quality high --format vertical -v
```

### Web UI

```bash
python web_ui.py
# Opens at http://localhost:7860
```

### CLI Commands

```bash
python main.py --help          # All commands
python main.py voices          # List available voices
python main.py themes          # List visual themes
python main.py captions        # List caption styles
python main.py generate --help # All generation options
```

---

## AI Image Providers

| Provider | Cost | Quality | Reliability | API Key |
|---|---|---|---|---|
| **Replicate** (default) | ~$0.003/img | Excellent | Unlimited | Required |
| **HuggingFace** | Free | Excellent | Rate-limited | Required |
| **Pollinations** | Free | Good | Unreliable | None |

The system auto-falls back through the chain if any provider fails.

---

## Output

Each run creates a timestamped folder in `output/`:

```
output/video_20260219_155311/
├── beep-the-repair-robot.mp4    # Final video
├── beep-the-repair-robot.srt    # Subtitles
├── thumbnail.jpg                # Auto-generated poster
├── manifest.json                # Run metadata
├── ai_img_*.png                 # AI-generated images (if --ai-images)
└── narration_*.mp3              # TTS audio clips
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI/LLM | Groq API (Llama 3.1-8b-instant) |
| Image Gen | Replicate (FLUX), HuggingFace, Pollinations |
| Stock Images | Pexels API |
| TTS | Microsoft Edge TTS |
| Video | MoviePy 2.1 + Pillow |
| Web | Flask + SSE |
| CLI | Click + Rich |

---

## License

Private project. All rights reserved.
