"""Reference-v2 contract, synchronized phrases, factual preservation and geometry."""
import tempfile
import unittest
from pathlib import Path
from agent.editorial.director import VisualSettings
from agent.editorial.models import Timeline,Word
from agent.editorial.reference import chunks
from tests import test_visual_director as fixture


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.script=fixture.story()
    def tearDown(self):self.tmp.cleanup()
    def timeline(self,script=None):
        return fixture.DirectorTests.timeline(self,script,VisualSettings(editorialStyleVersion='reference-v2'))
    def test_exact_words_names_provenance_and_original_claims(self):
        before=self.script.model_dump();m=self.timeline()
        self.assertEqual(before,self.script.model_dump())
        self.assertEqual(m.editorialStyleVersion,'reference-v2')
        self.assertEqual(m.script,self.script.narration)
        phrases=[l for l in m.layers if l.role=='phrase']
        self.assertEqual([wid for l in phrases for wid in l.phrase.wordIds],[w.id for w in m.words])
        self.assertTrue(all(l.phrase.label in ('Mira','Diamond','Microscope') for l in m.layers if l.role=='label'))
        self.assertTrue(all(a.source=='fixture illustration' for a in m.assets))
        self.assertEqual(m.sections[0].sourceIds,['c1'])
        for row in m.diagnostics['referenceStoryboard']['beats']:self.assertLessEqual(row['revealErrorMs'],1000/60+.01)
        Timeline.model_validate(m.model_dump())
    def test_proper_names_never_split(self):
        tokens='In 1807 Zheng Yi Sao took command of a fleet.'.split()
        words=[Word(id=str(i),sectionId='s1',text=t,start=i*.3,end=i*.3+.2,provenance='provider',confidence=1) for i,t in enumerate(tokens)]
        rows=chunks(words,['Zheng Yi Sao'])
        self.assertTrue(any('Zheng Yi Sao' in ' '.join(w.text for w in row) for row in rows))
        self.assertEqual([w.id for row in rows for w in row],[w.id for w in words])
    def test_no_duplicate_date_and_headline_tracks_or_subtitle_requirement(self):
        m=self.timeline()
        self.assertFalse(any(l.role=='heading' for l in m.layers))
        for a,b in zip(m.beats,m.beats[1:]):self.assertEqual(a.endFrame,b.startFrame)
        self.assertEqual(m.subtitleMode,'editorial')
        self.assertTrue(all(l.bounds.x+l.bounds.w<=1080 and l.bounds.y+l.bounds.h<=1920 for l in m.layers))
    def test_text_only_story_has_a_real_phrase_timeline(self):
        from agent.news_models import Script,Sentence
        text='The result remains uncertain. More evidence is needed.'
        s=Script(summary='Uncertainty',narration=text,entities=[],sentences=[Sentence(id='s1',text=text,phrase='Result remains uncertain',role='close',claim_ids=['c1'],entity_ids=[])])
        m=self.timeline(s)
        self.assertTrue(m.layers);self.assertTrue(m.beats)
        self.assertEqual(m.editorialStyleVersion,'reference-v2')
        self.assertTrue(all(l.phrase for l in m.layers))
    def test_legacy_stays_available(self):
        m=fixture.DirectorTests.timeline(self,settings=VisualSettings(editorialStyleVersion='legacy'))
        self.assertEqual(m.editorialStyleVersion,'legacy')
        self.assertFalse(any(l.role=='phrase' for l in m.layers))
    def test_reframes_do_not_overlap_or_collide_with_text(self):
        m=self.timeline()
        for l in [l for l in m.layers if l.assetId]:
            events=sorted([e for e in m.events if l.id in e.targetIds and e.type=='reframe'],key=lambda e:e.startFrame)
            self.assertTrue(all(a.endFrame<=b.startFrame for a,b in zip(events,events[1:])))
        for row in m.diagnostics['referenceStoryboard']['beats']:
            box=row['textBounds'];self.assertGreaterEqual(box['x'],80);self.assertLessEqual(box['y']+box['h'],1650)

if __name__=='__main__':unittest.main()
