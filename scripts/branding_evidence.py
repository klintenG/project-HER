"""Extract review images and a short reel from the actual encoded deliverable."""
import json
import subprocess
from pathlib import Path
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('directory',type=Path)
args=parser.parse_args()
root=args.directory.resolve()
schedule=json.loads((root/'schedule.json').read_text())
fps=schedule['fps'];story=schedule['storyFrames'];events=schedule['events']
frames={'01-corner':0,'02-protective':events[0]['start']+events[0]['fade']+30,
        '03-credit':next(e for e in events if e['kind']=='credit')['start']+30,
        '04-closing-start':story,'05-closing-motion':story+12,'06-signature':schedule['totalFrames']-1}
video=root/'branded-story.mp4'
for name,frame in frames.items():
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf',f"select=eq(n\\,{frame})",'-frames:v','1',str(root/(name+'.png'))],check=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(root/(name+'.png')),'-vf','scale=360:-1','-frames:v','1',str(root/(name+'-mobile.png'))],check=True)
# Hard cuts between review excerpts keep each original animation at its real speed.
credit=next(e for e in events if e['kind']=='credit')
spans=[(1,3),(events[0]['start']/fps,(events[0]['end']+1)/fps),
       (credit['start']/fps,(credit['end']+1)/fps),((story-30)/fps,schedule['totalFrames']/fps)]
filters=[]
for i,(start,end) in enumerate(spans):
    filters.extend([f'[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]',f'[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]'])
filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(spans)))+f'concat=n={len(spans)}:v=1:a=1[v][a]')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-c:v','libx264','-crf','19','-c:a','aac','-movflags','+faststart',str(root/'branding-preview.mp4')],check=True)
metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
v=next(s for s in metadata['streams'] if s['codec_type']=='video')
assert int(v['nb_frames'])==schedule['totalFrames']
assert v['width']==1080 and v['height']==1920
(root/'encoded-metadata.json').write_text(json.dumps(metadata,indent=2))
print(f'Extracted six full-size and six mobile frames; review reel; verified {v["nb_frames"]} encoded frames.')
