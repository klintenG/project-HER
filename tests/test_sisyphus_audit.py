"""Acceptance contracts for the full audit, without billable providers."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agent.editorial.quality_artifacts import VisualScenePlan, visual_contract, write, enforce
from agent.news_models import NewsError
from utils.image_models import build_input, ImageModelConfigError
import config


class SisyphusAuditTests(unittest.TestCase):
    def test_portrait_cannot_fulfill_action_interaction_or_reversal(self):
        for kind in ('PHYSICAL_ACTION','INTERACTION','CONSEQUENCE'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                VisualScenePlan(scene_id='event',beat_type=kind,verb='act',required_visible_relationships=['contact'],asset_role='ACTOR_ONLY',scene_asset_id='portrait')

    def test_seedream_schema_embeds_exclusions_and_caps_outputs(self):
        payload=build_input('bytedance/seedream-4','Push huge rock. Exclude wheels.',['ref'],size='4K',enhance_prompt=False)
        self.assertEqual(payload['max_images'],1)
        self.assertEqual(payload['sequential_image_generation'],'disabled')
        self.assertEqual(payload['size'],'4K')
        self.assertFalse(payload['enhance_prompt'])
        self.assertNotIn('negative_prompt',payload)
        with self.assertRaises(ImageModelConfigError):build_input('bytedance/seedream-4','scene',['ref']*11)

    def test_full_story_has_distinct_push_rollback_and_cycle(self):
        from scripts.evaluate_sisyphus import sample
        source,script,_,_=sample()
        self.assertEqual(source.narration,script.narration)
        beats=script.event_plan['beats']
        self.assertEqual(len(beats),12)
        self.assertEqual([b['verb'] for b in beats[-3:]],['push_uphill','roll_downhill','repeat_push'])
        self.assertEqual(len({b['asset_entity_id'] for b in beats[-3:]}),3)
        for b in beats:
            self.assertIn(visual_contract(b).asset_role,('EVENT_ACTION','EVENT_OUTCOME'))
        for b in script.sentence_storyboard[-3:]:
            self.assertIn('boulder',b['event_generation_prompt'])
            self.assertIn('wheel',b['event_generation_prompt'])

    def test_critical_qa_blocks_and_failed_artifacts_remain_reviewable(self):
        with patch.object(config,'RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE',True),self.assertRaises(NewsError):
            enforce({'metrics':{'p0_acceptance_passed':False}})
        with tempfile.TemporaryDirectory() as tmp:
            report=write(tmp,status='failed')
            self.assertEqual(report['status'],'failed')
            self.assertIsNone(report['visual_coverage_percent'])
            for name in ('asset_manifest.json','generation_cost_report.json','quality_report.json'):
                self.assertTrue((Path(tmp)/name).exists())

    def test_fatal_completeness_audit_cannot_become_advisory_success(self):
        from tests.test_event_storyboard import response
        from tests.test_sentence_storyboard import script_for
        from agent.editorial.event_storyboard import plan
        script=script_for(['She pushed the rock.'])
        reply=response(script)
        def llm(instruction,*args):
            return {'accepted':False,'problems':['Missing rollback event']} if instruction.startswith('Audit event') else reply
        with self.assertRaisesRegex(NewsError,'Semantic completeness audit'):
            plan(script,None,llm,{})

    def test_actor_only_asset_fails_even_with_positive_vision_metadata(self):
        from tests.test_event_storyboard import planned
        from agent.editorial.event_storyboard import report
        _,script,_=planned(['She pushed the boulder.'])
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'portrait.png';Image.new('RGB',(80,80),'red').save(path)
            b=script.event_plan['beats'][0]
            asset=SimpleNamespace(entityId=b['asset_entity_id'],id='a',path=str(path),assetRole='ACTOR_ONLY')
            proof=dict(relevant=True,actionCorrect=True,objectsCorrect=True,continuityCorrect=True,requirementsVisible=True,forbiddenAbsent=True,portraitSubstitution=False,problems=[])
            result=report(script,[asset],{'assets':[{'entityId':asset.entityId,'generation':{'sentenceReview':proof}}]},[])
            self.assertEqual(result['beats'][0]['validation_status'],'needs_review')
            self.assertIn('Actor-only',result['beats'][0]['reasons'][0])

if __name__=='__main__':unittest.main()
