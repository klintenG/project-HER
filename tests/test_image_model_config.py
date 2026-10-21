"""The two-model image policy must hold across configuration and request paths."""
import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import config
from agent.ai_visuals import AIImageGenerator
from agent.editorial.images import EditorialImages
from utils.image_models import ADAPTERS, KNOWN_MODELS, ImageModelConfigError, adapter_for, build_input, validate_role


class ImageModelConfigTests(unittest.TestCase):
    def test_allowlist_contains_exactly_two_models(self):
        self.assertEqual(set(KNOWN_MODELS),{'black-forest-labs/flux-schnell','bytedance/seedream-4'})
        self.assertEqual(set(ADAPTERS),{'flux_schnell','seedream'})

    def test_supported_model_specific_schemas(self):
        simple=build_input(config.SIMPLE_IMAGE_MODEL,'portrait',aspect_ratio='3:4')
        self.assertEqual(simple['num_outputs'],1)
        self.assertNotIn('image_input',simple)
        action=build_input(config.ACTION_IMAGE_MODEL,'two people interacting',['one','two'],seed=42)
        self.assertEqual(action['image_input'],['one','two'])
        self.assertEqual(action['max_images'],1)
        self.assertEqual(action['sequential_image_generation'],'disabled')
        self.assertEqual(action['seed'],42)
        self.assertNotIn('negative_prompt',action)
        self.assertNotIn('num_outputs',action)

    def test_unknown_model_cannot_bypass_allowlist_with_adapter(self):
        for adapter in (None,'flux_schnell','seedream'):
            with self.subTest(adapter=adapter),self.assertRaises(ImageModelConfigError):
                adapter_for('vendor/unsupported-image-model',adapter)

    def test_roles_and_references_are_checked(self):
        for role,model in (('continuity',config.SIMPLE_IMAGE_MODEL),('identity',config.ACTION_IMAGE_MODEL)):
            with self.assertRaises(ImageModelConfigError):validate_role(role,model)
        with self.assertRaises(ImageModelConfigError):build_input(config.SIMPLE_IMAGE_MODEL,'edit',['reference'])
        with self.assertRaises(ImageModelConfigError):adapter_for(config.ACTION_IMAGE_MODEL,'flux_schnell')

    def test_startup_rejects_unsupported_canonical_configuration(self):
        for key in ('ACTION_IMAGE_MODEL','CHARACTER_IMAGE_MODEL','OBJECT_IMAGE_MODEL','BACKGROUND_IMAGE_MODEL','SIMPLE_IMAGE_MODEL'):
            env=os.environ.copy();env[key]='vendor/unsupported-image-model'
            result=subprocess.run([sys.executable,'-c','import config'],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Unsupported image model',result.stderr)

    def test_defaults_and_legacy_aliases_cannot_select_other_models(self):
        env=os.environ.copy();env.update(HER_SKIP_DOTENV='1',REPLICATE_MODEL='vendor/unsupported-image-model',PROJECTHER_IMAGE_CONTINUITY_MODEL='vendor/unsupported-image-model',HER_EDITORIAL_EVENT_IMAGE_MODEL='vendor/unsupported-image-model')
        for key in ('CHARACTER_IMAGE_MODEL','OBJECT_IMAGE_MODEL','BACKGROUND_IMAGE_MODEL','SIMPLE_IMAGE_MODEL','ACTION_IMAGE_MODEL'):env.pop(key,None)
        code='import config; print(config.PROJECTHER_IMAGE_IDENTITY_MODEL,config.EDITORIAL_ACTION_IMAGE_MODEL,config.EDITORIAL_EVENT_IMAGE_MODEL,config.REPLICATE_MODEL)'
        result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.split(),['black-forest-labs/flux-schnell','bytedance/seedream-4','bytedance/seedream-4','black-forest-labs/flux-schnell'])

    def test_provider_switching_is_removed(self):
        with self.assertRaises(ImageModelConfigError):AIImageGenerator(provider='unapproved-provider')
        self.assertFalse(hasattr(AIImageGenerator,'_build_fallback_chain'))
        self.assertFalse(hasattr(EditorialImages,'fallback_scene_subject'))
        self.assertFalse(hasattr(EditorialImages,'alternate_scene_subject'))

    def test_attempt_caps_cannot_be_increased_by_environment(self):
        env=os.environ.copy();env.update(PROJECTHER_EVENT_MAX_ATTEMPTS='99',PROJECTHER_IMAGE_EXTRA_ATTEMPTS_PER_EVENT='99',PROJECTHER_IMAGE_SPARE_CALLS='99')
        code='import config; print(config.PROJECTHER_EVENT_MAX_ATTEMPTS,config.PROJECTHER_IMAGE_EXTRA_ATTEMPTS_PER_EVENT,config.PROJECTHER_IMAGE_SPARE_CALLS)'
        result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.split(),['2','1','2'])

    def test_production_action_request_uses_seedream_with_multiple_references(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(config,'REPLICATE_API_TOKEN','offline'):
            root=Path(directory);reference=root/'reference.png';Image.new('RGB',(64,64),'red').save(reference)
            response=MagicMock(status_code=201);response.json.return_value={'id':'prediction123','status':'succeeded','output':['https://example.org/image.png']}
            client=MagicMock(post=AsyncMock(return_value=response))
            context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
            with patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',return_value=(reference.read_bytes(),'https://example.org/image.png')):
                generator=EditorialImages(primary_count=1);generator.admission.wait=AsyncMock()
                asyncio.run(generator.scene_subject('same two characters interacting',root/'scene.png',SimpleNamespace(path=str(reference),paths=[str(reference),str(reference)])))
            self.assertEqual(client.post.await_count,1)
            self.assertIn(config.ACTION_IMAGE_MODEL,client.post.call_args.args[0])
            payload=client.post.call_args.kwargs['json']['input']
            self.assertEqual(len(payload['image_input']),2)
            self.assertEqual(payload['max_images'],1)
            self.assertEqual(generator.prediction_records[0]['estimated_cost'],config.SEEDREAM_ESTIMATED_COST_USD)


if __name__=='__main__':unittest.main()
