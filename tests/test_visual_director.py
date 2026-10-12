"""Atomic timing and persistence regression tests through the real compiler."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from agent.editorial.director import Cue, Direction, VisualSettings, direct, validate_direction
from agent.editorial.models import Timeline, Entity as VisualEntity
from agent.editorial.assets import prepare, symbolic
from agent.editorial.audio import prepare_existing
from agent.editorial.planner import build
from agent.news_audio import synthesize
from agent.news_models import Script, Sentence, Entity
from tests.news_fixtures import FixtureTTS, subject_image


def story():
    text='Mira examined the diamond beside a microscope.'
    return Script(summary='A fictional demonstration',narration=text,sentences=[Sentence(id='s1',text=text,phrase='Mira examines a diamond',role='development',claim_ids=['c1'],entity_ids=['mira','diamond','microscope'])],entities=[
        Entity(id='mira',name='Mira',kind='person',identity='fictional',description='A fictional scientist'),
        Entity(id='diamond',name='Diamond',kind='object',description='An ordinary diamond'),
        Entity(id='microscope',name='Microscope',kind='object',description='A laboratory microscope')])


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.script=story()
    def tearDown(self):self.tmp.cleanup()
    def timeline(self,script=None,settings=None,direction=None):
        script=script or self.script;settings=settings or VisualSettings()
        audio=synthesize(script,self.root/'tts','edge_tts',engine=FixtureTTS())
        master,words,sections,diagnostics=prepare_existing(script,audio,self.root/'aligned')
        assets=[];entities=[]
        for entity in script.entities:
            path=self.root/(entity.id+'.png');subject_image(entity.id).save(path)
            a=prepare(entity,path,self.root/'assets',source='fixture illustration',license='test',attribution='test',factual=False)
            assets.append(a);entities.append(VisualEntity(id=entity.id,name=entity.name,identity=entity.identity,assetIds=[a.id],source=a.source))
        direction=direction or direct(script,words,settings=settings,diagnostics=diagnostics)
        return build(script,words,sections,entities,assets,master,self.root,'director-test',diagnostics,direction=direction,visual_settings=settings)
    def test_single_sentence_produces_three_exact_cues(self):
        m=self.timeline()
        self.assertEqual(len(m.beats),3)
        for eid,word in [('mira','Mira'),('diamond','diamond'),('microscope','microscope.')]:
            layer=next(l for l in m.layers if l.assetId and l.entityId==eid)
            onset=next(w.start for w in m.words if w.text==word)
            self.assertLessEqual(abs(layer.startFrame/30-onset),1/30)
        self.assertEqual(len([l for l in m.layers if l.assetId and l.endFrame==m.durationInFrames]),3)
    def test_persistence_across_sections_uses_one_asset_and_layer(self):
        s=self.script.model_copy(deep=True)
        second=Sentence(id='s2',text='The diamond remained beside the microscope.',phrase='The diamond remains',role='development',claim_ids=['c2'],entity_ids=['diamond','microscope'])
        s.sentences.append(second);s.narration+=' '+second.text
        m=self.timeline(s)
        self.assertEqual(len([l for l in m.layers if l.assetId and l.entityId=='diamond']),1)
        self.assertEqual(len([l for l in m.layers if l.assetId and l.entityId=='microscope']),1)
        self.assertTrue(m.transitions[-1].persist)
    def test_invalid_span_unknown_asset_and_early_secondary_rejected(self):
        good=direct(self.script,[]).model_dump()
        for mutate in [lambda x:x['cues'][0].update(phrase='unspoken'),lambda x:x['cues'][0].update(primaryEntityId='unknown'),lambda x:x['cues'][0].update(secondaryEntityIds=['diamond'])]:
            data=copy.deepcopy(good);mutate(data)
            with self.assertRaises(ValueError):validate_direction(Direction.model_validate(data),self.script,VisualSettings())
    def test_model_repair_and_fallback_preserve_original_script(self):
        original=self.script.model_dump();audit={};good=direct(self.script,[]).model_dump()
        llm=Mock(side_effect=[{'cues':[{'bad':True}]},good])
        result=direct(self.script,[],llm=llm,diagnostics=audit)
        self.assertEqual(len(result.cues),3);self.assertEqual(llm.call_count,2)
        self.assertEqual(audit['visualDirector']['mode'],'llm');self.assertEqual(original,self.script.model_dump())
        result=direct(self.script,[],llm=Mock(return_value={}),diagnostics=audit)
        self.assertEqual(audit['visualDirector']['mode'],'deterministic_fallback')
    def test_cue_coverage_and_layer_duration_boundaries(self):
        m=self.timeline()
        for a,b in zip(m.beats,m.beats[1:]):self.assertEqual(a.endFrame,b.startFrame)
        for event in m.events:
            for lid in event.targetIds:
                layer=next(l for l in m.layers if l.id==lid)
                self.assertGreaterEqual(event.startFrame,layer.startFrame);self.assertLessEqual(event.endFrame,layer.endFrame)
        self.assertEqual(m.beats[-1].endFrame,m.durationInFrames)
        data=m.model_dump();data['layers'][-1]['assetId']='missing'
        with self.assertRaises(ValueError):Timeline.model_validate(data)
    def test_one_subject_limit_and_persistence_disabled(self):
        m=self.timeline(settings=VisualSettings(maxSimultaneousSubjects=1,enableSubjectPersistence=False))
        layers=[l for l in m.layers if l.assetId]
        for first,second in zip(layers,layers[1:]):self.assertLessEqual(first.endFrame,second.startFrame)
    def test_missing_named_asset_is_disclosed(self):
        a=symbolic(self.script.entities[0],self.root)
        self.assertFalse(a.factual);self.assertIn('does not establish',a.fallback)
    def test_alignment_failure_has_explicit_provenance(self):
        from agent.editorial.audio import assemble
        from agent.news_models import NewsError
        audio=synthesize(self.script,self.root/'tts','edge_tts',engine=FixtureTTS())
        with patch('agent.editorial.audio.Aligner',side_effect=NewsError('Unavailable')):
            _,words,_,diagnostics=assemble(self.script,[audio.path],self.root/'fallback')
        self.assertTrue(all(w.provenance=='estimated_phrase' and w.confidence==0 for w in words))
        self.assertIn('ESTIMATED',diagnostics['alignmentWarnings'][0])
    def test_config_validation(self):
        for bad in ({'maxSimultaneousSubjects':4},{'syncToleranceMs':-1},{'unknown':True}):
            with self.assertRaises(ValueError):VisualSettings.model_validate(bad)

    def test_geographic_movement_replaces_location_and_preserves_object(self):
        text='The diamond moved from Kolkata to Dhaka.'
        s=Script(summary='A supplied transfer',narration=text,sentences=[Sentence(id='s1',text=text,phrase='A transfer',role='development',claim_ids=['c1'],entity_ids=['diamond','kolkata','dhaka'])],entities=[
            Entity(id='diamond',name='diamond',kind='object',description='The same object'),
            Entity(id='kolkata',name='Kolkata',kind='place',identity='real',description='Named origin'),
            Entity(id='dhaka',name='Dhaka',kind='place',identity='real',description='Named destination')])
        m=self.timeline(s)
        diamond=[l for l in m.layers if l.assetId and l.entityId=='diamond']
        self.assertEqual(len(diamond),1)
        origin=next(l for l in m.layers if l.assetId and l.entityId=='kolkata')
        destination=next(l for l in m.layers if l.assetId and l.entityId=='dhaka')
        self.assertEqual(origin.endFrame,destination.startFrame)
        self.assertEqual(m.beats[-1].template,'location_transfer')
        self.assertGreater(diamond[0].endFrame,destination.startFrame)
        self.assertTrue(any(e.type=='reframe' for e in m.events))

    def test_more_than_three_total_subjects_are_sequential(self):
        from agent.editorial.visuals import EditorialScript,EditorialSentence
        text='Mira carried the diamond past a microscope into the treasury.'
        entities=[*self.script.entities,Entity(id='treasury',name='treasury',kind='building',description='An anonymous treasury')]
        s=EditorialScript(summary='A fictional sequence',narration=text,entities=entities,sentences=[EditorialSentence(id='s1',text=text,phrase='A sequence',role='development',claim_ids=['c1'],entity_ids=[e.id for e in entities])])
        m=self.timeline(s)
        self.assertEqual(len(m.beats),4)
        visuals=[l for l in m.layers if l.assetId]
        for frame in {l.startFrame for l in visuals}:
            self.assertLessEqual(sum(l.startFrame<=frame<l.endFrame for l in visuals),3)

    def test_rate_change_reconciles_to_actual_audio(self):
        import wave
        normal=self.timeline()
        class Slower(FixtureTTS):
            def generate_narration(self,points,output):
                clips=super().generate_narration(points,output)
                for clip in clips:
                    with wave.open(str(clip.audio_path),'rb') as f:params=f.getparams();data=f.readframes(f.getnframes())
                    with wave.open(str(clip.audio_path),'wb') as f:
                        f.setparams(params);f.setframerate(params.framerate//2);f.writeframes(data)
                    for word in clip.word_timings:word.start*=2;word.end*=2
                    clip.duration*=2
                return clips
        with patch(__name__+'.FixtureTTS',Slower):slow=self.timeline()
        before=next(l for l in normal.layers if l.assetId and l.entityId=='microscope')
        after=next(l for l in slow.layers if l.assetId and l.entityId=='microscope')
        self.assertGreater(after.startFrame,before.startFrame*1.8)
        cue=next(w for w in slow.words if w.text=='microscope.')
        self.assertLessEqual(abs(after.startFrame/30-cue.start),1/30)

    def test_transition_conflicts_rejected(self):
        m=self.timeline().model_dump()
        event=next(e for e in m['events'] if e['type']=='settle')
        duplicate=copy.deepcopy(event);duplicate['id']='conflicting'
        m['events'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'Conflicting atomic scale'):Timeline.model_validate(m)

    def test_ordinal_script_spans_and_separate_captions(self):
        m=self.timeline()
        for row in m.diagnostics['atomicStoryboard']['beats']:
            start,end=row['scriptSpan'];self.assertEqual(m.script[start:end],row['phrase'])
        self.assertTrue(m.narrationDriven)
        self.assertFalse(any(l.role=='phrase' for l in m.layers))

    def test_named_object_candidates_are_ranked_and_provenance_retained(self):
        from agent.editorial.assets import acquire
        from agent.news_references import ReferencePhoto
        e=Entity(id='artifact',name='Named artifact',kind='object',identity='real',description='A specific historical object')
        text='The Named artifact was displayed.'
        s=Script(summary='An artifact',narration=text,entities=[e],sentences=[Sentence(id='s1',text=text,phrase='An artifact',role='development',claim_ids=['c1'],entity_ids=[e.id])])
        path=self.root/'reference.png';subject_image('diamond').save(path)
        ref=ReferencePhoto(str(path),'https://commons.wikimedia.org/wiki/File:Example','CC BY 4.0','Fixture author','https://www.wikidata.org/wiki/Q1')
        review=Mock(return_value={'identityMatch':True,'relevant':True,'watermark':False,'confidence':.95});audit={}
        with patch('agent.news_references.ReferencePhotos.find',return_value=[ref,ref]):
            _,assets=acquire(s,self.root/'ranked',visual_review=review,diagnostics=audit)
        self.assertEqual(review.call_count,1);self.assertTrue(assets[0].factual)
        self.assertEqual(assets[0].license,'CC BY 4.0')
        self.assertEqual(audit['assetAcquisition']['assets'][0]['route'],'identity_linked_ranked')

    def test_existing_input_modes_explicitly_route_the_editorial_preset(self):
        from agent.orchestrator import AgentOrchestrator
        orchestrator=AgentOrchestrator.__new__(AgentOrchestrator)
        orchestrator._llm_provider=None;orchestrator._llm_model=None
        for mode in ('article','topic','story','news'):
            with self.subTest(mode=mode),patch('agent.news_script.NewsLLM'),patch('agent.editorial.pipeline.run_editorial',return_value='directed') as run:
                self.assertEqual(orchestrator.run('Supplied text',content_mode=mode,visual_preset='reference_editorial',speed='+20%'),'directed')
                self.assertEqual(run.call_args.kwargs['speed'],'+20%')
                if mode=='story':self.assertEqual(run.call_args.kwargs['source_policy'],'supplied')
        with patch('agent.news_script.NewsLLM'),patch('agent.news_pipeline.run_news',return_value='legacy') as run:
            self.assertEqual(orchestrator.run('Topic',content_mode='news',visual_preset='default'),'legacy')
            self.assertEqual(run.call_args.kwargs['visual_preset'],'default')

    def test_strict_alignment_does_not_estimate(self):
        import config
        from agent.editorial.audio import assemble
        from agent.news_models import NewsError
        audio=synthesize(self.script,self.root/'tts','edge_tts',engine=FixtureTTS())
        with patch.object(config,'NARRATION_VISUAL_SETTINGS',{'allowPhraseTimingFallback':False}),patch('agent.editorial.audio.Aligner',side_effect=NewsError('Unavailable')):
            with self.assertRaisesRegex(NewsError,'Unavailable'):
                assemble(self.script,[audio.path],self.root/'strict')


if __name__=='__main__':unittest.main()
