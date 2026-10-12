"""Malformed semantic classifications must repair before expensive generation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch

from agent.news_models import NewsError
from agent.news_research import analyze_input,research,extract_evidence
from agent.news_models import Source


class NewsInputTests(unittest.TestCase):
    def classification(self,**updates):
        data={'subject':'Starlink India entry','kind':'topic_query','basis':'reported','event_date':None,'entities':['Starlink'],'places':['India'],'assumptions':[],'clarification':None,'choices':[]}
        data.update(updates);return data

    def test_reported_kind_is_repaired_using_same_input_and_schema(self):
        bad=self.classification(kind='reported');original=copy.deepcopy(bad)
        llm=MagicMock(side_effect=[bad,self.classification()])
        inp=analyze_input('  Starlink entry into India  ','auto',llm)
        self.assertEqual(inp.kind,'topic_query');self.assertEqual(inp.basis,'reported')
        self.assertEqual(inp.original,'  Starlink entry into India  ')
        self.assertEqual(inp.normalized,'Starlink entry into India')
        self.assertEqual(llm.call_count,2);self.assertEqual(bad,original)
        repair=llm.call_args.args[1]
        self.assertEqual(repair['previous_output_to_repair']['kind'],'reported')
        self.assertTrue(any(error.startswith('kind:') for error in repair['repair_feedback']))
        schema=repair['classification_schema']
        self.assertEqual(schema['properties']['kind']['enum'],['source_url','topic_query','supplied_account','mixed'])
        self.assertIn('reported',schema['properties']['basis']['enum'])
        self.assertNotIn('original',schema['properties']);self.assertFalse(schema['additionalProperties'])

    def test_account_repair_keeps_user_attribution(self):
        text='Our village opened a library yesterday.'
        llm=MagicMock(side_effect=[self.classification(kind='reported'),self.classification(subject='Village library',kind='supplied_account')])
        inp=analyze_input(text,'auto',llm)
        self.assertEqual(inp.kind,'supplied_account');self.assertEqual(inp.basis,'user_supplied')
        self.assertEqual(inp.normalized,text)

    def test_url_only_and_mixed_routing_remain_authoritative(self):
        for text,kind in [('https://public.example/event','source_url'),('https://public.example/event\nAdditional event details.','mixed')]:
            with self.subTest(kind=kind),patch('agent.news_research.public_url') as validate:
                llm=MagicMock(return_value=self.classification(kind='reported'))
                inp=analyze_input(text,'auto',llm)
                self.assertEqual(inp.kind,kind);self.assertEqual(inp.basis,'reported')
                llm.assert_called_once();validate.assert_called_once_with('https://public.example/event')

    def test_malformed_fields_and_nonobjects_get_bounded_repair(self):
        cases=[None,[], 'reported',
            self.classification(kind=['reported']),
            self.classification(kind='source_url'),
            self.classification(entities='Starlink'),
            self.classification(event_date=2026),
            self.classification(clarification=True),
            self.classification(choices='India'),
            self.classification(extra='unexpected'),
            self.classification(subject=''),
        ]
        for bad in cases:
            with self.subTest(response=bad):
                llm=MagicMock(side_effect=[bad,self.classification()])
                inp=analyze_input('Starlink entry into India','auto',llm)
                self.assertEqual(inp.kind,'topic_query');self.assertEqual(llm.call_count,2)
                self.assertTrue(llm.call_args.args[1]['repair_feedback'])

    def test_invalid_basis_is_repaired_before_supplied_policy_override(self):
        llm=MagicMock(side_effect=[self.classification(kind='supplied_account',basis='fiction'),self.classification(kind='supplied_account',basis='fictional')])
        inp=analyze_input('Fictional account of a village library.','supplied',llm)
        self.assertEqual(inp.basis,'fictional');self.assertEqual(llm.call_count,2)
        self.assertTrue(any(error.startswith('basis:') for error in llm.call_args.args[1]['repair_feedback']))

    def test_supplied_account_clarification_is_preserved_without_retry(self):
        question='Which satellite launch should this explain?';choices=['Mission A','Mission B']
        llm=MagicMock(return_value=self.classification(clarification=question,choices=choices))
        with self.assertRaises(NewsError) as error:analyze_input('The satellite launch','supplied',llm)
        self.assertEqual(error.exception.status,'needs_clarification')
        self.assertEqual(str(error.exception),question);self.assertEqual(error.exception.choices,choices)
        llm.assert_called_once()

    def test_headline_uncertainty_is_resolved_after_search(self):
        headline='Rahul Gandhi and CM Vijay Share Lunch and Cafe Chat in Chennai'
        question='Are you referring to the actor Vijay, and is this factual or hypothetical?'
        body='Sources identify the participants and describe a lunch and cafe visit in Chennai. This is a synthetic regression article, used only to check that evidence retrieval precedes clarification and supports linked claims.'
        html='<html><h1>Regression article</h1><article><p>'+body+'</p></article></html>'
        for policy in ('auto','online'):
            with self.subTest(policy=policy),tempfile.TemporaryDirectory() as tmp:
                def respond(instruction,data):
                    if instruction.startswith('Classify'):
                        return self.classification(subject='Actor Vijay hypothetical meeting',event_date='1999',basis='user_supplied',clarification=question)
                    self.assertTrue(instruction.startswith('Extract'))
                    self.assertEqual(len(data['sources']),1)
                    self.assertNotEqual(data['sources'][0]['id'],'input')
                    self.assertTrue(any(question in item for item in data['input']['assumptions']))
                    source=data['sources'][0]
                    return {'claims':[{'id':'c1','source_ids':[source['id']],'text':'The regression article describes lunch and a cafe visit.','passage_ids':{source['id']:[source['passages'][0]['id']]}}],'conflicts':[],'unresolved':[],'event_choices':[]}
                llm=MagicMock(side_effect=respond)
                search=MagicMock();search.search.return_value=[{'url':'https://public.example/event'}]
                fetcher=MagicMock(return_value=(html,'https://public.example/event'))
                audit_path=Path(tmp)/'classification.json'
                inp=analyze_input(headline,policy,llm,diagnostics_path=audit_path)
                self.assertEqual(inp.basis,'reported')
                self.assertIsNone(inp.event_date)
                with patch('agent.news_research.public_url'):
                    evidence,_=research(inp,llm,search,fetcher)
                search.search.assert_called_once_with(headline)
                fetcher.assert_called_once();self.assertEqual(llm.call_count,2)
                self.assertEqual(evidence.verification,'single_source')
                audit=json.loads(audit_path.read_text())
                self.assertEqual(audit['status'],'ready');self.assertEqual(audit['sourcePolicy'],policy)
                self.assertEqual(audit['attempts'][0]['deferredClarification']['question'],question)
                self.assertEqual(audit['attempts'][0]['discardedInferredEventDate'],'1999')

    def test_date_constraints_are_kept_only_when_present_in_the_topic(self):
        for headline,date in [('Undated public event',None),('Public event in 2022','2022'),('Public event yesterday','2026-10-11')]:
            with self.subTest(headline=headline):
                proposed=date or '2026-10-12'
                inp=analyze_input(headline,'auto',MagicMock(return_value=self.classification(event_date=proposed)))
                self.assertEqual(inp.event_date,date)

    def test_url_clarification_waits_for_article(self):
        with patch('agent.news_research.public_url'):
            inp=analyze_input('https://public.example/event','auto',MagicMock(return_value=self.classification(clarification='Which Vijay?')))
        self.assertEqual(inp.kind,'source_url')
        self.assertTrue(any('Which Vijay?' in item for item in inp.assumptions))

    def test_online_uncertain_account_is_a_search_request_not_a_source(self):
        inp=analyze_input('Unfamiliar public event','online',MagicMock(return_value=self.classification(kind='supplied_account',clarification='Did this occur?')))
        self.assertEqual(inp.kind,'topic_query');self.assertEqual(inp.basis,'reported')
        search=MagicMock();search.search.return_value=[]
        with self.assertRaisesRegex(NewsError,'No readable evidence'):
            research(inp,MagicMock(),search)
        search.search.assert_called_once()

    def test_auto_local_account_can_still_request_missing_details(self):
        question='Which village are you describing?'
        llm=MagicMock(return_value=self.classification(kind='supplied_account',clarification=question))
        with self.assertRaises(NewsError) as error:
            analyze_input('Our village opened a library.','auto',llm)
        self.assertEqual(error.exception.status,'needs_clarification')

    def test_ambiguous_historical_events_ask_only_after_evidence_retrieval(self):
        cases=[('Trump becoming president of USA',['2016 election victory','2017 inauguration','2024 election victory','2025 inauguration']),
               ('Argentina winning FIFA World Cup',['1978 FIFA World Cup','1986 FIFA World Cup','2022 FIFA World Cup'])]
        for headline,choices in cases:
            with self.subTest(headline=headline):
                llm=MagicMock(side_effect=[self.classification(subject=headline,clarification='Which event?',choices=choices),
                    {'claims':[],'conflicts':[],'unresolved':[],'event_choices':choices}])
                inp=analyze_input(headline,'auto',llm)
                search=MagicMock();search.search.return_value=[{'url':'https://public.example/history'}]
                html='<html><article><p>'+('This regression source covers different historical events. '*6)+'</p></article></html>'
                fetcher=MagicMock(return_value=(html,'https://public.example/history'))
                with patch('agent.news_research.public_url'),self.assertRaises(NewsError) as error:
                    research(inp,llm,search,fetcher)
                self.assertEqual(error.exception.status,'needs_clarification');self.assertEqual(error.exception.choices,choices)
                search.search.assert_called_once();fetcher.assert_called_once();self.assertEqual(llm.call_count,2)

    def test_invalid_kind_with_clarification_still_requires_repair(self):
        llm=MagicMock(side_effect=[self.classification(kind='reported',clarification='Which event?'),self.classification()])
        inp=analyze_input('A public news headline','auto',llm)
        self.assertEqual(inp.kind,'topic_query');self.assertEqual(llm.call_count,2)

    def test_extracted_date_absent_from_passages_is_repaired_before_writing(self):
        inp=analyze_input('A lunch meeting','auto',MagicMock(return_value=self.classification()))
        source=Source(id='source1',title='Meeting',text='The leaders met for lunch on Saturday.',published_at='2026-10-10',retrieved_at='2026-10-12')
        bad={'claims':[{'id':'c1','source_ids':['source1'],'text':'The leaders met on October 10, 2026.','passage_ids':{'source1':['source1:p1']}}],'conflicts':[],'unresolved':[]}
        good=copy.deepcopy(bad);good['claims'][0]['text']='The leaders met for lunch on Saturday.'
        llm=MagicMock(side_effect=[bad,good])
        evidence,_,_,_=extract_evidence(inp,[source],llm)
        self.assertEqual(llm.call_count,2)
        self.assertIn('absent from its supporting passages',llm.call_args.args[1]['repair_feedback'][0])
        self.assertEqual(evidence.claims[0].text,good['claims'][0]['text'])

    def test_persistent_unsupported_claim_year_stops_within_evidence_repair_limit(self):
        inp=analyze_input('A lunch meeting','auto',MagicMock(return_value=self.classification()))
        source=Source(id='source1',title='Meeting',text='The leaders met for lunch on Saturday.',retrieved_at='2026-10-12')
        bad={'claims':[{'id':'c1','source_ids':['source1'],'text':'The leaders met in 2026.','passage_ids':{'source1':['source1:p1']}}],'conflicts':[],'unresolved':[]}
        llm=MagicMock(return_value=bad)
        with self.assertRaisesRegex(NewsError,'three attempts'):
            extract_evidence(inp,[source],llm)
        self.assertEqual(llm.call_count,3)

    def test_repeated_invalid_kind_stops_at_resolve_and_saves_diagnostics(self):
        from agent.news_pipeline import run_news
        llm=MagicMock(return_value=self.classification(kind='reported'))
        with tempfile.TemporaryDirectory() as tmp, \
                patch('agent.news_research.research') as research, \
                patch('agent.news_audio.synthesize') as narration, \
                patch('agent.editorial.pipeline.acquire') as assets:
            result=run_news('Starlink entry into India',output_dir=tmp,visual_preset='reference_editorial',llm=llm)
            self.assertFalse(result.success);self.assertEqual(llm.call_count,3)
            for dependency in (research,narration,assets):dependency.assert_not_called()
            self.assertIn('three automatic repair attempts',result.errors[0])
            self.assertNotIn('pydantic',result.errors[0])
            audit=json.loads((Path(tmp)/'input_classification.json').read_text())
            self.assertEqual(audit['status'],'error');self.assertEqual(len(audit['attempts']),3)
            self.assertTrue(all(row['kind']=='reported' and row['errors'] for row in audit['attempts']))
            failure=json.loads((Path(tmp)/'editorial_failure.json').read_text())
            self.assertEqual(failure['stage'],'resolve')


if __name__=='__main__':unittest.main()
