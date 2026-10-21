"""All delivery paths isolate foreground; a padded panel is not a cutout."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageOps
import config
from agent.cutout_processor import CutoutProcessor, CutoutQualityError, repair_cutout, usable_cutout
from agent.editorial.image_recovery import preserve
from agent.news_models import Entity


class CutoutRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        patched=patch.object(config,'NEWS_CUTOUT_CACHE',self.root/'cache');patched.start();self.addCleanup(patched.stop)

    def test_transparent_border_does_not_make_a_scene_card_acceptable(self):
        opaque=Image.new('RGB',(200,300),'gray')
        self.assertFalse(usable_cutout(opaque))
        padded=ImageOps.expand(opaque.convert('RGBA'),border=30,fill=(0,0,0,0))
        self.assertFalse(usable_cutout(padded))
        rounded=Image.new('RGBA',(240,340));ImageDraw.Draw(rounded).rounded_rectangle((20,20,220,320),radius=8,fill='red')
        self.assertFalse(usable_cutout(rounded))

    def test_clipped_alpha_is_padded_locally_without_new_generation(self):
        raw=self.root/'clipped.png';im=Image.new('RGBA',(200,300))
        ImageDraw.Draw(im).ellipse((-20,20,180,280),fill='brown');im.save(raw)
        out=self.root/'cut.png'
        method=repair_cutout(raw,out,CutoutProcessor(backend='none'))
        self.assertEqual(method,'preserved_existing_alpha')
        with Image.open(out) as cut:
            self.assertTrue(usable_cutout(cut))
            self.assertEqual(cut.getpixel((0,0))[3],0)
            self.assertGreater(cut.getchannel('A').getbbox()[0],0)

    def test_local_segmentation_cache_prevents_repeated_mask_inference(self):
        raw=self.root/'raw.png';Image.new('RGB',(200,300),'gray').save(raw);calls=[]
        def segment(im,model):
            calls.append(model);cut=Image.new('RGBA',im.size)
            ImageDraw.Draw(cut).ellipse((40,30,160,270),fill='blue');return cut
        processor=CutoutProcessor(segmenter=segment,models=['local-test'])
        repair_cutout(raw,self.root/'first.png',processor)
        repair_cutout(raw,self.root/'second.png',processor)
        self.assertEqual(calls,['local-test'])
        with Image.open(self.root/'second.png') as im:self.assertTrue(usable_cutout(im))

    def test_no_mask_means_explicit_unavailable_visual_never_a_square(self):
        raw=self.root/'blank.png';Image.new('RGB',(160,240),'red').save(raw)
        e=Entity(id='scene',name='Story scene',kind='person',identity='fictional',description='A scene in the story')
        record={}
        with patch('agent.cutout_processor.CutoutProcessor',return_value=CutoutProcessor(backend='none')):
            a=preserve(e,raw,None,self.root/'output','No mask',record)
        self.assertTrue(a.alpha)
        self.assertEqual(record['route'],'unavailable_cutout')
        self.assertTrue(raw.exists())
        self.assertNotEqual(a.path,str(raw))

if __name__=='__main__':unittest.main()
