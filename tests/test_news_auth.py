"""Authentication failures must provide recovery steps without exposing secrets."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import httpx
from openai import AuthenticationError,RateLimitError
from agent.news_script import NewsLLM
from agent.news_models import NewsError


class NewsAuthTests(unittest.TestCase):
    def client(self,provider,error=None):
        create=Mock(side_effect=error) if error else Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))]))
        sdk=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch('agent.news_script.get_llm_client',return_value=(sdk,'test-model')):
            return NewsLLM(provider=provider),create

    def auth_error(self):
        request=httpx.Request('POST','https://generativelanguage.googleapis.com/v1beta/openai/chat/completions')
        return AuthenticationError('private-provider-body AQ.secret-test-value',response=httpx.Response(401,request=request),body={'error':{'message':'private-provider-body'}})

    def test_gemini_auth_failure_is_actionable_and_redacted(self):
        for provider in ('gemini','google'):
            llm,create=self.client(provider,self.auth_error())
            with self.assertRaises(NewsError) as result:llm('Classify input',{})
            message=str(result.exception)
            self.assertIn('GEMINI_API_KEY',message)
            self.assertIn('Generative Language API',message)
            self.assertIn('restart ProjectHER',message)
            self.assertNotIn('private-provider-body',message)
            self.assertNotIn('AQ.secret-test-value',message)
            self.assertEqual(create.call_count,1)

    def test_groq_error_names_its_own_setting(self):
        llm,_=self.client('groq',self.auth_error())
        with self.assertRaises(NewsError) as result:llm('Classify input',{})
        self.assertIn('GROQ_API_KEY',str(result.exception))
        self.assertNotIn('GEMINI_API_KEY',str(result.exception))

    def test_rate_limit_is_not_misreported_as_invalid_key(self):
        error=RateLimitError('quota',response=httpx.Response(429,request=httpx.Request('POST','https://example.test')),body={})
        llm,_=self.client('gemini',error)
        with self.assertRaises(RateLimitError) as result:llm('Classify input',{})
        self.assertIs(result.exception,error)

    def test_successful_json_contract_unchanged(self):
        llm,_=self.client('gemini')
        self.assertEqual(llm('Classify input',{}),{'ok':True})

if __name__=='__main__':unittest.main()
