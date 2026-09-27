---
title: Project HER
emoji: 🎬
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# 🎬 Project HER — AI Article-to-Video Agent

Convert any article, news story, or text into a cinematic short video using a fully automated AI pipeline.

## What it does

1. **Analyzes** your article/text with Gemini AI
2. **Writes** a narration script with emotional beats
3. **Generates** AI voiceover (Google TTS / Edge TTS)
4. **Fetches** matching visuals (Pexels stock or AI-generated images)
5. **Composes** a video with karaoke captions, transitions & music

## Required Secrets (Space Settings → Variables and Secrets)

| Secret | Where to get it | Required? |
|--------|----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/apikey) | ✅ Yes |
| `PEXELS_API_KEY` | [pexels.com/api](https://www.pexels.com/api/) | ✅ Yes (free tier) |
| `GOOGLE_TTS_API_KEY` | Same as GEMINI_API_KEY | For Google TTS voice |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io) | Optional (premium voice) |
| `HF_API_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | Optional (AI images) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/keys) | Optional (free LLM fallback) |

## Optional Variables

```
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
TTS_PROVIDER=google_tts
DEFAULT_VIDEO_FORMAT=vertical
WATERMARK_TEXT=YourName
```
