"""Reproducible offline integration proof, with synthetic images and speech.

Uses real input orchestration, acquisition, alignment, timeline and optionally
Remotion. This is NOT evidence of live image relevance or voice quality.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import config
from tests.news_fixtures import FixtureLLM,FixtureTTS
from tests.test_sentence_storyboard import script_for,STORIES,fixture_planner,review
from agent.editorial.pipeline import run_editorial
from agent.cutout_processor import CutoutProcessor
from agent.news_models import NewsError


class Generator:
    def __init__(self,fail_primary=False):self.fail_primary=fail_primary
    async def scene_subject(self,prompt,path,reference=None):
        if self.fail_primary and 'Visual focus: Sisyphus pushed a boulder uphill.' in prompt:
            raise NewsError('Injected mid-story primary image failure')
        seed=int(hashlib.sha256(prompt.encode()).hexdigest()[:8],16)
        im=Image.new('RGBA',(1024,1024));draw=ImageDraw.Draw(im)
        draw.polygon([(240,240),(760,270),(seed%280+360,780)],fill=(seed%200+30,110,180,255))
        draw.ellipse((330,360,520,550),fill=(220,seed%180+40,80,255));im.save(path)
        return 'fixture:synthetic'
    subject=scene_subject
    real_subject=scene_subject
    action_subject=scene_subject


def run(output,render_video=False,fail_primary=False):
    script=script_for(STORIES[0])
    for i,sentence in enumerate(script.sentences):sentence.claim_ids=[f'c{i+1}']
    account='Fictional account: '+script.narration
    class LLM(FixtureLLM):
        def __call__(self,instruction,data):
            if instruction.startswith('Plan one genuinely'):return fixture_planner(instruction,data)
            return super().__call__(instruction,data)
    def render_manifest(m,path,event=None,trace=None):
        from agent.editorial.render import stage
        stage(m,output)
        return path,{'verification':'render not executed; staged manifest only'}
    from contextlib import nullcontext
    with patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',output/'cache'),patch.object(config,'PERF_DIAGNOSTICS',True),patch('agent.editorial.vision.VisualReview',return_value=review),patch('agent.editorial.pipeline.render',side_effect=render_manifest) if not render_video else nullcontext(),patch('agent.editorial.pipeline.run') if not render_video else nullcontext():
        result=run_editorial(account,output_dir=output,source_policy='supplied',target_duration=0,
            llm=LLM(account,script),tts_provider='edge_tts',tts_engine=FixtureTTS(),image_generator=Generator(fail_primary),
            processor=CutoutProcessor(backend='none'),music=False)
    evidence={'verification':'OFFLINE FIXTURE: synthetic shapes, word pulses and mocked semantic/visual review. No live quality claim.',
        'success':result.success,'errors':result.errors,'processing_seconds':result.processing_time,
        'video_rendered':render_video and result.success,'injected_primary_failure':fail_primary,'sentence_quality':(result.news_details or {}).get('sentence_quality')}
    (output/'verification.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('output/sentence_primary_fixture'));p.add_argument('--render',action='store_true');p.add_argument('--fail-primary',action='store_true');args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    result=run(args.output,args.render,args.fail_primary)
    raise SystemExit(0 if result.success else 1)
