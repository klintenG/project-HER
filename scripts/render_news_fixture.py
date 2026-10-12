"""Render both real backends with an explicitly synthetic deterministic fixture."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.news_fixtures import fixture_manifest
from agent.news_compositor import render_moviepy,NewsFrames
from agent.news_audio import write_srt
from agent.news_renderer import render_remotion,stage_remotion
from PIL import Image
parser=argparse.ArgumentParser();parser.add_argument('--renderer',choices=['moviepy','remotion','both'],default='both');parser.add_argument('--width',type=int,default=1080);parser.add_argument('--height',type=int,default=1920)
args=parser.parse_args()
output=Path('output/news_validation').resolve(); m=fixture_manifest(output,args.width,args.height)
(output/'news_manifest.json').write_text(m.model_dump_json(indent=2))
write_srt(m.audio,output/'subtitles.srt')
frames=NewsFrames(m)
indices=sorted({0,15,m.duration_frames-1,*[b.start+d for b in m.beats for d in (-1,0,5,12,35) if 0<=b.start+d<m.duration_frames]})
for f in indices: Image.fromarray(frames.frame(f)).save(output/f'frame-{f:04}.png')
if args.renderer in ('moviepy','both'): render_moviepy(m,output/'fixture_moviepy.mp4')
if args.renderer in ('remotion','both'): render_remotion(m,output/'fixture_remotion.mp4')
print(output)
