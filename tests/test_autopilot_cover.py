"""Real FFmpeg contracts for the shared opening, captions and Buffer frame."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops,ImageStat
from automation.video_quality import ThumbnailComposer,file_hash
from agent.orchestrator import PipelineResult
from agent.story_opening import add_opening,short_title

class CoverTests(unittest.TestCase):
    def test_two_second_opening_delays_audio_captions_and_matches_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);asset=root/'hero.png';video=root/'video.mp4'
            image=Image.new('RGBA',(400,600));ImageDraw.Draw(image).ellipse((20,20,380,580),fill='#bf684a');image.save(asset)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=gray:s=1080x1920:r=30:d=3',
                '-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(video)],check=True)
            (root/'editorial_props.json').write_text(json.dumps({'assets':[{'id':'hero','alpha':True,'role':'portrait','subject':'Hero','path':str(asset)}]}))
            srt=root/'subtitles.srt';srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nThe hero begins.\n')
            vtt=root/'subtitles.vtt';vtt.write_text('WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nThe hero begins.\n')
            result=PipelineResult(success=True,title='The hero who changed everything',video_path=video,srt_path=srt)
            result=add_opening(result)
            self.assertAlmostEqual(result.duration,5,delta=.1)
            self.assertIn('00:00:02,000 --> 00:00:03,000',srt.read_text())
            self.assertIn('00:00:02.000 --> 00:00:03.000',vtt.read_text())
            before=file_hash(video);add_opening(result);self.assertEqual(file_hash(video),before)
            cover=ThumbnailComposer().compose(video,{'script':{'hook_text':result.title}})
            self.assertEqual(file_hash(video),before) # Cover extraction must not rewrite the video.
            self.assertEqual(len(cover['visual_assets']),1)
            self.assertEqual(cover['additional_image_generations'],0)
            with Image.open(root/'opening.png') as expected,Image.open(cover['path']) as actual:
                difference=ImageChops.difference(expected.convert('RGB'),actual.convert('RGB'))
                self.assertLess(sum(ImageStat.Stat(difference).mean)/3,5)
            audio=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-af','silencedetect=noise=-40dB:d=0.5','-vn','-f','null','-'],capture_output=True,text=True,check=True).stderr
            import re
            end=float(re.search(r'silence_end: ([\d.]+)',audio)[1])
            self.assertAlmostEqual(end,2,delta=.08)
            storyframe=root/'story.png'
            subprocess.run(['ffmpeg','-v','error','-y','-ss','2.5','-i',str(video),'-frames:v','1',str(storyframe)],check=True)
            with Image.open(storyframe) as frame:self.assertLess(ImageStat.Stat(frame.convert('L')).stddev[0],2)

    def test_short_title_uses_approved_hook_and_does_not_end_on_a_joining_word(self):
        self.assertEqual(short_title('A much longer source summary','The brother who stole a throne'),'The brother who stole a throne')
        self.assertEqual(short_title('One two three four five six seven and eight nine'),'One two three four five six seven')
