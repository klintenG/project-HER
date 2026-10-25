"""Exercise the exported cover frame using real FFmpeg, without paid providers."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops
from automation.video_quality import ThumbnailComposer

class CoverTests(unittest.TestCase):
    def test_single_cutout_cover_is_embedded_at_buffer_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);asset=root/'hero.png';video=root/'video.mp4'
            image=Image.new('RGBA',(400,600));ImageDraw.Draw(image).ellipse((20,20,380,580),fill='#bf684a');image.save(asset)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=gray:s=1080x1920:r=30:d=3',
                '-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(video)],check=True)
            (root/'editorial_props.json').write_text(json.dumps({'assets':[{'id':'hero','alpha':True,'role':'portrait','subject':'Hero','path':str(asset)}]}))
            cover=ThumbnailComposer().compose(video,{'primary_characters':['Hero'],'script':{'hook_text':'The hero who changed everything'}})
            self.assertEqual(len(cover['visual_assets']),1)
            self.assertEqual(cover['additional_image_generations'],0)
            exported=root/'frame.png'
            subprocess.run(['ffmpeg','-v','error','-y','-ss','1.5','-i',str(video),'-frames:v','1',str(exported)],check=True)
            with Image.open(cover['path']) as expected,Image.open(exported) as actual:
                difference=ImageChops.difference(expected.convert('RGB'),actual.convert('RGB'))
                from PIL import ImageStat
                self.assertLess(sum(ImageStat.Stat(difference).mean)/3,5)
