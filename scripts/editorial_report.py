"""Recompute the delivery audit from actual media, alignment and render manifests."""
import json
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.audio import measure,samples
from agent.editorial.models import digest

root=Path('output/reference_editorial_review');root.mkdir(exist_ok=True)
manifest=json.loads(Path('output/reference_editorial_demo/editorial_manifest.json').read_text())
media={}
for name,path in [('reference','enhancements/reference-ai-video.mp4'),('baseline','enhancements/generated-video.mp4'),('editorial','output/reference_editorial_demo/editorial.mp4')]:
    import subprocess
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]))
    media[name]={'path':path,'sha256':digest(path),'audio':measure(path),'metadata':metadata}
boundaries=[]
for s in manifest['sections'][1:]:
    gap=next((x for x in media['editorial']['audio']['silences'] if x['start']<=s['start']<=x['end']),None)
    boundaries.append({'sectionId':s['id'],'sectionStart':s['start'],'measuredGap':gap})
uncertain=[w for w in manifest['words'] if w['confidence']<.5]
# Render visibility is measurable relative to alignment, not independent proof
# of phonetic accuracy. The 3-frame opacity ramp becomes opaque within 100ms.
checks=[]
for text in ('Musk',"Starlink's",'Mukesh','assessments.','license','unclear.'):
    w=next(w for w in manifest['words'] if w['text']==text)
    first=max(0,math.floor(w['start']*30));opaque=math.ceil(w['start']*30+2)
    checks.append({'word':text,'alignedStart':w['start'],'firstRevealFrame':first,'fullyOpaqueFrame':opaque,'opaqueDelayMilliseconds':(opaque/30-w['start'])*1000,'confidence':w['confidence']})
report={'baselineMatchesRecoveredRun':digest('enhancements/generated-video.mp4')==digest('output/news_af1a95199a7245c687819d15b7c56e3a/news.mp4'),
    'media':media,'boundaryGaps':boundaries,'wordRevealChecks':checks,'lowConfidenceWords':uncertain,
    'limits':['No acoustic listening or phone/speaker audition is possible through this session.','Token probabilities are not calibrated temporal accuracy. Independent 100ms phonetic verification is not claimed.','The reference ASR transcript has proper-name errors; its timing is separate from visually observed cues.']}
(root/'delivery-audit.json').write_text(json.dumps(report,indent=2))
# Waveform evidence, with actual word intervals over three useful excerpts.
data=samples('output/reference_editorial_demo/master.wav');sr=48000
canvas=Image.new('RGB',(1600,810),'#f0f0f3');d=ImageDraw.Draw(canvas)
for row,(start,end) in enumerate([(0,5.3),(9.1,11),(25.4,29.05)]):
    y=row*270;d.text((18,y+8),f'Master waveform {start:.2f}–{end:.2f}s · words from known-script DTW',fill='#222222')
    for x in range(1560):
        a=int((start+(end-start)*x/1560)*sr);b=max(a+1,int((start+(end-start)*(x+1)/1560)*sr));part=data[a:b]
        if len(part):
            hi=float(np.max(part));lo=float(np.min(part));d.line((x+20,y+132-hi*90,x+20,y+132-lo*90),fill='#575b66')
    for w in manifest['words']:
        if start<=w['start']<end:
            x=20+(w['start']-start)/(end-start)*1560
            d.line((x,y+42,x,y+224),fill='#b08065' if w['confidence']<.5 else '#858595')
            d.text((x+2,y+226),w['text'],fill='#33333a')
canvas.save(root/'aligned-waveform.png')
print(json.dumps({'boundaryGaps':[round(b['measuredGap']['duration'],3) if b['measuredGap'] else None for b in boundaries],
 'loudness':{k:(v['audio']['integratedLUFS'],v['audio']['truePeakDBTP'],v['metadata']['format']['duration']) for k,v in media.items()},'uncertainWords':len(uncertain)},indent=2))
