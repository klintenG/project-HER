"""Export start/middle/end frame evidence and an inspectable shot contact sheet."""
import argparse
import html
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def export(manifest, video, output):
    m=json.loads(Path(manifest).read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    plan=m['diagnostics'].get('shotDirection',{})
    (out/'shot_plan.json').write_text(json.dumps(plan,indent=2))
    shots=plan.get('shots',[])
    sheet=Image.new('RGB',(720,max(1,len(shots))*470),'#f7f6f2');draw=ImageDraw.Draw(sheet)
    rows=[]
    for i,s in enumerate(shots):
        samples=[s['startFrame'],(s['startFrame']+s['endFrame'])//2,max(s['startFrame'],s['endFrame']-1)]
        images=[]
        for j,f in enumerate(samples):
            image=out/f'{i:02d}-{j}-{f}.jpg'
            subprocess.run(['ffmpeg','-v','error','-y','-ss',str(f/30),'-i',str(video),'-frames:v','1','-vf','scale=216:384',str(image)],check=True)
            sheet.paste(Image.open(image),(j*240,i*470+65));images.append(image.name)
        draw.text((8,i*470+5),f"{s['beatType']} | {s['layoutId']} | {s['startFrame']/30:.2f}-{s['endFrame']/30:.2f}s",fill='#24242a')
        draw.text((8,i*470+24),s['narrationText'][:95],fill='#24242a')
        draw.text((8,i*470+44),' / '.join(t['assetId'] for t in s['objectTracks'])[:90],fill='#24242a')
        rows.append('<article><h2>'+html.escape(s['beatType']+' / '+s['layoutId'])+'</h2><p>'+html.escape(s['narrationText'])+'</p>'+''.join(f'<img width="216" src="{p}">' for p in images)+'<pre>'+html.escape(json.dumps(s,indent=2))+'</pre></article>')
    sheet.save(out/'contact-sheet.jpg')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>ProjectHER shot review</title><style>body{background:#f7f6f2;color:#24242a;font:16px system-ui;max-width:1100px;margin:32px auto}article{margin:24px 0}pre{white-space:pre-wrap}img{margin:8px}</style><h1>ProjectHER editorial motion review</h1><p>Start / middle / end. Semantic action correctness requires human review; motion measurements are diagnostics.</p>'+''.join(rows))
    return out/'index.html'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--video',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(export(a.manifest,a.video,a.output))
