import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent.editorial import assets
from agent.news_models import Entity
from agent.editorial.visuals import EditorialScript, EditorialSentence
from PIL import Image
import config

class CriticalEventFallbackTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.root.mkdir(parents=True, exist_ok=True)
        cache_patch=patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',self.root/'cache')
        cache_patch.start();self.addCleanup(cache_patch.stop)
        img_path = self.root / 'ref.png'
        Image.new('RGBA', (100, 100), (255, 0, 0, 255)).save(img_path)
        self.ref_path = str(img_path)

    def test_p0_cannot_use_portrait_even_when_legacy_fallback_enabled(self):
        text = "Sisyphus chained Thanatos."
        sisyphus = Entity(id='sisyphus', name='Sisyphus', kind='person', identity='fictional', description='Ancient king')
        event_entity = Entity(id='event-001', name='Sisyphus chaining Thanatos', kind='person', identity='fictional', description='Chaining action')
        
        script = EditorialScript(
            summary="Sisyphus myth",
            narration=text,
            entities=[sisyphus, event_entity],
            sentences=[EditorialSentence(id='s1', text=text, phrase='Chained Thanatos', role='development', claim_ids=['c1'], entity_ids=['sisyphus', 'event-001'])],
            sentence_storyboard=[{
                'sentence_id': 's1',
                'primary_entity_id': 'event-001',
                'narration_text': text,
                'visual_focus': 'Chaining Thanatos',
                'description': 'Chaining Thanatos',
                'event_contract': 'v1',
                'event_generation_prompt': 'Sisyphus actively chaining Thanatos',
                'continuity_revision': 'rev1',
                'story_hash': 'hash1',
                'criticality': 'P0',
                'continuity_references': ['sisyphus'],
                'actor_ids': ['sisyphus'],
                'must_show': ['Sisyphus fastening chains on Thanatos'],
                'must_not_show': []
            }]
        )
        
        from agent.news_models import NewsError
        async def fail(*args, **kwargs):
            raise NewsError("HTTP 429 Provider Throttled")
        
        generator = MagicMock()
        generator.replicate_token = 'token'
        generator.event_scene_subject = fail
        generator.subject = fail
        generator.identity_subject = fail
        
        # Reused character master asset for sisyphus
        master = MagicMock()
        master.entityId = 'sisyphus'
        master.source = 'replicate:black-forest-labs/flux-schnell'
        master.license = 'Generated illustration'
        master.attribution = 'flux-schnell'
        master.path = self.ref_path

        with patch.object(config, 'PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK', True), patch.object(config,'IMAGE_FAILURE_POLICY','strict'):
            with self.assertRaisesRegex(NewsError,'portrait/label substitution prohibited'):
                assets.acquire(script,self.root/'job',image_generator=generator,existing=[master])

    def test_p0_critical_event_raises_when_fallback_disabled(self):
        text = "Sisyphus chained Thanatos."
        sisyphus = Entity(id='sisyphus', name='Sisyphus', kind='person', identity='fictional', description='Ancient king')
        event_entity = Entity(id='event-001', name='Sisyphus chaining Thanatos', kind='person', identity='fictional', description='Chaining action')
        
        script = EditorialScript(
            summary="Sisyphus myth",
            narration=text,
            entities=[sisyphus, event_entity],
            sentences=[EditorialSentence(id='s1', text=text, phrase='Chained Thanatos', role='development', claim_ids=['c1'], entity_ids=['sisyphus', 'event-001'])],
            sentence_storyboard=[{
                'sentence_id': 's1',
                'primary_entity_id': 'event-001',
                'narration_text': text,
                'visual_focus': 'Chaining Thanatos',
                'description': 'Chaining Thanatos',
                'event_contract': 'v1',
                'event_generation_prompt': 'Sisyphus actively chaining Thanatos',
                'continuity_revision': 'rev1',
                'story_hash': 'hash1',
                'criticality': 'P0',
                'continuity_references': ['sisyphus'],
                'actor_ids': ['sisyphus'],
                'must_show': ['Sisyphus fastening chains on Thanatos'],
                'must_not_show': []
            }]
        )
        
        from agent.news_models import NewsError
        async def fail(*args, **kwargs):
            raise NewsError("HTTP 429 Provider Throttled")
        
        generator = MagicMock()
        generator.replicate_token = 'token'
        generator.event_scene_subject = fail
        generator.subject = fail
        generator.identity_subject = fail
        
        master = MagicMock()
        master.entityId = 'sisyphus'
        master.source = 'replicate:black-forest-labs/flux-schnell'
        master.license = 'Generated illustration'
        master.attribution = 'flux-schnell'
        master.path = self.ref_path

        with patch.object(config, 'PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK', False), patch.object(config,'IMAGE_FAILURE_POLICY','strict'):
            with self.assertRaises(NewsError) as cm:
                assets.acquire(
                    script,
                    self.root / 'job_strict',
                    image_generator=generator,
                    existing=[master]
                )
            self.assertIn("Critical event needs review", str(cm.exception))

    def test_seedream_rejection_blocks_even_with_legacy_fallback_flag(self):
        text = "Sisyphus gesturing defiantly toward Zeus."
        sisyphus = Entity(id='sisyphus', name='Sisyphus', kind='person', identity='fictional', description='Ancient king')
        event_entity = Entity(id='scene-001', name='Sisyphus defying Zeus', kind='person', identity='fictional', description='Defying Zeus')

        script = EditorialScript(
            summary="Sisyphus myth",
            narration=text,
            entities=[sisyphus, event_entity],
            sentences=[EditorialSentence(id='s1', text=text, phrase='Defied Zeus', role='development', claim_ids=['c1'], entity_ids=['sisyphus', 'scene-001'])],
            sentence_storyboard=[{
                'sentence_id': 's1',
                'primary_entity_id': 'scene-001',
                'narration_text': text,
                'visual_focus': 'Sisyphus gesturing defiantly',
                'description': 'Sisyphus gesturing defiantly toward Zeus',
                'event_contract': 'v1',
                'continuity_revision': 'rev1',
                'story_hash': 'hash1',
                'event_generation_prompt': 'Sisyphus standing defiantly before Zeus',
                'criticality': 'P0',
                'continuity_references': ['sisyphus'],
                'actor_ids': ['sisyphus'],
                'must_show': ['Sisyphus gesturing defiantly'],
                'must_not_show': []
            }]
        )

        master = MagicMock()
        master.entityId = 'sisyphus'
        master.source = 'replicate:black-forest-labs/flux-schnell'
        master.license = 'Generated illustration'
        master.attribution = 'flux-schnell'
        master.path = self.ref_path

        seedream_calls = 0
        schnell_calls = 0
        class SeedreamGenerator:
            replicate_token = 'token'
            prediction_records = []
            async def event_scene_subject(self, prompt, path, reference=None):
                nonlocal seedream_calls
                seedream_calls += 1
                Image.new('RGBA', (100, 100), (0, 255, 0, 255)).save(path)
                return 'replicate:bytedance/seedream-4'
            scene_subject = event_scene_subject
            action_subject = event_scene_subject
            async def subject(self, prompt, path):
                nonlocal schnell_calls
                schnell_calls += 1
                Image.new('RGBA', (100, 100), (0, 255, 0, 255)).save(path)
                return 'replicate:black-forest-labs/flux-schnell'

        generator = SeedreamGenerator()

        class DummyProcessor:
            version = 'test'
            def process(self, src, dst, **kwargs):
                Image.new('RGBA', (100, 100), (0, 255, 0, 255)).save(dst)
                return {}, 'test'

        def review_func(instruction, data, paths):
            # Let character master pass, but fail the sentence action primary review
            if 'established character' in instruction or 'subject' in data and data['subject'] == 'Sisyphus':
                return dict(subjectMatch=True, usable=True, singlePerson=True, sameLikeness=True, problems=[])
            return dict(relevant=False, actionCorrect=False, objectsCorrect=False,
                        portraitSubstitution=True, problems=['Mandatory sentence primary failed relevance review.'])

        diag = {}
        with patch.object(config, 'PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK', True), patch.object(config,'IMAGE_FAILURE_POLICY','strict'):
            from agent.news_models import NewsError
            with self.assertRaisesRegex(NewsError,'regeneration prohibited'):
                assets.acquire(script,self.root/'job_seedream_fallback',image_generator=generator,
                    processor=DummyProcessor(),visual_review=review_func,existing=[master],diagnostics=diag)
            self.assertEqual(seedream_calls,1)
            acq_record=next(r for r in diag['assetAcquisition']['assets'] if r['entityId']=='scene-001')
            self.assertTrue(acq_record.get('degraded'))
            self.assertEqual(acq_record['route'],'blocked_critical_event')

    def test_master_identity_asset_uses_best_unverified_fallback_under_smart_plan(self):
        thanatos = Entity(id='thanatos', name='Thanatos', kind='person', identity='fictional', description='A dark, ethereal figure representing death')
        script = EditorialScript(
            summary="Sisyphus myth",
            narration="Death came for Sisyphus.",
            entities=[thanatos],
            sentences=[EditorialSentence(id='s1', text="Death came for Sisyphus.", phrase='Death came', role='development', claim_ids=['c1'], entity_ids=['thanatos'])],
            sentence_storyboard=[]
        )
        # Attach a smart plan
        script.asset_generation_plan = {
            'status': 'ready',
            'assets': [{'id': 'thanatos', 'mode': 'schnell', 'model': 'black-forest-labs/flux-schnell', 'reference_ids': []}]
        }

        class SchnellGenerator:
            replicate_token = 'token'
            prediction_records = []
            async def subject(self, prompt, path):
                Image.new('RGBA', (100, 100), (30, 30, 30, 255)).save(path)
                return 'replicate:black-forest-labs/flux-schnell'

        class DummyProcessor:
            version = 'test'
            def process(self, src, dst, **kwargs):
                Image.new('RGBA', (100, 100), (30, 30, 30, 255)).save(dst)
                return {}, 'test'

        # Review returns subjectMatch=True, but usable=False (e.g. flagging silhouette)
        def review_func(instruction, data, paths):
            return dict(subjectMatch=True, usable=False, geometricPlaceholder=False,
                        contextAppropriate=True, subjectConfidence=0.8,
                        problems=['The image is a silhouette, violates no black silhouettes.'])

        diag = {}
        # Under smart plan, retries will fail strict check, but best_unverified should be used without crashing
        entities, acquired = assets.acquire(
            script,
            self.root / 'job_thanatos_fallback',
            image_generator=SchnellGenerator(),
            processor=DummyProcessor(),
            visual_review=review_func,
            diagnostics=diag
        )
        self.assertEqual(len(acquired), 1)
        thanatos_asset = acquired[0]
        self.assertEqual(thanatos_asset.entityId, 'thanatos')
        self.assertTrue(Path(thanatos_asset.path).is_file())
        acq_record = next(r for r in diag['assetAcquisition']['assets'] if r['entityId'] == 'thanatos')
        self.assertEqual(acq_record.get('route'), 'unavailable_cutout')
        self.assertTrue(acq_record['degraded'])

if __name__ == '__main__':
    unittest.main()
