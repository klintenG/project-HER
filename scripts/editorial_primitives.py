"""Short deterministic studies; no narration, news facts or paid services.

Map outlines are Natural Earth geometry, not generated or invented boundaries.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.models import *
from agent.editorial.audio import write_wave
from agent.editorial.render import render,stage
from agent.news_layout import font_path

def base(name,seconds=4):
    out=Path('output/reference_editorial_primitives')/name;out.mkdir(parents=True,exist_ok=True)
    audio=out/'silence.wav';write_wave(audio,np.zeros(seconds*48000))
    m=dict(generationId='primitive-'+name,contentMode='motion_study',script='',scriptHash=hashlib.sha256(b'').hexdigest(),durationInFrames=seconds*30,
        fonts=Fonts(semibold=str(font_path().resolve()),bold=str(font_path(700).resolve()),version=digest(font_path())+digest(font_path(700))),
        audio=[Audio(path=str(audio.resolve()),duration=seconds,sha256=digest(audio))],words=[],sections=[],entities=[],assets=[],layers=[],events=[],transitions=[],warnings=['Silent motion study; no historical event is asserted.'])
    return out,m

def label(m,id,text,x,y,w,h,size=60):
    m['layers'].append(Layer(id=id,role='heading',startFrame=0,endFrame=m['durationInFrames'],bounds=Bounds(x=x,y=y,w=w,h=h),
        phrase=Phrase(wordIds=[],lines=[],mode='entity_label',size=size,label=text)))

def finish(out,m,template,prepare_only):
    m['beats']=[Beat(id='study',template=template,startFrame=0,endFrame=m['durationInFrames'],sectionIds=[],layerIds=[l.id for l in m['layers']],purpose='Isolated reusable primitive demonstration.')]
    model=Timeline(**m);(out/'editorial_manifest.json').write_text(model.model_dump_json(indent=2));stage(model,out)
    if not prepare_only:render(model,out/(out.name+'.mp4'))
    print(out,flush=True)

def year(prepare_only):
    out,m=base('year-counter')
    label(m,'heading','A year comes into focus',100,420,880,190)
    label(m,'caption','Numeric transition study\nFinal display: 2026',140,1170,800,200,44)
    m['layers'].append(Layer(id='year',role='year',startFrame=0,endFrame=120,bounds=Bounds(x=140,y=790,w=800,h=240),value=2000))
    m['events']=[Event(id='count',type='year_counter',startFrame=24,endFrame=64,targetIds=['year'],fromValue=2000,toValue=2026)]
    finish(out,m,'date_year',prepare_only)

def box(prepare_only):
    out,m=base('object-action')
    label(m,'heading','An object changes state',100,410,880,190)
    label(m,'caption','Open → closed\nPerspective lid action',140,1230,800,200,44)
    m['layers'].append(Layer(id='box',role='box',startFrame=0,endFrame=120,bounds=Bounds(x=270,y=770,w=540,h=430),shadow=True))
    m['events']=[Event(id='close',type='object_action',startFrame=34,endFrame=58,targetIds=['box'],angleFrom=-105,angleTo=0)]
    finish(out,m,'single_subject',prepare_only)

def map_study(prepare_only):
    out,m=base('map-separation',5)
    source=Path('assets/editorial/natural-earth-countries.geojson')
    feature=next(f for f in json.loads(source.read_text())['features'] if f['properties']['ADMIN']=='New Zealand')
    polys=feature['geometry']['coordinates']
    rings=[p[0] for p in polys]
    area=lambda r:abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(r,r[1:])))/2
    rings=sorted(rings,key=area,reverse=True)[:2]
    # The two largest polygon exteriors are the North and South Islands.
    rings.sort(key=lambda r:sum(p[1] for p in r)/len(r),reverse=True)
    xs=[p[0] for r in rings for p in r];ys=[p[1] for r in rings for p in r];c=math.cos(math.radians(sum(ys)/len(ys)))
    minx,maxy=min(xs),max(ys);scale=min(650/((max(xs)-minx)*c),600/(maxy-min(ys)))
    for i,ring in enumerate(rings):
        # Common viewBox retains their factual initial geographic relationship.
        coords=[((x-minx)*c*scale+70,(maxy-y)*scale+40) for x,y in ring]
        d='M'+' L'.join(f'{x:.3f},{y:.3f}' for x,y in coords)+' Z'
        path=out/f'island-{i}.svg';path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 700"><path d="{d}" fill="#8f959f"/></svg>')
        name=['North Island','South Island'][i];aid=f'map-{i}'
        m['assets'].append(Asset(id=aid,entityId='nz',path=str(path.resolve()),originalPath=str(source.resolve()),role='map',subject=name,source='https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson',license='Public domain',attribution='Made with Natural Earth',width=800,height=700,alpha=True,factual=True,confidence=1,preparation='vetted_geometry',sha256=digest(path)))
        m['layers'].append(Layer(id=aid,role='map',entityId='nz',assetId=aid,startFrame=0,endFrame=150,bounds=Bounds(x=140,y=640,w=800,h=700),shadow=True))
    m['entities']=[Entity(id='nz',name='New Zealand',identity='real',assetIds=['map-0','map-1'],source='Natural Earth, 1:110m')]
    label(m,'heading','New Zealand',100,370,880,180,90)
    label(m,'caption','Two main islands\nSchematic separation, not a border change',90,1390,900,180,36)
    m['events']=[Event(id='separate',type='map_separate',startFrame=38,endFrame=64,targetIds=['map-0','map-1'],dx=-65,dy=50)]
    finish(out,m,'object_location',prepare_only)

def continuity(prepare_only):
    # Exchange two symbolic views of the same generic entity, preserving its
    # identity across the crossfade. Neither is presented as a photograph.
    out,m=base('continuity',6)
    from agent.news_models import Entity as NewsEntity
    from agent.editorial.assets import symbolic
    e=NewsEntity(id='parcel',name='Parcel',kind='object',description='A generic delivery parcel',identity='generic')
    a=symbolic(e,out,'object');b=symbolic(e,out/'alternate','document');b=b.model_copy(update={'id':'parcel-record','subject':'Parcel record symbol'})
    m['assets']=[a,b];m['entities']=[Entity(id=e.id,name=e.name,identity='generic',assetIds=[a.id,b.id],source='Generic diagram')]
    m['layers']=[Layer(id='parcel',role='object',entityId=e.id,assetId=a.id,startFrame=0,endFrame=180,bounds=Bounds(x=220,y=810,w=330,h=330),shadow=True),
        Layer(id='parcel-label',role='label',parentId='parcel',anchor='entity',startFrame=0,endFrame=180,bounds=Bounds(x=0,y=355,w=330,h=100),phrase=Phrase(wordIds=[],lines=[],mode='entity_label',size=36,label='Same parcel'))]
    label(m,'heading','One object, two contexts',100,380,880,200,64)
    label(m,'origin','Origin',90,660,400,100,48);label(m,'destination','Destination',570,660,420,100,48)
    label(m,'caption','Object → associated record\nA symbolic representation swap',100,1350,880,180,40)
    m['events']=[Event(id='intro',type='settle',startFrame=0,endFrame=12,targetIds=['parcel'],scaleFrom=1.6,opacityFrom=.2,dy=30),
        Event(id='move',type='transfer',startFrame=36,endFrame=54,targetIds=['parcel'],dx=360),
        Event(id='swap',type='representation_swap',startFrame=92,endFrame=104,targetIds=['parcel'],assetId=b.id)]
    finish(out,m,'location_transfer',prepare_only)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');p.add_argument('--only',choices=['year','box','map','continuity']);a=p.parse_args()
    for name,fn in [('year',year),('box',box),('map',map_study),('continuity',continuity)]:
        if not a.only or a.only==name:fn(a.prepare_only)
