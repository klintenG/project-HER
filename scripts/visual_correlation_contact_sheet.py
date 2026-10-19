"""Export timed final-video frames, aligned narration and a portable review page."""
import argparse
import html
import json
import math
import subprocess
import textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--interval',type=float,default=2);p.add_argument('--before',type=Path)
    args=p.parse_args();root=args.run.resolve();edl=json.loads((root/'event_edl.json').read_text());video=root/'editorial.mp4'
    frames=root/'contact_frames';frames.mkdir(exist_ok=True)
    duration=max(row['audio_end_ms'] for row in edl['beats'])/1000
    times=sorted(set([round(i*args.interval,3) for i in range(math.ceil(duration/args.interval))]+[round((b.get('visual_onset_ms',b['audio_start_ms'])+b['audio_end_ms'])/2000,3) for b in edl['beats']]))
    fontpath=Path(__file__).resolve().parents[1]/'assets/fonts/news/Poppins-Medium.ttf'
    font=ImageFont.truetype(str(fontpath),14);small=ImageFont.truetype(str(fontpath),12)
    tiles=[]
    for i,at in enumerate(times):
        path=frames/f'{i:03d}.jpg'
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(at),'-i',str(video),'-frames:v','1','-vf','scale=270:480',str(path)],check=True,capture_output=True)
        beat=next((b for b in edl['beats'] if b['audio_start_ms']/1000<=at<b['audio_end_ms']/1000),None)
        tile=Image.new('RGB',(290,620),'#efefef');tile.paste(Image.open(path),(10,25));draw=ImageDraw.Draw(tile)
        draw.text((10,4),f'{at:.2f}s | '+(beat['validation_status'] if beat else 'spoken pause'),fill='#222222',font=small)
        caption=beat['narration_excerpt'] if beat else '(Pause between aligned events)'
        draw.multiline_text((10,512),'\n'.join(textwrap.wrap(caption,34)),fill='#222222',font=font,spacing=3)
        tiles.append(tile)
    cols=5;sheet=Image.new('RGB',(cols*290,math.ceil(len(tiles)/cols)*620),'#dddddd')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%cols)*290,(i//cols)*620))
    sheet.save(root/'contact_sheet.jpg',quality=90)
    if args.before:
        pairs=[]
        for i,b in enumerate(edl['beats']):
            at=(b.get('visual_onset_ms',b['audio_start_ms'])+b['audio_end_ms'])/2000
            tile=Image.new('RGB',(560,600),'#efefef');draw=ImageDraw.Draw(tile)
            for side,source in enumerate([args.before,video]):
                target=frames/f'compare-{i:02d}-{side}.jpg'
                subprocess.run(['ffmpeg','-v','error','-y','-ss',str(at),'-i',str(source),'-frames:v','1','-vf','scale=270:480',str(target)],check=True,capture_output=True)
                tile.paste(Image.open(target),(side*280+5,25));draw.text((side*280+5,4),('BEFORE' if side==0 else 'AFTER')+f' {at:.2f}s',fill='#222222',font=small)
            draw.multiline_text((8,512),'\n'.join(textwrap.wrap(b['narration_excerpt'],66)),fill='#222222',font=font,spacing=3)
            pairs.append(tile)
        comparison=Image.new('RGB',(1680,math.ceil(len(pairs)/3)*600),'#dddddd')
        for i,tile in enumerate(pairs):comparison.paste(tile,((i%3)*560,(i//3)*600))
        comparison.save(root/'before_after_contact_sheet.jpg',quality=90)
    cards=[]
    for b in edl['beats']:
        rel=lambda value:Path(value).resolve().relative_to(root).as_posix()
        imagepath=rel(b['asset_path']) if b.get('asset_path') else ''
        cards.append(f'<article><img src="{html.escape(imagepath)}"><div><h2>{html.escape(b["beat_id"])}</h2><p>{b["audio_start_ms"]/1000:.3f}–{b["audio_end_ms"]/1000:.3f}s · {html.escape(b["validation_status"])}</p><p>Visual entrance: {b.get("visual_onset_ms",b["audio_start_ms"])/1000:.3f}s</p><p>{html.escape(b["narration_excerpt"])}</p><button onclick="seek({b["audio_start_ms"]/1000})">Play this event</button><details><summary>Requirements, prompt and review</summary><pre>{html.escape(json.dumps(b,ensure_ascii=False,indent=2))}</pre></details></div></article>')
    page='''<!doctype html><meta charset="utf-8"><title>ProjectHER event review</title><style>body{font-family:system-ui;background:#f2f0ec;color:#182232;max-width:1100px;margin:30px auto}video{height:65vh;max-width:100%;position:sticky;top:10px}article{display:flex;gap:22px;background:white;padding:20px;margin:20px 0}img{width:220px;object-fit:contain}pre{white-space:pre-wrap;overflow-wrap:anywhere}button{padding:10px}h1{font-size:24px}</style><h1>ProjectHER · narration and visual review</h1><video id="video" src="editorial.mp4" controls></video><p>Requirements are checked against imagery, not caption text. Estimated timing and unresolved reviews remain explicit.</p>'''+''.join(cards)+'''<script>function seek(t){const v=document.getElementById('video');v.currentTime=t;v.play();}</script>'''
    (root/'review.html').write_text(page)
    print(root/'contact_sheet.jpg');print(root/'review.html')

if __name__=='__main__':main()
