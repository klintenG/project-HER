"""Identity-aware photo selection, economical generation and provenance."""
import asyncio
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from PIL import Image
from pydantic import ValidationError
import config
from agent.cutout_processor import CutoutProcessor
from agent.news_assets import NewsImageGenerator, generate_cutouts, subject_prompt
from agent.news_models import Entity, NewsError, Manifest
from agent.news_references import ReferencePhoto, ReferencePhotos
from tests.news_fixtures import subject_image, fixture_manifest, FixtureLLM, SCRIPT, ACCOUNT


class IdentityImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ('NEWS_REFERENCE_CACHE','NEWS_IDENTITY_IMAGE_CACHE','NEWS_CUTOUT_CACHE'):
            override=patch.object(config,name,self.root/name);override.start();self.addCleanup(override.stop)
        self.entity=Entity(id='trump',name='Donald Trump',kind='person',identity='real',
            description='Donald Trump, the American politician, upper-body portrait in a dark suit.')
        self.path=self.root/'reference.png';subject_image('mira').save(self.path)
        self.reference=ReferencePhoto(str(self.path),'https://commons.wikimedia.org/wiki/File:Portrait.jpg',
            'Public domain','Portrait by photographer; Public domain','https://www.wikidata.org/wiki/Q22686')
        self.processor=CutoutProcessor(backend='none',models=[])
        self.references=SimpleNamespace(find=MagicMock(return_value=[self.reference]))
        self.generator=SimpleNamespace(provider='fixture',subject=AsyncMock(),real_subject=AsyncMock(side_effect=self.generate))

    async def generate(self,prompt,path,reference):
        subject_image('mira').save(path)
        return 'replicate:fixture'

    def assets(self,entity=None,directory='job'):
        return generate_cutouts(SimpleNamespace(entities=[entity or self.entity]),self.root/directory,'reported',
            self.generator,self.processor,reference_provider=self.references)

    def test_actual_photo_precedes_paid_generation_and_retains_attribution(self):
        asset=self.assets()[0]
        self.generator.real_subject.assert_not_called();self.generator.subject.assert_not_called()
        self.assertEqual(asset.origin,'photo');self.assertFalse(asset.illustrative)
        self.assertTrue(asset.identity_verified);self.assertIn('photographer',asset.attribution)
        self.assertIn('background removed',asset.attribution)
        self.assertEqual(asset.reference_entity,'https://www.wikidata.org/wiki/Q22686')

    def test_actual_photo_needs_no_image_provider_initialization(self):
        with patch('agent.news_assets.NewsImageGenerator',side_effect=AssertionError('Paid provider was initialized')):
            assets=generate_cutouts(SimpleNamespace(entities=[self.entity]),self.root/'free-photo','reported',
                processor=self.processor,reference_provider=self.references)
        self.assertEqual(assets[0].origin,'photo')

    def test_reference_edit_retains_reference_identity_and_is_not_a_photo(self):
        Image.new('RGB',(512,640),'white').save(self.path)
        asset=self.assets()[0]
        self.assertEqual(asset.origin,'reference_edit');self.assertTrue(asset.illustrative)
        self.assertFalse(asset.identity_verified)
        self.assertEqual(asset.image_model,'black-forest-labs/flux-kontext-pro')
        self.assertEqual(self.generator.real_subject.call_args.args[2],self.reference)
        self.assertIn('same identity',asset.prompt)
        self.generator.subject.assert_not_called()

    def test_missing_photo_uses_named_higher_model_and_caches_paid_result(self):
        self.references.find.return_value=[]
        first=self.assets()[0];second=self.assets(directory='another-job')[0]
        self.assertEqual(self.generator.real_subject.call_count,1)
        self.assertEqual(first.image_model,'black-forest-labs/flux-1.1-pro')
        self.assertIn('Donald Trump',first.prompt);self.assertEqual(first.origin,'generated')
        self.assertFalse(first.identity_verified);self.assertNotEqual(first.path,second.path)
        self.generator.subject.assert_not_called()

    def test_fictional_odysseus_and_generic_subjects_skip_reference_and_premium_models(self):
        async def ordinary(prompt,path):
            subject_image('mira').save(path);return 'fixture-cheap'
        self.generator.subject.side_effect=ordinary
        for identity,name in [('fictional','Odysseus'),('generic','Anonymous scientist')]:
            entity=self.entity.model_copy(update={'identity':identity,'name':name})
            asset=self.assets(entity,identity)[0]
            self.assertEqual(asset.origin,'generated');self.assertIsNone(asset.image_model)
        self.references.find.assert_not_called();self.generator.real_subject.assert_not_called()
        self.assertIn('Odysseus',self.generator.subject.call_args_list[0].args[0])

    def test_fictional_portrait_accepts_intentional_torso_crop(self):
        from PIL import ImageDraw
        async def portrait(prompt,path):
            image=subject_image('mira')
            ImageDraw.Draw(image).rectangle((110,350,400,639),fill='#63727e')
            image.save(path);return 'fixture-cheap'
        self.generator.subject.side_effect=portrait
        entity=self.entity.model_copy(update={'identity':'fictional','name':'Odysseus',
            'description':'An upper-body portrait of Odysseus in ancient armor'})
        asset=self.assets(entity)[0]
        self.assertEqual(asset.origin,'generated')
        self.assertEqual(self.generator.subject.call_count,1)
        self.assertGreater(asset.mask['transparent_margin'],.018)

    def test_paid_call_cap_is_shared_across_real_entities_in_one_video(self):
        self.references.find.return_value=[]
        second=self.entity.model_copy(update={'id':'second','name':'Another real public figure'})
        with patch.object(config,'NEWS_MAX_REAL_IMAGE_CALLS',1),self.assertRaisesRegex(NewsError,'call limit'):
            generate_cutouts(SimpleNamespace(entities=[self.entity,second]),self.root/'shared-budget','reported',
                self.generator,self.processor,reference_provider=self.references)
        self.assertEqual(self.generator.real_subject.call_count,1)

    def test_paid_call_cap_prevents_more_predictions_and_no_generic_fallback(self):
        self.references.find.return_value=[]
        self.generator.real_subject.side_effect=NewsError('Provider unavailable')
        with patch.object(config,'NEWS_MAX_REAL_IMAGE_CALLS',1),self.assertRaisesRegex(NewsError,'call limit'):
            self.assets()
        self.assertEqual(self.generator.real_subject.call_count,1)
        self.generator.subject.assert_not_called()

    def test_real_groups_are_not_replaced_by_three_generic_people(self):
        group=self.entity.model_copy(update={'name':'France football team','description':'A group of soccer players'})
        prompt=subject_prompt(group)
        self.assertNotIn('three representative',prompt)
        self.assertIn('France football team',prompt)

    def test_entity_ids_cannot_escape_output_directory(self):
        entity=self.entity.model_copy(update={'id':'../../outside'})
        asset=self.assets(entity)[0]
        self.assertEqual(Path(asset.path).parent,(self.root/'job'/'cutouts').resolve())
        self.assertEqual(Path(asset.raw_path).parent,(self.root/'job'/'cutouts').resolve())

    def reference_payloads(self,license='Public domain'):
        return [
            {'search':[{'id':'Q22686','label':'Donald Trump','description':'American politician'}]},
            {'entities':{'Q22686':{'claims':{'P18':[{'rank':'preferred','mainsnak':{'datavalue':{'value':'Portrait.jpg'}}}]}}}},
            {'query':{'pages':{'1':{'imageinfo':[{'url':'https://upload.wikimedia.org/portrait.jpg',
                'descriptionurl':self.reference.source_url,'size':10000,'width':512,'height':640,
                'extmetadata':{'LicenseShortName':{'value':license},'Artist':{'value':'<b>Photographer</b>'}}}]}}}},
        ]

    def test_reference_lookup_links_exact_identity_metadata_download_and_cache(self):
        with patch('agent.news_references._json',side_effect=self.reference_payloads()) as metadata, \
                patch('agent.news_references.fetch',return_value=(self.path.read_bytes(),'https://upload.wikimedia.org/portrait.jpg')) as download:
            photos=ReferencePhotos().find(self.entity)
            again=ReferencePhotos().find(self.entity)
        self.assertEqual(len(photos),1);self.assertEqual(metadata.call_count,3);self.assertEqual(download.call_count,1)
        self.assertEqual(photos[0],again[0]);self.assertIn('Photographer',photos[0].attribution)
        self.assertEqual(photos[0].entity_url,self.reference.entity_url)

    def test_ambiguous_names_do_not_choose_first_match(self):
        candidates={'search':[{'id':'Q1','label':'Donald Trump','description':'Politician'},
            {'id':'Q2','label':'Donald Trump','description':'Physician'}]}
        with patch('agent.news_references._json',return_value=candidates) as fetch:
            self.assertEqual(ReferencePhotos().find(self.entity),[])
        self.assertEqual(fetch.call_count,1)
        llm=MagicMock(return_value={'matched':True,'id':'Q999'})
        with patch('agent.news_references._json',return_value=candidates):
            self.assertEqual(ReferencePhotos().find(self.entity,llm),[])

    def test_unknown_and_restricted_licenses_are_not_downloaded(self):
        for license in ('','Fair use','CC BY-NC 4.0','CC BY-ND 4.0'):
            with self.subTest(license=license),patch('agent.news_references._json',side_effect=self.reference_payloads(license)), \
                    patch('agent.news_references.fetch') as download:
                self.assertEqual(ReferencePhotos().find(self.entity),[])
                download.assert_not_called()

    def test_download_hosts_and_decoded_image_limits_are_checked(self):
        from agent.news_references import _commons_url,_safe_image
        for url in ('http://upload.wikimedia.org/a.jpg','https://upload.wikimedia.org.attacker.test/a.jpg','http://127.0.0.1/a.jpg'):
            with self.assertRaises(NewsError):_commons_url(url,download=True)
        buffer=io.BytesIO();Image.new('RGB',(100,100)).save(buffer,format='PNG')
        with self.assertRaisesRegex(NewsError,'small'):_safe_image(buffer.getvalue())

    def test_manifest_cannot_label_generated_asset_as_verified_photo(self):
        manifest=fixture_manifest(self.root/'fixture',540,960)
        raw=manifest.model_dump();raw['assets'][0]['origin']='photo'
        with self.assertRaises(ValidationError):Manifest.model_validate(raw)
        raw=manifest.model_dump();raw['assets'][0]['origin']='reference_edit'
        with self.assertRaises(ValidationError):Manifest.model_validate(raw)

    def test_premium_provider_uses_one_output_and_correct_reference_input(self):
        async def run(reference):
            calls=[]
            def handler(request):
                calls.append(request)
                return httpx.Response(201,json={'id':'prediction1','status':'succeeded','output':['https://replicate.delivery/image.png']})
            original=httpx.AsyncClient
            generator=object.__new__(NewsImageGenerator);generator.replicate_token='test-token'
            with patch('agent.news_assets.httpx.AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs)), \
                    patch('agent.news_research.fetch',return_value=(self.path.read_bytes(),'https://replicate.delivery/image.png')):
                await generator.real_subject('Preserve Donald Trump',self.root/'generated.png',reference)
            return calls
        for reference in (None,self.reference):
            calls=asyncio.run(run(reference));self.assertEqual(len(calls),1)
            data=json.loads(calls[0].content)['input']
            self.assertEqual(data['aspect_ratio'],'1:1');self.assertFalse(data['prompt_upsampling'])
            self.assertNotIn('num_outputs',data)
            self.assertEqual('input_image' in data,reference is not None)
            if reference:self.assertTrue(data['input_image'].startswith('data:image/jpeg;base64,'))

    def test_expensive_model_is_rejected_before_network(self):
        generator=object.__new__(NewsImageGenerator);generator.replicate_token='test-token'
        with patch.object(config,'NEWS_REAL_IMAGE_MODEL','expensive/ultra-model'),patch('agent.news_assets.httpx.AsyncClient') as client:
            with self.assertRaisesRegex(NewsError,'expensive models'):
                asyncio.run(generator.real_subject('A subject',self.root/'image.png'))
        client.assert_not_called()

    def test_cancelled_premium_prediction_is_cancelled_at_provider(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(201,json={'id':'prediction1','status':'processing'})
        original=httpx.AsyncClient
        generator=object.__new__(NewsImageGenerator);generator.replicate_token='test-token'
        with patch('agent.news_assets.httpx.AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs)), \
                patch('agent.news_assets.asyncio.sleep',side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(generator.real_subject('A subject',self.root/'cancelled.png'))
        self.assertEqual(len(calls),2);self.assertTrue(str(calls[-1].url).endswith('/prediction1/cancel'))
        self.assertFalse((self.root/'cancelled.png').exists())

    def test_actual_portrait_may_crop_torso_but_never_top_or_head_sides(self):
        from PIL import ImageDraw
        from agent.cutout_processor import mask_statistics
        portrait=subject_image('mira')
        ImageDraw.Draw(portrait).rectangle((110,350,400,639),fill='#63727e')
        with self.assertRaisesRegex(NewsError,'edge'):mask_statistics(portrait)
        mask_statistics(portrait,allow_portrait_crop=True)
        for position in ((160,0,200,90),(0,120,200,190)):
            clipped=portrait.copy();ImageDraw.Draw(clipped).rectangle(position,fill='blue')
            with self.assertRaisesRegex(NewsError,'edge'):mask_statistics(clipped,allow_portrait_crop=True)

    def test_portrait_qa_rejects_ghosted_torso_after_background_removal(self):
        from PIL import ImageDraw
        from agent.cutout_processor import mask_statistics
        portrait=subject_image('mira')
        ImageDraw.Draw(portrait).rectangle((110,350,400,600),fill=(30,40,60,90))
        with self.assertRaisesRegex(NewsError,'torso became semitransparent'):
            mask_statistics(portrait,allow_portrait_crop=True)

    def test_actual_photo_provenance_passes_full_manifest_validation(self):
        manifest=fixture_manifest(self.root/'fixture',540,960)
        asset=self.assets()[0]
        raw=manifest.model_dump()
        raw['script']['entities'][0]['identity']='real'
        replacement=asset.model_dump();replacement['id']=raw['assets'][0]['id'];replacement['entity_id']=raw['assets'][0]['entity_id']
        raw['assets'][0]=replacement
        result=Manifest.model_validate(raw)
        self.assertEqual(result.assets[0].origin,'photo')
        raw['assets'][0]['identity_verified']=False
        with self.assertRaises(ValidationError):Manifest.model_validate(raw)

    def test_script_prompt_and_review_require_real_fictional_and_generic_routing(self):
        from agent.news_research import analyze_input,research
        from agent.news_script import write_script
        fixture=FixtureLLM();inp=analyze_input(ACCOUNT,'supplied',fixture);evidence,_=research(inp,fixture)
        llm=MagicMock(side_effect=fixture)
        write_script(inp,evidence,llm)
        instructions=[call.args[0] for call in llm.call_args_list]
        self.assertIn('Donald Trump',instructions[0]);self.assertIn('Odysseus',instructions[0])
        self.assertIn('identity routing',instructions[1])


if __name__=='__main__':unittest.main()
