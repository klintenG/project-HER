"""Source-grounded people, image tiers, alpha cutouts and spoken visual cues."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,MagicMock,patch
from PIL import Image
import config
from agent.news_models import Entity,Sentence,Script,Source,Claim,Evidence,NewsError
from agent.news_references import ReferencePhoto
from agent.cutout_processor import CutoutProcessor
from agent.editorial.assets import acquire
from agent.editorial.visuals import plan_visuals,anchor_index
from agent.editorial.people import People
from tests.news_fixtures import subject_image


def story():
    person=Entity(id='person',name='Example Person',kind='person',identity='real',description='Example Person in a complete portrait with visible torso')
    sentences=[Sentence(id='s1',text='Example Person arrived for lunch.',phrase='Arrived for lunch',claim_ids=['c1'],entity_ids=['person'],role='hook'),
        Sentence(id='s2',text='Coffee followed the lunch meeting.',phrase='Coffee after lunch',claim_ids=['c2'],entity_ids=['person'],role='development')]
    return Script(summary='Fixture meal',narration=' '.join(s.text for s in sentences),entities=[person],sentences=sentences)


class EditorialVisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patches=[patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',self.root/'images'),patch.object(config,'NEWS_CUTOUT_CACHE',self.root/'cutouts'),
                      patch('utils.provider_admission.ProviderAdmission.wait',new_callable=AsyncMock)]
        for p in self.patches:p.start()
        self.image=self.root/'reference.png';subject_image('mira').save(self.image)
        self.reference=ReferencePhoto(str(self.image),'https://commons.wikimedia.org/wiki/File:Portrait.png','Public domain','Fixture artist','https://www.wikidata.org/wiki/Q123')
        self.people=MagicMock();self.people.resolve.return_value={'kind':'real','sources':[self.reference.entity_url],'references':[self.reference]}
        self.generator=MagicMock()
        async def create(prompt,path,reference=None):subject_image('mira').save(path);return 'replicate:'+str(config.NEWS_REFERENCE_IMAGE_MODEL if reference else config.EDITORIAL_SUPPORT_IMAGE_MODEL)
        self.generator.subject=AsyncMock(side_effect=create);self.generator.real_subject=AsyncMock(side_effect=create)
        self.review=MagicMock(return_value={'sameLikeness':True,'singlePerson':True,'bodyPreserved':True,'confidence':.94,'problems':[],'subjectMatch':True,'usable':True,'geometricPlaceholder':False,'contextAppropriate':True,'subjectConfidence':.95})
        review_patch=patch('agent.editorial.vision.VisualReview',return_value=self.review);review_patch.start();self.patches.append(review_patch)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def assets(self,**kwargs):
        return acquire(story().model_copy(update={'sentences':story().sentences[:1],'narration':story().sentences[0].text}),self.root/'job',people=self.people,image_generator=self.generator,visual_review=self.review,**kwargs)
    def failed_photo_processor(self):
        real=CutoutProcessor()
        def process(src,dest,**kwargs):
            if Path(src)==self.image:raise NewsError('Reference segmentation rejected opaque background')
            return real.process(src,dest,**kwargs)
        return MagicMock(process=MagicMock(side_effect=process))

    def test_available_real_portrait_is_an_alpha_cutout_without_ai(self):
        _,assets=self.assets()
        self.assertTrue(assets[0].alpha);self.assertTrue(assets[0].factual)
        self.assertEqual(assets[0].role,'portrait')
        self.generator.real_subject.assert_not_called();self.generator.subject.assert_not_called()
        image=Image.open(assets[0].path)
        self.assertLess(image.getchannel('A').getextrema()[0],255)

    def test_premium_fallback_checks_reference_and_caches_only_accepted_likeness(self):
        diagnostics={};_,assets=self.assets(processor=self.failed_photo_processor(),diagnostics=diagnostics)
        self.assertTrue(assets[0].alpha);self.assertFalse(assets[0].factual)
        self.assertIn('reference likeness reviewed',assets[0].fallback)
        self.assertEqual(self.generator.real_subject.call_count,1);self.generator.subject.assert_not_called()
        self.assertEqual(self.review.call_args.args[2][0],self.reference.path)
        self.assertEqual(diagnostics['assetAcquisition']['assets'][0]['route'],'premium_reference_illustration')
        self.assets(processor=self.failed_photo_processor())
        self.assertEqual(self.generator.real_subject.call_count,1);self.assertEqual(self.review.call_count,1)

    def test_wrong_likeness_gets_bounded_retries_then_disclosed_illustration(self):
        self.review.return_value={'sameLikeness':False,'singlePerson':True,'bodyPreserved':True,'confidence':.2,'problems':['Wrong face'],'subjectMatch':True,'usable':True,'geometricPlaceholder':False,'contextAppropriate':True,'subjectConfidence':.95}
        _,assets=self.assets(processor=self.failed_photo_processor())
        self.assertEqual(self.generator.real_subject.call_count,2)
        self.generator.subject.assert_called_once()
        self.assertFalse(assets[0].factual)
        self.assertEqual(assets[0].fallback,'AI illustration; identity/likeness not verified')
        cached=[json.loads(p.read_text()) for p in (self.root/'images').glob('*/review.json')]
        self.assertEqual(len(cached),1)
        self.assertFalse(cached[0]['identityVerified'])
        self.assertNotIn('visualReview',cached[0])
        audit=json.loads((self.root/'job'/'asset_acquisition.json').read_text())
        self.assertEqual(len(audit['assets'][0]['rejectedAttempts']),2)
        self.assertEqual(audit['assets'][0]['route'],'unverified_identity_ai_illustration')

    def test_cutout_retry_zooms_out_and_preserves_rejected_raw_attempt(self):
        calls=[]
        async def create(prompt,path):
            calls.append(prompt)
            image=subject_image('mira')
            if len(calls)<=2:
                from PIL import ImageDraw
                ImageDraw.Draw(image).rectangle((0,180,200,300),fill='blue')
            image.save(path);return 'fixture'
        self.generator.subject.side_effect=create
        script=story();script.entities[0].identity='fictional'
        processor=CutoutProcessor(segmenter=lambda image,model:image)
        _,assets=acquire(script,self.root/'retry',processor=processor,image_generator=self.generator)
        self.assertEqual(len(calls),3)
        self.assertIn('20 percent empty margin',calls[0])
        self.assertIn('fresh zoomed-out composition',calls[1])
        self.assertIn('Subject touches image edge',calls[1])
        self.assertEqual(len(list((self.root/'retry').glob('*-generated-*.png'))),3)
        self.assertTrue(assets[0].alpha)

    def test_exhausted_cutouts_use_subject_label_without_geometric_placeholder(self):
        from agent.cutout_processor import CutoutQualityError
        script=story();script.entities[0]=Entity(id='person',name='Cup',kind='object',identity='generic',description='One ceramic cup')
        processor=MagicMock();processor.process.side_effect=CutoutQualityError('Subject touches image edge')
        _,assets=acquire(script,self.root/'failed',processor=processor,image_generator=self.generator)
        self.assertIn('Subject name only',assets[0].fallback)
        self.assertEqual(self.generator.subject.call_count,config.NEWS_ASSET_RETRIES+1)
        self.assertFalse(list((self.root/'failed').glob('*-symbol.svg')))

    def test_missing_real_emu_photo_uses_reviewed_illustration_instead_of_cube(self):
        text='In 1932, emus damaged Australian farms.'
        script=Script(summary='Emu War',narration=text,entities=[Entity(id='emu',name='Emus',kind='animal',identity='real',description='Large Australian flightless birds with long necks and legs')],sentences=[Sentence(id='s1',text=text,phrase='Emus on farms',role='context',claim_ids=['c1'],entity_ids=['emu'])])
        audit={}
        with patch('agent.news_references.ReferencePhotos.find',return_value=[]):
            _,assets=acquire(script,self.root/'emu',image_generator=self.generator,visual_review=self.review,diagnostics=audit)
        self.assertEqual(len(assets),1);self.assertTrue(assets[0].alpha);self.assertFalse(assets[0].factual)
        self.assertNotEqual(assets[0].preparation,'symbolic')
        self.assertIn('AI contextual illustration',assets[0].fallback)
        self.assertEqual(audit['assetAcquisition']['assets'][0]['route'],'contextual_ai_after_missing_reference')
        prompt=self.generator.subject.call_args.args[0]
        self.assertIn('1932',prompt);self.assertIn('single animal',prompt);self.assertIn('Never use a cube',prompt)
        self.assertNotIn('recognizable facial features',prompt)
        self.assertFalse(list((self.root/'emu').glob('*-symbol.svg')))

    def test_transient_visual_review_rechecks_same_image_without_regeneration(self):
        self.review.side_effect=[TimeoutError('Temporary vision connection'),copy.deepcopy(self.review.return_value)]
        script=story();script.entities[0].identity='fictional'
        _,assets=acquire(script,self.root/'review-recovery',image_generator=self.generator,visual_review=self.review)
        self.generator.subject.assert_called_once();self.assertEqual(self.review.call_count,2)
        self.assertTrue(assets[0].alpha)

    def test_generated_geometric_or_unrelated_image_is_rejected_and_regenerated(self):
        good=copy.deepcopy(self.review.return_value)
        bad={**good,'subjectMatch':False,'geometricPlaceholder':True,'problems':['A cube is not an emu']}
        self.review.side_effect=[bad,good]
        script=story();script.entities[0]=Entity(id='person',name='Emu',kind='animal',identity='generic',description='One emu')
        _,assets=acquire(script,self.root/'qa-retry',image_generator=self.generator,visual_review=self.review)
        self.assertEqual(self.generator.subject.call_count,2)
        self.assertIn('A cube is not an emu',self.generator.subject.call_args.args[0])
        self.assertNotEqual(assets[0].preparation,'symbolic')
        accepted=[json.loads(p.read_text()) for p in (self.root/'images').glob('*/review.json')]
        self.assertEqual(len(accepted),1);self.assertFalse(accepted[0]['subjectReview']['geometricPlaceholder'])

    def test_plausible_ai_illustration_survives_uncertain_review(self):
        uncertain={**self.review.return_value,'subjectConfidence':.3,'contextAppropriate':False,'problems':['Exact historical details uncertain']}
        self.review.return_value=uncertain
        script=story();script.entities[0]=Entity(id='emu',name='Emu',kind='animal',identity='real',description='Large Australian flightless bird')
        with patch('agent.news_references.ReferencePhotos.find',return_value=[]):
            _,assets=acquire(script,self.root/'uncertain',image_generator=self.generator,visual_review=self.review)
        self.assertEqual(len(assets),1)
        self.assertFalse(assets[0].factual)
        self.assertIn('not verified',assets[0].fallback)
        self.assertNotEqual(assets[0].preparation,'symbolic')

    def test_rejected_ai_subject_uses_final_labelled_rescue(self):
        self.review.return_value={**self.review.return_value,'subjectMatch':False,'geometricPlaceholder':True,'problems':['Unrelated box']}
        script=story();script.entities[0]=Entity(id='emu',name='Emu',kind='animal',identity='generic',description='Large Australian flightless bird')
        _,assets=acquire(script,self.root/'rescue',image_generator=self.generator,visual_review=self.review)
        self.assertEqual(len(assets),1)
        self.assertFalse(assets[0].factual)
        self.assertIn('Approximate AI illustration',assets[0].fallback)
        self.assertGreaterEqual(self.generator.subject.call_count,config.NEWS_ASSET_RETRIES+1)
        self.assertTrue(list((self.root/'rescue').glob('*-rescue.png')))

    def test_review_outage_uses_generated_asset_without_fake_identity(self):
        self.review.side_effect=TimeoutError('vision offline')
        script=story();script.entities[0]=Entity(id='emu',name='Emu',kind='animal',identity='generic',description='Large Australian flightless bird')
        _,assets=acquire(script,self.root/'review-outage',image_generator=self.generator,visual_review=self.review)
        self.assertEqual(len(assets),1)
        self.assertFalse(assets[0].factual)
        self.assertIn('not independently verified',assets[0].fallback)

    def test_longer_visual_plan_can_acquire_more_than_eight_relevant_images(self):
        from agent.editorial.images import EditorialImages
        names=['Emu','Fence','Wheat','Farm','Soldier','Machine gun','Truck','Ammunition','Farmer','Field']
        entities=[Entity(id='visual-'+str(i),name=name,kind='object',identity='generic',description='One '+name) for i,name in enumerate(names)]
        script=story().model_copy(update={'entities':entities,'narration':'In 1932: '+', '.join(names)+'.'})
        async def prediction(prompt,path,reference,tier):
            subject_image('diamond').save(path);return 'fixture'
        with patch.object(config,'REPLICATE_API_TOKEN','fixture'),patch.object(config,'EDITORIAL_MAX_SUPPORT_CALLS',24):
            generator=EditorialImages();generator._prediction=AsyncMock(side_effect=prediction)
            _,assets=acquire(script,self.root/'long-plan',image_generator=generator,visual_review=self.review)
        self.assertEqual(generator.support_calls,10);self.assertEqual(len(assets),10)
        self.assertTrue(all(a.preparation!='symbolic' and a.alpha for a in assets))

    def test_missing_exact_asset_and_local_asset_do_not_get_placeholder_or_invented_map(self):
        for mode,exact in [('local',None),('auto','map-required')]:
            script=story();script.entities[0]=Entity(id='map',name='Australia map',kind='place',identity='real',description='Exact geographic borders',exact_asset=exact)
            with self.assertRaisesRegex(NewsError,'No verified asset'):
                acquire(script,self.root/mode,asset_mode=mode,image_generator=self.generator)
        self.generator.subject.assert_not_called()

    def test_rejected_cached_image_is_regenerated_instead_of_reused_each_retry(self):
        from agent.cutout_processor import CutoutQualityError
        script=story();script.entities[0].identity='fictional'
        acquire(script,self.root/'cached-first',image_generator=self.generator)
        processor=CutoutProcessor();calls=[]
        def process(src,dest,**kwargs):
            calls.append(str(src))
            if len(calls)==1:raise CutoutQualityError('Cached mask now fails quality')
            return processor.process(src,dest,**kwargs)
        acquire(script,self.root/'cached-retry',image_generator=self.generator,processor=MagicMock(process=process))
        self.assertEqual(len(calls),2)
        self.assertEqual(self.generator.subject.call_count,2)

    def test_real_person_without_any_reference_does_not_claim_a_verified_ai_face(self):
        self.people.resolve.return_value={'kind':'real','sources':['https://public.example/biography'],'references':[]}
        _,assets=self.assets()
        self.generator.real_subject.assert_not_called();self.generator.subject.assert_called_once()
        self.assertFalse(any('Compare image 1' in c.args[0] for c in self.review.call_args_list))
        self.assertFalse(assets[0].factual)
        self.assertEqual(assets[0].fallback,'AI illustration; identity/likeness not verified')
        self.assertIn('Not a verified likeness',self.generator.subject.call_args.args[0])

    def test_historical_person_without_photo_uses_direct_supporting_illustration(self):
        self.people.resolve.return_value={'kind':'historical','sources':['https://public.example/biography'],'references':[]}
        _,assets=self.assets()
        self.generator.subject.assert_called_once();self.generator.real_subject.assert_not_called();self.assertFalse(any('Compare image 1' in c.args[0] for c in self.review.call_args_list))
        self.assertFalse(assets[0].factual);self.assertTrue(assets[0].alpha)
        self.assertIn('reconstruction',assets[0].fallback)

    def test_real_forces_use_representative_ai_group_without_individual_lookup(self):
        from tests.test_cutout_groups import group_image
        script=story()
        script.entities[0]=Entity(id='person',name='Portuguese forces',kind='person',identity='real',description='A group of soldiers.')
        script.sentences[0].text='The queen resisted Portuguese forces in the sixteenth century.'
        script.narration=' '.join(s.text for s in script.sentences)
        async def create(prompt,path):
            group_image().save(path)
            return 'replicate:black-forest-labs/flux-schnell'
        self.generator.subject.side_effect=create
        for mode in ('auto','ai'):
            with self.subTest(mode=mode):
                diagnostics={}
                entities,assets=acquire(script,self.root/mode,asset_mode=mode,people=self.people,
                    image_generator=self.generator,visual_review=self.review,diagnostics=diagnostics)
                self.assertEqual(entities[0].name,'Portuguese forces')
                self.assertEqual(assets[0].subject,'Portuguese forces')
                self.assertTrue(assets[0].alpha);self.assertFalse(assets[0].factual)
                self.assertEqual(assets[0].role,'portrait')
                self.assertIn('not actual members',assets[0].fallback)
                record=diagnostics['assetAcquisition']['assets'][0]
                self.assertEqual(record['route'],'representative_group_illustration')
                self.assertEqual(record['depictionIdentity'],'generic')
        self.people.resolve.assert_not_called();self.generator.real_subject.assert_not_called();self.assertFalse(any('Compare image 1' in c.args[0] for c in self.review.call_args_list))
        self.generator.subject.assert_called_once()  # Second request reuses the accepted cutout.
        prompt=self.generator.subject.call_args.args[0]
        self.assertIn('sixteenth century',prompt)
        self.assertIn('representative people',prompt)
        self.assertNotIn('Preserve the specific identity',prompt)

    def test_collective_names_are_groups_without_explicit_group_description(self):
        for name in ('Portuguese forces','Portuguese Army','British troops','Village warriors','Factory workers'):
            with self.subTest(name=name):
                entity=Entity(id='group',name=name,kind='person',identity='real',description='Standing figures')
                self.assertTrue(entity.is_group)
        entity=Entity(id='commander',name='Named Commander',kind='person',identity='real',description='One officer commanding Portuguese forces')
        self.assertFalse(entity.is_group)
        entity.description='Portrait of Named Commander standing in front of a group of soldiers'
        self.assertFalse(entity.is_group)

    def test_group_description_keeps_group_segmentation_for_a_collective_proper_name(self):
        from tests.test_cutout_groups import group_image
        script=story();script.entities[0]=Entity(id='person',name='Portugal',kind='person',identity='real',description='A group of soldiers')
        async def create(prompt,path):
            group_image().save(path)
            return 'replicate:black-forest-labs/flux-schnell'
        self.generator.subject.side_effect=create
        _,assets=acquire(script,self.root/'group-name',people=self.people,image_generator=self.generator)
        self.assertTrue(assets[0].alpha)
        self.assertIn('three representative people',self.generator.subject.call_args.args[0])
        self.people.resolve.assert_not_called()

    def test_local_group_asset_takes_precedence_over_representative_generation(self):
        from tests.test_cutout_groups import group_image
        group_image().save(self.image)
        script=story();script.entities[0]=Entity(id='person',name='Portuguese forces',kind='person',identity='real',description='A group of soldiers')
        registry=self.root/'registry.json'
        registry.write_text(json.dumps({'Portuguese forces':{'path':str(self.image),'subject':'Portuguese forces',
            'source':'Supplied group image','license':'Test','attribution':'Test author','role':'portrait'}}))
        _,assets=acquire(script,self.root/'local',local_registry=registry,people=self.people,image_generator=self.generator)
        self.assertTrue(assets[0].alpha);self.assertTrue(assets[0].factual)
        self.people.resolve.assert_not_called();self.generator.subject.assert_not_called()

    def test_group_generation_failure_uses_subject_label_not_profile_symbol(self):
        script=story();script.entities[0]=Entity(id='person',name='Portuguese forces',kind='person',identity='real',description='A group of soldiers')
        self.generator.subject.side_effect=NewsError('Image provider unavailable')
        _,assets=acquire(script,self.root/'failed-group',people=self.people,image_generator=self.generator)
        self.assertIn('Subject name only',assets[0].fallback)
        self.people.resolve.assert_not_called();self.generator.real_subject.assert_not_called()
        self.assertFalse(list((self.root/'failed-group').glob('*-symbol.svg')))

    def test_fictional_people_skip_real_identity_lookup_and_keep_full_cutout(self):
        script=story();script.entities[0].identity='fictional'
        _,assets=acquire(script,self.root/'fiction',asset_mode='auto',people=self.people,image_generator=self.generator)
        self.people.resolve.assert_not_called();self.generator.subject.assert_called_once()
        self.assertTrue(assets[0].alpha)
        self.assertIn('torso',self.generator.subject.call_args.args[0])

    def test_visual_plan_adds_relevant_objects_and_preserves_spoken_content(self):
        script=story();original=script.model_dump()
        value={'subjects':[{'id':'coffee','name':'Coffee cup','kind':'object','description':'One isolated ceramic cup with coffee','identity':'generic','reference_query':None,'exact_asset':None}],
            'sections':[{'sectionId':'s1','cues':[{'entityId':'person','anchor':'Example Person'}]},
                        {'sectionId':'s2','cues':[{'entityId':'coffee','anchor':'Coffee'}]}]}
        llm=MagicMock(side_effect=[value,{'supported':True,'problems':[]}]);diagnostics={}
        planned,cues=plan_visuals(script,llm=llm,diagnostics=diagnostics)
        self.assertEqual(script.model_dump(),original);self.assertEqual(planned.narration,script.narration)
        self.assertEqual(planned.sentences[1].entity_ids,['coffee']);self.assertEqual(len(planned.entities),2)
        self.assertEqual(cues[1]['cues'][0]['anchor'],'Coffee');self.assertEqual(diagnostics['visualPlan']['mode'],'llm')

    def test_invented_visual_anchors_and_new_real_people_are_rejected(self):
        base={'subjects':[],'sections':[{'sectionId':'s1','cues':[{'entityId':'person','anchor':'Unspoken name'}]},{'sectionId':'s2','cues':[]}]}
        for value in [base,{'subjects':[{'id':'new','name':'Invented Person','kind':'person','identity':'real','description':'A new person'}],'sections':base['sections']}]:
            with self.subTest(value=value):
                llm=MagicMock(return_value=value);diagnostics={};planned,cues=plan_visuals(story(),llm=llm,diagnostics=diagnostics)
                self.assertEqual(llm.call_count,2);self.assertEqual(planned.narration,story().narration)
                self.assertEqual(diagnostics['visualPlan']['mode'],'deterministic_fallback')

    def test_semantically_unsupported_new_visuals_fail_the_independent_review(self):
        value={'subjects':[],'sections':[{'sectionId':'s1','cues':[{'entityId':'person','anchor':'Example Person'}]},{'sectionId':'s2','cues':[]}]}
        llm=MagicMock(side_effect=[value,{'supported':False,'problems':['Omitted context']},value,{'supported':False,'problems':['Omitted context']}])
        diagnostics={};plan_visuals(story(),llm=llm,diagnostics=diagnostics)
        self.assertEqual(diagnostics['visualPlan']['mode'],'deterministic_fallback');self.assertEqual(llm.call_count,4)

    def test_anchor_matching_handles_punctuation_and_rejects_noncontiguous_words(self):
        self.assertEqual(anchor_index('Then coffee, followed lunch.','coffee'),1)
        self.assertIsNone(anchor_index('Then coffee followed lunch.','coffee lunch'))

    def test_explicitly_named_person_is_restored_to_their_visual_beat(self):
        from agent.editorial.visuals import restore_named_cues
        script=story();rows=[{'sectionId':'s1','cues':[]},{'sectionId':'s2','cues':[{'entityId':'person','anchor':'Coffee'}]}]
        planned,cues=restore_named_cues(script,rows)
        self.assertEqual(cues[0]['cues'],[{'entityId':'person','anchor':'Example Person'}])
        self.assertEqual(planned.sentences[0].entity_ids,['person'])

    def test_opening_gets_story_subject_when_planner_leaves_it_text_only(self):
        sentence=Sentence(id='s1',text='A boulder kept falling back down the hill.',phrase='The boulder fell',claim_ids=['c1'],entity_ids=[],role='hook')
        later=Sentence(id='s2',text='Sisyphus had to push it again.',phrase='Push it again',claim_ids=['c1'],entity_ids=['sisyphus'],role='development')
        figure=Entity(id='sisyphus',name='Sisyphus',kind='person',identity='fictional',description='Full-body Greek myth figure')
        script=Script(summary='Myth',narration=sentence.text+' '+later.text,sentences=[sentence,later],entities=[figure])
        planned,rows=plan_visuals(script)
        self.assertTrue(planned.sentences[0].entity_ids[0].startswith('action-'))
        self.assertEqual(rows[0]['cues'][0]['anchor'],'falling')
        self.assertEqual(planned.narrative_plan.beats[0].verb,'downhill_return')

    def test_action_variant_does_not_restore_old_portrait_alongside_it(self):
        from agent.editorial.visuals import restore_named_cues
        person=Entity(id='sisyphus',name='Sisyphus',kind='person',identity='fictional',description='Standing figure')
        action=Entity(id='sisyphus_boulder',name='Sisyphus',kind='person',identity='fictional',description='Same figure pushing a boulder')
        first=Sentence(id='s1',text='Sisyphus faced a punishment.',phrase='A punishment',claim_ids=['c1'],entity_ids=['sisyphus'],role='hook')
        second=Sentence(id='s2',text='Sisyphus rolled the boulder uphill.',phrase='Boulder uphill',claim_ids=['c1'],entity_ids=['sisyphus_boulder'],role='development')
        script=Script(summary='Myth',narration=first.text+' '+second.text,sentences=[first,second],entities=[person,action])
        rows=[{'sectionId':'s1','cues':[{'entityId':'sisyphus','anchor':'Sisyphus'}]},
              {'sectionId':'s2','cues':[{'entityId':'sisyphus_boulder','anchor':'rolled the boulder'}]}]
        planned,cues=restore_named_cues(script,rows)
        self.assertEqual(planned.sentences[1].entity_ids,['sisyphus_boulder'])
        self.assertEqual(cues[1]['cues'],rows[1]['cues'])

    def test_historical_identity_requires_actual_source_death_passage(self):
        source=Source(id='bio',title='Biography',text='Example Person was executed in 1931.',retrieved_at='2026-10-12',url='https://public.example/biography')
        evidence=Evidence(sources=[source],claims=[Claim(id='c1',text=source.text,source_ids=['bio'],excerpts={'bio':source.text})],verification='single_source')
        llm=MagicMock(return_value={'kind':'historical','source_id':'bio','excerpt':source.text,'reason':'Explicit execution passage'})
        with patch('agent.editorial.people.ReferencePhotos') as refs,patch('agent.editorial.people.SerperSearch') as search:
            refs.return_value.find.return_value=[];search.return_value.search.return_value=[]
            result=People().resolve(story().entities[0],evidence,llm)
        self.assertEqual(result['kind'],'historical');self.assertEqual(result['sources'],[source.url])

    def test_unsupported_identity_is_not_accepted_from_search_snippets(self):
        llm=MagicMock(return_value={'kind':'real','source_id':'missing','excerpt':'Not in a source','reason':'Looks plausible'})
        with patch('agent.editorial.people.ReferencePhotos') as refs,patch('agent.editorial.people.SerperSearch') as search:
            refs.return_value.find.return_value=[];search.return_value.search.return_value=[]
            with self.assertRaisesRegex(NewsError,'Could not establish'):People().resolve(story().entities[0],None,llm)
        self.assertEqual(llm.call_count,2)

    def test_supplied_account_alone_cannot_establish_a_real_identity(self):
        source=Source(id='input',title='Account',text='Example Person is a politician.',retrieved_at='2026-10-12')
        evidence=Evidence(sources=[source],claims=[Claim(id='c1',text=source.text,source_ids=['input'],excerpts={'input':source.text})],verification='user_supplied')
        llm=MagicMock(return_value={'kind':'real','source_id':'input','passage_id':'input:p1','reason':'User said so'})
        with patch('agent.editorial.people.ReferencePhotos') as refs,patch('agent.editorial.people.SerperSearch') as search:
            refs.return_value.find.return_value=[];search.return_value.search.return_value=[]
            with self.assertRaisesRegex(NewsError,'Could not establish'):People().resolve(story().entities[0],evidence,llm)

    def test_sourced_death_date_routes_a_historical_person_without_memory(self):
        reference=copy.copy(self.reference);reference.death_date='+1931-03-23T00:00:00Z'
        llm=MagicMock()
        with patch('agent.editorial.people.ReferencePhotos') as refs:
            refs.return_value.find.return_value=[reference]
            result=People().resolve(story().entities[0],None,llm)
        self.assertEqual(result['kind'],'historical');self.assertEqual(result['deathDate'],reference.death_date)
        llm.assert_not_called()

    def test_three_subjects_enter_on_their_spoken_cues_and_late_focus_is_bounded(self):
        from agent.news_audio import synthesize
        from agent.editorial.audio import prepare_existing
        from agent.editorial.models import Entity as VisualEntity
        from agent.editorial.assets import prepare
        from agent.editorial.planner import build
        from tests.news_fixtures import FixtureTTS
        entities=[Entity(id='person',name='Example Person',kind='person',identity='generic',description='Complete illustrated person'),
                  Entity(id='lunch',name='Lunch plate',kind='object',identity='generic',description='One isolated plate'),
                  Entity(id='coffee',name='Coffee cup',kind='object',identity='generic',description='One isolated cup')]
        sentence=Sentence(id='s1',text='Example Person first ate lunch and then ordered coffee.',phrase='Lunch and coffee',claim_ids=['c1'],entity_ids=[e.id for e in entities],role='development')
        script=Script(summary='Spoken cue timing',narration=sentence.text,sentences=[sentence],entities=entities)
        audio=synthesize(script,self.root/'speech','edge_tts',engine=FixtureTTS())
        master,words,sections,_=prepare_existing(script,audio,self.root/'aligned')
        assets=[prepare(e,self.image,self.root/'prepared',source='fixture',license='test',attribution='test',role='portrait' if e.kind=='person' else 'object') for e in entities]
        visual_entities=[VisualEntity(id=e.id,name=e.name,identity=e.identity,assetIds=[a.id],source=a.source) for e,a in zip(entities,assets)]
        cues=[{'sectionId':'s1','cues':[{'entityId':'person','anchor':'Example Person'},{'entityId':'lunch','anchor':'lunch'},{'entityId':'coffee','anchor':'coffee'}]}]
        m=build(script,words,sections,visual_entities,assets,master,self.root/'timeline','cue-test',visual_cues=cues)
        for eid,term in [('lunch','lunch'),('coffee','coffee.')]:
            layer=next(l for l in m.layers if l.id=='entity-'+eid)
            word=next(w for w in words if w.text==term)
            self.assertLessEqual(abs(layer.startFrame/30-word.start),3/30)
            self.assertEqual(layer.mask,'none')
        person=next(l for l in m.layers if l.id=='entity-person')
        self.assertEqual(person.mask,'none')
        self.assertEqual(person.startFrame,0)
        self.assertEqual(next(l for l in m.layers if l.id=='entity-person-label').startFrame,0)
        self.assertGreater(next(l for l in m.layers if l.id=='entity-coffee').startFrame,next(l for l in m.layers if l.id=='entity-lunch').startFrame)

    def test_replicate_tiers_are_explicit_and_global_preferences_are_unchanged(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        response=MagicMock(status_code=201);response.json.return_value={'id':'fixture1','status':'succeeded','output':['https://public.example/image.png']}
        client=MagicMock();client.post=AsyncMock(return_value=response)
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        old=config.REPLICATE_USE_SCHNELL
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',return_value=(self.image.read_bytes(),'https://public.example/image.png')):
            generator=EditorialImages()
            asyncio.run(generator.subject('One isolated cup',self.root/'support.png'))
            support=client.post.call_args
            self.assertIn('flux-schnell',support.args[0]);self.assertEqual(support.kwargs['json']['input']['num_inference_steps'],4)
            asyncio.run(generator.real_subject('Preserve reference person',self.root/'person.png',self.reference))
            premium=client.post.call_args
            self.assertIn('p-image-edit',premium.args[0]);self.assertTrue(premium.kwargs['json']['input']['images'][0].startswith('data:image/'))
            self.assertEqual(generator.support_calls,1);self.assertEqual(generator.real_calls,1)
        self.assertEqual(config.REPLICATE_USE_SCHNELL,old)

    def test_action_model_has_multiple_references_and_no_hidden_fallback(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        response=MagicMock(status_code=201);response.json.return_value={'id':'fixture1','status':'succeeded','output':['https://public.example/image.png']}
        client=MagicMock();client.post=AsyncMock(return_value=response)
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        reference=type('References',(),{'path':self.image,'paths':[self.image,self.image]})()
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch.object(config,'EDITORIAL_ACTION_IMAGE_MODEL','google/nano-banana-pro'),patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',return_value=(self.image.read_bytes(),'https://public.example/image.png')):
            generator=EditorialImages()
            asyncio.run(generator.action_subject('Exact contact',self.root/'action.png',reference))
        request=client.post.call_args
        self.assertIn('google/nano-banana-pro',request.args[0])
        payload=request.kwargs['json']['input']
        self.assertEqual(len(payload['image_input']),2)
        self.assertEqual(payload['resolution'],'2K')
        self.assertFalse(payload['allow_fallback_model'])
        self.assertNotIn('input_image',payload)
        self.assertEqual(generator.real_calls,1)

    def test_billing_failure_stops_further_job_predictions(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        response=MagicMock(status_code=402)
        client=MagicMock();client.post=AsyncMock(return_value=response)
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch('httpx.AsyncClient',return_value=context):
            generator=EditorialImages()
            for index in range(2):
                with self.assertRaisesRegex(NewsError,'HTTP 402'):
                    asyncio.run(generator.subject('Cup',self.root/('cup'+str(index)+'.png')))
        self.assertEqual(client.post.await_count,1)

    def test_supporting_call_cap_is_enforced_before_another_prediction(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch.object(config,'EDITORIAL_MAX_SUPPORT_CALLS',1):
            generator=EditorialImages();generator._prediction=AsyncMock(return_value='fixture')
            asyncio.run(generator.subject('Cup',self.root/'cup.png'))
            with self.assertRaisesRegex(NewsError,'call limit'):asyncio.run(generator.subject('Plate',self.root/'plate.png'))
            self.assertEqual(generator._prediction.call_count,1)

    def test_provider_http_error_is_actionable_and_does_not_include_response_body(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        response=MagicMock(status_code=429,text='credential-bearing provider response must not escape')
        client=MagicMock();client.post=AsyncMock(return_value=response)
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch('httpx.AsyncClient',return_value=context),patch('asyncio.sleep',new_callable=AsyncMock):
            with self.assertRaisesRegex(NewsError,'HTTP 429') as error:asyncio.run(EditorialImages().subject('Cup',self.root/'cup.png'))
        self.assertNotIn('credential-bearing',str(error.exception))

    def test_replicate_throttling_waits_then_polls_only_one_accepted_prediction(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        rejected=MagicMock(status_code=429,headers={'retry-after':'2'})
        accepted=MagicMock(status_code=201);accepted.json.return_value={'id':'fixture1','status':'succeeded','output':['https://public.example/image.png']}
        client=MagicMock();client.post=AsyncMock(side_effect=[rejected,accepted])
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch('httpx.AsyncClient',return_value=context),patch('asyncio.sleep',new_callable=AsyncMock) as pause,patch('agent.news_research.fetch',return_value=(self.image.read_bytes(),'https://public.example/image.png')):
            generator=EditorialImages();asyncio.run(generator.subject('Cup',self.root/'cup.png'))
        pause.assert_awaited_once_with(2);self.assertEqual(client.post.call_count,2);self.assertEqual(generator.support_calls,1)

    def test_cancelled_prediction_is_cancelled_remotely(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        response=MagicMock(status_code=201);response.json.return_value={'id':'fixture1','status':'processing'}
        client=MagicMock();client.post=AsyncMock(return_value=response)
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        async def cancel_sleep(_):raise asyncio.CancelledError()
        with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'),patch('httpx.AsyncClient',return_value=context),patch('asyncio.sleep',side_effect=cancel_sleep):
            with self.assertRaises(asyncio.CancelledError):asyncio.run(EditorialImages().subject('Cup',self.root/'cup.png'))
        self.assertTrue(client.post.call_args.args[0].endswith('/fixture1/cancel'))

    def test_web_job_uses_automatic_imagery_when_no_asset_override_is_sent(self):
        from types import SimpleNamespace
        import web_ui
        from agent.orchestrator import PipelineResult
        with web_ui.app.test_request_context('/'),patch('agent.news_script.NewsLLM'),patch('agent.news_pipeline.run_news',return_value=PipelineResult(errors=['fixture'])) as run,patch('web_ui.threading.Thread') as thread:
            thread.side_effect=lambda target,**kwargs:SimpleNamespace(start=target)
            web_ui._start_news_job({'visual_preset':'reference_editorial'},'A public story')
        self.assertEqual(run.call_args.kwargs['asset_mode'],'auto')

    def test_multi_subject_profiles_keep_narration_below_images_and_labels(self):
        from agent.editorial.templates import profile
        for template in ('process','document_photo','comparison','conclusion','object_location'):
            for count in (1,2,3):
                with self.subTest(template=template,count=count):
                    _,text,boxes=profile(template,count)
                    for box in boxes:
                        # Single process/document compositions deliberately put
                        # text beside or above the image, with separate x/y bands.
                        if template in ('process','document_photo') and count==1:continue
                        self.assertGreaterEqual(text.y,box.y+box.h+18+108)


if __name__=='__main__':unittest.main()
