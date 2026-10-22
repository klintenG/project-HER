import copy
import json
import unittest
from pathlib import Path
from agent.editorial.canonical import lock_script,assert_locked,validate_closure
from agent.editorial.action_beats import action_events
from agent.editorial.narrative import storyboard_narrative
from agent.editorial.sentence_storyboard import plan
from tests.test_sentence_storyboard import script_for,fixture_planner


class IntegrationTests(unittest.TestCase):
    def test_osiris_actions_are_ordered_and_negation_does_not_invent_an_event(self):
        data=json.loads(Path('tests/fixtures/narrative/osiris.json').read_text())
        events=[e['verb'] for sentence in data['sentences'] for e in action_events(sentence)]
        for kind in data['required_actions']:self.assertIn(kind,events)
        trap=action_events(data['sentences'][4])
        self.assertEqual([e['verb'] for e in trap],['sealing','disposal'])
        self.assertEqual(action_events('He never opened the chest.'),[])

    def test_script_lock_detects_downstream_sentence_mutation(self):
        script=script_for(['The king ruled the land.','The son inherited the throne.'])
        locked=lock_script(script)
        assert_locked(script,locked)
        changed=copy.deepcopy(script);changed.sentences[-1].text='The son challenged the king.'
        with self.assertRaisesRegex(Exception,'Canonical narration'):assert_locked(changed,locked)

    def test_complete_myth_ending_and_ongoing_news_are_distinguished(self):
        bad=script_for(['A king died.','His son challenged the usurper.'])
        with self.assertRaisesRegex(ValueError,'unresolved'):validate_closure(bad)
        good=script_for(['A king died.','His son defeated the usurper and claimed the throne.'])
        validate_closure(good)
        bad.entities[0].identity='real'
        validate_closure(bad)

    def test_default_storyboard_covers_every_word_and_locks_exact_action_spans(self):
        script=script_for(['The king ruled the land.','He opened a chest and entered it.'])
        planned,_=plan(script,None,fixture_planner,{})
        p=planned.narrative_plan
        p.validate_coverage(planned)
        self.assertEqual([b.verb for b in p.beats if b.required_action_visible],['opening','entering'])
        for b in p.beats:self.assertEqual(planned.narration[b.start_char:b.end_char],b.text)
        p.beats.pop(0)
        with self.assertRaisesRegex(ValueError,'Incomplete'):p.validate_coverage(planned)

    def test_character_named_inside_composite_is_removed_from_secondaries(self):
        from agent.news_models import Entity
        s=script_for(['Character embraced Companion.'])
        s.entities.append(Entity(id='companion',name='Companion',kind='person',identity='fictional',description='Red tunic'))
        def planner(i,d):
            r=fixture_planner(i,d);c=r['sentences'][0]['candidates'][0]
            c.update(subject='Character embracing Companion',visual_focus='Character embracing Companion',
                description='Character and Companion in a connected embrace cutout.',secondary_ids=['companion'])
            return r
        result,_=plan(s,None,planner,{})
        row=result.sentence_storyboard[0]
        self.assertIn('companion',row['depicted_entity_ids'])
        self.assertEqual(row['secondary_entity_ids'],[])

    def test_clouds_gathering_does_not_require_a_new_character_action(self):
        self.assertEqual(action_events('Clouds gathered overhead.'),[])

    def test_unpictured_supporting_prop_remains_an_independent_layer(self):
        from agent.editorial.sentence_storyboard import embedded_members
        from agent.news_models import Entity
        registry=[Entity(id='hero',name='Hero',kind='person',identity='fictional',description='Blue tunic'),
            Entity(id='chest',name='Magnificent chest',kind='object',identity='generic',description='Wooden chest')]
        self.assertEqual(embedded_members('Hero standing alone.',registry),['hero'])
        self.assertEqual(embedded_members('Hero stepping inside a wooden chest.',registry),['hero','chest'])

    def test_delivery_rejects_estimated_words_and_a_truncated_final_hold(self):
        from tests.test_visual_director import DirectorTests
        from agent.editorial.visuals import EditorialScript
        from agent.editorial.quality import audit_timeline
        case=DirectorTests('runTest');case.setUp()
        try:
            script=EditorialScript.model_validate(case.script.model_dump())
            timeline=case.timeline()
            locked=lock_script(script)
            audit_timeline(script,timeline,locked)
            changed=timeline.model_copy(deep=True)
            changed.words[0].provenance='estimated_phrase'
            with self.assertRaisesRegex(ValueError,'measured'):audit_timeline(script,changed,locked)
            changed=timeline.model_copy(deep=True)
            changed.durationInFrames=int(changed.words[-1].end*30)+3
            with self.assertRaisesRegex(ValueError,'hold'):audit_timeline(script,changed,locked)
        finally:case.tearDown()

    def test_action_motion_targets_exact_word_onsets_and_stays_within_layer(self):
        from types import SimpleNamespace
        from agent.editorial.models import Layer,Bounds,Word,Section
        from agent.editorial.choreography import choreograph_actions
        from agent.editorial.director import VisualSettings
        script,_=plan(script_for(['Character opened a chest.']),None,fixture_planner,{})
        eid=script.sentence_storyboard[0]['primary_entity_id']
        words=[Word(id=str(i),sectionId='s0',text=t,start=i*.4,end=i*.4+.3,provenance='provider',confidence=1)
            for i,t in enumerate(script.narration.split())]
        layer=Layer(id='actor',role='object',entityId=eid,assetId='a',bounds=Bounds(x=150,y=570,w=780,h=760),startFrame=0,endFrame=60)
        m={'words':words,'sections':[SimpleNamespace(id='s0')],'layers':[layer],'events':[],'diagnostics':{}}
        choreograph_actions(m,script,VisualSettings())
        self.assertEqual(m['events'][0].startFrame,12)
        self.assertTrue(all(layer.startFrame<=e.startFrame<e.endFrame<=layer.endFrame for e in m['events']))
        self.assertEqual(sum(e.dx for e in m['events']),0)
        self.assertEqual(sum(e.dy for e in m['events']),0)
        self.assertFalse(m['diagnostics']['actionChoreography']['articulatedActionAcceptance'])

if __name__=='__main__':unittest.main()
