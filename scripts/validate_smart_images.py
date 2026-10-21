"""Exercise the complete editorial flow with offline providers and REAL video export.

Artwork and audio are synthetic fixtures, visual judgments are mocked. This is
an integration check, not evidence of live model quality or speech alignment.
No external API request or billing is permitted by this script.
"""
import argparse
import io
import json
import sys
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from tests.test_smart_images import sample
from tests.news_fixtures import FixtureTTS, FixtureLLM
from agent.editorial.pipeline import run_editorial
from agent.editorial.images import EditorialImages
from agent.editorial.planner import semantic_plan
import config


class Processor:
    version='offline-alpha-fixture-v1'
    def process(self,raw,cut,**kwargs):
        shutil.copyfile(raw,cut)
        return {'alpha':True},'offline fixture alpha'


def review(*args):
    return dict(relevant=True,actionCorrect=True,objectsCorrect=True,continuityCorrect=True,
        requirementsVisible=True,forbiddenAbsent=True,portraitSubstitution=False,problems=[],
        subjectMatch=True,usable=True,geometricPlaceholder=False,contextAppropriate=True,
        subjectConfidence=.99,sameCharacter=True,sameLikeness=True,singlePerson=True,
        bodyPreserved=True,confidence=.99)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='output/smart_images_validation');args=parser.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'assets'/'image_prediction_ledger.json').exists():
        raise RuntimeError('Use a fresh output directory; Seedream reservations must not be resubmitted')
    source,_,_,reply=sample()
    for i,sentence in enumerate(source.sentences):sentence.claim_ids=[f'c{i+1}']
    class LLM(FixtureLLM):
        def __call__(self,instruction,data):
            if instruction.startswith('Plan the semantic events'):return reply
            if instruction.startswith('Audit event'):return {'accepted':True}
            if instruction.startswith('Propose'):return {'beats':semantic_plan(source)}
            return super().__call__(instruction,data)
    llm=LLM(account='Fictional account: '+source.narration,script=source)
    # Each mock prediction has distinct fixture geometry, so duplicate-image
    # diagnostics still exercise their real implementation.
    artwork={}
    async def post(url,**kwargs):
        n=len(artwork);im=Image.new('RGBA',(512,640));d=ImageDraw.Draw(im)
        color=('#8a6547','#657b8a','#9a7549','#6d7b66')[n%4]
        d.ellipse((160+n*3,45,340,225+n*2),fill=color)
        d.polygon([(180,215),(335,215),(460-n*13,530),(80+n*11,575)],fill=color)
        d.line((60,80+n*22,445,170+n*24),fill='#e1bd69',width=10+n)
        # Distinct seeded texture prevents perceptual-hash collisions as fixtures grow.
        import random
        rng=random.Random(n)
        for row in range(8):
            for col in range(8):
                x=100+col*38;y=240+row*38
                shade=rng.randrange(30,230)
                d.rectangle((x,y,x+35,y+35),fill=(shade,shade,shade,255))
        buffer=io.BytesIO();im.save(buffer,format='PNG');artwork[f'https://offline.invalid/{n}.png']=buffer.getvalue()
        response=MagicMock(status_code=201);response.json.return_value={'id':f'offline{n}','status':'succeeded','output':[f'https://offline.invalid/{n}.png']}
        return response
    client=MagicMock();client.post=AsyncMock(side_effect=post)
    context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
    # Fail closed: all image downloads use only in-memory offline fixtures.
    def fetch(url,*args,**kwargs):return artwork[url],url
    with patch.object(config,'EVENT_STORYBOARD_ENABLED',True),patch.object(config,'SENTENCE_PRIMARY_VISUALS',True),patch.object(config,'REPLICATE_API_TOKEN','offline-token'),patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',out/'cache'),patch.object(config,'EDITORIAL_IMAGE_MIN_INTERVAL',0),patch.object(config,'PARALLEL_ASSET_PIPELINE_V2',False),patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',side_effect=fetch),patch('agent.editorial.vision.VisualReview',return_value=review):
        result=run_editorial('Fictional account: '+source.narration,output_dir=out,source_policy='supplied',llm=llm,tts_provider='edge_tts',tts_engine=FixtureTTS(),image_generator=EditorialImages(primary_count=14),processor=Processor(),asset_mode='ai',music=False)
    plan_path=out/'asset_generation_plan.json'
    asset_plan=json.loads(plan_path.read_text()) if plan_path.exists() else {}
    report={'typography_pacing':asset_plan.get('typography_pacing'),'model_counts':{'schnell':asset_plan.get('schnell_count'),'seedream':asset_plan.get('seedream_count')},'scope':'Full orchestration and real Remotion/FFmpeg export; offline synthetic artwork/audio and mocked visual review. Live generation quality unverified.',
        'success':result.success,'errors':result.errors,'video':str(result.video_path),
        'paid_requests':0,'mock_prediction_requests':client.post.await_count}
    (out/'validation_result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    if not result.success:raise SystemExit(1)


if __name__=='__main__':main()
