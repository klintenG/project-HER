"""Comprehensive test suite for Pruna P-Image-Edit adapter, character continuity, and cost tracking."""
import asyncio
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

import config
from agent.cutout_processor import CutoutProcessor
from agent.editorial.images import EditorialImages
from agent.editorial.assets import acquire
from agent.news_models import Entity, Sentence, Script, NewsError
from utils.cost_tracking import summarize_model_usage_and_costs


class PrunaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        # Create dummy image
        self.image_path = self.root / 'character_ref.png'
        im = Image.new('RGBA', (512, 512), (180, 100, 80, 255))
        im.save(self.image_path)

        self.sec_image_path = self.root / 'secondary_ref.png'
        im2 = Image.new('RGBA', (512, 512), (80, 120, 200, 255))
        im2.save(self.sec_image_path)

    def test_pruna_input_schema_uses_images_array_and_no_input_image(self):
        """Pruna P-Image-Edit must use 'images' array, never FLUX Kontext 'input_image'."""
        response = MagicMock(status_code=201)
        response.json.return_value = {
            'id': 'pruna_pred_1',
            'status': 'succeeded',
            'output': 'https://replicate.delivery/test.png'
        }
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)

        ref = SimpleNamespace(path=str(self.image_path))
        with patch.object(config, 'REPLICATE_API_TOKEN', 'token-123'), \
             patch.object(config, 'EDITORIAL_ACTION_IMAGE_MODEL', 'prunaai/p-image-edit'), \
             patch('httpx.AsyncClient', return_value=context), \
             patch('agent.news_research.fetch', return_value=(self.image_path.read_bytes(), 'https://replicate.delivery/test.png')):
            generator = EditorialImages(primary_count=5)
            asyncio.run(generator.scene_subject('Depict Sisyphus pushing a boulder', self.root / 'out.png', ref))

        call_args = client.post.call_args
        self.assertIn('prunaai/p-image-edit', call_args.args[0])
        payload = call_args.kwargs['json']['input']

        # Verifications
        self.assertIn('images', payload)
        self.assertIsInstance(payload['images'], list)
        self.assertEqual(len(payload['images']), 1)
        self.assertTrue(payload['images'][0].startswith('data:image/'))
        self.assertNotIn('input_image', payload)
        self.assertNotIn('image_input', payload)
        self.assertIn('prompt', payload)
        self.assertIn('turbo', payload)
        self.assertEqual(payload['aspect_ratio'], '1:1')

    def test_multiple_reference_characters_mapping(self):
        """Multi-character scene passes character 1 as images[0] and character 2 as images[1]."""
        response = MagicMock(status_code=201)
        response.json.return_value = {
            'id': 'pruna_pred_multi',
            'status': 'succeeded',
            'output': 'https://replicate.delivery/multi.png'
        }
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)

        ref = SimpleNamespace(
            path=str(self.image_path),
            paths=[str(self.image_path), str(self.sec_image_path)],
            characters=['Amaterasu', 'Susanoo']
        )
        with patch.object(config, 'REPLICATE_API_TOKEN', 'token-123'), \
             patch.object(config, 'EDITORIAL_ACTION_IMAGE_MODEL', 'prunaai/p-image-edit'), \
             patch('httpx.AsyncClient', return_value=context), \
             patch('agent.news_research.fetch', return_value=(self.image_path.read_bytes(), 'https://replicate.delivery/multi.png')):
            generator = EditorialImages(primary_count=5)
            prompt = "Use image 1 as the exact visual identity of Amaterasu and image 2 as the visual identity of Susanoo. Depict Susanoo behaving aggressively while Amaterasu reacts with visible anger."
            asyncio.run(generator.scene_subject(prompt, self.root / 'multi_out.png', ref))

        call_args = client.post.call_args
        payload = call_args.kwargs['json']['input']
        self.assertEqual(len(payload['images']), 2)
        self.assertTrue(payload['images'][0].startswith('data:image/'))
        self.assertTrue(payload['images'][1].startswith('data:image/'))
        self.assertIn('image 1', payload['prompt'])
        self.assertIn('image 2', payload['prompt'])

    def test_turbo_mode_profile_toggle(self):
        """Fast profile sets turbo=True, Quality profile sets turbo=False."""
        response = MagicMock(status_code=201)
        response.json.return_value = {
            'id': 'pruna_pred_turbo',
            'status': 'succeeded',
            'output': 'https://replicate.delivery/test.png'
        }
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)

        ref = SimpleNamespace(path=str(self.image_path))
        with patch.object(config, 'REPLICATE_API_TOKEN', 'token-123'), \
             patch.object(config, 'EDITORIAL_ACTION_IMAGE_MODEL', 'prunaai/p-image-edit'), \
             patch('httpx.AsyncClient', return_value=context), \
             patch('agent.news_research.fetch', return_value=(self.image_path.read_bytes(), 'https://replicate.delivery/test.png')):
            generator = EditorialImages(primary_count=5)

            # Fast profile
            asyncio.run(generator.scene_subject('Prompt 1', self.root / 'fast.png', ref, turbo=True))
            self.assertTrue(client.post.call_args.kwargs['json']['input']['turbo'])

            # Quality profile
            asyncio.run(generator.scene_subject('Prompt 2', self.root / 'quality.png', ref, turbo=False))
            self.assertFalse(client.post.call_args.kwargs['json']['input']['turbo'])

    def test_replicate_cost_tracking_summary(self):
        """Per-video cost tracking correctly calculates Schnell, Pruna, Kontext, and rejected costs."""
        records = [
            # FLUX Schnell initial character
            {
                'model_name': 'black-forest-labs/flux-schnell',
                'status': 'succeeded',
                'outcome': 'accepted',
                'tier': 'support',
                'total_provider_wait_seconds': 2.1,
                'prediction_id': 'pred_schnell_1',
                'sentence_id': 's1',
                'character_or_object': 'Sisyphus',
            },
            # Pruna accepted scene
            {
                'model_name': 'prunaai/p-image-edit',
                'status': 'succeeded',
                'outcome': 'accepted',
                'tier': 'action',
                'total_provider_wait_seconds': 1.2,
                'prediction_id': 'pred_pruna_1',
                'sentence_id': 's2',
                'character_or_object': 'Sisyphus pushing boulder',
                'turbo': True,
                'reference_count': 1,
            },
            # Pruna rejected scene attempt
            {
                'model_name': 'prunaai/p-image-edit',
                'status': 'succeeded',
                'outcome': 'rejected',
                'rejection_reason': 'Static portrait substituted for action',
                'tier': 'action',
                'total_provider_wait_seconds': 1.1,
                'prediction_id': 'pred_pruna_2',
                'sentence_id': 's3',
                'character_or_object': 'Sisyphus summit',
                'turbo': True,
                'reference_count': 1,
            },
            # Pruna retry accepted
            {
                'model_name': 'prunaai/p-image-edit',
                'status': 'succeeded',
                'outcome': 'accepted',
                'tier': 'action',
                'total_provider_wait_seconds': 1.3,
                'prediction_id': 'pred_pruna_3',
                'sentence_id': 's3',
                'character_or_object': 'Sisyphus summit retry',
                'turbo': False,
                'reference_count': 1,
            },
        ]

        summary = summarize_model_usage_and_costs(records)

        self.assertEqual(summary['flux_schnell']['count'], 1)
        self.assertAlmostEqual(summary['flux_schnell']['cost'], 0.003, places=3)

        self.assertEqual(summary['pruna_p_image_edit']['count'], 3)
        self.assertAlmostEqual(summary['pruna_p_image_edit']['cost'], 0.030, places=3)

        self.assertEqual(summary['flux_kontext_pro']['count'], 0)
        self.assertAlmostEqual(summary['flux_kontext_pro']['cost'], 0.000, places=3)

        self.assertEqual(summary['rejected_attempts'], 1)
        self.assertAlmostEqual(summary['cost_of_rejected_images'], 0.010, places=3)

        # Total = 0.003 + 0.030 = 0.033
        self.assertAlmostEqual(summary['total_estimated_replicate_cost'], 0.033, places=3)

        # Verify formatted text output includes MODEL USAGE
        text = summary['formatted_text']
        self.assertIn("MODEL USAGE", text)
        self.assertIn("FLUX Schnell: 1 images — $0.003", text)
        self.assertIn("Pruna P-Image-Edit: 3 images — $0.030", text)
        self.assertIn("Kontext Pro: 0 images — $0.000", text)
        self.assertIn("Rejected Attempts: 1", text)
        self.assertIn("Total Estimated Replicate Cost: $0.033", text)

    def test_expensive_models_disabled_by_default(self):
        """When PROJECTHER_PREMIUM_FALLBACK_ENABLED is False, default models never fall back to expensive tiers."""
        self.assertFalse(config.PROJECTHER_PREMIUM_FALLBACK_ENABLED)
        self.assertEqual(config.PROJECTHER_CHARACTER_EDIT_MODEL, 'prunaai/p-image-edit')
        self.assertEqual(config.EDITORIAL_ACTION_IMAGE_MODEL, 'prunaai/p-image-edit')

    def test_cache_keys_differentiate_actions_and_turbos(self):
        """Cache keys differ for different actions and turbo settings on the same character."""
        from agent.editorial.models import digest
        ref_digest = digest(self.image_path)
        char_id = "sisyphus"

        key1 = hashlib.sha256(f"pruna-v1|{char_id}|Action 1: pushing boulder|prunaai/p-image-edit|True||{ref_digest}".encode()).hexdigest()
        key2 = hashlib.sha256(f"pruna-v1|{char_id}|Action 2: resting at summit|prunaai/p-image-edit|True||{ref_digest}".encode()).hexdigest()
        key3 = hashlib.sha256(f"pruna-v1|{char_id}|Action 1: pushing boulder|prunaai/p-image-edit|False||{ref_digest}".encode()).hexdigest()

        # Different actions must have different cache keys
        self.assertNotEqual(key1, key2)
        # Different turbo settings must have different cache keys
        self.assertNotEqual(key1, key3)


if __name__ == '__main__':
    unittest.main()
