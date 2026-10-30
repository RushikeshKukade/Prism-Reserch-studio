"""Offline contract tests; these do not measure a live model's factual accuracy."""
import copy
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

import ai_brief
from engine import answer


class BriefTests(unittest.TestCase):
    def setUp(self):
        ai_brief._cache.clear()
        self.question = 'Compare revenue for TCS, Infosys and HCLTech in FY2024'
        self.result = answer(self.question)
        self.source = self.result['evidence'][0]['id']
        self.valid = {'summary': 'The table compares disclosed revenues.',
                      'observations': [{'text': 'TCS has the largest revenue in this comparison.',
                                        'source_ids': [self.source]}],
                      'limitations': ['The comparison covers historical consolidated results.'],
                      'follow_up_questions': ['Which additional filings would explain the revenue mix?']}
        self.config = patch('ai_brief.configuration', return_value=('test-placeholder', 'gpt-4.1-mini'))
        self.config.start()
        self.addCleanup(self.config.stop)

    def response(self, brief=None):
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(self.valid if brief is None else brief)}]}],
            'usage': {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150}}

    def test_missing_key_never_calls_provider(self):
        transport = Mock()
        with patch('ai_brief.configuration', return_value=('', 'gpt-4.1-mini')):
            result = ai_brief.generate_brief(self.question, self.result, transport)
        self.assertEqual(result['status'], 'not_configured')
        self.assertEqual(result['model_calls'], 0)
        transport.assert_not_called()

    def test_missing_evidence_never_calls_provider(self):
        transport = Mock()
        result = ai_brief.generate_brief('Unknown', {'status': 'insufficient_information'}, transport)
        self.assertEqual(result['status'], 'insufficient_evidence')
        transport.assert_not_called()

    def test_supported_answer_is_preserved_and_request_is_bounded(self):
        original = copy.deepcopy(self.result)
        transport = Mock(return_value=self.response())
        result = ai_brief.generate_brief(self.question, self.result, transport)
        self.assertEqual(result['status'], 'generated')
        self.assertEqual(self.result, original)
        payload, key = transport.call_args.args
        self.assertFalse(payload['store'])
        self.assertEqual(payload['max_output_tokens'], 1200)
        self.assertNotIn('tools', payload)
        self.assertNotIn(key, payload['input'])
        self.assertEqual(json.loads(payload['input'])['evidence_packet']['rows'], original['rows'])
        self.assertEqual(result['usage']['total_tokens'], 150)

    def test_unknown_missing_and_malformed_citations_are_rejected(self):
        for refs in ([], ['invented-source'], [123], 'source'):
            with self.subTest(refs=refs):
                brief = copy.deepcopy(self.valid)
                brief['observations'][0]['source_ids'] = refs
                result = ai_brief.generate_brief(self.question, self.result, Mock(return_value=self.response(brief)))
                self.assertEqual(result['status'], 'unavailable')
                self.assertNotIn('brief', result)

    def test_incomplete_refused_and_invalid_json_responses_are_rejected(self):
        responses = [{'status': 'incomplete'},
                     {'status': 'completed', 'output': [{'content': [{'type': 'refusal'}]}]},
                     {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': 'not JSON'}]}]}]
        for response in responses:
            with self.subTest(response=response):
                result = ai_brief.generate_brief(self.question, self.result, Mock(return_value=response))
                self.assertEqual(result['status'], 'unavailable')

    def test_api_errors_are_sanitised_and_not_retried(self):
        for code in (401, 429, 500):
            transport = Mock(side_effect=urllib.error.HTTPError(ai_brief.ENDPOINT, code, 'SENSITIVE ERROR BODY', {}, None))
            result = ai_brief.generate_brief(self.question, self.result, transport)
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotIn('SENSITIVE', json.dumps(result))
            self.assertNotIn('test-placeholder', json.dumps(result))
            self.assertEqual(transport.call_count, 1)

    def test_cache_reuses_same_evidence_but_invalidates_changed_data(self):
        transport = Mock(return_value=self.response())
        first = ai_brief.generate_brief(self.question, self.result, transport)
        second = ai_brief.generate_brief(self.question, self.result, transport)
        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(second['model_calls'], 0)
        changed = copy.deepcopy(self.result)
        changed['warnings'].append('New accounting caveat')
        third = ai_brief.generate_brief(self.question, changed, transport)
        self.assertFalse(third['cached'])
        self.assertEqual(transport.call_count, 2)

    def test_busy_request_does_not_start_another_call(self):
        transport = Mock()
        with ai_brief._gate:
            result = ai_brief.generate_brief(self.question, self.result, transport)
        self.assertEqual(result['status'], 'busy')
        transport.assert_not_called()

    def test_extra_fields_and_oversized_output_are_rejected(self):
        for brief in ({**self.valid, 'api_key': 'not-allowed'}, {**self.valid, 'summary': 'x' * 2000}):
            with self.assertRaises(ValueError):
                ai_brief.validate_brief(brief, {self.source})

    def test_local_env_and_environment_override_without_key_in_status(self):
        self.config.stop()
        contents = 'OPENAI_API_KEY=local-placeholder\nOPENAI_MODEL=test-model\nIGNORED=value\n'
        with patch('pathlib.Path.read_text', return_value=contents), patch.dict('os.environ', {}, clear=True):
            self.assertEqual(ai_brief.configuration(), ('local-placeholder', 'test-model'))
            self.assertNotIn('local-placeholder', json.dumps(ai_brief.status()))
            with patch.dict('os.environ', {'OPENAI_API_KEY': 'environment-placeholder'}):
                self.assertEqual(ai_brief.configuration()[0], 'environment-placeholder')


if __name__ == '__main__':
    unittest.main()
