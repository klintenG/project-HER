"""Render a full Remotion review video demonstrating the Pruna P-Image-Edit visual pipeline.

Renders the Sisyphus narration sequence using the Pruna Turbo generated assets,
with high-resolution cutouts, synchronized audio, subtitles, and motion graphics.
"""
from __future__ import annotations
import asyncio
import json
import logging
import math
import subprocess
import sys
import time
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from agent.cutout_processor import CutoutProcessor
from agent.editorial.director import VisualSettings
from agent.editorial.models import Asset, Audio, Entity as RenderEntity, Fonts, Section, Word, digest
from agent.editorial.planner import build
from agent.editorial.render import render
from agent.editorial.sentence_storyboard import direction
from agent.editorial.visuals import EditorialScript
from agent.news_audio import synthesize
from agent.editorial.audio import normalize
from agent.news_models import Entity, Script, Sentence

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("render_benchmark_video")

BENCHMARK_DIR = ROOT / "output" / "pruna_controlled_benchmark"
VIDEO_OUT_DIR = BENCHMARK_DIR / "video_review"
VIDEO_OUT_DIR.mkdir(parents=True, exist_ok=True)

SISYPHUS_BEATS = [
    ("sisyphus_01", "In ancient Corinth, King Sisyphus believed he could outsmart the gods themselves.", "standing proudly in Corinth", "Corinth courtyard", "haughty"),
    ("sisyphus_02", "When Thanatos came to claim him, the cunning king tricked Death into chains.", "tricking Death into chains", "shadowy chamber", "triumphant"),
    ("sisyphus_03", "Enraged by his deceit, Zeus condemned Sisyphus to the deepest realm of the Underworld.", "kneeling under divine judgment", "Tartarus underworld", "defiant"),
    ("sisyphus_04", "His eternal punishment was to push an enormous granite boulder up a steep mountain.", "pushing enormous boulder uphill", "rocky mountain slope", "straining"),
    ("sisyphus_05", "With every muscle straining, he inched closer to the summit.", "straining near the mountain summit", "narrow mountain crest", "exhaustion"),
    ("sisyphus_06", "Just as triumph seemed within reach, the stone slipped from his grasp.", "boulder slipping from his grasp", "steep precipice", "shock"),
    ("sisyphus_07", "The boulder rolled violently all the way back down to the plain below.", "boulder rolling violently downhill", "mountain slope to plain", "despair"),
    ("sisyphus_08", "And Sisyphus began his hopeless labor once again.", "returning to the bottom to restart", "desolate plain", "weary acceptance"),
]


def main():
    full_text = " ".join(text for _, text, _, _, _ in SISYPHUS_BEATS)
    master_wav = VIDEO_OUT_DIR / "master.wav"
    if not master_wav.is_file():
        logger.info("Generating narration audio for Sisyphus review video...")
        script_sentences = [
            Sentence(id=f"s_{i+1}", text=text, phrase=action, claim_ids=["c_sisyphus"], role="hook" if i == 0 else "development")
            for i, (_, text, action, _, _) in enumerate(SISYPHUS_BEATS)
        ]
        script_obj = Script(
            summary="The Myth of Sisyphus",
            narration=full_text,
            sentences=script_sentences
        )

        audio_res = synthesize(script_obj, VIDEO_OUT_DIR, "google_tts")
        audio_path = Path(audio_res.path)
        logger.info("Synthesized narration audio: %s", audio_path)
        normalize(audio_path, master_wav)
    else:
        logger.info("Reusing existing normalized narration audio: %s", master_wav)

    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(master_wav)
    ]))
    logger.info("Audio duration: %.2f seconds", duration)

    # Process cutouts for Pruna Turbo images
    processor = CutoutProcessor(backend='rembg', models=['isnet-general-use'])
    cutout_dir = VIDEO_OUT_DIR / "cutouts"
    cutout_dir.mkdir(parents=True, exist_ok=True)

    entities = []
    assets = []
    sentence_rows = []
    sections = []
    words = []
    storyboard = []

    # Calculate approximate sentence time boundaries
    beat_dur = duration / len(SISYPHUS_BEATS)
    for i, (bid, text, action, setting, emotion) in enumerate(SISYPHUS_BEATS):
        start_t = i * beat_dur
        end_t = (i + 1) * beat_dur if i < len(SISYPHUS_BEATS) - 1 else duration

        raw_img = BENCHMARK_DIR / "pruna_turbo" / f"{bid}.png"
        if not raw_img.is_file():
            # Fallback to master if missing
            raw_img = BENCHMARK_DIR / "masters" / "sisyphus_master.png"

        cut_img = cutout_dir / f"{bid}_cutout.png"
        has_alpha = True
        try:
            stats, method = processor.process(raw_img, cut_img, allow_portrait_crop=True, allow_bottom_crop=True)
        except Exception as exc:
            logger.warning("Cutout extraction fell back to rectangle for %s: %s", bid, exc)
            shutil.copyfile(raw_img, cut_img)
            has_alpha = False

        eid = f"entity_{bid}"
        aid = f"asset_{bid}"
        sid = f"sentence_{bid}"

        ent = Entity(id=eid, name="Sisyphus", kind="person", identity="fictional", description=action)
        entities.append(ent)
        sentence_rows.append(Sentence(id=sid, text=text, claim_ids=["c_sisyphus"], entity_ids=[eid], phrase=action, role="development"))

        with Image.open(cut_img) as im:
            w, h = im.size

        assets.append(Asset(
            id=aid,
            entityId=eid,
            path=str(cut_img),
            originalPath=str(raw_img),
            role="portrait",
            subject="Sisyphus",
            source="prunaai/p-image-edit:turbo",
            license="ProjectHER internal benchmark",
            attribution="Pruna P-Image-Edit (Turbo)",
            width=w,
            height=h,
            alpha=has_alpha,
            factual=False,
            confidence=0.92,
            preparation="trimmed_alpha" if has_alpha else "rectangle",
            fallback="AI illustration generated via Pruna P-Image-Edit for narrative continuity",
            sha256=digest(cut_img)
        ))

        # Words & section
        tokens = text.split()
        wids = []
        for j, token in enumerate(tokens):
            wid = f"w_{i}_{j}"
            wids.append(wid)
            w_start = start_t + (end_t - start_t) * (j / len(tokens))
            w_end = start_t + (end_t - start_t) * ((j + 1) / len(tokens))
            words.append(Word(id=wid, sectionId=sid, text=token, start=w_start, end=w_end, provenance="estimated_phrase", confidence=0.85))

        sections.append(Section(id=sid, text=text, start=start_t, end=end_t, wordIds=wids))
        storyboard.append({
            "sentence_id": sid,
            "primary_entity_id": eid,
            "secondary_entity_ids": [],
            "main_action": action,
            "state_before": "prior state",
            "state_after": action,
            "visual_focus": action,
            "location": setting,
            "emotional_response": emotion,
            "composition_type": "split-screen" if i % 2 == 1 else "centered",
        })

    editorial_script = EditorialScript(
        narration=full_text,
        summary="The Myth of Sisyphus (Pruna P-Image-Edit Benchmark)",
        sentences=[s.model_dump() for s in sentence_rows],
        entities=entities,
        sentence_storyboard=storyboard
    )
    render_entities = [RenderEntity(id=e.id, name=e.name, identity="fictional", assetIds=[assets[i].id], source="pruna_turbo") for i, e in enumerate(entities)]

    settings = VisualSettings.configured().model_copy(update={"editorialStyleVersion": "reference-v2"})
    timeline = build(
        editorial_script,
        words,
        sections,
        render_entities,
        assets,
        master_wav,
        VIDEO_OUT_DIR,
        "pruna_sisyphus_review",
        {},
        direction=direction(editorial_script),
        visual_settings=settings
    )

    out_mp4 = VIDEO_OUT_DIR / "sisyphus_pruna_benchmark_review.mp4"
    logger.info("Rendering Remotion video to: %s ...", out_mp4)
    t0 = time.monotonic()
    video, stats = render(timeline, out_mp4)
    render_time = time.monotonic() - t0
    logger.info("Video successfully rendered in %.2f seconds! Output file: %s (size: %d bytes)", render_time, video, video.stat().st_size)

    # Validate output
    assert video.is_file(), "Rendered MP4 file missing!"
    assert video.stat().st_size > 100_000, "Rendered MP4 file unexpectedly small!"

    # Create thumbnail
    thumb = VIDEO_OUT_DIR / "thumbnail.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3", "-i", str(video), "-frames:v", "1", str(thumb)], check=True)
    logger.info("Saved video thumbnail: %s", thumb)


if __name__ == "__main__":
    main()
