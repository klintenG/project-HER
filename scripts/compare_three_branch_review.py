"""Extract genuine encoded frames by semantic event, never equal timestamps."""
import argparse
import io
import json
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw

EVENTS=[
 ('opening','hook',[1,1,None]),
 ('setup','ruled',[12,12,2]),
 ('chest','opening',[22,22,11]),
 ('trap_river','disposal',[28,28,16]),
 ('search','search',[34,34,20]),
 ('scattering','scattering',[41,41,25]),
 ('revival','restoration',[51,51,35]),
 ('underworld','underworld',[58,60,41]),
 ('horus','confrontation',[65,66,46]),
 ('resolution','resolution',[71,72,None]),
 ('outro','outro',[None,76,50])]


def frame(video,at):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(max(0,at)),'-i',str(video),
        '-frames:v','1','-vf','scale=270:480','-f','image2pipe','-vcodec','png','-'])
    return Image.open(io.BytesIO(data)).convert('RGB')


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--references',type=Path,default=Path('/Users/klinten/Downloads/ProjectHER_Three_Branch_Codex_Review_Package'))
    args=p.parse_args();out=args.job/'visual_evidence';out.mkdir(parents=True,exist_ok=True)
    m=json.loads((args.job/'editorial_manifest.json').read_text())
    plan=json.loads((args.job/'narrative_beat_plan.json').read_text())
    sources=[args.references/f'working-branch-{i}.mp4' for i in (1,2,3)]+[args.video]
    words=m['words'];records=[]
    for name,kind,times in EVENTS:
        beat=next((b for b in plan['beats'] if b.get('verb')==kind),None)
        if beat:at=beat['start_ms']/1000+.25
        elif kind=='outro':at=m['durationInFrames']/30+1.7
        elif kind=='resolution':
            section=next((s for s in m['sections'] if 'defeated' in s['text'].lower() and 'seth' in s['text'].lower()),None)
            at=(section['start']+section['end'])/2 if section else None
        elif kind=='hook':at=.7
        else:
            w=next((w for w in words if kind in w['text'].lower()),None);at=w['start']+.5 if w else None
        samples=times+[at];sheet=Image.new('RGB',(1080,520),'#eeeef1');draw=ImageDraw.Draw(sheet)
        for i,(video,t) in enumerate(zip(sources,samples)):
            label=f'Branch {i+1}' if i<3 else 'Integrated'
            draw.text((270*i+8,5),f'{label}: {t:.2f}s' if t is not None else label+': absent',fill='black')
            if t is not None:
                picture=frame(video,t);sheet.paste(picture,(270*i,35));picture.save(out/f'{name}-{i+1}.png')
        sheet.save(out/f'{name}-comparison.jpg',quality=94)
        records.append({'event':name,'sampleSeconds':samples,'evidence':f'{name}-comparison.jpg'})
    # Actual quarter-second samples around each narrated action; crop metrics
    # exclude typography, so text changes cannot masquerade as actor movement.
    import numpy as np
    motions=[]
    for b in plan['beats']:
        if not b['required_action_visible']:continue
        at=b['start_ms']/1000
        a=frame(args.video,at);z=frame(args.video,at+.25)
        crop=(25,135,245,335)
        delta=float(np.abs(np.asarray(a.crop(crop),dtype=float)-np.asarray(z.crop(crop),dtype=float)).mean())
        strip=Image.new('RGB',(1080,520),'#eeeef1');draw=ImageDraw.Draw(strip)
        for i,offset in enumerate((-.25,0,.25,.5)):
            t=max(0,at+offset);draw.text((270*i+8,5),f'{b["verb"]} {t:.2f}s',fill='black')
            strip.paste(frame(args.video,t),(270*i,35))
        strip.save(out/(b['id']+'-motion.jpg'),quality=94)
        motions.append({'beatId':b['id'],'verb':b['verb'],'at':at,'stageMeanDelta025':delta,
            'interpretation':'Pixel activity only; does not prove correct physical action or anatomy.'})
    (out/'sample_audit.json').write_text(json.dumps({'eventComparisons':records,'motionSamples':motions,
        'reviewStatus':'Human full-speed and audio review still required.'},indent=2))
    print(out)

if __name__=='__main__':main()
