"""Mandatory verification tests for ProjectHER video generation pipeline.

Test 1 — Bhasmasura story (action prioritization, continuity, prominent composition, label filtering)
Test 2 — Image-generation failure (halfway failure recovers gracefully via fallback hierarchy to playable output)
Test 3 — Image validation rejection (bounded retries without fatal crash)
Test 4 — Regression (prominent single-hero layouts, hierarchical 3-cutouts, label filtering, subtitles)
"""
import copy
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw

from agent.news_models import Entity, Sentence, Script, NewsError
from agent.editorial import sentence_storyboard as sb
from agent.editorial.assets import acquire
from agent.editorial.models import Word, Section, Bounds
from agent.editorial.planner import build
from agent.editorial.director import VisualSettings, composition_bounds, should_render_label
from agent.editorial.reference import layout as ref_layout, choreograph as ref_choreograph
import config


def create_dummy_wav(path, duration_seconds=3.0):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        num_frames = round(duration_seconds * 16000)
        wav.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * 220 * i / 16000))) for i in range(num_frames)))


def make_bhasmasura_script():
    e_bhasma = Entity(id='bhasmasura', name='Bhasmasura', kind='person', identity='fictional', description='A formidable asura demon with dark muscular build and fierce countenance')
    e_shiva = Entity(id='shiva', name='Lord Shiva', kind='person', identity='fictional', description='The great ascetic deity with matted hair, crescent moon, and trident')
    e_vishnu = Entity(id='vishnu', name='Lord Vishnu', kind='person', identity='fictional', description='The supreme preserver deity draped in golden garments')
    e_mohini = Entity(id='mohini', name='Mohini', kind='person', identity='fictional', description='The enchanting celestial dancer in vibrant silk robes with graceful mudras')

    sentences_data = [
        ('s1', 'Bhasmasura prayed intensely to Shiva on Mount Kailash.', ['bhasmasura', 'shiva']),
        ('s2', 'Shiva granted him the deadly boon that anyone he touched would burn to ashes.', ['shiva', 'bhasmasura']),
        ('s3', 'Shiva fled in terror as Bhasmasura pursued him across the cosmos.', ['shiva', 'bhasmasura']),
        ('s4', 'Vishnu transformed into the enchanting dancer Mohini to intervene.', ['vishnu', 'mohini']),
        ('s5', 'Mohini challenged him to copy every intricate step of her dance.', ['mohini', 'bhasmasura']),
        ('s6', 'Bhasmasura placed his hand on his head to copy her final pose.', ['bhasmasura']),
        ('s7', 'In that exact second Bhasmasura turned into ashes by his own touch.', ['bhasmasura']),
    ]
    ss = [Sentence(id=sid, text=text, claim_ids=['c'], entity_ids=eids, phrase=' '.join(text.split()[:4]), role='development') for sid, text, eids in sentences_data]
    return Script(
        summary='The Legend of Bhasmasura',
        narration=' '.join(s.text for s in ss),
        sentences=ss,
        entities=[e_bhasma, e_shiva, e_vishnu, e_mohini]
    )


def bhasmasura_action_planner(instruction, data):
    """Action-oriented visual concepts depicting narrative events rather than inanimate props."""
    concepts = [
        dict(
            sentence_id='s1',
            candidates=[dict(
                subject='Bhasmasura performing penance before Shiva',
                action='kneeling and praying deeply before the meditating deity',
                important_objects=[],
                setting='Mount Kailash',
                emotion='devotional',
                state_change='seeking boon',
                visual_focus='Bhasmasura praying to Shiva',
                description='Bhasmasura performing deep penance on Mount Kailash before the seated Lord Shiva.',
                identity_ids=['bhasmasura', 'shiva'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
        dict(
            sentence_id='s2',
            candidates=[dict(
                subject='Shiva bestowing boon upon Bhasmasura',
                action='raising blessing hand while granting the fiery boon',
                important_objects=[],
                setting='Mount Kailash',
                emotion='benevolent',
                state_change='boon granted',
                visual_focus='Shiva granting boon to Bhasmasura',
                description='Lord Shiva extending his right palm in benediction, bestowing the touch-to-ash boon upon Bhasmasura.',
                identity_ids=['shiva', 'bhasmasura'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
        dict(
            sentence_id='s3',
            candidates=[dict(
                subject='Shiva visibly fleeing from pursuing Bhasmasura',
                action='leaping swiftly away as the demon reaches forward aggressively',
                important_objects=[],
                setting='cosmic sky',
                emotion='fear and urgency',
                state_change='pursuit begins',
                visual_focus='Shiva fleeing with Bhasmasura in pursuit',
                description='Lord Shiva in swift motion fleeing across the cosmic sky as Bhasmasura aggressively chases him.',
                identity_ids=['shiva', 'bhasmasura'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
        dict(
            sentence_id='s4',
            candidates=[dict(
                subject='Vishnu transforming into the celestial dancer Mohini',
                action='divine mystical transformation from four-armed deity into enchanting dancer',
                important_objects=[],
                setting='ethereal glade',
                emotion='mystical allure',
                state_change='transformation complete',
                visual_focus='Vishnu transforming into Mohini',
                description='Lord Vishnu visibly undergoing divine metamorphosis into the celestial enchantress Mohini with silk veils.',
                identity_ids=['vishnu', 'mohini'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
        dict(
            sentence_id='s5',
            candidates=[dict(
                subject='Mohini dancing gracefully while Bhasmasura imitates her movements',
                action='Mohini striking an intricate dance posture while Bhasmasura mirrors her posture',
                important_objects=[],
                setting='temple courtyard',
                emotion='captivation',
                state_change='demon entrapped in dance',
                visual_focus='Mohini leading dance and Bhasmasura copying',
                description='Mohini in dynamic classical dance pose with Bhasmasura awkwardly copying her dance movements.',
                identity_ids=['mohini', 'bhasmasura'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
        dict(
            sentence_id='s6',
            candidates=[dict(
                subject='Bhasmasura copying Mohini hand-on-head gesture',
                action='Bhasmasura raising his hand and placing it squarely atop his own crown',
                important_objects=[],
                setting='courtyard center',
                emotion='unaware concentration',
                state_change='deadly gesture triggered',
                visual_focus='Bhasmasura placing palm on own head',
                description='Bhasmasura raising his right palm and resting it directly upon his own head to copy Mohini.',
                identity_ids=['bhasmasura'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
        dict(
            sentence_id='s7',
            candidates=[dict(
                subject='Bhasmasura visibly transforming into ashes and flame',
                action='demon body dissolving into swirling grey ash, smoke and embers',
                important_objects=[],
                setting='ground',
                emotion='dissolution and destruction',
                state_change='total destruction',
                visual_focus='Bhasmasura turning into ash',
                description='Bhasmasura dramatically disintegrating into smoke and embers as his body turns into ash.',
                identity_ids=['bhasmasura'],
                secondary_ids=[],
                relevance=0.98, narrative_importance=0.95, novelty=0.9, readability=0.92
            )]
        ),
    ]
    return {'sentences': concepts}


class MockImageGenerator:
    """Simulates reliable image generation for testing."""
    def __init__(self, fail_on_prompts=None, fail_count=0):
        self.fail_on_prompts = fail_on_prompts or []
        self.fail_count = fail_count
        self.attempts = 0
        self.prediction_records = []

    async def subject(self, prompt, path):
        return await self.scene_subject(prompt, path)

    async def scene_subject(self, prompt, path, reference=None):
        self.attempts += 1
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if any(bad in prompt for bad in self.fail_on_prompts):
            self.prediction_records.append({'target_path': str(path), 'status': 'failed', 'error': 'Simulated provider error'})
            raise NewsError('Simulated provider generation failure', 'provider_unavailable')
        # Render a simple distinguishable image
        im = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        draw.ellipse((50, 50, 350, 350), fill=(200, 160, 60, 255))
        draw.text((60, 60), prompt[:30], fill=(0, 0, 0, 255))
        im.save(path)
        rec = {'target_path': str(path), 'status': 'succeeded', 'totalPredictionSeconds': 0.1, 'admissionWaitSeconds': 0.05}
        self.prediction_records.append(rec)
        return 'fixture:mock_flux'

    action_subject = scene_subject
    real_subject = scene_subject


class MockProcessor:
    version = 'mock_cutout_v2'
    def process(self, source, dest, **kwargs):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(source).convert('RGBA')
        im.save(dest)
        return {}, 'mock_processor'


def reliable_review(instruction, data, paths):
    """Reliable review that approves action visuals and flags non-action props."""
    return dict(
        relevant=True,
        actionCorrect=True,
        objectsCorrect=True,
        portraitSubstitution=False,
        problems=[],
        subjectMatch=True,
        usable=True,
        geometricPlaceholder=False,
        contextAppropriate=True,
        subjectConfidence=0.96,
        recognizable=True,
        sameClothingOrFur=True,
        distinct=True,
        duplicate_pairs=[],
        uncertain=False
    )


class MandatoryVerificationTests(unittest.TestCase):
    def setUp(self):
        # These cases exercise explicit strict-mode rejection. Delivery-mode
        # preservation is covered by test_image_delivery_recovery.
        mode=patch.object(config,'IMAGE_FAILURE_POLICY','strict')
        mode.start();self.addCleanup(mode.stop)

    """Verifies all mandatory test requirements."""

    def test_mandatory_1_bhasmasura_action_visual_storytelling(self):
        """Test 1: Verify action-over-keywords, character continuity, prominent layout, and clean labels."""
        script = make_bhasmasura_script()
        planned, _ = sb.plan(script, None, bhasmasura_action_planner, {})
        storyboard = planned.sentence_storyboard
        self.assertEqual(len(storyboard), 7)

        # A. Prioritize ACTION over KEYWORDS: verify each scene depicts the actual narrative event
        # s1: Penance before Shiva (not prayer beads)
        self.assertEqual(storyboard[0]['primary_subject_type'], 'person')
        self.assertIn('bhasmasura', storyboard[0]['continuity_references'])
        self.assertIn('shiva', storyboard[0]['continuity_references'])
        self.assertNotIn('prayer beads', storyboard[0]['image_generation_prompt'].lower())

        # s2: Boon granted
        self.assertIn('shiva', storyboard[1]['continuity_references'])

        # s3: Shiva fleeing from Bhasmasura (not conch shell)
        self.assertEqual(storyboard[2]['primary_subject_type'], 'person')
        self.assertIn('shiva', storyboard[2]['continuity_references'])
        self.assertIn('bhasmasura', storyboard[2]['continuity_references'])
        self.assertNotIn('conch shell', storyboard[2]['image_generation_prompt'].lower())

        # s4: Vishnu transforming into Mohini (not ankle bells)
        self.assertEqual(storyboard[3]['primary_subject_type'], 'person')
        self.assertIn('vishnu', storyboard[3]['continuity_references'])
        self.assertIn('mohini', storyboard[3]['continuity_references'])
        self.assertNotIn('ankle bells', storyboard[3]['image_generation_prompt'].lower())

        # s5: Dance imitation (not wooden clappers)
        self.assertEqual(storyboard[4]['primary_subject_type'], 'person')
        self.assertIn('mohini', storyboard[4]['continuity_references'])
        self.assertIn('bhasmasura', storyboard[4]['continuity_references'])
        self.assertNotIn('wooden dance clappers', storyboard[4]['image_generation_prompt'].lower())

        # s6: Hand on head gesture (not stone hand statue)
        self.assertEqual(storyboard[5]['primary_subject_type'], 'person')
        self.assertIn('bhasmasura', storyboard[5]['continuity_references'])
        self.assertNotIn('stone statue', storyboard[5]['image_generation_prompt'].lower())

        # s7: Turning into ashes (visible dissolution of character)
        self.assertEqual(storyboard[6]['primary_subject_type'], 'person')
        self.assertIn('bhasmasura', storyboard[6]['continuity_references'])

        # B. Composition & Bounds: Verify single hero visual gets prominent geometry (720x720)
        single_bounds = composition_bounds(['scene-s1'], 'focus', {'scene-s1': 'person'})
        self.assertGreaterEqual(single_bounds['scene-s1'].w, 720)
        self.assertGreaterEqual(single_bounds['scene-s1'].h, 700)

        # C. Label suppression: Verify unwanted catalog labels are filtered out while proper names remain
        self.assertFalse(should_render_label(Entity(id='scene-s5', name='A pair of wooden dance clappers', kind='object', description='An object')))
        self.assertFalse(should_render_label(Entity(id='scene-s6', name='A stone statue of a hand', kind='object', description='An object')))
        self.assertFalse(should_render_label(Entity(id='scene-s7', name='A pile of fine grey ash', kind='object', description='An object')))
        self.assertFalse(should_render_label(Entity(id='scene-s1', name='Bhasmasura praying to Shiva', kind='person', description='A character')))

        # Proper names should be preserved
        self.assertTrue(should_render_label(Entity(id='shiva', name='Lord Shiva', kind='person', description='A deity')))
        self.assertTrue(should_render_label(Entity(id='bhasmasura', name='Bhasmasura', kind='person', description='A demon')))
        self.assertTrue(should_render_label(Entity(id='mohini', name='Mohini', kind='person', description='An enchantress')))

    def test_mandatory_2_image_generation_failure_halfway_recovery(self):
        """Test 2: Simulate failure of mandatory image halfway through; pipeline must recover via fallback."""
        script = make_bhasmasura_script()
        planned, _ = sb.plan(script, None, bhasmasura_action_planner, {})

        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            # Make the generator fail on sentence 4 ("Vishnu transformed into Mohini")
            failing_generator = MockImageGenerator(fail_on_prompts=['Mohini'])
            diag = {}
            with patch.object(config, 'NEWS_IDENTITY_IMAGE_CACHE', root / 'cache'):
                entities, assets = acquire(
                    planned,
                    root / 'assets',
                    image_generator=failing_generator,
                    processor=MockProcessor(),
                    visual_review=reliable_review,
                    diagnostics=diag
                )

            # Verification:
            # 1. Pipeline did NOT abort with NewsError!
            self.assertGreaterEqual(len(assets), 7)
            # 2. Check the failed asset in diagnostics: marked degraded with fallbackMethod
            acq_assets = diag['assetAcquisition']['assets']
            failed_records = [r for r in acq_assets if r.get('degraded')]
            self.assertGreater(len(failed_records), 0)
            self.assertTrue(any('typography_fallback' in r.get('fallbackMethod', '') or 'reused' in r.get('fallbackMethod', '') for r in failed_records))

            # 3. Asset validation reports acceptancePassed=True and fullyCompliant=False
            val = sb.validate_assets(planned, assets, diag['assetAcquisition'], reliable_review)
            self.assertTrue(val['acceptancePassed'])
            self.assertFalse(val['fullyCompliant'])
            self.assertIn('s4', val['degradedSentences'])

            # 4. Verify playable timeline build completes
            words = []
            sections = []
            now = 0.0
            for s in planned.sentences:
                w_start = now
                s_words = []
                for tok in s.text.split():
                    wid = f'w_{len(words)}'
                    w = Word(id=wid, sectionId=s.id, text=tok, start=now, end=now + 0.3, provenance='provider', confidence=1.0)
                    words.append(w)
                    s_words.append(wid)
                    now += 0.3
                sections.append(Section(id=s.id, text=s.text, start=w_start, end=now, wordIds=s_words))

            audio_path = root / 'narration.wav'
            create_dummy_wav(audio_path, now)

            manifest = build(
                planned, words, sections, entities, assets, audio_path, root, 'fixture', {},
                direction=sb.direction(planned), visual_settings=VisualSettings()
            )
            self.assertIsNotNone(manifest)
            self.assertGreaterEqual(len(manifest.beats), 7)

    def test_mandatory_3_seedream_validation_rejection_requires_review_without_regeneration(self):
        """Test 3: Seedream rejection stops with a review requirement and no repeat generation."""
        script = make_bhasmasura_script()
        planned, _ = sb.plan(script, None, bhasmasura_action_planner, {})

        def rejecting_review(instruction, data, paths):
            # Reject relevance on sentence primary review
            if 'Validate this isolated transparent foreground cutout' in instruction or 'actual narrated event' in instruction or 'action visibility review' in instruction:
                return dict(relevant=False, actionCorrect=False, objectsCorrect=False, problems=['Simulated relevance rejection'])
            return reliable_review(instruction, data, paths)

        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            generator = MockImageGenerator()
            diag = {}
            with patch.object(config, 'PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK', False), patch.object(config, 'NEWS_IDENTITY_IMAGE_CACHE', root / 'cache'):
                with self.assertRaisesRegex(NewsError,'regeneration prohibited'):
                    acquire(planned,root/'assets',image_generator=generator,processor=MockProcessor(),visual_review=rejecting_review,diagnostics=diag)
            rejected=[r for r in diag['assetAcquisition']['assets'] if r.get('route')=='needs_review_seedream']
            self.assertTrue(rejected)
            self.assertTrue(all(r.get('attemptCount')==1 for r in rejected))
            self.assertTrue(all(len(r.get('requests',[]))==1 for r in rejected))
            self.assertTrue(all('fallbackMethod' not in r for r in rejected))

    def test_mandatory_4_regression_compositions_and_labels(self):
        """Test 4: Regression coverage for prominent compositions, hierarchical 3-cutouts, and label filtering."""
        # 1. composition_bounds: 1 visual should be prominent (720x720)
        b1 = composition_bounds(['hero'], 'focus', {'hero': 'person'})
        self.assertGreaterEqual(b1['hero'].w, 720)
        self.assertGreaterEqual(b1['hero'].h, 700)

        # 2. composition_bounds: 3 visuals should be hierarchical (center hero elevated and prominent)
        b3 = composition_bounds(['hero', 'sec1', 'sec2'], 'comparison', {'hero': 'person', 'sec1': 'object', 'sec2': 'object'})
        # Hero is central and elevated
        self.assertGreater(b3['hero'].w, b3['sec1'].w)
        self.assertGreater(b3['hero'].h, b3['sec1'].h)
        self.assertLess(b3['hero'].y, b3['sec1'].y)  # hero is elevated above bottom row

        # 3. reference_editorial layout bounds
        ref_b1, _ = ref_layout('hero-object', [type('Visual', (), {'id': 'v1', 'assetId': 'a1'})()], {'a1': type('Asset', (), {'role': 'portrait'})()})
        _, targets1 = ref_layout('final-reveal', [type('Visual', (), {'id': 'v1', 'assetId': 'a1'})()], {'a1': type('Asset', (), {'role': 'portrait'})()})
        self.assertGreaterEqual(targets1['v1'].w, 760)

        # 4. should_render_label rules
        # Suppress long/generic object descriptions
        self.assertFalse(should_render_label(Entity(id='o1', name='A pair of wooden dance clappers', kind='object', description='An object')))
        self.assertFalse(should_render_label(Entity(id='o2', name='A stone statue of a hand', kind='object', description='An object')))
        self.assertFalse(should_render_label(Entity(id='o3', name='The brass ceremonial bell', kind='object', description='An object')))
        self.assertFalse(should_render_label(Entity(id='scene-action-1', name='Shiva fleeing from demon', kind='person', description='An action')))

        # Retain clean short names
        self.assertTrue(should_render_label(Entity(id='p1', name='Lord Shiva', kind='person', description='A deity')))
        self.assertTrue(should_render_label(Entity(id='p2', name='Bhasmasura', kind='person', description='A demon')))
        self.assertTrue(should_render_label(Entity(id='p3', name='Mohini', kind='person', description='An enchantress')))
        self.assertTrue(should_render_label(Entity(id='pl1', name='Mount Kailash', kind='place', description='A sacred mountain')))


if __name__ == '__main__':
    unittest.main()
