# 🎬 Project HER v2.0 – AI Article-to-Video Agent

> Turn any article, URL, or text story into a polished, cinematic short video — fully automated, AI-powered, zero editing required. Now with **Remotion React/TypeScript rendering** and **99 cinematic effects**.

News mode is an additive, evidence-linked paper-cutout pipeline with its own shared Remotion/MoviePy manifest. See [README_NEWS.md](README_NEWS.md) for setup, source policies, current authenticated provider integrations, CLI examples, and observed validation limits. News deliberately uses restrained effects and phrase timing when native word boundaries are unavailable; the general effects/provider descriptions below describe the older modes.

---

## What It Does

Project HER takes text input (a URL, article, or raw story) and produces a ready-to-upload short-form video with AI narration, visuals, animated captions, transitions, and background music — all in one command.

**Dual rendering engine**: Choose between MoviePy (Python-native) or Remotion (React/TypeScript) for video rendering, with 99 built-in cinematic effects including text animations, image animations, scene transitions, overlays, and animated backgrounds.

---

## Core Features

### Input
- **URL scraping** – Paste any article/blog URL; content is auto-extracted
- **Raw text** – Pass a story or article directly as text
- **File input** – Load content from a `.txt` file

### AI Content Engine
- **Multi-provider LLM support** – Groq (Llama 3.1), Copilot Bridge, or any OpenAI-compatible API
- **7 tone presets** – informative · storytelling · social · dramatic · educational · motivational · explainer
- **Multiple content modes** – article · ghost collab · deep dive
- **Automatic story splitting** – AI breaks long stories into screen-level segments with visual type hints, narration position, and emotion tagging

### Visuals
- **Pexels stock images** – Auto-fetched royalty-free images matching each key point
- **AI-generated images (Claymorphism mode)** – Toggle `--ai-images` to generate unique visuals using:
  - **Replicate** (primary, paid) – FLUX Schnell ($0.003/img) or FLUX Pro ($0.04/img), unlimited
  - **HuggingFace** (free fallback) – FLUX.1-schnell via Inference API
  - **Pollinations.ai** (final fallback) – No API key required
  - 3-tier automatic fallback chain with retry logic and credit depletion detection
- **11 visual styles** – claymorphism, glassmorphism, neon_punk, vintage_paper, watercolor, comic_book, minimalist, cyberpunk, pastel_dream, dark_elegance, retro_futurism
- **Claymorphism design system** – Soft 3D clay-rendered style with pastel palette, rounded cards, and warm lighting

### Narration
- **15+ voices** – Microsoft Edge TTS (free), including US, UK, Australian, and Indian English
- **Word-level timing** – Karaoke-style lip-sync accuracy for animated captions
- **Speed control** – Adjustable narration rate (`--speed "+20%"`)
- **12+ languages** – English, Hindi, Spanish, French, German, Portuguese, Japanese, Korean, Chinese, Arabic, Tamil, Telugu, Bengali, Marathi

### Rendering Engines

#### MoviePy (Classic)
- Python-native rendering with Pillow frames
- Standard transitions and compositor
- Good for simple/quick renders

#### Remotion (React/TypeScript) ⭐ NEW
- Professional-grade rendering via React components
- **99 built-in effects** organized into 9 categories:
  - **19 Text Entry Animations** – fade_in, slide_up, scale_bounce, stamp_in, elastic_drop, blur_reveal, zoom_blur_in, spiral_in, glitch_in, 3D flip/tilt, typewriter, card_flip_3d, and more
  - **14 Text Exit Animations** – fade_out, dissolve_out, evaporate, explode_out, swipe_wipe, vortex_out, 3D flip_out, crumble, and more
  - **13 Text Continuous Effects** – breathe, glow_pulse, shake, wave_motion, float_drift, flicker, heartbeat, pendulum, bounce, fire_flicker, 3D wobble, neon_flash
  - **6 Image Entry Animations** – img_fade_in, img_scale_bounce, img_zoom_in, img_blur_reveal, img_slide_left, img_3d_entrance
  - **12 Image Treatments** – ken_burns, zoom_pulse, parallax_2d, brightness_pulse, color_shift, vignette, tilt_shift, sepia_blend, desaturate, 3D tilt, film_grain, cinematic_crop
  - **3 Image Exit Animations** – img_fade_out, img_zoom_out, img_blur_out
  - **18 Scene Transitions** – crossfade, flash, circle_wipe, slide_horizontal, wipe_left/right/down, ink_bleed, blur_transition, pixelate, zoom_in/out, elastic_bounce, glitch, 3D cube_rotate, 3D page_flip, dissolve, morph
  - **9 Overlays** – subtle_grain, bokeh, fire_embers, sparkle, dust_particles, scan_lines, chromatic_aberration, VHS_distortion, rain
  - **6 Animated Backgrounds** – color_breathe, gradient_shift, pulse, particle_float, aurora, radial_pulse
- **Spring physics library** – 10 presets (snappy, bouncy, smooth, heavy, elastic, gentle, pop, dramatic, tremor, soft_land) with emotion-based auto-selection
- **AI Effects Agent** – Automatically selects optimal effects per scene based on emotion, content type, and narrative flow
- Renders at 1080×1920 (portrait), 30 FPS, H.264+AAC

### Video Composition
- **3 formats** – Vertical 9:16 (Reels/Shorts/TikTok) · Horizontal 16:9 (YouTube) · Square 1:1 (Instagram)
- **8 visual themes** – cinematic · neon · minimal · playful · news · retro · corporate · explainer
- **6 caption styles** – karaoke · pop · glow · bold_impact · classic · reveal
- **18 transitions** (Remotion) or **5 transitions** (MoviePy)
- **7 color grades** – none · warm · cool · vintage · cinematic · b&w · vibrant
- **Procedural background music** – Auto-generated BGM with mood matching
- **SRT subtitles** – Exported alongside every video
- **Thumbnail generation** – Auto-generated poster frame
- **Safe zones** – Top/bottom reserved for branding; images fixed center; text dynamically positioned

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

### Web UI
- **Tabbed interface** – Generate, History, Reference, Remotion Studio
- **Remotion Studio** – Browse and preview all 99 effects by category with on-demand video rendering and caching
- **Render engine toggle** – Switch between MoviePy and Remotion in Advanced settings
- **SSE progress tracking** – Real-time stage-by-stage progress updates
- **Batch preview rendering** – Pre-cache all effect previews with one click

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
┌──────────────────────────────────────────────────────────────────────────┐
│               CLI (main.py) / Web UI (web_ui.py:7860)                    │
├──────────────────────────────────────────────────────────────────────────┤
│                    Orchestrator (orchestrator.py)                         │
│           renderer="moviepy" │ renderer="remotion"                        │
├─────────┬───────────┬────────┴──┬────────────┬───────────────────────────┤
│ Scraper │ Analyzer  │ Visuals   │ Narration  │ Compositor                │
│ URL /   │ Multi-LLM │ Pexels /  │ Edge-TTS   │ MoviePy (standard)       │
│ Text    │ Provider  │ AI Images │ 15+ voices │ Clay (AI mode)            │
│         │           │           │ 12+ langs  │ Remotion (React/TS) ⭐    │
├─────────┴───────────┤           ├────────────┤                           │
│   Story Splitter    │           │ Effects    │  Remotion Pipeline:       │
│   (screen segments, │           │ Agent      │  18 TypeScript files      │
│    emotion, layout) │           │ (AI-based) │  99 effects, spring       │
│                     │           │            │  physics, 3D transforms   │
└─────────────────────┴───────────┴────────────┴───────────────────────────┘
```

### Module Breakdown

| Module | File | Role |
|---|---|---|
| CLI | `main.py` | Command-line interface with Click |
| Web UI | `web_ui.py` | Flask app at `localhost:7860` with SSE progress, Remotion Studio |
| Orchestrator | `agent/orchestrator.py` | Pipeline coordination, dual renderer support |
| Scraper | `agent/scraper.py` | URL extraction + raw text handling |
| Analyzer | `agent/analyzer.py` | Multi-provider LLM content analysis |
| Visuals | `agent/visuals.py` | Pexels image fetching |
| AI Visuals | `agent/ai_visuals.py` | Replicate/HF/Pollinations image generation |
| Story Splitter | `agent/story_splitter.py` | AI screen segmentation with emotion/layout |
| Narration | `agent/narration.py` | Edge-TTS with word-level timing |
| Compositor | `agent/compositor.py` | Standard video rendering (MoviePy) |
| Clay Compositor | `agent/clay_compositor.py` | Claymorphism video rendering (Pillow frames) |
| **Remotion Renderer** | `agent/remotion_renderer.py` | **Python→Remotion bridge, asset staging, CLI render** |
| Audio Engine | `agent/audio_engine.py` | Procedural BGM + SFX |
| Effects Agent | `agent/effects_agent.py` | AI-powered per-scene effect selection |
| Effects Catalog | `agent/effects_catalog.py` | 148 Python-side effect definitions |
| Effects Engine | `agent/effects_engine.py` | MoviePy effect application engine |
| Config | `config.py` | Central settings (700+ lines) |

### Remotion TypeScript Files (18 files, ~4,600 lines)

| File | Role |
|---|---|
| `remotion/src/Root.tsx` | Composition registration (ProjectHER + EffectPreview) |
| `remotion/src/Video.tsx` | Main video compositor with scene sequencing + transitions |
| `remotion/src/types.ts` | Zod schemas + TypeScript interfaces for all props |
| `remotion/src/EffectPreview.tsx` | Short preview composition for Remotion Studio |
| `remotion/src/components/Scene.tsx` | 5-layer scene compositor (bg → image → text → overlay → brand) |
| `remotion/src/components/TextBlock.tsx` | Karaoke word highlighting + text animations |
| `remotion/src/components/ImageBlock.tsx` | Image rendering with entry/treatment/exit effects |
| `remotion/src/components/BrandBar.tsx` | Animated brand bar with spring physics |
| `remotion/src/effects/textAnimations.ts` | 30+ text entry/exit/continuous CSS animations |
| `remotion/src/effects/imageAnimations.ts` | Cinematic image effects (Ken Burns, parallax, 3D) |
| `remotion/src/effects/overlays.tsx` | 9 overlay effects (grain, bokeh, embers, rain, VHS, etc.) |
| `remotion/src/effects/backgrounds.tsx` | 6 animated backgrounds (aurora, particles, gradients) |
| `remotion/src/effects/springs.ts` | 10 spring physics presets + emotion mapping |
| `remotion/src/transitions/sceneTransitions.ts` | 18 scene transitions (2D + 3D) |
| `remotion/src/three/ThreeComponents.tsx` | Three.js integration for 3D effects |

---

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+ (for Remotion renderer)
- FFmpeg

```bash
# macOS
brew install ffmpeg node

# Ubuntu/Debian
sudo apt-get install ffmpeg
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Install

```bash
cd project-HER

# Python dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Remotion dependencies (for React/TS renderer)
cd remotion && npm install && cd ..
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
# From a URL (MoviePy renderer)
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
| AI/LLM | Groq (Llama 3.1), Copilot Bridge, OpenAI-compatible APIs |
| Image Gen | Replicate (FLUX), HuggingFace, Pollinations |
| Stock Images | Pexels API |
| TTS | Microsoft Edge TTS (15+ voices, 12+ languages) |
| Video (Python) | MoviePy 2.1 + Pillow |
| Video (React) | Remotion v4 + React 19 + TypeScript |
| 3D Effects | Three.js via @remotion/three |
| Web | Flask + SSE + Bootstrap 5 |
| CLI | Click + Rich |

---

## Effect Categories (Remotion)

| Category | Count | Examples |
|---|---|---|
| Text Entry | 19 | fade_in, scale_bounce, stamp_in, glitch_in, 3D flip/tilt, typewriter |
| Text Exit | 14 | fade_out, evaporate, explode_out, vortex_out, crumble |
| Text Continuous | 13 | breathe, glow_pulse, shake, neon_flash, 3D wobble |
| Image Entry | 6 | img_fade_in, img_zoom_in, img_3d_entrance |
| Image Treatment | 12 | ken_burns, zoom_pulse, parallax, vignette, film_grain |
| Image Exit | 3 | img_fade_out, img_zoom_out, img_blur_out |
| Scene Transitions | 18 | crossfade, circle_wipe, 3D cube_rotate, page_flip, morph |
| Overlays | 9 | grain, bokeh, fire_embers, rain, VHS_distortion |
| Backgrounds | 6 | aurora, gradient_shift, particle_float, radial_pulse |
| **Total** | **99** | |

---

## License

Private project. All rights reserved.

ProjectHER video branding, review evidence, configuration, renderer trade-offs, and manual deployment commands are documented in [BRANDING_IMPLEMENTATION.md](BRANDING_IMPLEMENTATION.md).
