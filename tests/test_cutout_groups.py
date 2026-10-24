"""Intentional groups must survive segmentation without accepting backdrops."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw
import config
from agent.cutout_processor import CutoutProcessor, mask_statistics
from agent.news_assets import generate_cutouts, subject_prompt
from agent.news_models import Entity, NewsError


def group_image():
    image = Image.new("RGBA", (512, 512))
    draw = ImageDraw.Draw(image)
    for x in (70, 210, 350):
        draw.ellipse((x + 10, 65, x + 70, 125), fill="#b68e73")
        draw.polygon([(x + 10, 120), (x + 70, 120), (x + 80, 310),
                      (x + 60, 440), (x + 40, 320), (x + 20, 440), (x, 310)], fill="#18305a")
    return image


class GroupCutoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cache = patch.object(config, "NEWS_CUTOUT_CACHE", self.root / "cache")
        cache.start()
        self.addCleanup(cache.stop)
        self.team = Entity(id="france", name="France national football team", kind="person",
            description="A group of athletes in dark blue jerseys standing on a field.")

    def test_only_explicit_human_groups_enable_multiple_silhouettes(self):
        self.assertTrue(self.team.is_group)
        for entity in (
            Entity(id="player", name="Team captain", kind="person", description="One soccer player standing still"),
            Entity(id="stadium", name="France football team stadium", kind="building", description="A stadium for players"),
        ):
            self.assertFalse(entity.is_group)
        with self.assertRaisesRegex(NewsError, "detached"):
            mask_statistics(group_image())
        self.assertGreater(mask_statistics(group_image(), allow_group=True)["detached_fraction"], .045)

    def test_group_validation_still_rejects_opaque_clipped_and_rectangular_assets(self):
        clipped = group_image()
        ImageDraw.Draw(clipped).rectangle((0, 200, 80, 300), fill="blue")
        rectangle = Image.new("RGBA", (512, 512))
        ImageDraw.Draw(rectangle).rectangle((60, 60, 450, 450), fill="blue")
        for image in (Image.new("RGBA", (512, 512), "white"), clipped, rectangle):
            with self.subTest(image=image), self.assertRaises(NewsError):
                mask_statistics(image, allow_group=True)

    def test_group_validation_rejects_ground_strips_and_small_stray_components(self):
        ground = group_image()
        ImageDraw.Draw(ground).rectangle((35, 460, 475, 485), fill="green")
        stray = Image.new("RGBA", (512, 512))
        draw = ImageDraw.Draw(stray)
        draw.ellipse((100, 60, 300, 440), fill="blue")
        draw.ellipse((360, 185, 430, 255), fill="green")
        for image in (ground, stray):
            with self.subTest(image=image), self.assertRaisesRegex(NewsError, "detached"):
                mask_statistics(image, allow_group=True)

    def test_allow_bottom_crop_permits_grounded_subject_without_clipping_top_or_sides(self):
        grounded = group_image()
        ImageDraw.Draw(grounded).rectangle((100, 400, 400, 511), fill="#18305a")
        with self.assertRaisesRegex(NewsError, "edge"):
            mask_statistics(grounded, allow_group=True)
        stats = mask_statistics(grounded, allow_group=True, allow_bottom_crop=True)
        self.assertGreater(stats["coverage"], 0.05)
        # Clipping top must still fail even with allow_bottom_crop
        top_clipped = grounded.copy()
        ImageDraw.Draw(top_clipped).rectangle((150, 0, 350, 50), fill="blue")
        with self.assertRaisesRegex(NewsError, "edge"):
            mask_statistics(top_clipped, allow_group=True, allow_bottom_crop=True)
        # Clipping side in upper 55% must still fail even with allow_bottom_crop
        side_clipped = grounded.copy()
        ImageDraw.Draw(side_clipped).rectangle((0, 100, 50, 200), fill="blue")
        with self.assertRaisesRegex(NewsError, "edge"):
            mask_statistics(side_clipped, allow_group=True, allow_bottom_crop=True)

    def test_stray_edge_noise_does_not_falsely_reject_subject(self):
        image = group_image()
        # Add 2 single-pixel noise points on the outer margin
        image.putpixel((0, 0), (200, 200, 200, 100))
        image.putpixel((511, 0), (200, 200, 200, 100))
        stats = mask_statistics(image, allow_group=True)
        self.assertGreater(stats["coverage"], 0.05)

    def test_group_cache_cannot_bypass_single_subject_validation(self):
        source = self.root / "group.png"
        group_image().save(source)
        processor = CutoutProcessor(backend="none", models=[])
        processor.process(source, self.root / "group-cutout.png", allow_group=True)
        processor.process(source, self.root / "group-cached.png", allow_group=True)
        with self.assertRaises(NewsError):
            processor.process(source, self.root / "single-cutout.png")
        self.assertFalse((self.root / "single-cutout.png").exists())

    def test_soccer_group_prompts_override_field_description_and_change_each_retry(self):
        prompts = [subject_prompt(self.team, attempt) for attempt in range(3)]
        self.assertEqual(len(set(prompts)), 3)
        for prompt in prompts:
            for instruction in ("representative people", "Association football (soccer)",
                    "no American football uniforms", "no field, grass, pitch", "No invented badges"):
                self.assertIn(instruction, prompt)

    def test_retry_preserves_raw_attempts_and_group_cutout_reaches_compositor(self):
        from agent.news_compositor import NewsFrames
        from tests.news_fixtures import fixture_manifest
        manifest = fixture_manifest(self.root / "fixture", 540, 960)
        team = self.team.model_copy(update={"id": "mira"})
        manifest.script.entities[0] = team
        prompts = []

        class Generator:
            provider = "fixture"

            async def subject(self, prompt, path):
                prompts.append(prompt)
                image = Image.new("RGBA", (512, 512), "white") if len(prompts) == 1 else group_image()
                image.save(path)
                return self.provider

        with self.assertLogs("agent.news_assets", level="WARNING") as logs:
            assets = generate_cutouts(SimpleNamespace(entities=[team]), self.root / "retries", "fictional",
                generator=Generator(), processor=CutoutProcessor(backend="none", models=[]))
        self.assertEqual(len(prompts), 2)
        self.assertNotEqual(prompts[0], prompts[1])
        self.assertIn("attempt 1/3 failed", logs.output[0])
        self.assertEqual(len(list((self.root / "retries" / "cutouts").glob("*-raw.png"))), 2)
        self.assertIn("attempt-2-raw.png", assets[0].raw_path)
        self.assertEqual(assets[0].fallback, "regenerated after mask QA failure")
        manifest.assets[0] = assets[0]
        self.assertEqual(NewsFrames(manifest).frame(30).shape, (960, 540, 3))

    def test_single_subject_prunes_detached_background_clutter_successfully(self):
        source = self.root / "cluttered.png"
        image = Image.new("RGBA", (512, 512))
        draw = ImageDraw.Draw(image)
        # Dominant centered subject
        draw.ellipse((200, 60, 310, 140), fill="#b68e73")
        draw.polygon([(200, 135), (310, 135), (320, 330), (290, 450), (265, 340), (240, 450), (210, 330)], fill="#18305a")
        # Detached background debris
        draw.rectangle((30, 410, 90, 480), fill="#555555")
        draw.ellipse((420, 80, 470, 130), fill="#444444")
        image.save(source)

        dest = self.root / "cleaned-cutout.png"
        processor = CutoutProcessor(backend="none", models=[])
        stats, method = processor.process(source, dest, allow_group=False)
        self.assertTrue(dest.exists())
        self.assertEqual(stats["detached_fraction"], 0.0)


if __name__ == "__main__":
    unittest.main()
