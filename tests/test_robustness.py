"""Kiểm tra lỗi hạ tầng và retry bằng fake provider, không gọi API."""
import json
import io
import urllib.error
import unittest
from unittest.mock import patch

from agent import run_agent
from bonus.tools import BonusTools
from status_tools import StatusTools
from providers import Provider, post_json
from test_lab import FakeProvider, tool_call, final


class RobustnessTests(unittest.TestCase):
    def test_last_step_reserves_a_final_answer_instead_of_more_tool_calls(self):
        class BudgetProvider:
            def complete(self, messages, schemas):
                if schemas:
                    return tool_call('status', 'get_status', '{"provider":"github"}')
                return final('Chỉ xác minh được phạm vi snapshot hiện có.')
        result = run_agent('Kiểm tra', BudgetProvider(), StatusTools(), max_steps=2)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(sum(e['event'] == 'tool' for e in result['trace']), 1)
        self.assertEqual(sum(e['event'] == 'model' for e in result['trace']), 2)

    def test_source_repair_receives_observed_url_instead_of_guessing_alias(self):
        class RepairProvider:
            count = 0
            def complete(self, messages, schemas):
                self.count += 1
                if self.count == 1:
                    return tool_call('detail', 'get_incident_details',
                                     '{"provider":"github","incident_id":"xr3myzj7ms51"}')
                if self.count == 2:
                    return final('Nguồn: https://www.githubstatus.com/incidents/xr3myzj7ms51')
                feedback = json.loads(messages[-1]['content'])
                return final('Nguồn đã quan sát: ' + feedback['observed_incident_urls'][0])
        result = run_agent('Kiểm tra', RepairProvider(), StatusTools(), max_steps=3)
        self.assertEqual(result['status'], 'completed')
        observed = next(event['result']['url'] for event in result['trace']
                        if event['event'] == 'tool')
        self.assertIn(observed, result['answer'])
        self.assertEqual(sum(event['event'] == 'validation_missing_source'
                             for event in result['trace']), 1)

    @patch('providers.time.sleep')
    @patch('providers.urllib.request.urlopen')
    def test_persistent_llm_429_has_bounded_attempts(self, urlopen, sleep):
        errors = [urllib.error.HTTPError('https://example.invalid', 429, 'limited', {},
                                        io.BytesIO(b'{"error":{"code":429}}')) for _ in range(4)]
        urlopen.side_effect = errors
        try:
            with self.assertRaises(RuntimeError):
                post_json('https://example.invalid', {}, {})
            self.assertEqual(urlopen.call_count, 4)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [15, 30, 60])
        finally:
            for error in errors:
                error.close()

    @patch('providers.time.sleep')
    @patch('providers.urllib.request.urlopen')
    def test_transient_llm_429_honors_retry_after(self, urlopen, sleep):
        error = urllib.error.HTTPError('https://example.invalid', 429, 'limited',
                                      {'Retry-After': '2'}, io.BytesIO(b'{"error":{"code":429}}'))
        urlopen.side_effect = [error, io.BytesIO(b'{}')]
        self.assertEqual(post_json('https://example.invalid', {}, {}), {})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)
        error.close()

    @patch('providers.time.sleep')
    @patch('providers.urllib.request.urlopen')
    def test_long_llm_retry_after_is_not_retried_early(self, urlopen, sleep):
        error = urllib.error.HTTPError('https://example.invalid', 429, 'limited',
                                      {'Retry-After': '120'}, io.BytesIO(b'{}'))
        urlopen.side_effect = error
        with self.assertRaises(RuntimeError):
            post_json('https://example.invalid', {}, {})
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()
        error.close()

    @patch('providers.time.sleep')
    @patch('providers.urllib.request.urlopen')
    def test_quota_failure_is_not_retried(self, urlopen, sleep):
        error = urllib.error.HTTPError('https://example.invalid', 429, 'quota', {},
                                      io.BytesIO(b'{"error":{"code":"insufficient_quota"}}'))
        urlopen.side_effect = error
        with self.assertRaises(RuntimeError):
            post_json('https://example.invalid', {}, {})
        sleep.assert_not_called()
        error.close()

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test'})
    @patch('providers.post_json')
    def test_openrouter_luna_uses_non_reasoning_tool_calling(self, post):
        post.return_value = {'choices': [{'message': {'role': 'assistant', 'content': 'OK'},
                                         'finish_reason': 'stop'}]}
        Provider('openrouter', 'openai/gpt-6-luna').complete(
            [{'role': 'user', 'content': 'Hi'}], [])
        self.assertEqual(post.call_args.args[0], 'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(post.call_args.args[2]['reasoning'], {'effort': 'none'})

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test',
                             'OPENAI_BASE_URL': 'https://opencode.ai/inference/go/openai/v1'})
    @patch('providers.post_json')
    def test_opencode_session_is_stable_per_conversation(self, post):
        post.return_value = {'choices': [{'message': {'role': 'assistant', 'content': 'OK'},
                                         'finish_reason': 'stop'}]}
        first = Provider('openai', 'compatible-model')
        first.complete([{'role': 'user', 'content': 'Hi'}], [])
        first.complete([{'role': 'user', 'content': 'Again'}], [])
        ids = [call.args[1]['x-opencode-session'] for call in post.call_args_list]
        self.assertTrue(ids[0])
        self.assertEqual(ids[0], ids[1])
        self.assertNotEqual(first.session_id, Provider('openai', 'compatible-model').session_id)

    @patch('providers.urllib.request.urlopen')
    def test_http_request_identifies_the_lab_application(self, urlopen):
        urlopen.return_value = io.BytesIO(b'{}')
        self.assertEqual(post_json('https://example.invalid', {}, {}), {})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'), 'StatusInvestigationLab/1.0')

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test',
                             'OPENAI_BASE_URL': 'https://example.invalid/openai/v1/'})
    @patch('providers.post_json')
    def test_openai_compatible_api_uses_configured_base_url(self, post):
        post.return_value = {'choices': [{'message': {'role': 'assistant', 'content': 'OK'},
                                         'finish_reason': 'stop'}]}
        provider = Provider('openai', 'compatible-model')
        provider.complete([{'role': 'user', 'content': 'Hi'}], [])
        self.assertEqual(post.call_args.args[0],
                         'https://example.invalid/openai/v1/chat/completions')
        self.assertEqual(post.call_args.args[2]['model'], 'compatible-model')

    def test_provider_exception_does_not_leak_exception_message(self):
        class BrokenProvider:
            def complete(self, messages, schemas):
                raise RuntimeError('private-request-data')
        result = run_agent('Kiểm tra', BrokenProvider(), StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['trace'][0]['event'], 'provider_error')
        self.assertNotIn('private-request-data', json.dumps(result))

    def test_array_arguments_are_rejected(self):
        provider = FakeProvider([tool_call('1', 'get_status', '[]'), final()])
        result = run_agent('Kiểm tra', provider, StatusTools())
        self.assertEqual(result['trace'][1]['result']['error'], 'INVALID_ARGUMENTS')

    def test_persistent_simulated_rate_limit_stops_real_tool_retries(self):
        tools = BonusTools(scenario='rate_limit_always')
        provider = FakeProvider([
            tool_call(str(i), 'get_vercel_status', '{}') for i in range(4)
        ] + [final('Chưa kiểm tra được Vercel do rate limit.')])
        with patch.object(tools, 'execute', wraps=tools.execute) as execute:
            result = run_agent('Kiểm tra', provider, tools, max_steps=5)
        self.assertEqual(execute.call_count, 2)
        events = [event for event in result['trace'] if event['event'] == 'tool']
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(events[2]['result']['retry_blocked'])
        self.assertEqual(events[1]['result']['error'], 'RATE_LIMITED')

    def test_live_rate_limit_returns_retry_after_without_retrying(self):
        class LimitedTools:
            mode = 'live'
            count = 0
            def execute(self, name, args):
                self.count += 1
                return {'ok': False, 'error': 'RATE_LIMITED', 'retry_after': '120'}
        tools = LimitedTools()
        provider = FakeProvider([
            tool_call('1', 'get_status', '{"provider":"github"}'),
            tool_call('2', 'get_status', '{"provider":"github"}'), final(),
        ])
        result = run_agent('Kiểm tra', provider, tools)
        self.assertEqual(tools.count, 1)
        observation = json.loads(provider.histories[2][-1]['content'])
        self.assertEqual(observation['retry_after'], '120')
        self.assertTrue(observation['retry_blocked'])
        self.assertEqual(result['status'], 'completed')

    def test_unexpected_finish_is_error(self):
        response = final('Bị chặn')
        response['finish'] = 'content_filter'
        self.assertEqual(run_agent('x', FakeProvider([response]), StatusTools())['status'], 'error')

    def test_bonus_returns_all_five_provider_results_before_next_model_call(self):
        names = ['github', 'cloudflare', 'vercel', 'npm', 'digitalocean']
        replies = [tool_call(name, f'get_{name}_status', '{}') for name in names]
        batch = replies[0]
        for reply in replies[1:]:
            batch['calls'].extend(reply['calls'])
            batch['message']['tool_calls'].extend(reply['message']['tool_calls'])
        provider = FakeProvider([batch, final()])
        result = run_agent('Kiểm tra cả năm dịch vụ', provider, BonusTools())
        self.assertEqual(result['status'], 'completed')
        observations = provider.histories[1][-5:]
        self.assertEqual([message['tool_call_id'] for message in observations], names)
        self.assertEqual([json.loads(message['content'])['provider']
                          for message in observations], names)

    def test_bonus_can_read_every_timeline_page_with_matching_ids(self):
        tools = BonusTools()
        responses, offsets = [], []
        offset = 0
        while True:
            args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg', 'offset': offset}
            page = tools.execute('get_incident_details', args)
            offsets.append(offset)
            responses.append(tool_call(str(offset), 'get_incident_details', json.dumps(args)))
            if page.get('next_offset') is None:
                break
            offset = page['next_offset']
        responses.append(final('Đã đọc timeline. Nguồn: ' + page['url']))
        provider = FakeProvider(responses)
        result = run_agent('Đọc toàn bộ timeline', provider, tools, max_steps=len(responses))
        self.assertEqual(result['status'], 'completed')
        events = [event for event in result['trace'] if event['event'] == 'tool']
        self.assertEqual([event['arguments']['offset'] for event in events], offsets)
        updates = [update for event in events for update in event['result']['updates']]
        self.assertEqual(len(updates), page['total_updates'])
        for history, offset in zip(provider.histories[1:], offsets):
            observation = next(message for message in reversed(history) if message['role'] == 'tool')
            self.assertEqual(observation['tool_call_id'], str(offset))
