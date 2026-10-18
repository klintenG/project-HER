"""Failures that previously stopped an otherwise playable News/editorial job."""
import tempfile
import unittest
from pathlib import Path

from agent.editorial.planner import phrase_layout
from agent.news_assets import generate_cutouts
from agent.news_models import Entity, NewsError, Script, Sentence


class VisualRecoveryTests(unittest.TestCase):
    def test_long_editorial_phrase_keeps_every_spoken_word(self):
        from types import SimpleNamespace
        phrase='Ame-no-Uzume devised an unusual plan that brought the hidden sun goddess out of the cave'
        words=[SimpleNamespace(id=str(i),text=w) for i,w in enumerate(phrase.split())]
        lines,size=phrase_layout([w.id for w in words],words,470,94,240)
        self.assertEqual([wid for line in lines for wid in line],[w.id for w in words])
        self.assertLessEqual(size,94)

    def test_classic_news_failed_subject_becomes_degraded_asset(self):
        class FailingGenerator:
            provider='fixture'
            async def subject(self,prompt,path):
                raise NewsError('simulated provider outage')
        entity=Entity(id='actor',name='The actor',kind='person',identity='fictional',description='A person in motion')
        sentence=Sentence(id='s1',text='The actor ran across the stage.',phrase='ran across the stage',entity_ids=['actor'],claim_ids=['c1'],role='development')
        script=Script(summary='Stage',narration=sentence.text,sentences=[sentence],entities=[entity])
        with tempfile.TemporaryDirectory() as tmp:
            assets=generate_cutouts(script,Path(tmp),'fictional',generator=FailingGenerator())
            self.assertEqual(len(assets),1)
            self.assertEqual(assets[0].qa,'degraded')
            self.assertTrue(Path(assets[0].path).is_file())
            self.assertTrue((Path(tmp)/'news_visual_recovery.json').is_file())


if __name__=='__main__':unittest.main()
