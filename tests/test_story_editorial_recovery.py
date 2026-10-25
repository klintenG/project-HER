"""Bounded editorial repairs retain evidence and apply the correct origin policy."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from automation.autopilot_store import Registry
from agent.portfolio_store import SQLiteStore
from automation.autonomous_story_director import AutonomousStoryDirector,Script,Editorial
from automation.autopilot_config import Settings

class StoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.registry=Registry(SQLiteStore(Path(self.tmp.name)/'state.sqlite3'))
        self.story={'story_id':'fixture','story_origin':'ORIGINAL_FICTION','title':'The clockmaker',
            'major_plot_events':['clock stops','maker repairs it','town wakes'],'ending':'The town wakes'}
        self.registry.store.set('story:fixture',self.story)
        self.script=Script(narration=' '.join(['The clockmaker repaired the clock and saved the town.']*12),
            hook_text='The clock that saved everyone',setup='clock stops',conflict='town sleeps',
            escalation='time runs out',climax='clock repaired',resolution='town wakes')
        self.good=Editorial(passed=True,coherence=True,complete_arc=True,source_faithful=True,visual_ending=True,feedback='Complete')

    def director(self,outputs):
        self.calls=[];iterator=iter(outputs)
        def ask(task,prompt,schema):
            self.calls.append((task,prompt))
            value=next(iterator)
            if isinstance(value,Exception):raise value
            return value
        return AutonomousStoryDirector(Settings(max_script_revisions=1),self.registry,SimpleNamespace(ask=ask,usage=[]))

    def test_repair_receives_feedback_and_retains_both_attempts(self):
        bad=self.good.model_copy(update={'passed':False,'complete_arc':False,'feedback':'Speak the clock repair before the town wakes'})
        director=self.director([self.script,bad,self.script,self.good])
        result=director.write(self.story)
        self.assertEqual(len(result['editorial_attempts']),2)
        self.assertIn('Speak the clock repair',self.calls[2][1])
        self.assertIn('ORIGINAL_FICTION',self.calls[1][1])
        self.assertIn('historical/mythological accuracy are not required',self.calls[1][1])

    def test_final_error_contains_actual_rejection_and_saved_drafts(self):
        bad=self.good.model_copy(update={'passed':False,'source_faithful':False,'feedback':'The ending contradicts the selected arc'})
        director=self.director([self.script,bad,self.script,bad])
        with self.assertRaisesRegex(ValueError,'2 attempts:.*ending contradicts'):
            director.write(self.story)
        row=self.registry.store.get('story:fixture')
        self.assertEqual(len(row['editorial_attempts']),2)
        self.assertIn('script',row['editorial_attempts'][0])

    def test_traditional_narrative_requires_retrieved_evidence_and_same_variant(self):
        self.story.update(story_origin='MYTHOLOGY',source_evidence=[{'url':'fixture','text':'A supported version'}])
        self.director([self.script,self.good]).write(self.story)
        self.assertIn('retrieved source_evidence',self.calls[1][1])
        self.assertIn('not a different remembered variant',self.calls[1][1])
        self.assertIn('A supported version',self.calls[1][1])

    def test_cost_ceiling_is_not_retried_as_invalid_script(self):
        director=self.director([ValueError('Story LLM call ceiling reached')])
        with self.assertRaisesRegex(ValueError,'call ceiling'):director.write(self.story)
        self.assertEqual(len(self.calls),1)

    def test_schema_failure_reports_the_field_without_echoing_narration(self):
        from automation.autonomous_story_director import parse_structured
        import json
        invalid=self.script.model_dump();invalid['hook_text']='This hook has far too many words to fit in the allowed title'
        with self.assertRaisesRegex(ValueError,'Hook must have') as caught:
            parse_structured(json.dumps(invalid),Script)
        self.assertNotIn(invalid['narration'],str(caught.exception))
