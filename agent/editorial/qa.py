"""Low-cost encoded-media diagnostics; never optimize motion by adding noise."""
import subprocess
import numpy as np
from .audio import samples


def activity(path):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','fps=5,scale=90:160,format=gray','-f','rawvideo','-pix_fmt','gray','-'])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,160,90).astype(np.int16)
    delta=np.abs(np.diff(frames,axis=0))
    mean=delta.mean(axis=(1,2));changed=(delta>8).mean(axis=(1,2))
    data=samples(path);windows=[np.sqrt(np.mean(data[i:i+12000]**2)) for i in range(0,len(data),12000)]
    return {'sampling':'5 Hz, 90x160 grayscale; delta >8/255; low activity mean <0.9/255',
            'meanChangedPixelPercent':float(changed.mean()*100),'lowActivityPercent':float((mean<.9).mean()*100),
            'quietQuarterSeconds':int(sum(x<10**(-35/20) for x in windows)),'audioWindowCount':len(windows),
            'intervals':[{'at':round((i+1)*.2,1),'meanDelta':float(x),'changedPercent':float(changed[i]*100)} for i,x in enumerate(mean)]}

