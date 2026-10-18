"""Schema and configuration switching regressions; no paid requests."""
import os
import asyncio
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image

import config
from agent.editorial.images import EditorialImages
from agent.news_models import NewsError

from utils.image_models import ImageModelConfigError, adapter_for, build_input, validate_role


class ImageModelConfigTests(unittest.TestCase):
    def test_pruna_schema_and_profiles(self):
        payload = build_input('prunaai/p-image-edit', 'show the character running', ['image-one', 'image-two'], turbo=False, seed=42)
        self.assertEqual(payload['images'], ['image-one', 'image-two'])
        self.assertFalse(payload['turbo'])
        self.assertEqual(payload['seed'], 42)
        self.assertNotIn('input_image', payload)
        self.assertNotIn('output_format', payload)

    def test_kontext_pro_and_dev_switch(self):
        for model in ('black-forest-labs/flux-kontext-pro', 'black-forest-labs/flux-kontext-dev'):
            with self.subTest(model=model):
                payload = build_input(model, 'show the character running', ['image-one'])
                self.assertEqual(payload['input_image'], 'image-one')
                self.assertNotIn('images', payload)
                self.assertEqual(adapter_for(model).name, 'flux_kontext')

    def test_unsupported_and_incompatible_fail_before_request(self):
        with self.assertRaises(ImageModelConfigError):
            validate_role('continuity', 'black-forest-labs/flux-schnell')
        with self.assertRaises(ImageModelConfigError):
            build_input('black-forest-labs/flux-kontext-pro', 'two people', ['one', 'two'])
        with self.assertRaises(ImageModelConfigError):
            adapter_for('unknown/brand-new-model')
        self.assertEqual(adapter_for('vendor/schema-compatible-edit', 'flux_kontext').name, 'flux_kontext')

    def test_environment_switch_without_source_edit(self):
        code = 'import config; print(config.PROJECTHER_IMAGE_CONTINUITY_MODEL, config.EDITORIAL_ACTION_IMAGE_MODEL, config.NEWS_REFERENCE_IMAGE_MODEL)'
        for model in ('prunaai/p-image-edit', 'black-forest-labs/flux-kontext-pro', 'black-forest-labs/flux-kontext-dev'):
            with self.subTest(model=model):
                env = os.environ.copy()
                env['PROJECTHER_IMAGE_CONTINUITY_MODEL'] = model
                result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip().split(), [model] * 3)

    def test_bad_environment_fails_at_startup(self):
        env = os.environ.copy()
        env['PROJECTHER_IMAGE_CONTINUITY_MODEL'] = 'unknown/unsupported'
        result = subprocess.run([sys.executable, '-c', 'import config'], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsupported image model', result.stderr)

    def test_production_request_switches_pruna_kontext_pro_and_dev(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.png'
            Image.new('RGB', (64, 64), 'red').save(reference)
            response = MagicMock(status_code=201)
            response.json.return_value = {'id': 'prediction123', 'status': 'succeeded', 'output': 'https://replicate.delivery/image.png'}
            client = MagicMock(post=AsyncMock(return_value=response))
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=client)
            context.__aexit__ = AsyncMock(return_value=False)
            for model, reference_key in (('prunaai/p-image-edit','images'),
                                         ('black-forest-labs/flux-kontext-pro','input_image'),
                                         ('black-forest-labs/flux-kontext-dev','input_image')):
                with self.subTest(model=model), patch.object(config, 'EDITORIAL_ACTION_IMAGE_MODEL', model), \
                     patch('httpx.AsyncClient', return_value=context), \
                     patch('agent.news_research.fetch', return_value=(reference.read_bytes(), 'https://replicate.delivery/image.png')):
                    generator = EditorialImages(primary_count=1)
                    asyncio.run(generator.scene_subject('the same person running', Path(directory) / 'scene.png', SimpleNamespace(path=str(reference))))
                    self.assertIn(model, client.post.call_args.args[0])
                    payload = client.post.call_args.kwargs['json']['input']
                    self.assertIn(reference_key, payload)
                    self.assertEqual(generator.prediction_records[0]['actual_model'], model)

    def test_premium_fallback_disabled_before_request(self):
        with patch.object(config, 'PROJECTHER_PREMIUM_FALLBACK_ENABLED', False):
            generator = EditorialImages(primary_count=1)
            with patch.object(generator, '_prediction', new_callable=AsyncMock) as request:
                with self.assertRaises(NewsError):
                    asyncio.run(generator.fallback_scene_subject('scene', Path('unused.png'), SimpleNamespace(path='unused.png')))
                request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
