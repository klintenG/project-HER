"""Render a cached reference-editorial timeline through the production renderer.

No story, image or speech provider requests are made. Useful for branding/cover
regressions; this does not approve the cached story or schedule a publication.
"""
import argparse
import json
import uuid
from pathlib import Path
import config
from agent.editorial.models import Timeline
from agent.editorial.render import render
from automation.video_quality import ThumbnailComposer


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--props',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    data=json.loads(args.props.read_text());data.pop('branding',None)
    for row in [*data['assets'],*data['audio']]:row['path']=str((config.BASE_DIR/'remotion/public'/row['path']).resolve())
    for key in ('semibold','bold'):data['fonts'][key]=str((config.BASE_DIR/'remotion/public'/data['fonts'][key]).resolve())
    data['generationId']='editorial_'+uuid.uuid4().hex
    data['diagnostics']['autopilotHook']='The pirate who ruled the seas'
    timeline=Timeline.model_validate(data);args.output.mkdir(parents=True,exist_ok=True)
    video,stats=render(timeline,args.output/'editorial.mp4')
    cover=ThumbnailComposer().compose(video,{'script':{'hook_text':data['diagnostics']['autopilotHook']}})
    report={'fixture_only':True,'video':str(video),'cover':cover,'audio_and_export':stats,
            'providers_called':0,'publication_attempted':False}
    (args.output/'render-validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'video':str(video),'cover':cover['path'],'fixture_only':True,'providers_called':0}))


if __name__=='__main__':main()
