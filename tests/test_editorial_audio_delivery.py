"""Actual AAC correction and bounded delivery checks; no Chromium/providers."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock

import numpy as np

from agent.editorial.audio import normalize,write_wave,measure
from agent.editorial.models import digest
from agent.editorial.render import delivery_issues,finalize_audio
from agent.news_models import NewsError


class AlignmentRecoveryTests(unittest.TestCase):
    def aligner(self,rows):
        from agent.editorial.audio import Aligner
        aligner=Aligner.__new__(Aligner);aligner.model=MagicMock();aligner.tokenizer=MagicMock()
        aligner.model.find_alignment.side_effect=[[row] for row in rows]
        return aligner
    def test_zero_duration_word_recomputes_measured_alignment(self):
        rejected=[{'word':' eliminate','start':.3,'end':.3,'probability':.8}]
        accepted=[{'word':' eliminate','start':.2,'end':.6,'probability':.9}]
        aligner=self.aligner([rejected,accepted])
        with patch.dict('sys.modules',{'faster_whisper.audio':SimpleNamespace(pad_or_trim=lambda value:value)}):
            rows=aligner.align(np.ones(16000,dtype=np.float32),'eliminate')
        self.assertEqual(rows[0]['start'],.2);self.assertEqual(rows[0]['end'],.6)
        self.assertEqual(rows[0]['provenance'],'whisper_forced')
        self.assertEqual([c.kwargs['median_filter_width'] for c in aligner.model.find_alignment.call_args_list],[7,3])
        self.assertEqual(aligner.model.encode.call_count,1)
    def test_all_zero_alignments_fail_after_three_local_attempts(self):
        rejected=[{'word':' eliminate','start':.3,'end':.3,'probability':.8}]
        aligner=self.aligner([rejected,rejected,rejected])
        with patch.dict('sys.modules',{'faster_whisper.audio':SimpleNamespace(pad_or_trim=lambda value:value)}):
            with self.assertRaisesRegex(NewsError,'Zero-duration'):aligner.align(np.ones(16000,dtype=np.float32),'eliminate')
        self.assertEqual(aligner.model.find_alignment.call_count,3)
    def test_token_mismatch_is_not_replaced_with_estimated_timing(self):
        rejected=[{'word':' different','start':.1,'end':.5,'probability':.8}]
        aligner=self.aligner([rejected])
        with patch.dict('sys.modules',{'faster_whisper.audio':SimpleNamespace(pad_or_trim=lambda value:value)}):
            with self.assertRaisesRegex(NewsError,'token mismatch'):aligner.align(np.ones(16000,dtype=np.float32),'eliminate')
        self.assertEqual(aligner.model.find_alignment.call_count,1)


class AudioDeliveryTests(unittest.TestCase):
    def model(self,master):
        track=SimpleNamespace(kind='master',gain=1,offsetFrames=0,path=str(master),sha256=digest(master))
        return SimpleNamespace(audio=[track],words=['spoken'],durationInFrames=60,fps=30,warnings=[])

    def make_media(self,root,gain):
        t=np.arange(96000)/48000
        raw=root/'raw.wav';master=root/'master.wav'
        write_wave(raw,.07*np.sin(2*np.pi*220*t)+.03*np.sin(2*np.pi*511*t))
        normalize(raw,master)
        output=root/'video.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=gray:s=160x288:r=30:d=2','-i',str(master),
            '-map','0:v:0','-map','1:a:0','-af',f'volume={gain}','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',
            '-x264-params','colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv',
            '-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
            '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','2',str(output)],capture_output=True,check=True)
        return master,output

    def video_hash(self,path):
        return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-c','copy','-f','hash','-'])

    def test_codec_overshoot_is_rejected_without_relaxing_ceiling(self):
        self.assertTrue(delivery_issues({'integratedLUFS':-14.91,'truePeakDBTP':-.97}))
        self.assertFalse(delivery_issues({'integratedLUFS':-15,'truePeakDBTP':-1}))
        self.assertTrue(delivery_issues({'integratedLUFS':-17,'truePeakDBTP':-2}))
        silent={'integratedLUFS':None,'truePeakDBTP':None}
        self.assertTrue(delivery_issues(silent))
        self.assertFalse(delivery_issues(silent,allow_silence=True))

    def test_actual_aac_correction_preserves_video_and_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);master,output=self.make_media(root,8)
            m=self.model(master);before=self.video_hash(output);master_hash=digest(master)
            self.assertTrue(delivery_issues(measure(output)))
            stats=finalize_audio(m,output,output)
            self.assertFalse(delivery_issues(stats))
            self.assertEqual(stats['deliveryCorrection']['repairs'],1)
            self.assertEqual(self.video_hash(output),before)
            self.assertEqual(digest(master),master_hash)
            audit=json.loads((root/'video-metrics.json').read_text())
            self.assertTrue(audit['audioDelivery']['passed'])
            self.assertTrue(audit['audioDelivery']['attempts'][0]['issues'])
            self.assertEqual(len(audit['audioDelivery']['attempts']),2)
            video=next(s for s in audit['media']['streams'] if s['codec_type']=='video')
            self.assertEqual(int(video['nb_frames']),60)
            self.assertTrue(m.warnings)

    def test_compliant_aac_is_not_reencoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);master,output=self.make_media(root,1);before=digest(output)
            with patch('agent.editorial.render.normalize') as correction:
                stats=finalize_audio(self.model(master),output,output)
            self.assertFalse(delivery_issues(stats));correction.assert_not_called()
            self.assertEqual(digest(output),before)

    def test_failed_repairs_are_bounded_and_keep_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);master=root/'master.wav';master.write_bytes(b'master')
            output=root/'video.mp4';output.write_bytes(b'original video')
            meta={'streams':[{'codec_type':'video','color_space':'bt709','color_transfer':'bt709','color_primaries':'bt709','pix_fmt':'yuv420p'}]}
            stats={'integratedLUFS':-14.91,'truePeakDBTP':-.97}
            def encode(args,**kwargs):Path(args[-1]).write_bytes(b'encoded audio')
            with patch('agent.editorial.render.measure',return_value=stats.copy()) as measured, \
                    patch('agent.editorial.render.normalize',return_value={}) as normalized, \
                    patch('agent.editorial.render.subprocess.check_output',return_value=json.dumps(meta).encode()), \
                    patch('agent.editorial.render.subprocess.run',side_effect=encode):
                with self.assertRaisesRegex(NewsError,'-0.97 dBTP.*Measurements:'):
                    finalize_audio(self.model(master),output,output)
            self.assertEqual(measured.call_count,3);self.assertEqual(normalized.call_count,2)
            self.assertEqual([call.kwargs['true_peak'] for call in normalized.call_args_list],[-2,-2.5])
            audit=json.loads((root/'video-metrics.json').read_text())
            self.assertFalse(audit['audioDelivery']['passed'])
            self.assertEqual(len(audit['audioDelivery']['attempts']),3)


if __name__=='__main__':unittest.main()
