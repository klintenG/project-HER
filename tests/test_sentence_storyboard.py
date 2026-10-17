import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image,ImageDraw
from agent.news_models import Entity,Sentence,Script,NewsError
from agent.editorial import sentence_storyboard as sb
from agent.editorial.assets import acquire
from agent.editorial.models import Word,Section
from agent.editorial.planner import build
from agent.editorial.director import VisualSettings
from utils.job_trace import JobTrace
from utils.generation_diagnostics import export_reports
import config

STORIES=[
 ['Sisyphus was a clever king.','He cheated death.','Zeus decided to punish him.','Sisyphus pushed a boulder uphill.','The boulder rolled downhill.','He faced the task forever.'],
 ['The gods feared Fenrir.','They chained him.','He broke the chains.','They made a ribbon.','Tyr placed his hand in his jaws.','Fenrir bit the hand.','The ribbon restrained him.','A prophecy remained.'],
 ['A diamond was discovered.','A ruler owned it.','A ship transported it.','An army seized it.','It reached the crown.'],
 ['A ship entered a storm.','A fire broke out.','The crew rescued a sailor.','A building collapsed.','They found a mysterious object.']]


def script_for(lines):
    e=Entity(id='identity',name='Character',kind='person',identity='fictional',description='A brown-haired figure in blue historical clothing')
    ss=[Sentence(id=f's{i}',text=t,claim_ids=['c'],entity_ids=[e.id],phrase=' '.join(t.split()[:4]),role='development') for i,t in enumerate(lines)]
    return Script(summary='Fixture',narration=' '.join(lines),sentences=ss,entities=[e])


def fixture_planner(instruction,data):
    # Controlled semantic response tests orchestration, not a real model's quality.
    return {'sentences':[{'sentence_id':s['id'],'candidates':[dict(subject='Event '+s['id'],action=s['text'],important_objects=[],setting='story setting',emotion='neutral',state_change=s['text'],visual_focus=s['text'],description='An isolated connected cutout depicting '+s['text'],identity_ids=['identity'],relevance=.95,narrative_importance=.9,novelty=.9,readability=.9)]} for s in data['script']['sentences']]}


def review(*args):
    return dict(relevant=True,actionCorrect=True,objectsCorrect=True,portraitSubstitution=False,problems=[],subjectMatch=True,usable=True,geometricPlaceholder=False,contextAppropriate=True,subjectConfidence=.95,recognizable=True,sameClothingOrFur=True,distinct=True,duplicate_pairs=[],uncertain=False)


class SentenceStoryboardTests(unittest.TestCase):
    def test_punctuation_and_full_spoken_mapping(self):
        text='Dr. A. Smith paid 3.14 dollars. “Really?” Yes!'
        self.assertEqual(sb.split_spoken(text),['Dr. A. Smith paid 3.14 dollars.','“Really?”','Yes!'])
        self.assertEqual(sb.split_spoken('船沉了。船员获救！'),['船沉了。','船员获救！'])
        script=sb.segment(script_for([text]))
        self.assertEqual(script.narration,text)
        self.assertEqual(len(script.sentences),3)

    def test_all_stories_require_sentence_specific_tasks(self):
        for lines in STORIES:
            planned,_=sb.plan(sb.segment(script_for(lines)),None,fixture_planner,{})
            ids=[b['primary_entity_id'] for b in planned.sentence_storyboard]
            self.assertEqual(len(set(ids)),len(lines))
            self.assertTrue(all(b['continuity_references']==['identity'] for b in planned.sentence_storyboard))
            self.assertEqual([c.primaryEntityId for c in sb.direction(planned).cues],ids)
            self.assertEqual(planned.narration,' '.join(lines))

    def test_missing_or_repeated_concepts_rejected_before_images(self):
        def invalid(i,d):
            result=fixture_planner(i,d)
            for row in result['sentences']:row['candidates'][0]['visual_focus']='Same portrait'
            return result
        with self.assertRaises(NewsError):sb.plan(script_for(STORIES[0]),None,invalid,{})

    def test_actual_acquisition_and_render_plan_not_just_ids(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);script,_=sb.plan(script_for(STORIES[0]),None,fixture_planner,{})
            class Generator:
                async def subject(self,prompt,path):return await self.scene_subject(prompt,path)
                async def scene_subject(self,prompt,path,reference=None):
                    # Different shapes, not renamed files. Deliberately synthetic.
                    import hashlib
                    seed=int(hashlib.sha256(prompt.encode()).hexdigest()[:8],16)
                    im=Image.new('RGBA',(320,320));draw=ImageDraw.Draw(im)
                    draw.polygon([(40,40),(270,60),(seed%140+60,270)],fill=(seed%255,100,180,255));im.save(path)
                    return 'fixture:generated'
                action_subject=scene_subject
                real_subject=scene_subject
            class Processor:
                version='fixture'
                def process(self,source,dest,**kwargs):
                    import shutil
                    shutil.copyfile(source,dest);return {},'fixture'
            diag={}
            with patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',root/'cache'):
                entities,assets=acquire(script,root/'assets',image_generator=Generator(),processor=Processor(),visual_review=review,diagnostics=diag)
            metrics=sb.validate_assets(script,assets,diag['assetAcquisition'],review)
            self.assertEqual(metrics['distinctPrimaryVisuals'],6)
            words=[];sections=[];now=0
            for sentence in script.sentences:
                start=now;ids=[]
                for token in sentence.text.split():
                    wid='w'+str(len(words));ids.append(wid)
                    words.append(Word(id=wid,sectionId=sentence.id,text=token,start=now,end=now+.3,provenance='provider',confidence=1));now+=.3
                sections.append(Section(id=sentence.id,text=sentence.text,start=start,end=now,wordIds=ids))
            import wave,math,struct
            audio=root/'master.wav'
            with wave.open(str(audio),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
                wav.writeframes(b''.join(struct.pack('<h',int(4000*math.sin(2*math.pi*220*i/16000))) for i in range(round((now+.1)*16000))))
            m=build(script,words,sections,entities,assets,audio,root,'fixture',{},direction=sb.direction(script),visual_settings=VisualSettings())
            self.assertEqual(sb.validate_render(script,m)['primaryAssetsInRender'],6)
            missing=m.model_copy(deep=True);missing.layers=[l for l in missing.layers if l.assetId!=script.sentence_storyboard[0]['primary_asset_id']]
            with self.assertRaises(NewsError):sb.validate_render(script,missing)
            duplicate=copy.deepcopy(assets);primary=[a for a in duplicate if a.entityId.startswith('scene-')]
            primary[1].path=primary[0].path
            dup_result=sb.validate_assets(script,duplicate,diag['assetAcquisition'],review)
            self.assertTrue(dup_result['acceptancePassed'])
            self.assertFalse(dup_result['fullyCompliant'])
            self.assertGreater(dup_result['imagesRejectedForDuplication'],0)

    def test_secondary_cutouts_preserved_without_duplicating_conditioned_primary_identity(self):
        e1=Entity(id='hero',name='Hero',kind='person',identity='fictional',description='A hero in bronze armor')
        e2=Entity(id='relic',name='Relic',kind='object',identity='generic',description='An ancient glowing crown')
        s=Sentence(id='s0',text='The hero lifted the ancient relic.',claim_ids=['c'],entity_ids=['hero','relic'],phrase='Hero lifted relic',role='development')
        script=Script(summary='Fixture',narration=s.text,sentences=[s],entities=[e1,e2])
        def planner(i,d):
            return {'sentences':[{'sentence_id':'s0','candidates':[dict(
                subject='Hero lifting relic',action='lifting',important_objects=['relic'],setting='hall',
                emotion='focused',state_change='lifted',visual_focus='Hero lifting relic',
                description='An isolated connected cutout depicting hero lifting relic',
                identity_ids=['hero'],secondary_ids=['hero','relic'],
                relevance=.95,narrative_importance=.9,novelty=.9,readability=.9)]}]}
        planned,_=sb.plan(script,None,planner,{})
        beat=planned.sentence_storyboard[0]
        # 'hero' is already conditioned into the primary scene cutout, so only 'relic' remains secondary
        self.assertEqual(beat['continuity_references'],['hero'])
        self.assertEqual(beat['secondary_entity_ids'],['relic'])
        self.assertEqual(beat['composition_type'],'multi_cutout')

    def test_failure_reports_are_sanitized_and_retrievable_files(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(config,'DIAGNOSTICS_RUNS_DIR',Path(root)/'runs'):
                trace=JobTrace(Path(root)/'job_trace.json','job_test_01')
                with self.assertRaises(RuntimeError):
                    with trace.span('end_to_end'):
                        with trace.span('image_provider_wait',entity_id='scene-1',attempt=1):raise RuntimeError('private token https://secret.example/x')
                paths=export_reports(root,'job_test_01')
                self.assertTrue(all(p.exists() for p in paths))
                self.assertTrue((Path(root)/'runs'/'job_test_01'/'generation_diagnostics.json').is_file())
                data=json.loads(paths[0].read_text())
                txt=paths[1].read_text()
                self.assertEqual(data['outcome'],'failed');self.assertEqual(data['peak_image_provider_concurrency'],1)
                for section in ('## A. Generation Summary','## B. Stage Duration Breakdown','## C. Individual Image-Generation Times',
                                '## D. Concurrency Analysis','## E. Critical Path','## F. Bottleneck Ranking',
                                '## G. Errors and Retries','## H. Scene-Level Visual Quality Report','## I. Recommended Next Investigation'):
                    self.assertIn(section,txt)
                self.assertNotIn('private token',paths[0].read_text()+txt)
                self.assertNotIn('secret.example',paths[0].read_text()+txt)
                import web_ui
                client=web_ui.app.test_client()
                r_json=client.get('/api/diagnostics/job_test_01/json')
                r_txt=client.get('/api/diagnostics/job_test_01/text')
                r_cov=client.get('/api/diagnostics/job_test_01/coverage')
                r_tl=client.get('/api/diagnostics/job_test_01/timeline')
                self.assertEqual(r_json.status_code,200)
                self.assertEqual(r_txt.status_code,200)
                self.assertEqual(r_cov.status_code,200)
                self.assertEqual(r_tl.status_code,200)
                self.assertEqual(len(paths),4)
                self.assertIn(b'PROJECTHER GENERATION DIAGNOSTIC REPORT',r_txt.data)

    def test_real_person_story_separates_supporting_identity_from_scene_primary(self):
        e1=Entity(id='kendrick',name='Kendrick Lamar',kind='person',identity='real',description='American rapper')
        e2=Entity(id='drake',name='Drake',kind='person',identity='real',description='Canadian rapper')
        s1=Sentence(id='s1',text='Kendrick Lamar recorded the verse in a studio.',claim_ids=['c1'],entity_ids=['kendrick'],phrase='Recorded the verse',role='hook')
        s2=Sentence(id='s2',text='The track topped the global music charts.',claim_ids=['c2'],entity_ids=['kendrick','drake'],phrase='Topped global charts',role='close')
        script=Script(summary='Hip-hop feud',narration=' '.join([s1.text,s2.text]),sentences=[s1,s2],entities=[e1,e2])
        def planner(i,d):
            return {'sentences':[
                {'sentence_id':'s1','candidates':[dict(
                    subject='Studio condenser microphone',action='recording a vocal verse',important_objects=['condenser microphone'],
                    setting='recording studio',emotion='intense',state_change='verse recorded',visual_focus='Studio microphone on boom arm',
                    description='An isolated studio condenser microphone with pop filter on a boom arm.',
                    identity_ids=['kendrick'],secondary_ids=[],relevance=.95,narrative_importance=.9,novelty=.9,readability=.95)]},
                {'sentence_id':'s2','candidates':[dict(
                    subject='Number one chart trophy',action='rising to number one on the charts',important_objects=['chart trophy'],
                    setting='editorial stage',emotion='triumphant',state_change='reached number one',visual_focus='Number one music chart trophy',
                    description='An isolated metallic number-one music chart award trophy.',
                    identity_ids=['kendrick','drake'],secondary_ids=[],relevance=.95,narrative_importance=.9,novelty=.9,readability=.95)]},
            ]}
        planned,_=sb.plan(script,None,planner,{})
        self.assertEqual(len(planned.sentence_storyboard),2)
        for beat in planned.sentence_storyboard:
            self.assertEqual(beat['continuity_references'],[])
            self.assertFalse(beat['primary_asset_request']['allow_identity_conditioning'])
            self.assertTrue(beat['primary_asset']['required'])
            self.assertIn('kendrick',beat['secondary_entity_ids'])

    def test_split_screen_normalization_and_rejected_unverified_primary(self):
        e1=Entity(id='kendrick',name='Kendrick Lamar',kind='person',identity='fictional',description='A man in a black hoodie and cap')
        e2=Entity(id='drake',name='Drake',kind='person',identity='fictional',description='A man in a dark leather jacket')
        s=Sentence(id='s1',text='What began as a battle transformed into an unforgettable rivalry.',claim_ids=['c'],entity_ids=['kendrick','drake'],phrase='Unforgettable rivalry',role='close')
        script=Script(summary='Fixture',narration=s.text,sentences=[s],entities=[e1,e2])
        def planner(i,d):
            return {'sentences':[{'sentence_id':'s1','candidates':[dict(
                subject='Kendrick Lamar and Drake',action='standing on opposite sides of a split-screen composition',
                important_objects=[],setting='abstract dark background',emotion='tense',state_change='cementing rivalry',
                visual_focus='contrast between the two figures',
                description='Kendrick Lamar and Drake are depicted in a split-screen composition representing the rivalry.',
                identity_ids=['kendrick','drake'],secondary_ids=[],
                relevance=.95,narrative_importance=.9,novelty=.85,readability=.9)]}]}
        planned,_=sb.plan(script,None,planner,{})
        beat=planned.sentence_storyboard[0]
        self.assertEqual(beat['continuity_references'],['kendrick'])
        self.assertEqual(beat['secondary_entity_ids'],['drake'])
        self.assertEqual(beat['composition_type'],'multi_cutout')
        self.assertNotIn('split-screen',beat['description'].casefold())

        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            class Generator:
                async def subject(self,prompt,path):return await self.scene_subject(prompt,path)
                async def scene_subject(self,prompt,path,reference=None):
                    im=Image.new('RGBA',(320,320));draw=ImageDraw.Draw(im)
                    draw.rectangle((60,50,250,270),fill=(80,140,220,255));im.save(path)
                    return 'fixture:generated'
                action_subject=scene_subject
                real_subject=scene_subject
            class Processor:
                version='fixture'
                def process(self,source,dest,**kwargs):
                    import shutil
                    shutil.copyfile(source,dest);return {},'fixture'
            def strict_sentence_review(instruction,data,paths):
                if 'Validate this isolated transparent foreground cutout' in instruction:
                    return dict(relevant=False,actionCorrect=False,objectsCorrect=False,portraitSubstitution=True,problems=['Background studio omitted'])
                return review(instruction,data,paths)
            diag={}
            with patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',root/'cache'):
                entities,assets=acquire(planned,root/'assets',image_generator=Generator(),processor=Processor(),visual_review=strict_sentence_review,diagnostics=diag)
            self.assertTrue(len(assets)>=1)
            primary_asset=next(a for a in assets if a.entityId.startswith('scene-'))
            self.assertIsNotNone(primary_asset)
            audit_record=next(r for r in diag['assetAcquisition']['assets'] if r['entityId']==primary_asset.entityId)
            self.assertTrue(audit_record.get('degraded'))
            self.assertIn('fallbackMethod',audit_record)
            val=sb.validate_assets(planned,assets,diag['assetAcquisition'],review)
            self.assertTrue(val['acceptancePassed'])
            self.assertFalse(val['fullyCompliant'])
            self.assertIn('s1',val['degradedSentences'])

    def test_fictional_standalone_object_primary_disables_character_identity_conditioning(self):
        demon=Entity(id='bhasmasura',name='Bhasmasura',kind='person',identity='fictional',description='A powerful demon with dark muscular build')
        s=Sentence(id='s9',text='In a single second, Bhasmasura turned himself into ashes.',claim_ids=['c9'],entity_ids=['bhasmasura'],phrase='Turned into ashes',role='development')
        script=Script(summary='Mythology',narration=s.text,sentences=[s],entities=[demon])
        def planner(i,d):
            return {'sentences':[{'sentence_id':'s9','candidates':[dict(
                subject='Pile of fine grey ash',action='Settling on the ground',
                important_objects=['Ash','Scattered embers'],setting='stage floor',emotion='finality',state_change='destruction',
                visual_focus='Pile of ash',
                description='A small, concentrated pile of fine grey ash resting on the stage floor.',
                identity_ids=['bhasmasura'],secondary_ids=[],
                relevance=.95,narrative_importance=.95,novelty=.9,readability=.9)]}]}
        planned,_=sb.plan(script,None,planner,{})
        beat=planned.sentence_storyboard[0]
        self.assertEqual(beat['continuity_references'],[])
        self.assertFalse(beat['primary_asset_request']['allow_identity_conditioning'])
        self.assertEqual(beat['primary_subject_type'],'object')
        self.assertNotIn('Identity continuity:',beat['description'])
        self.assertNotIn('Identity continuity:',beat['image_generation_prompt'])
        self.assertIn('bhasmasura',beat['secondary_entity_ids'])

        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            captured_prompts=[]
            captured_references=[]
            class Generator:
                async def subject(self,prompt,path):return await self.scene_subject(prompt,path)
                async def scene_subject(self,prompt,path,reference=None):
                    captured_prompts.append(prompt)
                    captured_references.append(reference)
                    im=Image.new('RGBA',(320,320),(128,128,128,255));im.save(path)
                    return 'fixture:generated'
                action_subject=scene_subject
                real_subject=scene_subject
            class Processor:
                version='fixture'
                def process(self,source,dest,**kwargs):
                    import shutil
                    shutil.copyfile(source,dest);return {},'fixture'
            diag={}
            with patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',root/'cache'):
                entities,assets=acquire(planned,root/'assets',image_generator=Generator(),processor=Processor(),visual_review=review,diagnostics=diag)
            self.assertEqual(len(assets),2)
            primary_asset=next(a for a in assets if a.entityId.startswith('scene-'))
            self.assertIsNotNone(primary_asset)
            # Find the generator call for the primary scene asset
            scene_prompt=next(p for p in captured_prompts if 'Pile of ash' in p)
            scene_ref=captured_references[captured_prompts.index(scene_prompt)]
            self.assertIsNone(scene_ref)
            self.assertNotIn('Match the supplied established character reference',scene_prompt)
            self.assertNotIn('Identity continuity:',scene_prompt)
            self.assertIn('Pile of ash',scene_prompt)

    def test_sentence_primary_relevance_fallback_after_bounded_retries(self):
        god=Entity(id='gods',name='The Gods',kind='person',identity='fictional',description='Immortal celestial beings')
        s=Sentence(id='s6',text='The other gods burst into sudden laughter at the festive spectacle.',claim_ids=['c6'],entity_ids=['gods'],phrase='Burst into laughter',role='development')
        script=Script(summary='Festival',narration=s.text,sentences=[s],entities=[god])
        def planner(i,d):
            return {'sentences':[{'sentence_id':'s6','candidates':[dict(
                subject='Traditional brass ceremonial bell',action='ringing during festive celebration',
                important_objects=['brass ceremonial bell'],setting='temple courtyard',emotion='joyful',state_change='celebration',
                visual_focus='brass ceremonial bell',
                description='An ornate brass ceremonial bell sitting next to a small wooden festival drum.',
                identity_ids=['gods'],secondary_ids=[],
                relevance=.95,narrative_importance=.9,novelty=.85,readability=.9)]}]}
        planned,_=sb.plan(script,None,planner,{})
        beat=planned.sentence_storyboard[0]
        self.assertEqual(beat['primary_subject_type'],'object')

        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            class Generator:
                async def subject(self,prompt,path):return await self.scene_subject(prompt,path)
                async def scene_subject(self,prompt,path,reference=None):
                    im=Image.new('RGBA',(320,320),(180,140,50,255));im.save(path)
                    return 'fixture:generated'
                action_subject=scene_subject
                real_subject=scene_subject
            class Processor:
                version='fixture'
                def process(self,source,dest,**kwargs):
                    import shutil
                    shutil.copyfile(source,dest);return {},'fixture'
            def skeptical_review(instruction,data,paths):
                if 'Validate this isolated transparent foreground cutout' in instruction:
                    return dict(relevant=False,actionCorrect=True,objectsCorrect=False,portraitSubstitution=False,
                                problems=['The sentence describes laughter, which has no direct narrative connection to a bell.'])
                return review(instruction,data,paths)
            diag={}
            with patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',root/'cache'):
                entities,assets=acquire(planned,root/'assets',image_generator=Generator(),processor=Processor(),visual_review=skeptical_review,diagnostics=diag)
            primary_asset=next(a for a in assets if a.entityId.startswith('scene-'))
            self.assertIsNotNone(primary_asset)
            validated=sb.validate_assets(planned,assets,diag['assetAcquisition'],review)
            self.assertTrue(validated['acceptancePassed'])
            self.assertGreaterEqual(validated['fallbackAttempts'],1)


