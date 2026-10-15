"""Brand timing contract shared by Python results and Remotion metadata."""
import json
import math
import os
import unittest
from unittest.mock import patch
from agent.branding import branding_settings, outro_frames, output_frames, screen_frames


class BrandingTests(unittest.TestCase):
    def test_frame_rate_and_duration_contract(self):
        for fps in (24,25,30,60):
            with self.subTest(fps=fps):
                self.assertEqual(output_frames(2005,fps,{}),2005+math.floor(2.7*fps+.5))
        self.assertEqual(outro_frames(30,{}),81)

    def test_disable_and_theme_independent_timing(self):
        for settings in ({'enabled':False},{'outro':{'enabled':False}}):
            self.assertEqual(outro_frames(30,settings),0)
        self.assertEqual(outro_frames(30,{'outro':{'theme':'ivory','durationSeconds':2}}),60)

    def test_never_truncate_words_or_audio(self):
        self.assertEqual(screen_frames({'duration':1,'audio_duration':2.01},30),61)
        self.assertEqual(screen_frames({'duration':1,'word_timings':[{'end':3}]},30),90)
        self.assertEqual(screen_frames({'duration':1.01},30),31)

    def test_environment_configuration_and_stable_seed(self):
        with patch.dict(os.environ,{'HER_BRANDING_JSON':json.dumps({'creditEnabled':False})}):
            a=branding_settings('saved-job-id')
            self.assertEqual(a,branding_settings('saved-job-id'))
            self.assertFalse(a['creditEnabled'])
            self.assertEqual(a['deterministicSeed'],'saved-job-id')
        with patch.dict(os.environ,{'HER_BRANDING_JSON':'[]'}):
            with self.assertRaises(ValueError):branding_settings()

    def test_reject_out_of_bounds_closing(self):
        for duration in (0,1.9,3.1,float('nan')):
            with self.assertRaises(ValueError):outro_frames(30,{'outro':{'durationSeconds':duration}})
