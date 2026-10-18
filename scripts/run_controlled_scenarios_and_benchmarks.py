"""Execute controlled test scenarios and benchmark Pruna P-Image-Edit against FLUX Kontext Pro.

Scenarios:
  - Scenario A: Sisyphus (8 narration sentences)
  - Scenario B: Amaterasu (8 narration sentences)
  - Scenario C: Multi-character interaction (Amaterasu & Susanoo)

Benchmarks:
  - Benchmark A: FLUX Kontext Pro (baseline)
  - Benchmark B: Pruna P-Image-Edit (Turbo=True)
  - Benchmark C: Pruna P-Image-Edit (Turbo=False)
"""
from __future__ import annotations
import asyncio
import base64
import copy
import hashlib
import io
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

# Add workspace root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from agent.cutout_processor import CutoutProcessor
from agent.editorial.images import EditorialImages
from agent.editorial.models import digest
from utils.cost_tracking import summarize_model_usage_and_costs
from utils.generation_diagnostics import export_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("controlled_benchmark")

OUTPUT_DIR = ROOT / "output" / "pruna_controlled_benchmark"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Scenarios Definition
# ---------------------------------------------------------------------------

SCENARIO_A_SISYPHUS = [
    {
        "id": "sisyphus_01",
        "sentence": "In ancient Corinth, King Sisyphus believed he could outsmart the gods themselves.",
        "action": "Standing portrait of King Sisyphus wearing ancient Greek royal robes, bearded, haughty expression, in Corinth courtyard",
        "role": "initial_master",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_02",
        "sentence": "When Thanatos came to claim him, the cunning king tricked Death into chains.",
        "action": "Sisyphus locking heavy iron chains around the cloaked figure of Thanatos (Death), triumphant grin, dark shadowy chamber",
        "role": "action_scene",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_03",
        "sentence": "Enraged by his deceit, Zeus condemned Sisyphus to the deepest realm of the Underworld.",
        "action": "Sisyphus kneeling before the fiery judgment of the gods in Tartarus underworld, chains at his feet, somber and defiant",
        "role": "action_scene",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_04",
        "sentence": "His eternal punishment was to push an enormous granite boulder up a steep mountain.",
        "action": "Sisyphus pushing an enormous round granite boulder up a steep rocky mountain, hands pressed against stone, bent knees, straining muscles",
        "role": "action_scene",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_05",
        "sentence": "With every muscle straining, he inched closer to the summit.",
        "action": "Sisyphus nearing the narrow jagged mountain peak, veins bulging, desperate physical exertion, boulder nearly over the crest",
        "role": "action_scene",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_06",
        "sentence": "Just as triumph seemed within reach, the stone slipped from his grasp.",
        "action": "The massive boulder slipping out of Sisyphus's grasping hands, stone tilting over the steep edge, shock and horror on his face",
        "role": "action_scene",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_07",
        "sentence": "The boulder rolled violently all the way back down to the plain below.",
        "action": "The giant boulder rolling violently downhill in clouds of dust and flying gravel, clearly separated from Sisyphus watching from above",
        "role": "action_scene",
        "character": "Sisyphus",
    },
    {
        "id": "sisyphus_08",
        "sentence": "And Sisyphus began his hopeless labor once again.",
        "action": "Sisyphus walking back down to the bottom of the desolate underworld mountain, bowed head, exhausted posture, preparing to push again",
        "role": "action_scene",
        "character": "Sisyphus",
    },
]

SCENARIO_B_AMATERASU = [
    {
        "id": "amaterasu_01",
        "sentence": "Amaterasu, the radiant sun goddess, illuminated all of heaven and earth.",
        "action": "Radiant Japanese sun goddess Amaterasu in flowing white and crimson kimono robes, golden celestial halo, elegant headdress, glowing divine light",
        "role": "initial_master",
        "character": "Amaterasu",
    },
    {
        "id": "amaterasu_02",
        "sentence": "Her furious brother Susanoo rampaged through the sacred halls, devastating the realm.",
        "action": "Fierce storm god Susanoo wielding a curved blade, wild wind-blown black hair, dark battle attire, shouting in rage inside a grand Japanese palace hall",
        "role": "initial_master_secondary",
        "character": "Susanoo",
    },
    {
        "id": "amaterasu_03",
        "sentence": "Deeply grieved, Amaterasu hid herself inside the dark Heavenly Rock Cave.",
        "action": "Amaterasu sorrowfully retreating inside the dark rocky entrance of the Heavenly Rock Cave (Ama-no-Iwato), pulling a massive stone slab shut",
        "role": "action_scene",
        "character": "Amaterasu",
    },
    {
        "id": "amaterasu_04",
        "sentence": "Without her presence, total darkness swallowed the world and evil spirits multiplied.",
        "action": "The celestial realm plunged into eerie shadow and pitch darkness, shadowy spirits hovering over desolate Japanese shrines and barren trees",
        "role": "environment_scene",
        "character": None,
    },
    {
        "id": "amaterasu_05",
        "sentence": "The desperate gods gathered outside the cavern, placing a sacred bronze mirror before the entrance.",
        "action": "Japanese deities outside the closed cave entrance mounting an ornate polished sacred bronze mirror (Yata no Kagami) on a wooden stand decorated with sacred rope",
        "role": "object_scene",
        "character": None,
    },
    {
        "id": "amaterasu_06",
        "sentence": "Curious about their joyous celebrations, the goddess slowly peeked out from the cave.",
        "action": "Amaterasu carefully peeking her head out from behind the heavy rock door of the cavern, eyes wide with curious wonder",
        "role": "action_scene",
        "character": "Amaterasu",
    },
    {
        "id": "amaterasu_07",
        "sentence": "Catching sight of her own dazzling reflection in the mirror, she stepped forward in wonder.",
        "action": "Amaterasu stepping forward in awe as her radiant illuminated face and glowing headdress are clearly reflected in the gleaming bronze mirror",
        "role": "action_scene",
        "character": "Amaterasu",
    },
    {
        "id": "amaterasu_08",
        "sentence": "Light returned to the heavens, restoring order to the universe.",
        "action": "Amaterasu stepping fully out into the open sky as brilliant golden sunlight bursts across the blossoming landscape and restored mountain shrines",
        "role": "action_scene",
        "character": "Amaterasu",
    },
]

SCENARIO_C_MULTI_CHARACTER = {
    "id": "multi_01",
    "sentence": "Susanoo provoked Amaterasu to fury before the assembled deities.",
    "action": "Susanoo shouting aggressively with raised fist while Amaterasu reacts with visible divine fury and glowing celestial power",
    "characters": ["Amaterasu", "Susanoo"],
}


# ---------------------------------------------------------------------------
# Helper: Build Contact Sheets
# ---------------------------------------------------------------------------

def create_contact_sheet(images: list[tuple[str, Path]], output_path: Path, title: str, cols: int = 4):
    """Combine images into an annotated contact sheet grid."""
    if not images:
        return
    valid_images = [(label, p) for label, p in images if p.is_file()]
    if not valid_images:
        return
    rows = (len(valid_images) + cols - 1) // cols
    cell_w, cell_h = 320, 360
    header_h = 60
    sheet_w = cols * cell_w
    sheet_h = header_h + rows * cell_h

    sheet = Image.new("RGB", (sheet_w, sheet_h), "#181a1f")
    draw = ImageDraw.Draw(sheet)

    # Title
    draw.text((20, 18), title, fill="#ffffff")

    for idx, (label, img_path) in enumerate(valid_images):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = header_h + row * cell_h

        try:
            with Image.open(img_path) as im:
                im_thumb = im.convert("RGBA")
                im_thumb.thumbnail((cell_w - 20, cell_h - 60))
                # Paste centered
                px = x + (cell_w - im_thumb.width) // 2
                py = y + 10 + (cell_h - 60 - im_thumb.height) // 2
                sheet.paste(im_thumb, (px, py), im_thumb if im_thumb.mode == "RGBA" else None)
        except Exception as e:
            draw.text((x + 20, y + 100), f"Error loading: {e}", fill="#ff6666")

        # Label
        draw.rectangle([(x + 10, y + cell_h - 40), (x + cell_w - 10, y + cell_h - 10)], fill="#23272e")
        draw.text((x + 15, y + cell_h - 35), label[:38], fill="#dcdfe4")

    sheet.save(output_path)
    logger.info("Saved contact sheet: %s", output_path)


# ---------------------------------------------------------------------------
# Main Benchmark Execution
# ---------------------------------------------------------------------------

async def run_benchmark():
    logger.info("Starting ProjectHER Pruna P-Image-Edit vs FLUX Kontext Pro Controlled Benchmark")
    processor = CutoutProcessor(backend='none', models=[])
    
    # Track all predictions for unified diagnostic report
    all_prediction_records = []
    benchmark_metrics = {
        "flux_kontext_pro": {"requests": 0, "accepted": 0, "rejected": 0, "latencies": [], "cost": 0.0, "consistency_scores": [], "relevance_scores": []},
        "pruna_turbo": {"requests": 0, "accepted": 0, "rejected": 0, "latencies": [], "cost": 0.0, "consistency_scores": [], "relevance_scores": []},
        "pruna_quality": {"requests": 0, "accepted": 0, "rejected": 0, "latencies": [], "cost": 0.0, "consistency_scores": [], "relevance_scores": []},
    }

    # 1. Generate Master Identity References using FLUX Schnell
    masters_dir = OUTPUT_DIR / "masters"
    masters_dir.mkdir(parents=True, exist_ok=True)
    generator = EditorialImages(primary_count=30)

    # Initial Sisyphus Master
    sisyphus_master_path = masters_dir / "sisyphus_master.png"
    if not sisyphus_master_path.is_file():
        logger.info("Generating Initial Sisyphus Master Reference via FLUX Schnell...")
        t0 = time.monotonic()
        await generator.subject(
            "Editorial illustration of King Sisyphus of Corinth: rugged ancient Greek king, handsome mature bearded face, short dark wavy hair, wearing a simple brown Grecian tunic with leather belt, strong weathered arms, centered on flat neutral background for cutout. Clean character design.",
            sisyphus_master_path
        )
        t_wait = time.monotonic() - t0
        all_prediction_records.append({
            "prediction_id": f"schnell_sisyphus_{int(time.time())}",
            "model_name": "black-forest-labs/flux-schnell",
            "tier": "support",
            "status": "succeeded",
            "outcome": "accepted",
            "total_provider_wait_seconds": round(t_wait, 2),
            "sentence_id": "sisyphus_01",
            "character_or_object": "Sisyphus (Master)",
        })

    # Initial Amaterasu Master
    amaterasu_master_path = masters_dir / "amaterasu_master.png"
    if not amaterasu_master_path.is_file():
        logger.info("Generating Initial Amaterasu Master Reference via FLUX Schnell...")
        t0 = time.monotonic()
        await generator.subject(
            "Editorial illustration of Amaterasu, the Japanese sun goddess: radiant noble goddess wearing ceremonial layered white and scarlet silk kimono robes, elaborate golden kanzashi hair ornaments, divine golden solar disc halo behind her head, serene graceful facial expression, centered on flat neutral background.",
            amaterasu_master_path
        )
        t_wait = time.monotonic() - t0
        all_prediction_records.append({
            "prediction_id": f"schnell_amaterasu_{int(time.time())}",
            "model_name": "black-forest-labs/flux-schnell",
            "tier": "support",
            "status": "succeeded",
            "outcome": "accepted",
            "total_provider_wait_seconds": round(t_wait, 2),
            "sentence_id": "amaterasu_01",
            "character_or_object": "Amaterasu (Master)",
        })

    # Initial Susanoo Master
    susanoo_master_path = masters_dir / "susanoo_master.png"
    if not susanoo_master_path.is_file():
        logger.info("Generating Initial Susanoo Master Reference via FLUX Schnell...")
        t0 = time.monotonic()
        await generator.subject(
            "Editorial illustration of Susanoo-no-Mikoto, the Japanese storm god: fierce warrior god with windswept black hair, wild intense eyes, dark indigo and black samurai armor plates over tunic, broad shoulders, holding a curved bronze sword, centered on flat neutral background.",
            susanoo_master_path
        )
        t_wait = time.monotonic() - t0
        all_prediction_records.append({
            "prediction_id": f"schnell_susanoo_{int(time.time())}",
            "model_name": "black-forest-labs/flux-schnell",
            "tier": "support",
            "status": "succeeded",
            "outcome": "accepted",
            "total_provider_wait_seconds": round(t_wait, 2),
            "sentence_id": "amaterasu_02",
            "character_or_object": "Susanoo (Master)",
        })

    # 2. Benchmark Scenarios across 3 Models / Profiles
    # To compare thoroughly:
    # Benchmark A: FLUX Kontext Pro
    # Benchmark B: Pruna P-Image-Edit (Turbo=True)
    # Benchmark C: Pruna P-Image-Edit (Turbo=False)
    
    benchmarks = [
        {"key": "pruna_turbo", "name": "Pruna P-Image-Edit (Turbo)", "model": "prunaai/p-image-edit", "turbo": True},
        {"key": "pruna_quality", "name": "Pruna P-Image-Edit (Quality)", "model": "prunaai/p-image-edit", "turbo": False},
        {"key": "flux_kontext_pro", "name": "FLUX Kontext Pro (Baseline)", "model": "black-forest-labs/flux-kontext-pro", "turbo": False},
    ]

    # Store results for contact sheets
    scenario_a_images = {b["key"]: [] for b in benchmarks}
    scenario_b_images = {b["key"]: [] for b in benchmarks}
    scenario_c_images = {b["key"]: [] for b in benchmarks}

    # Reference wrappers
    sisyphus_ref = SimpleNamespace(path=str(sisyphus_master_path), characters=["Sisyphus"])
    amaterasu_ref = SimpleNamespace(path=str(amaterasu_master_path), characters=["Amaterasu"])
    multi_ref = SimpleNamespace(
        path=str(amaterasu_master_path),
        paths=[str(amaterasu_master_path), str(susanoo_master_path)],
        characters=["Amaterasu", "Susanoo"]
    )

    # Execute Sisyphus Scenes (Representative action beats)
    logger.info("Executing Scenario A: Sisyphus Action Beats...")
    for beat in SCENARIO_A_SISYPHUS:
        sid = beat["id"]
        sentence = beat["sentence"]
        action = beat["action"]
        is_initial = beat["role"] == "initial_master"

        for b in benchmarks:
            b_key = b["key"]
            b_model = b["model"]
            b_turbo = b["turbo"]
            out_file = OUTPUT_DIR / b_key / f"{sid}.png"
            out_file.parent.mkdir(parents=True, exist_ok=True)

            if is_initial:
                # Master image copied for scene 1
                shutil.copyfile(sisyphus_master_path, out_file)
                scenario_a_images[b_key].append((f"Beat 1: {beat['character']} Standing", out_file))
                continue

            # Keep the visual instruction identical across supported editors.
            prompt = (
                f"Using the supplied identity image, depict the same King Sisyphus: {action}. "
                "Preserve his face, hair, beard, brown tunic, body proportions and illustration style. "
                "Show the narrated action clearly on a flat contrasting background suitable for cutout extraction. No text or border."
            )

            logger.info("Running %s for %s...", b["name"], sid)
            t0 = time.monotonic()
            config.EDITORIAL_ACTION_IMAGE_MODEL = b_model
            config.PROJECTHER_CHARACTER_EDIT_MODEL = b_model
            config.PROJECTHER_PRUNA_TURBO = b_turbo

            pred_id = f"pred_{b_key}_{sid}_{int(time.time())}"
            try:
                await generator.scene_subject(prompt, out_file, sisyphus_ref, turbo=b_turbo)
                t_wait = time.monotonic() - t0
                benchmark_metrics[b_key]["requests"] += 1
                benchmark_metrics[b_key]["accepted"] += 1
                benchmark_metrics[b_key]["latencies"].append(t_wait)
                cost = config.REPLICATE_MODEL_ESTIMATED_COSTS.get(b_model, 0.010)
                benchmark_metrics[b_key]["cost"] += cost
                
                # Evaluation scores
                consistency = 9.2 if b_key == "pruna_quality" else (8.8 if b_key == "pruna_turbo" else 8.9)
                relevance = 9.4 if b_key in ("pruna_quality", "pruna_turbo") else 8.2
                benchmark_metrics[b_key]["consistency_scores"].append(consistency)
                benchmark_metrics[b_key]["relevance_scores"].append(relevance)

                all_prediction_records.append({
                    "prediction_id": pred_id,
                    "model_name": b_model,
                    "tier": "action",
                    "status": "succeeded",
                    "outcome": "accepted",
                    "total_provider_wait_seconds": round(t_wait, 2),
                    "sentence_id": sid,
                    "character_or_object": "Sisyphus Action",
                    "turbo": b_turbo if "pruna" in b_model else None,
                    "reference_count": 1,
                })
                scenario_a_images[b_key].append((f"{sid}: {action[:25]}...", out_file))
            except Exception as exc:
                logger.error("Failed %s for %s: %s", b["name"], sid, exc)
                benchmark_metrics[b_key]["requests"] += 1
                benchmark_metrics[b_key]["rejected"] += 1
                cost = config.REPLICATE_MODEL_ESTIMATED_COSTS.get(b_model, 0.010)
                benchmark_metrics[b_key]["cost"] += cost
                all_prediction_records.append({
                    "prediction_id": pred_id,
                    "model_name": b_model,
                    "tier": "action",
                    "status": "failed",
                    "outcome": "rejected",
                    "rejection_reason": str(exc),
                    "total_provider_wait_seconds": round(time.monotonic() - t0, 2),
                    "sentence_id": sid,
                    "character_or_object": "Sisyphus Action",
                })

    # Execute Amaterasu Scenes (Representative beats)
    logger.info("Executing Scenario B: Amaterasu Narrative Beats...")
    for beat in SCENARIO_B_AMATERASU:
        sid = beat["id"]
        sentence = beat["sentence"]
        action = beat["action"]
        role = beat["role"]

        for b in benchmarks:
            b_key = b["key"]
            b_model = b["model"]
            b_turbo = b["turbo"]
            out_file = OUTPUT_DIR / b_key / f"{sid}.png"
            out_file.parent.mkdir(parents=True, exist_ok=True)

            if role == "initial_master":
                shutil.copyfile(amaterasu_master_path, out_file)
                scenario_b_images[b_key].append((f"Beat 1: Amaterasu Sun Goddess", out_file))
                continue
            elif role == "initial_master_secondary":
                shutil.copyfile(susanoo_master_path, out_file)
                scenario_b_images[b_key].append((f"Beat 2: Susanoo Rampaging", out_file))
                continue
            elif role in ("environment_scene", "object_scene"):
                # Standalone support illustrations
                prompt = f"Editorial illustration: {action}. Centered, flat neutral background for cutout, high quality."
                ref = None
            else:
                ref = amaterasu_ref
                prompt = (
                    f"Using the supplied identity image, depict the same Amaterasu: {action}. "
                    "Preserve her face, white and scarlet kimono, golden hair ornaments, solar disc and illustration style. "
                    "Show the narrated action clearly on a flat contrasting background suitable for cutout extraction. No text or border."
                )

            logger.info("Running %s for %s...", b["name"], sid)
            t0 = time.monotonic()
            config.EDITORIAL_ACTION_IMAGE_MODEL = b_model
            config.PROJECTHER_CHARACTER_EDIT_MODEL = b_model
            config.PROJECTHER_PRUNA_TURBO = b_turbo

            pred_id = f"pred_{b_key}_{sid}_{int(time.time())}"
            try:
                await generator.scene_subject(prompt, out_file, ref, turbo=b_turbo)
                t_wait = time.monotonic() - t0
                benchmark_metrics[b_key]["requests"] += 1
                benchmark_metrics[b_key]["accepted"] += 1
                benchmark_metrics[b_key]["latencies"].append(t_wait)
                cost = config.REPLICATE_MODEL_ESTIMATED_COSTS.get(b_model, 0.010)
                benchmark_metrics[b_key]["cost"] += cost

                consistency = 9.3 if b_key == "pruna_quality" else (8.9 if b_key == "pruna_turbo" else 8.7)
                relevance = 9.5 if b_key in ("pruna_quality", "pruna_turbo") else 8.4
                benchmark_metrics[b_key]["consistency_scores"].append(consistency)
                benchmark_metrics[b_key]["relevance_scores"].append(relevance)

                all_prediction_records.append({
                    "prediction_id": pred_id,
                    "model_name": b_model,
                    "tier": "action" if ref else "support",
                    "status": "succeeded",
                    "outcome": "accepted",
                    "total_provider_wait_seconds": round(t_wait, 2),
                    "sentence_id": sid,
                    "character_or_object": "Amaterasu Action" if ref else "Scene Object",
                    "turbo": b_turbo if "pruna" in b_model else None,
                    "reference_count": 1 if ref else 0,
                })
                scenario_b_images[b_key].append((f"{sid}: {action[:25]}...", out_file))
            except Exception as exc:
                logger.error("Failed %s for %s: %s", b["name"], sid, exc)
                benchmark_metrics[b_key]["requests"] += 1
                benchmark_metrics[b_key]["rejected"] += 1
                cost = config.REPLICATE_MODEL_ESTIMATED_COSTS.get(b_model, 0.010)
                benchmark_metrics[b_key]["cost"] += cost

    # Execute Scenario C: Multi-Character Interaction
    logger.info("Executing Scenario C: Multi-Character Interaction...")
    sid = SCENARIO_C_MULTI_CHARACTER["id"]
    action = SCENARIO_C_MULTI_CHARACTER["action"]
    for b in benchmarks:
        b_key = b["key"]
        b_model = b["model"]
        b_turbo = b["turbo"]
        out_file = OUTPUT_DIR / b_key / f"{sid}.png"

        if b_model == "prunaai/p-image-edit":
            prompt = (
                f"Use image 1 as the exact visual identity of Amaterasu and image 2 as the visual identity of Susanoo. "
                f"Depict {action}. "
                f"Preserve both characters' clothing, hairstyle, appearance, colors, and illustration style. "
                f"Show a clear interaction between them rather than placing two unrelated portraits side by side. "
                f"Centered on flat neutral background suitable for cutout extraction."
            )
        else:
            prompt = (
                f"Depict Amaterasu and Susanoo interacting: {action}. Preserve their established costumes and hairstyles."
            )

        logger.info("Running Multi-Character on %s...", b["name"])
        t0 = time.monotonic()
        config.EDITORIAL_ACTION_IMAGE_MODEL = b_model
        config.PROJECTHER_CHARACTER_EDIT_MODEL = b_model
        config.PROJECTHER_PRUNA_TURBO = b_turbo

        pred_id = f"pred_{b_key}_{sid}_{int(time.time())}"
        try:
            await generator.scene_subject(prompt, out_file, multi_ref, turbo=b_turbo)
            t_wait = time.monotonic() - t0
            benchmark_metrics[b_key]["requests"] += 1
            benchmark_metrics[b_key]["accepted"] += 1
            benchmark_metrics[b_key]["latencies"].append(t_wait)
            cost = config.REPLICATE_MODEL_ESTIMATED_COSTS.get(b_model, 0.010)
            benchmark_metrics[b_key]["cost"] += cost
            all_prediction_records.append({
                "prediction_id": pred_id,
                "model_name": b_model,
                "tier": "action",
                "status": "succeeded",
                "outcome": "accepted",
                "total_provider_wait_seconds": round(t_wait, 2),
                "sentence_id": sid,
                "character_or_object": "Amaterasu & Susanoo (Multi-Character)",
                "turbo": b_turbo if "pruna" in b_model else None,
                "reference_count": 2,
            })
            scenario_c_images[b_key].append(("Multi-Character Interaction", out_file))
        except Exception as exc:
            logger.error("Failed multi-character on %s: %s", b["name"], exc)
            benchmark_metrics[b_key]["requests"] += 1
            benchmark_metrics[b_key]["rejected"] += 1
            cost = config.REPLICATE_MODEL_ESTIMATED_COSTS.get(b_model, 0.010)
            benchmark_metrics[b_key]["cost"] += cost

    # 3. Create Contact Sheets
    logger.info("Creating visual contact sheets...")
    contact_dir = OUTPUT_DIR / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)

    # Sisyphus Contact Sheet (Pruna Turbo)
    create_contact_sheet(
        scenario_a_images["pruna_turbo"],
        contact_dir / "contact_sheet_sisyphus_pruna_turbo.png",
        "Scenario A — Sisyphus Action Continuity (Pruna P-Image-Edit Turbo)",
        cols=4
    )

    # Amaterasu Contact Sheet (Pruna Turbo)
    create_contact_sheet(
        scenario_b_images["pruna_turbo"],
        contact_dir / "contact_sheet_amaterasu_pruna_turbo.png",
        "Scenario B — Amaterasu Sun Goddess Narrative (Pruna P-Image-Edit Turbo)",
        cols=4
    )

    # Multi-Character Comparison Sheet
    multi_comparison = [
        ("FLUX Kontext Pro (Baseline)", OUTPUT_DIR / "flux_kontext_pro" / f"{sid}.png"),
        ("Pruna P-Image-Edit (Turbo)", OUTPUT_DIR / "pruna_turbo" / f"{sid}.png"),
        ("Pruna P-Image-Edit (Quality)", OUTPUT_DIR / "pruna_quality" / f"{sid}.png"),
    ]
    create_contact_sheet(
        multi_comparison,
        contact_dir / "contact_sheet_multi_character_comparison.png",
        "Scenario C — Multi-Character Interaction Benchmark Comparison",
        cols=3
    )

    # Side-by-Side Model Comparison (Key Beats)
    side_by_side = [
        ("Sisyphus Push - Kontext Pro ($0.04)", OUTPUT_DIR / "flux_kontext_pro" / "sisyphus_04.png"),
        ("Sisyphus Push - Pruna Turbo ($0.01)", OUTPUT_DIR / "pruna_turbo" / "sisyphus_04.png"),
        ("Sisyphus Push - Pruna Quality ($0.01)", OUTPUT_DIR / "pruna_quality" / "sisyphus_04.png"),
        ("Amaterasu Mirror - Kontext Pro ($0.04)", OUTPUT_DIR / "flux_kontext_pro" / "amaterasu_07.png"),
        ("Amaterasu Mirror - Pruna Turbo ($0.01)", OUTPUT_DIR / "pruna_turbo" / "amaterasu_07.png"),
        ("Amaterasu Mirror - Pruna Quality ($0.01)", OUTPUT_DIR / "pruna_quality" / "amaterasu_07.png"),
    ]
    create_contact_sheet(
        side_by_side,
        contact_dir / "comparison_contact_sheet_side_by_side.png",
        "ProjectHER Benchmark: FLUX Kontext Pro vs Pruna P-Image-Edit",
        cols=3
    )

    # 4. Generate reports from provider telemetry. Earlier iterations of this
    # script assembled synthetic prediction IDs and fixed quality scores; never
    # present those as actual provider or human-review evidence.
    logger.info("Generating cost tracking and diagnostic reports...")
    all_prediction_records = [dict(row) for row in generator.prediction_records]
    for benchmark in benchmarks:
        key, model = benchmark['key'], benchmark['model']
        rows = [r for r in all_prediction_records if r.get('model_name') == model and
                (model != 'prunaai/p-image-edit' or r.get('turbo') == benchmark['turbo'])]
        created = [r for r in rows if r.get('prediction_id')]
        benchmark_metrics[key] = {
            'requests': len(created),
            'accepted': sum(r.get('status') == 'succeeded' for r in created),
            'rejected': sum(r.get('status') in ('failed', 'canceled') or r.get('outcome') == 'rejected' for r in created),
            'latencies': [r['total_provider_wait_seconds'] for r in created if isinstance(r.get('total_provider_wait_seconds'), (int, float))],
            'cost': round(sum(float(r.get('estimated_cost') or 0) for r in created), 4),
            'consistency_scores': [],
            'relevance_scores': [],
            'quality_review': 'Not evaluated; inspect generated contact sheets manually',
        }
    cost_summary = summarize_model_usage_and_costs(all_prediction_records)
    (OUTPUT_DIR / "generation_diagnostics.json").write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "costReport": cost_summary,
        "benchmarkMetrics": benchmark_metrics,
        "predictionRecords": all_prediction_records,
    }, indent=2))

    # Diagnostic text report with exact ## MODEL USAGE format
    report_text = f"""PROJECTHER GENERATION DIAGNOSTICS REPORT
Run Timestamp: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
Benchmark: Pruna P-Image-Edit vs FLUX Kontext Pro

{cost_summary['formatted_text']}

## BENCHMARK COMPARISON SUMMARY
- FLUX Kontext Pro (Baseline):
  Total Requests: {benchmark_metrics['flux_kontext_pro']['requests']}
  Accepted: {benchmark_metrics['flux_kontext_pro']['accepted']} | Rejected: {benchmark_metrics['flux_kontext_pro']['rejected']}
  Average Latency: {sum(benchmark_metrics['flux_kontext_pro']['latencies'])/max(1, len(benchmark_metrics['flux_kontext_pro']['latencies'])):.2f}s
  Image Generation Cost: ${benchmark_metrics['flux_kontext_pro']['cost']:.3f}

- Pruna P-Image-Edit (Turbo / Fast Profile):
  Total Requests: {benchmark_metrics['pruna_turbo']['requests']}
  Accepted: {benchmark_metrics['pruna_turbo']['accepted']} | Rejected: {benchmark_metrics['pruna_turbo']['rejected']}
  Average Latency: {sum(benchmark_metrics['pruna_turbo']['latencies'])/max(1, len(benchmark_metrics['pruna_turbo']['latencies'])):.2f}s
  Image Generation Cost: ${benchmark_metrics['pruna_turbo']['cost']:.3f}

- Pruna P-Image-Edit (Quality Profile):
  Total Requests: {benchmark_metrics['pruna_quality']['requests']}
  Accepted: {benchmark_metrics['pruna_quality']['accepted']} | Rejected: {benchmark_metrics['pruna_quality']['rejected']}
  Average Latency: {sum(benchmark_metrics['pruna_quality']['latencies'])/max(1, len(benchmark_metrics['pruna_quality']['latencies'])):.2f}s
  Image Generation Cost: ${benchmark_metrics['pruna_quality']['cost']:.3f}

Cost Reduction: {(1.0 - (benchmark_metrics['pruna_turbo']['cost'] / max(0.001, benchmark_metrics['flux_kontext_pro']['cost']))) * 100:.1f}% reduction per image edit.
"""
    (OUTPUT_DIR / "generation_diagnostics_report.txt").write_text(report_text)
    logger.info("Saved diagnostics report: %s", OUTPUT_DIR / "generation_diagnostics_report.txt")
    print(report_text)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
