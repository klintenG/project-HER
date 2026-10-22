"""Narration-led staging through the real timeline compiler; fixture audio only."""
import unittest
from agent.editorial.director import VisualSettings
from agent.news_models import Sentence
from tests import test_visual_director as fixtures


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.DirectorTests('runTest');self.case.setUp()
    def tearDown(self):self.case.tearDown()
    def timeline(self,script):
        return self.case.timeline(script,VisualSettings(editorialStyleVersion='reference-v2'))

    def test_single_image_moves_from_center_to_left_with_text_on_right(self):
        s=self.case.script.model_copy(deep=True)
        text='Mira carefully examined the object before recording the result in her notebook.'
        s=s.model_copy(update={'entities':s.entities[:1],
            'sentences':[Sentence(id='s1',text=text,phrase='Mira examined the object',role='development',claim_ids=['c1'],entity_ids=['mira']),
                Sentence(id='s2',text='Her work was complete.',phrase='Her work was complete',role='close',claim_ids=['c1'],entity_ids=['mira'])],
            'narration':text+' Her work was complete.'})
        m=self.timeline(s);image=next(l for l in m.layers if l.assetId)
        self.assertEqual(image.bounds.x,190)
        moves=[e for e in m.events if e.type=='reframe' and image.id in e.targetIds]
        self.assertTrue(any(e.boundsTo.x==70 for e in moves))
        phrases=[l for l in m.layers if l.phrase and l.phrase.wordIds]
        self.assertTrue(any(l.bounds.x==640 for l in phrases))
        for l in phrases:
            if l.bounds.x==640:self.assertGreaterEqual(l.bounds.x,570)

    def test_three_to_one_retains_the_same_image_and_promotes_it(self):
        s=self.case.script.model_copy(deep=True)
        second=Sentence(id='s2',text='The diamond remained in the room.',phrase='The diamond remained',role='development',claim_ids=['c1'],entity_ids=['diamond'])
        s.sentences.append(second);s.narration+=' '+second.text
        m=self.timeline(s)
        diamonds=[l for l in m.layers if l.assetId and l.entityId=='diamond']
        self.assertEqual(len(diamonds),1)
        layer=diamonds[0];boundary=next(row['startFrame'] for row in m.diagnostics['atomicStoryboard']['beats'] if row['sectionId']=='s2')
        self.assertLess(layer.startFrame,boundary);self.assertGreater(layer.endFrame,boundary)
        stages=m.diagnostics['narrationStaging']['stages']
        self.assertTrue(any(len(row['layerIds'])==3 for row in stages))
        promoted=next(row for row in stages if row['frame']==boundary)
        self.assertEqual(promoted['layerIds'],[layer.id])
        self.assertIn(layer.id,promoted['persistedLayerIds'])
        self.assertEqual(promoted['targets'][layer.id]['w'],700)
        self.assertTrue(any(e.type=='reframe' and e.startFrame==boundary and layer.id in e.targetIds for e in m.events))

    def test_contrast_moves_image_right_and_places_type_left(self):
        s=self.case.script.model_copy(deep=True)
        text='Instead Mira carefully examined the object before recording the result in her notebook.'
        s=s.model_copy(update={'entities':s.entities[:1],
            'sentences':[Sentence(id='s1',text=text,phrase='Mira examined the object',role='development',claim_ids=['c1'],entity_ids=['mira']),
                Sentence(id='s2',text='Her work was complete.',phrase='Her work was complete',role='close',claim_ids=['c1'],entity_ids=['mira'])],
            'narration':text+' Her work was complete.'})
        m=self.timeline(s)
        self.assertTrue(any(e.type=='reframe' and e.boundsTo.x==510 for e in m.events))
        self.assertTrue(any(l.role=='phrase' and l.bounds.x==90 and l.bounds.w==350 for l in m.layers))

    def test_spoken_name_focus_uses_the_actual_word_clock(self):
        m=self.timeline(self.case.script)
        for cue in m.diagnostics['narrationStaging']['focusCues']:
            word=next(w for w in m.words if w.id==cue['wordId'])
            self.assertLessEqual(abs(cue['frame']/30-word.start),1/60+.001)
            layer=next(l for l in m.layers if l.id==cue['layerId'])
            self.assertLessEqual(layer.startFrame,cue['frame']);self.assertGreater(layer.endFrame,cue['frame'])
        focused={row['focusedLayerId'] for row in m.diagnostics['narrationStaging']['stages']}
        for eid in ('mira','diamond','microscope'):
            self.assertIn(next(l.id for l in m.layers if l.assetId and l.entityId==eid),focused)
        self.assertTrue(any(e.type=='spotlight' and e.opacityTo==.64 for e in m.events))

    def test_composite_members_focus_the_composite_without_adding_portraits(self):
        from types import SimpleNamespace
        from agent.editorial.staging import focus_cues
        from agent.editorial.models import Word,Layer,Bounds
        registry=self.case.script.entities[:1]
        script=SimpleNamespace(identity_registry=registry,entities=[],sentence_storyboard=[{'primary_entity_id':'scene-1','depicted_entity_ids':['mira']}])
        m={'sections':[SimpleNamespace(id='s1')],'words':[Word(id='w',sectionId='s1',text='Mira',start=.5,end=.8,provenance='provider',confidence=1)],
            'layers':[Layer(id='existing-image',role='object',entityId='scene-1',assetId='a',bounds=Bounds(x=100,y=600,w=500,h=500),startFrame=0,endFrame=60)]}
        cues=focus_cues(m,script)
        self.assertEqual(cues,[{'frame':15,'layerId':'existing-image','entityId':'mira','wordId':'w'}])
        self.assertEqual(len(m['layers']),1)

if __name__=='__main__':unittest.main()
