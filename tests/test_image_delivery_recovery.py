"""Local delivery keeps paid artwork despite cutout or semantic review failure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import config
from agent.editorial.image_recovery import preserve, usable
from agent.editorial.quality_artifacts import enforce
from agent.editorial.assets import acquire
from agent.news_models import Entity, NewsError
from agent.editorial.visuals import EditorialScript, EditorialSentence


class ImageDeliveryTests(unittest.TestCase):
    def test_failed_cutout_preserves_original_without_a_rectangular_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'original.png';Image.new('RGB',(200,300),'red').save(raw)
            e=Entity(id='action',name='Hero pushing rock',kind='person',identity='fictional',description='Narrated physical action')
            record={};asset=preserve(e,raw,None,root/'prepared','edge clipping',record)
            self.assertTrue(usable(asset.path));self.assertTrue(asset.alpha)
            self.assertIn(record['route'],('unavailable_cutout','saved_scene_cutout','local_segmentation_margin_repair:isnet-general-use','border_connected_neutral_matte'))
            self.assertTrue(record['degraded']);self.assertNotIn('generation',record)
            self.assertTrue(raw.exists())

    def test_quality_warning_delivers_but_strict_mode_still_blocks(self):
        edl={'metrics':{'p0_acceptance_passed':False}}
        with patch.object(config,'IMAGE_FAILURE_POLICY','deliver_with_warnings'),patch.object(config,'RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE',False):enforce(edl)
        with patch.object(config,'IMAGE_FAILURE_POLICY','strict'),self.assertRaises(NewsError):enforce(edl)

    def test_no_readable_image_does_not_invent_compatible_art(self):
        e=Entity(id='action',name='Hero',kind='person',identity='fictional',description='Hero in scene')
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(NewsError,'No decodable image'):preserve(e,None,None,tmp,'missing')

    def test_acquisition_failure_and_resume_use_one_paid_image(self):
        calls=[]
        class Generator:
            async def subject(self,prompt,path,*args,**kwargs):
                calls.append(str(path));Image.new('RGB',(100,140),'green').save(path);return 'replicate:bytedance/seedream-4'
            event_scene_subject=subject;scene_subject=subject;action_subject=subject;identity_subject=subject
        class BrokenProcessor:
            version='fixture-broken-mask'
            def process(self,*args,**kwargs):raise NewsError('Cutout quality failed: touches image edge')
        def reviewer(*args):raise AssertionError('Image review should not be needed after mask failure')
        e=Entity(id='scene',name='Pushing huge rock',kind='person',identity='fictional',description='Hero pushing huge rock uphill')
        text='The hero pushed the rock uphill.'
        row=dict(sentence_id='s0',primary_entity_id=e.id,narration_text=text,visual_focus=text,description=text,event_contract='event-storyboard-v1',event_generation_prompt=text,continuity_revision='one',story_hash='story',criticality='P0',continuity_references=[],actor_ids=[],must_show=[text],must_not_show=[])
        script=EditorialScript(summary='Scene',narration=text,sentences=[EditorialSentence(id='s0',text=text,phrase=text,role='development',claim_ids=['fixture'],entity_ids=['scene'])],entities=[e],sentence_storyboard=[row])
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'IMAGE_FAILURE_POLICY','deliver_with_warnings'),patch.object(config,'PARALLEL_ASSET_PIPELINE_V2',False),patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',Path(tmp)/'cache'):
            root=Path(tmp)/'assets';diag={}
            _,first=acquire(script,root,asset_mode='ai',image_generator=Generator(),processor=BrokenProcessor(),visual_review=reviewer,diagnostics=diag)
            self.assertEqual(len(calls),1)
            self.assertTrue(diag['assetAcquisition']['assets'][0]['degraded'])
            _,second=acquire(script,root,asset_mode='ai',image_generator=Generator(),processor=BrokenProcessor(),visual_review=reviewer)
            self.assertEqual(len(calls),1)
            self.assertTrue(Path(second[0].path).exists())

    def test_identical_app_request_returns_saved_video_without_providers(self):
        from agent.editorial.image_recovery import request_fingerprint
        from agent.editorial.pipeline import run_editorial
        settings=dict(source_policy='auto',tone='informative',language='english',duration=0,voice=None,tts=None,speed='+0%',music=None,music_path='None',subtitles='editorial',asset_mode='auto')
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'OUTPUT_DIR',Path(tmp)),patch.object(config,'IMAGE_FAILURE_POLICY','deliver_with_warnings'):
            prior=Path(tmp)/'editorial_saved';prior.mkdir()
            (prior/'request_checkpoint.json').write_text(json.dumps({'request_key':request_fingerprint('Same story',**settings)}))
            (prior/'visual_plan.json').write_text('{}');(prior/'assets').mkdir()
            (prior/'assets/image_prediction_ledger.json').write_text('[]')
            (prior/'editorial.mp4').write_bytes(b'saved exported video')
            with patch('agent.editorial.pipeline.acquire') as images,patch('agent.news_research.analyze_input') as analyze,patch('agent.editorial.recovery.recover') as recovery,patch('agent.news_audio.probe_duration',return_value=60):
                result=run_editorial('Same story')
            self.assertTrue(result.success,result.errors)
            self.assertEqual(result.video_path,prior/'editorial.mp4')
            images.assert_not_called();analyze.assert_not_called();recovery.assert_not_called()
            self.assertEqual(result.news_details['paid_generation_requests'],0)

if __name__=='__main__':unittest.main()
