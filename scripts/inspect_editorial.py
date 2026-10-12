"""Contact sheets, source-frame transition strips, waveform and delivery metadata."""
import argparse
import json
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def sheet(files,path,labels,cols=8,width=180):
    height=round(width*16/9);canvas=Image.new('RGB',(cols*width,((len(files)+cols-1)//cols)*(height+28)),'#dedee3');draw=ImageDraw.Draw(canvas)
    for i,(f,label) in enumerate(zip(files,labels)):
        x=i%cols*width;y=i//cols*(height+28)
        with Image.open(f) as im:canvas.paste(im.resize((width,height)),(x,y))
        draw.text((x+6,y+height+5),label,fill='#222222')
    canvas.save(path)

def inspect(video,out,transitions=()):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf','fps=1,scale=180:320',str(out/'second-%03d.jpg')],check=True)
    files=sorted(out.glob('second-*.jpg'));sheet(files,out/'contact.jpg',[f'{i//60:02}:{i%60:02}.000' for i in range(len(files))])
    for start,end in transitions:
        prefix=f'transition-{start:.2f}';a=round(start*30);b=round(end*30)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf',f'select=between(n\,{a}\,{b-1}),scale=180:320','-fps_mode','vfr',str(out/(prefix+'-%03d.jpg'))],check=True)
        files=sorted(out.glob(prefix+'-*.jpg'));sheet(files,out/(prefix+'.jpg'),[f'f{a+i} / {(a+i)/30:.3f}s' for i in range(len(files))])
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-filter_complex','showwavespic=s=1600x260:colors=454955','-frames:v','1',str(out/'waveform.png')],check=True)
    meta=subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)])
    (out/'metadata.json').write_bytes(meta)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('output');p.add_argument('--transition',action='append',default=[]);a=p.parse_args()
    inspect(a.video,a.output,[tuple(map(float,t.split(':'))) for t in a.transition])
